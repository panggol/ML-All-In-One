"""
调度器 API 路由
提供定时任务的 CRUD + 执行历史 + 手动触发功能。
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone as dt_tz
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import desc

from api.database import User, SessionLocal, get_db
from api.auth import get_current_user
from src.mlkit.scheduler.models import (
    Job as SchedulerJob,
    Execution,
    JobType,
    JobStatus,
    ExecutionStatus,
    TriggerType,
    Base,
)
from src.mlkit.scheduler.cron_parser import validate_cron, get_next_run_time, CronParseError, describe_cron
from src.mlkit.scheduler.scheduler import Scheduler, _scheduler_instance

logger = logging.getLogger("platform.scheduler")

router = APIRouter(redirect_slashes=False)

# 数据库会话工厂（供调度器使用）
def _get_db_factory():
    return SessionLocal


# =============================================================================
# Pydantic 请求/响应模型
# =============================================================================

class JobCreateRequest(BaseModel):
    """创建定时任务请求"""
    name: str = Field(..., min_length=1, max_length=128, description="任务名称")
    job_type: Literal["preprocessing", "training", "pipeline"] = Field(..., description="任务类型")
    target_id: Optional[int] = Field(None, description="关联任务 ID")
    cron_expression: str = Field(..., description="Cron 表达式（5段式）")
    params: Optional[dict] = Field(default_factory=dict, description="任务参数字典（JSON）")
    webhook_url: Optional[str] = Field(None, description="飞书 WebHook URL")
    retry_count: int = Field(default=0, ge=0, le=5, description="失败重试次数")
    is_enabled: bool = Field(default=True, description="是否启用")

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expr(cls, v: str) -> str:
        try:
            validate_cron(v)
            return v
        except CronParseError as e:
            raise ValueError(str(e))

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith("https://"):
            raise ValueError("WebHook URL 必须以 https:// 开头")
        return v


class JobUpdateRequest(BaseModel):
    """更新定时任务请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    cron_expression: Optional[str] = None
    params: Optional[dict] = None
    webhook_url: Optional[str] = Field(None, description="空字符串表示清除")
    retry_count: Optional[int] = Field(None, ge=0, le=5)
    is_enabled: Optional[bool] = None
    status: Optional[Literal["active", "paused", "failed"]] = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expr(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            validate_cron(v)
            return v
        except CronParseError as e:
            raise ValueError(str(e))

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "" and not v.startswith("https://"):
            raise ValueError("WebHook URL 必须以 https:// 开头")
        return v if v != "" else None


class ExecutionResponse(BaseModel):
    """执行记录响应"""
    id: str
    job_id: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    triggered_by: str

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    """定时任务响应"""
    id: str
    name: str
    job_type: str
    target_id: Optional[int] = None
    cron_expression: str
    status: str
    webhook_url: Optional[str] = None
    retry_count: int
    params: dict = {}
    is_enabled: bool
    next_run_time: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """分页任务列表响应"""
    data: list[JobResponse]
    total: int
    page: int
    page_size: int


class ExecutionHistoryResponse(BaseModel):
    """执行历史分页响应"""
    data: list[ExecutionResponse]
    total: int
    page: int
    page_size: int


class CronValidateRequest(BaseModel):
    """Cron 校验请求"""
    cron_expression: str


class CronValidateResponse(BaseModel):
    """Cron 校验响应"""
    valid: bool
    next_run_time: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None


class TriggerResponse(BaseModel):
    """手动触发响应"""
    message: str
    execution_id: str


# =============================================================================
# 辅助函数
# =============================================================================

def _job_to_response(job: SchedulerJob, scheduler: Optional[Scheduler] = None) -> JobResponse:
    """将 Job 模型转换为 API 响应"""
    # 获取下次执行时间（优先从调度器，fallback 到数据库）
    next_run = None
    if scheduler:
        try:
            next_run_utc = scheduler.get_next_run_time(job.id)
            if next_run_utc:
                next_run = next_run_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    if not next_run and job.next_run_time:
        next_run = job.next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    return JobResponse(
        id=job.id,
        name=job.name,
        job_type=job.job_type.value if hasattr(job.job_type, 'value') else str(job.job_type),
        target_id=job.target_id,
        cron_expression=job.cron_expression,
        status=job.status.value if hasattr(job.status, 'value') else str(job.status),
        webhook_url=job.webhook_url,
        retry_count=job.retry_count,
        params=json.loads(job.params) if job.params else {},
        is_enabled=job.is_enabled,
        next_run_time=next_run,
        created_at=job.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if job.created_at else "",
        updated_at=job.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") if job.updated_at else "",
    )


def _check_job_ownership(job: SchedulerJob, user: User):
    """检查任务所有权，不属于当前用户则抛出 403"""
    if job.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="您没有权限访问此任务",
        )


# =============================================================================
# API 路由
# =============================================================================

@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    request: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    创建定时任务。
    同时将任务注册到 APScheduler。
    """
    # 验证 target_id（preprocessing/training 必须指定）
    if request.job_type in ("preprocessing", "training") and not request.target_id:
        raise HTTPException(
            status_code=422,
            detail=f"任务类型 '{request.job_type}' 必须指定 target_id",
        )

    # 创建 Job
    job = SchedulerJob(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=request.name,
        job_type=JobType(request.job_type),
        target_id=request.target_id,
        cron_expression=request.cron_expression,
        status=JobStatus.ACTIVE if request.is_enabled else JobStatus.PAUSED,
        webhook_url=request.webhook_url,
        retry_count=request.retry_count,
        params=json.dumps(request.params) if request.params else None,
        is_enabled=request.is_enabled,
        next_run_time=get_next_run_time(request.cron_expression),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 注册到 APScheduler
    scheduler = Scheduler.get_instance() if Scheduler._instance else None
    if scheduler and request.is_enabled:
        try:
            scheduler.add_job(job)
        except Exception as e:
            logger.error(f"[Scheduler] 注册 Job {job.id} 到调度器失败: {e}")
            # 不阻止响应，Job 已创建成功

    logger.info(f"[API] 创建定时任务，id={job.id}, user={current_user.id}")
    return _job_to_response(job, scheduler)


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status", description="按状态筛选"),
    keyword: Optional[str] = Query(default=None, description="按名称关键词搜索"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出当前用户的所有定时任务"""
    query = db.query(SchedulerJob).filter(SchedulerJob.user_id == current_user.id)

    if status_filter:
        try:
            query = query.filter(SchedulerJob.status == JobStatus(status_filter))
        except ValueError:
            pass  # 无效状态值，忽略筛选

    if keyword:
        query = query.filter(SchedulerJob.name.ilike(f"%{keyword}%"))

    total = query.count()
    jobs = (
        query
        .order_by(desc(SchedulerJob.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    scheduler = Scheduler.get_instance() if Scheduler._instance else None
    return JobListResponse(
        data=[_job_to_response(j, scheduler) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个任务详情"""
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_job_ownership(job, current_user)

    scheduler = Scheduler.get_instance() if Scheduler._instance else None
    return _job_to_response(job, scheduler)


@router.patch("/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    request: JobUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新定时任务（名称、Cron、参数、状态等）"""
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_job_ownership(job, current_user)

    # 更新字段
    if request.name is not None:
        job.name = request.name
    if request.cron_expression is not None:
        job.cron_expression = request.cron_expression
        # 重新计算下次执行时间
        job.next_run_time = get_next_run_time(request.cron_expression)
    if request.params is not None:
        job.params = json.dumps(request.params) if request.params else None
    if "webhook_url" in request.model_fields_set:
        job.webhook_url = request.webhook_url
    if request.retry_count is not None:
        job.retry_count = request.retry_count
    if request.is_enabled is not None:
        job.is_enabled = request.is_enabled
    if request.status is not None:
        job.status = JobStatus(request.status)

    job.updated_at = datetime.now(dt_tz.utc)
    db.commit()
    db.refresh(job)

    # 同步更新 APScheduler
    scheduler = Scheduler.get_instance() if Scheduler._instance else None
    if scheduler:
        try:
            # 更新 status（暂停/恢复）
            if request.status == "paused" or (request.is_enabled is not None and not request.is_enabled):
                scheduler.pause_job(job_id)
                job.status = JobStatus.PAUSED
            elif request.status == "active" or (request.is_enabled is not None and request.is_enabled):
                scheduler.resume_job(job)
                job.status = JobStatus.ACTIVE
            else:
                scheduler.update_job(job)
        except Exception as e:
            logger.error(f"[API] 更新 APScheduler Job {job_id} 失败: {e}")

    db.commit()
    return _job_to_response(job, scheduler)


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除定时任务（同时从 APScheduler JobStore 移除）"""
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_job_ownership(job, current_user)

    # 先从 APScheduler 移除
    scheduler = Scheduler.get_instance() if Scheduler._instance else None
    if scheduler:
        try:
            scheduler.remove_job(job_id)
        except Exception as e:
            logger.error(f"[API] 从调度器移除 Job {job_id} 失败: {e}")

    # 删除数据库记录（级联删除 Execution）
    db.delete(job)
    db.commit()

    logger.info(f"[API] 删除定时任务，id={job_id}")
    return None


@router.get("/jobs/{job_id}/history", response_model=ExecutionHistoryResponse)
async def get_job_history(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取任务执行历史"""
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_job_ownership(job, current_user)

    query = db.query(Execution).filter(Execution.job_id == job_id)
    total = query.count()

    executions = (
        query
        .order_by(desc(Execution.started_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ExecutionHistoryResponse(
        data=[
            ExecutionResponse(
                id=e.id,
                job_id=e.job_id,
                status=e.status.value if hasattr(e.status, 'value') else str(e.status),
                started_at=e.started_at.strftime("%Y-%m-%dT%H:%M:%SZ") if e.started_at else None,
                finished_at=e.finished_at.strftime("%Y-%m-%dT%H:%M:%SZ") if e.finished_at else None,
                duration_seconds=e.duration_seconds,
                error_message=e.error_message,
                triggered_by=e.triggered_by.value if hasattr(e.triggered_by, 'value') else str(e.triggered_by),
            )
            for e in executions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/jobs/{job_id}/trigger", response_model=TriggerResponse, status_code=202)
async def trigger_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    手动立即触发任务。
    任务在后台线程中执行，立即返回。
    """
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    _check_job_ownership(job, current_user)

    # 创建手动触发执行记录
    execution_id = str(uuid.uuid4())
    execution = Execution(
        id=execution_id,
        job_id=job_id,
        status=ExecutionStatus.RUNNING,
        triggered_by=TriggerType.MANUAL,
        started_at=datetime.now(dt_tz.utc),
    )
    db.add(execution)
    job.status = JobStatus.ACTIVE  # 重置为 active
    job.updated_at = datetime.now(dt_tz.utc)
    db.commit()

    # 在后台线程执行（需要生成用户 Token）
    from src.mlkit.scheduler.runner import run_job
    from src.mlkit.scheduler.models import TriggerType as TType
    import asyncio
    import jwt

    # 为该用户生成 Token（供内部 API 调用）
    jwt_secret = os.getenv("SECRET_KEY", os.getenv("MLKIT_JWT_SECRET", "changeme"))
    user_payload = {
        "sub": str(current_user.id),
        "username": current_user.username,
        "role": current_user.role,
        "iat": datetime.now(dt_tz.utc),
        "exp": datetime.now(dt_tz.utc).timestamp() + 3600,
    }
    user_token = jwt.encode(user_payload, jwt_secret, algorithm="HS256")

    # 使用后台任务执行（不等待结果）
    async def _do_trigger():
        await run_job(
            job_id=job_id,
            db_session_factory=_get_db_factory,
            triggered_by=TType.MANUAL,
            token=user_token,
        )

    asyncio.create_task(_do_trigger())

    logger.info(f"[API] 手动触发任务，job_id={job_id}, user={current_user.id}")
    return TriggerResponse(
        message="任务已触发，将在后台执行",
        execution_id=execution_id,
    )


@router.post("/cron/validate", response_model=CronValidateResponse)
async def validate_cron_expr(
    request: CronValidateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    校验 Cron 表达式合法性，并返回下次执行时间。
    前端实时校验用。
    """
    try:
        validate_cron(request.cron_expression)
        next_run = get_next_run_time(request.cron_expression)
        return CronValidateResponse(
            valid=True,
            next_run_time=next_run.strftime("%Y-%m-%d %H:%M:%S"),
            description=describe_cron(request.cron_expression),
        )
    except CronParseError as e:
        return CronValidateResponse(
            valid=False,
            error=str(e),
        )
