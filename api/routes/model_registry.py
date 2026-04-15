"""
Model Registry API 路由
"""
import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from api.database import (
    ModelVersion,
    ModelVersionHistory,
    TrainedModel,
    User,
    get_db,
)
from api.auth import get_current_user
from mlkit.model_registry import (
    compute_next_version,
    compute_dataset_hash,
    compare_versions,
    VALID_TAGS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# =============================================================================
# Pydantic 请求/响应模型（定义在路由文件头部，Constitution 要求）
# =============================================================================


class RegisterVersionRequest(BaseModel):
    """注册新版本请求"""
    training_job_id: Optional[int] = None
    algorithm_type: Optional[str] = None
    model_type: Optional[str] = None
    task_type: Optional[str] = None
    dataset_name: Optional[str] = None
    dataset_hash: Optional[str] = None
    training_params: Optional[dict] = None
    training_time: Optional[float] = None
    metrics: Optional[dict] = None
    model_file_path: Optional[str] = None
    model_file_size: Optional[int] = None


class VersionResponse(BaseModel):
    """版本详情响应"""
    id: int
    model_id: int
    version: int
    tag: str
    algorithm_type: Optional[str] = None
    model_type: Optional[str] = None
    task_type: Optional[str] = None
    dataset_name: Optional[str] = None
    dataset_hash: Optional[str] = None
    training_params: Optional[dict] = None
    training_time: Optional[float] = None
    metrics: Optional[dict] = None
    training_job_id: Optional[int] = None
    model_file_path: Optional[str] = None
    model_file_size: Optional[int] = None
    registered_by: Optional[int] = None
    registered_at: str

    model_config = ConfigDict(from_attributes=True)


class VersionListItem(BaseModel):
    """版本列表项（精简字段）"""
    version: int
    tag: str
    algorithm_type: Optional[str] = None
    metrics: Optional[dict] = None
    registered_at: str
    registered_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class VersionListResponse(BaseModel):
    """版本列表分页响应"""
    total: int
    page: int
    items: List[VersionListItem]


class TagChangeRequest(BaseModel):
    """标签变更请求"""
    tag: str = Field(..., description="新标签：staging/production/archived")


class TagChangeResponse(BaseModel):
    """标签变更响应"""
    version: int
    previous_production_version: Optional[int] = None
    tag: str
    message: str


class CompareResponse(BaseModel):
    """版本对比响应"""
    version_a: int
    version_b: int
    metrics_a: dict
    metrics_b: dict
    comparison: List[dict]
    unique_to_a: List[str]
    unique_to_b: List[str]
    common_metrics_only: bool


class RollbackResponse(BaseModel):
    """回滚响应"""
    success: bool
    new_production_version: int
    previous_production_version: Optional[int] = None
    message: str


class HistoryItem(BaseModel):
    """操作历史条目"""
    id: int
    model_id: int
    version: int
    action: str
    actor_id: Optional[int] = None
    details: dict
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class HistoryResponse(BaseModel):
    """操作历史分页响应"""
    total: int
    page: int
    items: List[HistoryItem]


# =============================================================================
# 辅助函数
# =============================================================================


def _structured_log(
    request_id: str,
    user_id: int,
    action: str,
    elapsed_ms: float,
    status_code: int,
    extra: Optional[dict] = None,
) -> None:
    """
    输出结构化 JSON 日志（Constitution 第 VI 条要求）。

    Args:
        request_id: 请求唯一标识
        user_id: 当前操作用户 ID
        action: 操作类型（register/tag_change/rollback/compare/list/history）
        elapsed_ms: 耗时（毫秒）
        status_code: HTTP 状态码
        extra: 额外字段
    """
    log_data = {
        "request_id": request_id,
        "user_id": user_id,
        "action": action,
        "elapsed_ms": round(elapsed_ms, 2),
        "status_code": status_code,
        **(extra or {}),
    }
    logger.info(f"[ModelRegistry] {log_data}")


def _record_history(
    db: Session,
    model_id: int,
    version: int,
    action: str,
    actor_id: Optional[int],
    details: dict,
) -> ModelVersionHistory:
    """
    记录操作历史。

    Args:
        db: 数据库会话
        model_id: 模型 ID
        version: 版本号
        action: 操作类型
        actor_id: 操作人 ID
        details: 详情字典

    Returns:
        创建的 ModelVersionHistory 记录
    """
    record = ModelVersionHistory(
        model_id=model_id,
        version=version,
        action=action,
        actor_id=actor_id,
        details=details,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _is_admin(user: User) -> bool:
    """判断用户是否为 admin"""
    return user.role == "admin"


# =============================================================================
# API 端点
# =============================================================================


@router.post(
    "/{model_id}/versions",
    response_model=VersionResponse,
    status_code=201,
    summary="注册新版本",
)
async def register_version(
    request: Request,
    model_id: int,
    body: RegisterVersionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionResponse:
    """
    为指定模型注册新版本。
    - 版本号自动递增（整数，从 1 开始）
    - 默认标签为 staging
    - 关联 TrainingJob 时自动提取元数据
    - 记录注册操作历史
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]

    # 校验模型是否存在
    model = db.query(TrainedModel).filter(TrainedModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 计算下一个版本号
    next_version = compute_next_version(db, model_id)

    # 填充元数据（如果关联了 training_job，尝试从 TrainedModel/数据库获取）
    algorithm_type = body.algorithm_type or model.model_type
    model_type = body.model_type or model.model_type
    task_type = body.task_type
    metrics = body.metrics or model.metrics or {}
    training_job_id = body.training_job_id

    # 数据集指纹
    dataset_hash = body.dataset_hash
    if not dataset_hash and body.dataset_name:
        dataset_hash = compute_dataset_hash(filename=body.dataset_name)

    # 创建版本记录
    version_record = ModelVersion(
        model_id=model_id,
        version=next_version,
        tag="staging",
        algorithm_type=algorithm_type,
        model_type=model_type,
        task_type=task_type,
        dataset_name=body.dataset_name,
        dataset_hash=dataset_hash,
        training_params=body.training_params or {},
        training_time=body.training_time,
        metrics=metrics,
        training_job_id=training_job_id,
        model_file_path=body.model_file_path,
        model_file_size=body.model_file_size,
        registered_by=current_user.id,
    )
    db.add(version_record)
    db.commit()
    db.refresh(version_record)

    # 记录操作历史
    _record_history(
        db=db,
        model_id=model_id,
        version=next_version,
        action="register",
        actor_id=current_user.id,
        details={
            "algorithm_type": algorithm_type,
            "model_type": model_type,
            "task_type": task_type,
            "training_job_id": training_job_id,
            "metrics": metrics,
        },
    )

    elapsed = (time.perf_counter() - start) * 1000
    _structured_log(
        request_id=request_id,
        user_id=current_user.id,
        action="register",
        elapsed_ms=elapsed,
        status_code=201,
        extra={"model_id": model_id, "version": next_version},
    )

    return VersionResponse(
        id=version_record.id,
        model_id=version_record.model_id,
        version=version_record.version,
        tag=version_record.tag,
        algorithm_type=version_record.algorithm_type,
        model_type=version_record.model_type,
        task_type=version_record.task_type,
        dataset_name=version_record.dataset_name,
        dataset_hash=version_record.dataset_hash,
        training_params=version_record.training_params,
        training_time=version_record.training_time,
        metrics=version_record.metrics,
        training_job_id=version_record.training_job_id,
        model_file_path=version_record.model_file_path,
        model_file_size=version_record.model_file_size,
        registered_by=version_record.registered_by,
        registered_at=version_record.registered_at.isoformat(),
    )


@router.get(
    "/{model_id}/versions",
    response_model=VersionListResponse,
    summary="列出所有版本",
)
async def list_versions(
    request: Request,
    model_id: int,
    tag: Optional[str] = Query(None, description="标签筛选：staging/production/archived"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionListResponse:
    """
    列出指定模型的所有版本。
    - 默认按注册时间倒序
    - 支持标签筛选和分页
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]

    # 查询总数
    query = db.query(ModelVersion).filter(ModelVersion.model_id == model_id)
    if tag:
        query = query.filter(ModelVersion.tag == tag)

    total = query.count()

    # 分页查询
    offset = (page - 1) * page_size
    records = (
        query
        .order_by(ModelVersion.registered_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    elapsed = (time.perf_counter() - start) * 1000
    _structured_log(
        request_id=request_id,
        user_id=current_user.id,
        action="list",
        elapsed_ms=elapsed,
        status_code=200,
        extra={"model_id": model_id, "total": total, "tag": tag},
    )

    return VersionListResponse(
        total=total,
        page=page,
        items=[
            VersionListItem(
                version=r.version,
                tag=r.tag,
                algorithm_type=r.algorithm_type,
                metrics=r.metrics,
                registered_at=r.registered_at.isoformat(),
                registered_by=r.registered_by,
            )
            for r in records
        ],
    )


@router.get(
    "/{model_id}/versions/{version}",
    response_model=VersionResponse,
    summary="获取单版本详情",
)
async def get_version(
    request: Request,
    model_id: int,
    version: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionResponse:
    """
    获取指定版本的详细信息。
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]

    record = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model_id, ModelVersion.version == version)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"版本 v{version} 不存在")

    elapsed = (time.perf_counter() - start) * 1000
    _structured_log(
        request_id=request_id,
        user_id=current_user.id,
        action="get",
        elapsed_ms=elapsed,
        status_code=200,
        extra={"model_id": model_id, "version": version},
    )

    return VersionResponse(
        id=record.id,
        model_id=record.model_id,
        version=record.version,
        tag=record.tag,
        algorithm_type=record.algorithm_type,
        model_type=record.model_type,
        task_type=record.task_type,
        dataset_name=record.dataset_name,
        dataset_hash=record.dataset_hash,
        training_params=record.training_params,
        training_time=record.training_time,
        metrics=record.metrics,
        training_job_id=record.training_job_id,
        model_file_path=record.model_file_path,
        model_file_size=record.model_file_size,
        registered_by=record.registered_by,
        registered_at=record.registered_at.isoformat(),
    )


@router.patch(
    "/{model_id}/versions/{version}/tags",
    response_model=TagChangeResponse,
    summary="变更版本标签",
)
async def update_tag(
    request: Request,
    model_id: int,
    version: int,
    body: TagChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagChangeResponse:
    """
    变更版本标签（仅 admin 可变更 production）。
    - production 标签唯一：提升新版本为 production 时，旧 production 版本自动降级为 staging
    - 非法标签值返回 422
    - 记录操作历史
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]

    # 校验标签值
    if body.tag not in VALID_TAGS:
        raise HTTPException(
            status_code=422,
            detail=f"非法标签值：{body.tag}，有效值：{list(VALID_TAGS)}",
        )

    # 非 admin 不可变更 production
    if body.tag == "production" and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="权限不足：变更 production 标签需要 admin 权限")

    # 查询目标版本
    record = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model_id, ModelVersion.version == version)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"版本 v{version} 不存在")

    previous_tag = record.tag
    previous_production_version: Optional[int] = None
    message_parts = []

    # production 标签唯一性处理
    if body.tag == "production":
        old_prod = (
            db.query(ModelVersion)
            .filter(
                ModelVersion.model_id == model_id,
                ModelVersion.tag == "production",
            )
            .first()
        )
        if old_prod and old_prod.version != version:
            old_prod.tag = "staging"
            previous_production_version = old_prod.version
            message_parts.append(f"v{old_prod.version} 已自动降级为 staging")

    record.tag = body.tag
    db.commit()
    db.refresh(record)

    # 记录操作历史
    _record_history(
        db=db,
        model_id=model_id,
        version=version,
        action="tag_change",
        actor_id=current_user.id,
        details={
            "from_tag": previous_tag,
            "to_tag": body.tag,
            "auto_downgrade_previous": previous_production_version is not None,
            "previous_production_version": previous_production_version,
        },
    )

    message = f"v{version} 已设为 {body.tag}"
    if message_parts:
        message += "，" + "，".join(message_parts)

    elapsed = (time.perf_counter() - start) * 1000
    _structured_log(
        request_id=request_id,
        user_id=current_user.id,
        action="tag_change",
        elapsed_ms=elapsed,
        status_code=200,
        extra={
            "model_id": model_id,
            "version": version,
            "from_tag": previous_tag,
            "to_tag": body.tag,
        },
    )

    return TagChangeResponse(
        version=version,
        previous_production_version=previous_production_version,
        tag=record.tag,
        message=message,
    )


@router.get(
    "/{model_id}/compare",
    response_model=CompareResponse,
    summary="对比两个版本",
)
async def compare_model_versions(
    request: Request,
    model_id: int,
    version_a: int = Query(..., description="版本 A"),
    version_b: int = Query(..., description="版本 B"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompareResponse:
    """
    对比两个版本的评估指标。
    - 返回指标并集，交集字段计算 delta 和 winner
    - 非数值指标不计算 delta
    - 任一版本不存在返回 404
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]

    rec_a = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model_id, ModelVersion.version == version_a)
        .first()
    )
    rec_b = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model_id, ModelVersion.version == version_b)
        .first()
    )

    if not rec_a:
        raise HTTPException(status_code=404, detail=f"版本 v{version_a} 不存在")
    if not rec_b:
        raise HTTPException(status_code=404, detail=f"版本 v{version_b} 不存在")

    metrics_a = rec_a.metrics or {}
    metrics_b = rec_b.metrics or {}

    comparison, unique_a, unique_b = compare_versions(metrics_a, metrics_b)

    elapsed = (time.perf_counter() - start) * 1000
    _structured_log(
        request_id=request_id,
        user_id=current_user.id,
        action="compare",
        elapsed_ms=elapsed,
        status_code=200,
        extra={
            "model_id": model_id,
            "version_a": version_a,
            "version_b": version_b,
            "common_metrics": len(comparison),
        },
    )

    return CompareResponse(
        version_a=version_a,
        version_b=version_b,
        metrics_a=metrics_a,
        metrics_b=metrics_b,
        comparison=comparison,
        unique_to_a=unique_a,
        unique_to_b=unique_b,
        common_metrics_only=len(unique_a) == 0 and len(unique_b) == 0,
    )


@router.post(
    "/{model_id}/rollback",
    response_model=RollbackResponse,
    summary="回滚到指定版本",
)
async def rollback_version(
    request: Request,
    model_id: int,
    target_version: int = Query(..., description="目标版本号"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RollbackResponse:
    """
    将指定历史版本切换为 production（仅 admin 可操作）。
    - target_version 变为 production，原 production 版本降级为 staging
    - target_version 不存在返回 404
    - target_version 为 archived 返回 422
    - 记录回滚操作历史
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]

    # 非 admin 不可回滚
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="权限不足：回滚操作需要 admin 权限")

    # 查询目标版本
    target = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model_id, ModelVersion.version == target_version)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail=f"目标版本 v{target_version} 不存在")

    # archived 版本不允许直接回滚
    if target.tag == "archived":
        raise HTTPException(
            status_code=422,
            detail=f"版本 v{target_version} 当前状态为 archived，需先激活后才能回滚",
        )

    previous_production_version: Optional[int] = None

    # 找到当前 production 版本并降级
    old_prod = (
        db.query(ModelVersion)
        .filter(
            ModelVersion.model_id == model_id,
            ModelVersion.tag == "production",
        )
        .first()
    )
    if old_prod:
        previous_production_version = old_prod.version
        old_prod.tag = "staging"

    # 目标版本设为 production
    previous_tag = target.tag
    target.tag = "production"
    db.commit()

    # 记录操作历史
    _record_history(
        db=db,
        model_id=model_id,
        version=target_version,
        action="rollback",
        actor_id=current_user.id,
        details={
            "from_version": previous_production_version,
            "to_version": target_version,
            "previous_tag_of_target": previous_tag,
            "previous_production_version": previous_production_version,
        },
    )

    message = f"已回滚到 v{target_version}"
    if previous_production_version:
        message += f"，v{previous_production_version} 已降级为 staging"

    elapsed = (time.perf_counter() - start) * 1000
    _structured_log(
        request_id=request_id,
        user_id=current_user.id,
        action="rollback",
        elapsed_ms=elapsed,
        status_code=200,
        extra={
            "model_id": model_id,
            "target_version": target_version,
            "previous_production_version": previous_production_version,
        },
    )

    return RollbackResponse(
        success=True,
        new_production_version=target_version,
        previous_production_version=previous_production_version,
        message=message,
    )


@router.get(
    "/{model_id}/history",
    response_model=HistoryResponse,
    summary="操作历史",
)
async def get_history(
    request: Request,
    model_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    """
    查询版本操作历史。
    - 操作类型：register / tag_change / rollback / archive
    - 按时间倒序
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]

    total = (
        db.query(ModelVersionHistory)
        .filter(ModelVersionHistory.model_id == model_id)
        .count()
    )

    offset = (page - 1) * page_size
    records = (
        db.query(ModelVersionHistory)
        .filter(ModelVersionHistory.model_id == model_id)
        .order_by(ModelVersionHistory.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    elapsed = (time.perf_counter() - start) * 1000
    _structured_log(
        request_id=request_id,
        user_id=current_user.id,
        action="history",
        elapsed_ms=elapsed,
        status_code=200,
        extra={"model_id": model_id, "total": total},
    )

    return HistoryResponse(
        total=total,
        page=page,
        items=[
            HistoryItem(
                id=r.id,
                model_id=r.model_id,
                version=r.version,
                action=r.action,
                actor_id=r.actor_id,
                details=r.details or {},
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ],
    )
