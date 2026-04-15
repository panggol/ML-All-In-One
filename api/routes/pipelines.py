"""
Pipeline Orchestration API 路由

提供 Pipeline CRUD、Run 管理、版本查询、Cron 调度配置。
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone as dt_tz
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, and_
from sqlalchemy.exc import IntegrityError

from api.database import User, SessionLocal, get_db
from api.auth import get_current_user
from src.mlkit.pipeline.models import (
    Pipeline, PipelineVersion, PipelineRun, PipelineStepRun,
    PipelineStatus, RunStatus, StepStatus, TriggerType,
)
from src.mlkit.pipeline.dsl import parse_dsl, validate_dsl, DAGValidationError
from src.mlkit.pipeline.engine import PipelineEngine, StepExecutionError, get_executor_registry

logger = logging.getLogger("platform.pipelines")
router = APIRouter(prefix="", redirect_slashes=False)


# =============================================================================
# DB Session Factory（供 Engine 使用）
# =============================================================================

def _db_factory():
    return SessionLocal


# =============================================================================
# Pydantic 请求/响应模型
# =============================================================================

class PipelineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Pipeline 名称")
    description: str | None = Field(None, description="Pipeline 描述")
    dsl_content: str = Field(..., description="DSL 定义（JSON 或 YAML 文本）")
    dsl_format: str = Field("json", description="DSL 格式，json 或 yaml")
    status: str = Field("draft", description="初始状态")

    @field_validator("dsl_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v not in ("json", "yaml"):
            raise ValueError("dsl_format 必须为 json 或 yaml")
        return v


class PipelineUpdateRequest(BaseModel):
    dsl_content: str | None = None
    description: str | None = None
    changelog: str | None = Field(None, description="版本变更说明")
    status: str | None = None


class PipelineResponse(BaseModel):
    id: int
    name: str
    description: str | None
    version: int
    status: str
    dsl_format: str
    dsl_content: str
    schedule_cron: str | None
    schedule_enabled: bool
    schedule_job_id: str | None
    owner_id: int
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class PipelineListResponse(BaseModel):
    data: list[PipelineResponse]
    total: int
    page: int
    page_size: int


# Version

class VersionResponse(BaseModel):
    id: int
    pipeline_id: int
    version: int
    dsl_format: str
    dsl_content: str
    changelog: str | None
    created_by: int | None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


# Run

class RunTriggerRequest(BaseModel):
    params: dict | None = Field(default_factory=dict, description="执行参数（如数据集路径）")
    triggered_by: str = Field("manual", description="触发方式 manual/scheduled/api")


class RunRetryRequest(BaseModel):
    from_step: str | None = Field(None, description="从指定步骤重试（省略则全步骤重跑）")
    full_rerun: bool = Field(False, description="是否全步骤重跑")


class PipelineRunResponse(BaseModel):
    id: int
    pipeline_id: int
    pipeline_version: int
    run_number: int
    status: str
    triggered_by: str
    run_params: dict | None
    started_at: str | None
    finished_at: str | None
    duration_seconds: int | None
    error_message: str | None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class PipelineStepRunResponse(BaseModel):
    id: int
    run_id: int
    step_name: str
    step_type: str
    status: str
    order_index: int
    retry_count: int
    input_data: dict | None
    output_data: dict | None
    error_message: str | None
    started_at: str | None
    finished_at: str | None
    duration_seconds: int | None

    model_config = ConfigDict(from_attributes=True)


class RunDetailResponse(BaseModel):
    run: PipelineRunResponse
    steps: list[PipelineStepRunResponse]


class RunListResponse(BaseModel):
    data: list[PipelineRunResponse]
    total: int
    page: int
    page_size: int


# Schedule

class ScheduleRequest(BaseModel):
    cron_expression: str | None = Field(None, description="Cron 表达式")
    is_enabled: bool | None = Field(True, description="是否启用")
    timeout_seconds: int = Field(3600, ge=1, le=7200, description="超时秒数")
    auto_retry: bool = Field(False, description="失败自动重试")
    retry_count: int = Field(0, ge=0, le=5, description="重试次数")
    webhook_url: str | None = Field(None, description="失败通知 Webhook")

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from src.mlkit.scheduler.cron_parser import validate_cron, CronParseError
        try:
            validate_cron(v)
            return v
        except CronParseError as e:
            raise ValueError(f"Cron 表达式无效: {e}")

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://"):
            raise ValueError("Webhook URL 必须以 https:// 开头")
        return v


class ScheduleResponse(BaseModel):
    pipeline_id: int
    schedule_cron: str | None
    schedule_enabled: bool
    schedule_job_id: str | None
    next_run_time: str | None
    timeout_seconds: int
    auto_retry: bool
    retry_count: int
    webhook_url: str | None


# =============================================================================
# 辅助函数
# =============================================================================

def _pipeline_to_response(p: Pipeline) -> PipelineResponse:
    return PipelineResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        version=p.version,
        status=p.status.value if hasattr(p.status, 'value') else str(p.status),
        dsl_format=p.dsl_format,
        dsl_content=p.dsl_content,
        schedule_cron=p.schedule_cron,
        schedule_enabled=p.schedule_enabled,
        schedule_job_id=p.schedule_job_id,
        owner_id=p.owner_id,
        created_at=p.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if p.created_at else "",
        updated_at=p.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") if p.updated_at else "",
    )


def _run_to_response(r: PipelineRun) -> PipelineRunResponse:
    return PipelineRunResponse(
        id=r.id,
        pipeline_id=r.pipeline_id,
        pipeline_version=r.pipeline_version,
        run_number=r.run_number,
        status=r.status.value if hasattr(r.status, 'value') else str(r.status),
        triggered_by=r.triggered_by.value if hasattr(r.triggered_by, 'value') else str(r.triggered_by),
        run_params=r.run_params,
        started_at=r.started_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.started_at else None,
        finished_at=r.finished_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.finished_at else None,
        duration_seconds=r.duration_seconds,
        error_message=r.error_message,
        created_at=r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.created_at else "",
    )


def _step_to_response(s: PipelineStepRun) -> PipelineStepRunResponse:
    return PipelineStepRunResponse(
        id=s.id,
        run_id=s.run_id,
        step_name=s.step_name,
        step_type=s.step_type,
        status=s.status.value if hasattr(s.status, 'value') else str(s.status),
        order_index=s.order_index,
        retry_count=s.retry_count,
        input_data=s.input_data,
        output_data=s.output_data,
        error_message=s.error_message,
        started_at=s.started_at.strftime("%Y-%m-%dT%H:%M:%SZ") if s.started_at else None,
        finished_at=s.finished_at.strftime("%Y-%m-%dT%H:%M:%SZ") if s.finished_at else None,
        duration_seconds=s.duration_seconds,
    )


def _check_ownership(pipeline: Pipeline, user: User):
    """检查 Pipeline 所有权"""
    if pipeline.owner_id != user.id:
        raise HTTPException(status_code=403, detail="您没有权限访问此 Pipeline")


# =============================================================================
# Pipeline CRUD
# =============================================================================

@router.post("", response_model=PipelineResponse, status_code=201)
async def create_pipeline(
    request: PipelineCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    创建新的 Pipeline。
    创建时自动验证 DSL（DAG 循环检测），并保存 version=1 的快照。
    """
    # 路径遍历防护：Pipeline 名称禁止路径分隔符
    if any(c in request.name for c in "/\\"):
        raise HTTPException(status_code=400, detail="Pipeline 名称不能包含路径分隔符")

    # 验证 DSL 格式和 DAG
    try:
        validate_dsl(request.dsl_content, request.dsl_format)
    except DAGValidationError as e:
        raise HTTPException(status_code=400, detail=f"DSL 验证失败: {e}")

    # 创建 Pipeline
    pipeline = Pipeline(
        name=request.name,
        description=request.description,
        version=1,
        dsl_format=request.dsl_format,
        dsl_content=request.dsl_content,
        status=PipelineStatus(request.status),
        owner_id=current_user.id,
    )
    db.add(pipeline)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Pipeline 名称 '{request.name}' 已存在")

    # 保存 version=1 快照
    version_snapshot = PipelineVersion(
        pipeline_id=pipeline.id,
        version=1,
        dsl_format=pipeline.dsl_format,
        dsl_content=pipeline.dsl_content,
        changelog="初始版本",
        created_by=current_user.id,
    )
    db.add(version_snapshot)
    db.commit()
    db.refresh(pipeline)

    logger.info(f"[API] 创建 Pipeline，id={pipeline.id}, user={current_user.id}")
    return _pipeline_to_response(pipeline)


@router.get("", response_model=PipelineListResponse)
async def list_pipelines(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="按状态筛选"),
    q: str | None = Query(default=None, description="名称关键词搜索"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    列出当前用户的所有 Pipeline（软删除不显示）。
    """
    query = db.query(Pipeline).filter(
        Pipeline.owner_id == current_user.id,
        Pipeline.is_deleted == False,
    )

    if status:
        try:
            query = query.filter(Pipeline.status == PipelineStatus(status))
        except ValueError:
            pass

    if q:
        query = query.filter(Pipeline.name.ilike(f"%{q}%"))

    total = query.count()
    pipelines = (
        query
        .order_by(desc(Pipeline.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PipelineListResponse(
        data=[_pipeline_to_response(p) for p in pipelines],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个 Pipeline 详情"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)
    return _pipeline_to_response(pipeline)


@router.patch("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int,
    request: PipelineUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    更新 Pipeline 定义。
    - 如 dsl_content 变更 → version 递增 + 保存版本快照
    - 验证新的 DSL 无循环依赖
    """
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    # 验证新的 DSL（如提供）
    if request.dsl_content is not None:
        try:
            validate_dsl(request.dsl_content, pipeline.dsl_format)
        except DAGValidationError as e:
            raise HTTPException(status_code=400, detail=f"DSL 验证失败: {e}")

        # version 递增
        pipeline.version += 1
        # 保存新版本快照
        version_snapshot = PipelineVersion(
            pipeline_id=pipeline.id,
            version=pipeline.version,
            dsl_format=pipeline.dsl_format,
            dsl_content=request.dsl_content,
            changelog=request.changelog,
            created_by=current_user.id,
        )
        db.add(version_snapshot)
        pipeline.dsl_content = request.dsl_content

    if request.description is not None:
        pipeline.description = request.description
    if request.status is not None:
        pipeline.status = PipelineStatus(request.status)

    pipeline.updated_at = datetime.now(dt_tz.utc)
    db.commit()
    db.refresh(pipeline)

    logger.info(
        f"[API] 更新 Pipeline，id={pipeline.id}，新 version={pipeline.version}，"
        f"user={current_user.id}"
    )
    return _pipeline_to_response(pipeline)


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """软删除 Pipeline（历史 Run 记录保留）"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    # 取消关联的调度任务（如有）
    if pipeline.schedule_job_id:
        _cancel_schedule_job(pipeline.schedule_job_id)
        pipeline.schedule_job_id = None

    pipeline.is_deleted = True
    pipeline.updated_at = datetime.now(dt_tz.utc)
    db.commit()

    logger.info(f"[API] 删除 Pipeline，id={pipeline_id}")
    return None


# =============================================================================
# 版本管理
# =============================================================================

@router.get("/{pipeline_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出 Pipeline 的所有版本"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    versions = (
        db.query(PipelineVersion)
        .filter(PipelineVersion.pipeline_id == pipeline_id)
        .order_by(desc(PipelineVersion.version))
        .all()
    )

    return [
        VersionResponse(
            id=v.id,
            pipeline_id=v.pipeline_id,
            version=v.version,
            dsl_format=v.dsl_format,
            dsl_content=v.dsl_content,
            changelog=v.changelog,
            created_by=v.created_by,
            created_at=v.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if v.created_at else "",
        )
        for v in versions
    ]


@router.get("/{pipeline_id}/versions/{version}", response_model=VersionResponse)
async def get_version(
    pipeline_id: int,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取指定版本的 Pipeline 定义"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    ver = db.query(PipelineVersion).filter(
        PipelineVersion.pipeline_id == pipeline_id,
        PipelineVersion.version == version,
    ).first()
    if not ver:
        raise HTTPException(status_code=404, detail=f"版本 v{version} 不存在")

    return VersionResponse(
        id=ver.id,
        pipeline_id=ver.pipeline_id,
        version=ver.version,
        dsl_format=ver.dsl_format,
        dsl_content=ver.dsl_content,
        changelog=ver.changelog,
        created_by=ver.created_by,
        created_at=ver.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if ver.created_at else "",
    )


# =============================================================================
# Run 管理
# =============================================================================

@router.get("/{pipeline_id}/runs", response_model=RunListResponse)
async def list_runs(
    pipeline_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="按 Run 状态筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出 Pipeline 的执行历史"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    query = db.query(PipelineRun).filter(
        PipelineRun.pipeline_id == pipeline_id,
        PipelineRun.is_deleted == False,
    )
    if status:
        try:
            query = query.filter(PipelineRun.status == RunStatus(status))
        except ValueError:
            pass

    total = query.count()
    runs = (
        query
        .order_by(desc(PipelineRun.run_number))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return RunListResponse(
        data=[_run_to_response(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{pipeline_id}/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    pipeline_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单次 Run 的完整详情（含每个步骤的状态）"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id,
        PipelineRun.pipeline_id == pipeline_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run 不存在")

    steps = (
        db.query(PipelineStepRun)
        .filter(PipelineStepRun.run_id == run_id)
        .order_by(PipelineStepRun.order_index)
        .all()
    )

    return RunDetailResponse(
        run=_run_to_response(run),
        steps=[_step_to_response(s) for s in steps],
    )


@router.post("/{pipeline_id}/run", response_model=PipelineRunResponse, status_code=202)
async def trigger_run(
    pipeline_id: int,
    request: RunTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    手动触发 Pipeline 执行。
    Run 记录立即创建（状态 pending），执行在后台异步进行。
    """
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    # 计算 run_number（pipeline 内递增）
    max_run = db.query(func.max(PipelineRun.run_number)).filter(
        PipelineRun.pipeline_id == pipeline_id
    ).scalar() or 0

    triggered_by = TriggerType(request.triggered_by) if request.triggered_by else TriggerType.MANUAL

    run = PipelineRun(
        pipeline_id=pipeline_id,
        pipeline_version=pipeline.version,
        run_number=max_run + 1,
        status=RunStatus.PENDING,
        triggered_by=triggered_by,
        run_params=request.params,
        created_by=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 后台异步执行
    import asyncio
    import jwt
    import os

    jwt_secret = os.getenv("SECRET_KEY", os.getenv("MLKIT_JWT_SECRET", "changeme"))
    user_payload = {
        "sub": str(current_user.id),
        "username": current_user.username,
        "role": current_user.role,
        "iat": datetime.now(dt_tz.utc),
        "exp": datetime.now(dt_tz.utc).timestamp() + 3600,
    }
    user_token = jwt.encode(user_payload, jwt_secret, algorithm="HS256")

    async def _do_run():
        engine = PipelineEngine(_db_factory, get_executor_registry())
        try:
            dsl = parse_dsl(pipeline.dsl_content, pipeline.dsl_format)
            # 重新从 DB 读取 run_record（避免 Session 问题）
            db2 = _db_factory()()
            try:
                run2 = db2.query(PipelineRun).get(run.id)
                await engine.execute(
                    dsl=dsl,
                    run_record=run2,
                    params=request.params,
                    user_token=user_token,
                )
            finally:
                db2.close()
        except Exception as e:
            logger.error(f"[Engine] PipelineRun={run.id} 异步执行异常: {e}", exc_info=True)
            # 更新 Run 状态为 failed
            db3 = _db_factory()()
            try:
                r = db3.query(PipelineRun).get(run.id)
                if r and r.status == RunStatus.PENDING:
                    r.status = RunStatus.FAILED
                    r.error_message = f"引擎初始化失败: {e}"
                    r.finished_at = datetime.now(dt_tz.utc)
                    db3.commit()
            finally:
                db3.close()

    asyncio.create_task(_do_run())

    logger.info(f"[API] 触发 PipelineRun，id={run.id}, pipeline={pipeline_id}, user={current_user.id}")
    return _run_to_response(run)


@router.post("/{pipeline_id}/runs/{run_id}/retry", response_model=PipelineRunResponse)
async def retry_run(
    pipeline_id: int,
    run_id: int,
    request: RunRetryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    重试失败的 Pipeline Run。
    - full_rerun=True：从第一个步骤重新执行
    - from_step=xxx：从指定步骤重新执行（该步骤及其下游重跑）
    """
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    old_run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id,
        PipelineRun.pipeline_id == pipeline_id,
    ).first()
    if not old_run:
        raise HTTPException(status_code=404, detail="Run 不存在")

    # 计算新 run_number
    max_run = db.query(func.max(PipelineRun.run_number)).filter(
        PipelineRun.pipeline_id == pipeline_id
    ).scalar() or 0

    new_run = PipelineRun(
        pipeline_id=pipeline_id,
        pipeline_version=pipeline.version,
        run_number=max_run + 1,
        status=RunStatus.PENDING,
        triggered_by=TriggerType.MANUAL,
        run_params=old_run.run_params,
        created_by=current_user.id,
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    # 后台异步执行
    import asyncio
    import jwt
    import os

    jwt_secret = os.getenv("SECRET_KEY", os.getenv("MLKIT_JWT_SECRET", "changeme"))
    user_payload = {
        "sub": str(current_user.id),
        "username": current_user.username,
        "role": current_user.role,
    }
    user_token = jwt.encode(user_payload, jwt_secret, algorithm="HS256")

    async def _do_retry():
        engine = PipelineEngine(_db_factory, get_executor_registry())
        db2 = _db_factory()()
        try:
            dsl = parse_dsl(pipeline.dsl_content, pipeline.dsl_format)
            run2 = db2.query(PipelineRun).get(new_run.id)
            await engine.execute(dsl=dsl, run_record=run2, params=old_run.run_params,
                                 user_token=user_token)
        except Exception as e:
            logger.error(f"[Engine] 重试 PipelineRun={new_run.id} 异常: {e}", exc_info=True)
        finally:
            db2.close()

    asyncio.create_task(_do_retry())

    return _run_to_response(new_run)


@router.post("/{pipeline_id}/runs/{run_id}/cancel", response_model=PipelineRunResponse)
async def cancel_run(
    pipeline_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消正在运行中的 Pipeline Run"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id,
        PipelineRun.pipeline_id == pipeline_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run 不存在")

    if run.status not in (RunStatus.PENDING, RunStatus.RUNNING):
        raise HTTPException(
            status_code=409,
            detail=f"Run 状态为 '{run.status.value}'，无法取消"
        )

    run.status = RunStatus.CANCELLED
    run.finished_at = datetime.now(dt_tz.utc)
    db.commit()
    db.refresh(run)

    logger.info(f"[API] 取消 PipelineRun，id={run_id}")
    return _run_to_response(run)




@router.get("/{pipeline_id}/runs/{run_id}/steps", response_model=list[PipelineStepRunResponse])
async def list_step_runs(
    pipeline_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单次 Run 的所有步骤执行记录"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id,
        PipelineRun.pipeline_id == pipeline_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run 不存在")

    steps = (
        db.query(PipelineStepRun)
        .filter(PipelineStepRun.run_id == run_id)
        .order_by(PipelineStepRun.order_index)
        .all()
    )
    return [_step_to_response(s) for s in steps]


@router.get("/{pipeline_id}/runs/{run_id}/logs")
async def get_run_logs(
    pipeline_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取 Run 的日志（合并所有步骤日志）"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id,
        PipelineRun.pipeline_id == pipeline_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run 不存在")

    steps = (
        db.query(PipelineStepRun)
        .filter(PipelineStepRun.run_id == run_id)
        .order_by(PipelineStepRun.order_index)
        .all()
    )

    log_lines = [
        f"# Pipeline Run #{run.run_number} (pipeline={pipeline.name}, v{run.pipeline_version})",
        f"# Status: {run.status.value}",
        f"# Triggered by: {run.triggered_by.value}",
        f"# Started: {run.started_at}",
        f"# Finished: {run.finished_at}",
        f"# Duration: {run.duration_seconds}s",
        "",
    ]
    for step in steps:
        log_lines.append(f"## Step: {step.step_name} [{step.step_type}]")
        log_lines.append(f"Status: {step.status.value}")
        log_lines.append(f"Duration: {step.duration_seconds}s")
        if step.error_message:
            log_lines.append(f"ERROR: {step.error_message}")
        if step.output_data:
            log_lines.append(f"Output: {json.dumps(step.output_data, ensure_ascii=False)}")
        log_lines.append("")

    return {"logs": "\n".join(log_lines)}


# =============================================================================
# Schedule（Cron 调度）
# =============================================================================

@router.get("/{pipeline_id}/schedule", response_model=ScheduleResponse)
async def get_schedule(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取 Pipeline 的调度配置"""
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    next_run = None
    if pipeline.schedule_job_id:
        try:
            from src.mlkit.scheduler.scheduler import Scheduler
            sch = Scheduler.get_instance()
            if sch:
                next_run_utc = sch.get_next_run_time(pipeline.schedule_job_id)
                if next_run_utc:
                    next_run = next_run_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    return ScheduleResponse(
        pipeline_id=pipeline_id,
        schedule_cron=pipeline.schedule_cron,
        schedule_enabled=pipeline.schedule_enabled,
        schedule_job_id=pipeline.schedule_job_id,
        next_run_time=next_run,
        timeout_seconds=3600,
        auto_retry=False,
        retry_count=0,
        webhook_url=None,
    )


@router.post("/{pipeline_id}/schedule", response_model=ScheduleResponse)
async def set_schedule(
    pipeline_id: int,
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    创建或更新 Pipeline 的 Cron 调度。
    实际在 scheduled_jobs 模块中创建 job_type="pipeline" 的记录。
    """
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    if request.cron_expression is None:
        raise HTTPException(status_code=400, detail="必须提供 cron_expression")

    # 路径遍历防护：禁止 webhook 指向内部服务
    if request.webhook_url:
        import re
        internal_patterns = [
            r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|内网IP)",
        ]
        for pat in internal_patterns:
            if re.match(pat, request.webhook_url, re.IGNORECASE):
                raise HTTPException(status_code=400, detail="禁止指向内网地址")

    # 在 scheduled_jobs 中创建 Pipeline 类型 Job
    try:
        from src.mlkit.scheduler.models import Job as SchedulerJob, JobType, JobStatus
        from src.mlkit.scheduler.cron_parser import get_next_run_time
        from src.mlkit.scheduler.runner import run_job
    except ImportError as e:
        raise HTTPException(status_code=500, detail="Scheduler 模块不可用")

    job_params = {
        "pipeline_id": pipeline_id,
        "timeout_seconds": request.timeout_seconds,
        "auto_retry": request.auto_retry,
        "retry_count": request.retry_count,
        "webhook_url": request.webhook_url,
    }

    if pipeline.schedule_job_id:
        # 更新现有 Job
        job = db.query(SchedulerJob).filter(
            SchedulerJob.id == pipeline.schedule_job_id
        ).first()
        if job:
            job.cron_expression = request.cron_expression
            job.params = json.dumps(job_params)
            job.is_enabled = request.is_enabled
            job.next_run_time = get_next_run_time(request.cron_expression)
    else:
        # 创建新 Job
        job = SchedulerJob(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            name=f"Pipeline: {pipeline.name}",
            job_type=JobType.PIPELINE,
            target_id=pipeline_id,
            cron_expression=request.cron_expression,
            status=JobStatus.ACTIVE if request.is_enabled else JobStatus.PAUSED,
            webhook_url=request.webhook_url,
            retry_count=request.retry_count,
            params=json.dumps(job_params),
            is_enabled=request.is_enabled,
            next_run_time=get_next_run_time(request.cron_expression),
        )
        db.add(job)
        db.flush()
        pipeline.schedule_job_id = job.id

    pipeline.schedule_cron = request.cron_expression
    pipeline.schedule_enabled = request.is_enabled
    db.commit()

    # 注册到 APScheduler
    try:
        from src.mlkit.scheduler.scheduler import Scheduler
        sch = Scheduler.get_instance()
        if sch and job:
            sch.add_job(job)
    except Exception as e:
        logger.warning(f"[Schedule] 注册 APScheduler Job 失败: {e}")

    logger.info(f"[API] 设置 Pipeline={pipeline_id} 调度，cron={request.cron_expression}")
    return await get_schedule(pipeline_id, current_user, db)


@router.patch("/{pipeline_id}/schedule", response_model=ScheduleResponse)
async def update_schedule(
    pipeline_id: int,
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    更新调度配置（暂停/恢复/修改 Cron）。
    """
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.is_deleted == False,
    ).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")
    _check_ownership(pipeline, current_user)

    if not pipeline.schedule_job_id:
        raise HTTPException(status_code=404, detail="该 Pipeline 尚未配置调度")

    try:
        from src.mlkit.scheduler.models import Job as SchedulerJob, JobStatus
        from src.mlkit.scheduler.cron_parser import get_next_run_time
        from src.mlkit.scheduler.scheduler import Scheduler

        job = db.query(SchedulerJob).filter(
            SchedulerJob.id == pipeline.schedule_job_id
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="关联的调度任务不存在")

        if request.cron_expression is not None:
            job.cron_expression = request.cron_expression
            job.next_run_time = get_next_run_time(request.cron_expression)
            pipeline.schedule_cron = request.cron_expression

        if request.is_enabled is not None:
            pipeline.schedule_enabled = request.is_enabled
            job.is_enabled = request.is_enabled

        db.commit()

        sch = Scheduler.get_instance()
        if sch:
            if pipeline.schedule_enabled:
                sch.resume_job(job)
            else:
                sch.pause_job(job.id)

    except ImportError:
        pass  # Scheduler 不可用时仅更新 DB

    return await get_schedule(pipeline_id, current_user, db)


def _cancel_schedule_job(job_id: str) -> None:
    """从 APScheduler 移除 Job（辅助函数）"""
    try:
        from src.mlkit.scheduler.scheduler import Scheduler
        sch = Scheduler.get_instance()
        if sch:
            sch.remove_job(job_id)
    except Exception:
        pass
