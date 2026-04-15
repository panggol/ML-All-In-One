"""
API 路由：模型漂移检测与告警
Constitution: 结构化 JSON 日志, Depends(get_current_user), Library-First
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from io import StringIO
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, JSON, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import func

from api.auth import get_current_user
from api.database import Base, SessionLocal, engine
from src.mlkit.drift.detector import check_drift, compute_feature_stats
from src.mlkit.drift.alerter import send_feishu_alert

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ 数据库表定义 ============

class DriftReference(Base):
    """基准数据集表"""
    __tablename__ = "drift_reference"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    model_id = Column(Integer, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    feature_names = Column(JSON, nullable=False)
    feature_stats = Column(JSON, nullable=False)
    bin_edges = Column(JSON, nullable=True)
    data_blob = Column(Text, nullable=True)  # JSON-serialized reference DataFrame
    row_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Boolean, default=False)


class DriftCheckHistory(Base):
    """漂移检测历史表"""
    __tablename__ = "drift_check_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    reference_id = Column(Integer, ForeignKey("drift_reference.id"), nullable=False)
    model_id = Column(Integer, nullable=True, index=True)
    check_id = Column(String(36), nullable=False, unique=True)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    row_count = Column(Integer, nullable=False)
    psi_overall = Column(Float, nullable=True)
    psi_features = Column(JSON, nullable=False)
    ks_features = Column(JSON, nullable=False)
    drift_level = Column(String(20), nullable=False)
    alerted = Column(Boolean, default=False)
    alert_rule_id = Column(Integer, nullable=True)
    check_metadata = Column(JSON, nullable=True)  # renamed from metadata (reserved in SQLAlchemy)


class DriftAlert(Base):
    """漂移告警规则表"""
    __tablename__ = "drift_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    model_id = Column(Integer, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    metric = Column(String(20), nullable=False, default="psi")
    threshold = Column(Float, nullable=False, default=0.2)
    webhook_url = Column(String(500), nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DriftAlertHistory(Base):
    """告警发送历史表"""
    __tablename__ = "drift_alert_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_rule_id = Column(Integer, ForeignKey("drift_alerts.id"), nullable=False)
    check_history_id = Column(Integer, ForeignKey("drift_check_history.id"), nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), nullable=False, default="sent")
    response_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)


# 确保表存在（延迟创建）
Base.metadata.create_all(bind=engine)

# 轻量迁移：确保新列在已有数据库中存在
with engine.connect() as conn:
    from sqlalchemy import text
    for col_spec in [
        ("data_blob", "TEXT"),
    ]:
        col_name, col_type = col_spec
        try:
            conn.execute(text(f"ALTER TABLE drift_reference ADD COLUMN {col_name} {col_type}"))
            conn.commit()
        except Exception:
            # 列已存在 → 忽略
            pass


# ============ Pydantic 请求/响应模型 ============

class ReferenceCreateResponse(BaseModel):
    id: int
    name: str
    model_id: Optional[int]
    feature_names: list[str]
    row_count: int
    feature_stats: dict
    created_at: str


class ReferenceDetailResponse(BaseModel):
    id: int
    name: str
    model_id: Optional[int]
    feature_names: list[str]
    row_count: int
    feature_stats: dict
    bin_edges: dict
    created_at: str


class KSFeatureDetail(BaseModel):
    stat: float
    pvalue: float
    drifted: bool


class DriftCheckResponse(BaseModel):
    check_id: str
    reference_id: int
    model_id: Optional[int]
    recorded_at: str
    row_count: int
    psi_overall: float
    psi_features: dict[str, float]
    ks_features: dict[str, KSFeatureDetail]
    drift_level: str
    alerted: bool
    alert_rule_id: Optional[int]
    warnings: list[str]


class TopFeatureItem(BaseModel):
    feature: str
    psi: float
    ks_stat: float
    ks_pvalue: float
    recommendation: str


class DriftReportResponse(BaseModel):
    model_id: int
    report_time: str
    period_days: int
    total_checks: int
    drift_level: str
    psi_current: float
    psi_top_features: list[TopFeatureItem]
    ks_drifted_features: list[str]
    recommendations: list[str]
    drift_history_summary: dict[str, int]


class TrendDataPoint(BaseModel):
    timestamp: str
    psi_overall: float
    psi_features: dict[str, float]


class DriftTrendResponse(BaseModel):
    model_id: int
    metric: str
    days: int
    data: list[TrendDataPoint]


class DriftAlertCreate(BaseModel):
    name: str
    model_id: Optional[int] = None
    metric: str = "psi"
    threshold: float = 0.2
    webhook_url: str


class DriftAlertResponse(BaseModel):
    id: int
    name: str
    model_id: Optional[int]
    metric: str
    threshold: float
    webhook_url: str
    enabled: bool
    created_at: str


class DriftAlertListResponse(BaseModel):
    total: int
    alerts: list[DriftAlertResponse]


class DriftAlertUpdate(BaseModel):
    threshold: Optional[float] = None
    enabled: Optional[bool] = None
    webhook_url: Optional[str] = None


# ============ 辅助函数 ============

def _psi_recommendation(psi: float, ks_drifted: bool) -> str:
    if math.isnan(psi) or psi < 0.1:
        return "数据分布稳定"
    if psi < 0.2:
        return "轻微漂移，建议观察"
    if psi < 0.25:
        return "中度漂移，建议检查数据管道"
    return "严重漂移，建议立即重新训练模型"


def _find_matching_alert(
    db: Session,
    model_id: Optional[int],
    threshold: float,
) -> Optional[DriftAlert]:
    """查找匹配的告警规则"""
    query = db.query(DriftAlert).filter(
        DriftAlert.enabled == True,
        DriftAlert.metric == "psi",
        DriftAlert.threshold <= threshold + 0.001,
    )
    # 优先匹配特定模型规则，再匹配全局规则
    alert = query.filter(DriftAlert.model_id == model_id).first()
    if not alert:
        alert = query.filter(DriftAlert.model_id == None).first()
    return alert


def _parse_csv(file: UploadFile) -> pd.DataFrame:
    """解析 CSV 文件"""
    try:
        content = file.file.read().decode("utf-8")
        df = pd.read_csv(StringIO(content))
    except UnicodeDecodeError:
        file.file.seek(0)
        content = file.file.read().decode("gbk")
        df = pd.read_csv(StringIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV 解析失败: {str(e)}")
    return df


def _df_to_json(df: pd.DataFrame) -> str:
    """将 DataFrame 序列化为 JSON 字符串（处理 NaN/Inf）"""
    # 替换 NaN/Inf 为 None（JSON null）
    df_clean = df.replace([float('nan'), float('inf'), float('-inf')], None)
    return df_clean.to_json(orient='records', date_format='iso')


def _df_from_json(json_str: str, feature_names: list[str]) -> pd.DataFrame:
    """从 JSON 字符串反序列化为 DataFrame"""
    df = pd.read_json(json_str, orient='records')
    # 按 feature_names 顺序和类型重建，确保列一致
    result = pd.DataFrame()
    for col in feature_names:
        if col in df.columns:
            result[col] = df[col]
        else:
            result[col] = pd.Series(dtype=float)
    return result


def _compute_bin_edges(df: pd.DataFrame, n_bins: int = 10) -> dict[str, list[float]]:
    """计算每个数值特征的等频分箱边界（quantile binning）"""
    bin_edges: dict[str, list[float]] = {}
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        col_data = df[col].dropna()
        if len(col_data) < 2:
            continue
        try:
            quantiles = np.linspace(0, 1, n_bins + 1)
            edges = np.quantile(col_data.values, quantiles)
            edges = np.unique(edges)
            if len(edges) >= 2:
                bin_edges[col] = [round(float(e), 6) for e in edges]
        except Exception:
            continue
    return bin_edges


# ============ API 端点 ============

@router.post("/reference", response_model=ReferenceCreateResponse)
async def create_reference(
    file: UploadFile = File(...),
    name: str = Form(None),
    model_id: Optional[int] = Form(None),
    description: str = Form(None),
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    上传基准数据集（训练数据分布）
    - 自动计算统计量（均值/标准差/分位数）
    - 支持关联模型 ID
    - CSV 文件 ≤ 500MB
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    df = _parse_csv(file)

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV 文件为空")

    if len(df.columns) == 0:
        raise HTTPException(status_code=400, detail="CSV 文件没有有效列")

    feature_stats = compute_feature_stats(df)
    data_blob = _df_to_json(df)
    bin_edges = _compute_bin_edges(df)

    ref = DriftReference(
        user_id=current_user,
        model_id=model_id,
        name=name or file.filename.replace(".csv", ""),
        description=description,
        feature_names=list(df.columns),
        feature_stats=feature_stats,
        data_blob=data_blob,
        bin_edges=bin_edges,
        row_count=len(df),
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)

    return ReferenceCreateResponse(
        id=ref.id,
        name=ref.name,
        model_id=ref.model_id,
        feature_names=ref.feature_names,
        row_count=ref.row_count,
        feature_stats=ref.feature_stats,
        created_at=ref.created_at.isoformat(),
    )


@router.get("/reference/{ref_id}", response_model=ReferenceDetailResponse)
async def get_reference(
    ref_id: int,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取基准数据集详情"""
    ref = db.query(DriftReference).filter(
        DriftReference.id == ref_id,
        DriftReference.is_deleted == False,
    ).first()
    if not ref:
        raise HTTPException(status_code=404, detail="基准数据集不存在")
    return ReferenceDetailResponse(
        id=ref.id,
        name=ref.name,
        model_id=ref.model_id,
        feature_names=ref.feature_names,
        row_count=ref.row_count,
        feature_stats=ref.feature_stats,
        bin_edges=ref.bin_edges or {},
        created_at=ref.created_at.isoformat(),
    )


@router.post("/check", response_model=DriftCheckResponse)
async def check_drift_api(
    file: UploadFile = File(...),
    reference_id: int = Form(...),
    model_id: Optional[int] = Form(None),
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    提交当前数据，批量计算 PSI/KS
    - 自动触发飞书告警（如 PSI > 阈值）
    - 返回每个特征的 PSI + KS 检验结果
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    # 获取基准数据
    ref = db.query(DriftReference).filter(
        DriftReference.id == reference_id,
        DriftReference.is_deleted == False,
    ).first()
    if not ref:
        raise HTTPException(status_code=404, detail="基准数据集不存在")

    # 解析当前数据
    current_df = _parse_csv(file)

    if current_df.empty:
        raise HTTPException(status_code=400, detail="CSV 文件为空")

    # 检查特征匹配
    ref_features = set(ref.feature_names)
    cur_features = set(current_df.columns)
    missing = ref_features - cur_features
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"当前数据缺少基准特征: {list(missing)}",
        )

    # 从 data_blob 恢复基准 DataFrame
    if not ref.data_blob:
        raise HTTPException(
            status_code=500,
            detail="基准数据集缺少原始数据，请重新创建基准数据",
        )
    reference_df = _df_from_json(ref.data_blob, ref.feature_names)
    current_df_filtered = current_df[[c for c in ref.feature_names if c in current_df.columns]]

    # 获取告警阈值
    alert_rule = _find_matching_alert(db, model_id, threshold=0.2)
    threshold = alert_rule.threshold if alert_rule else 0.2

    # 执行漂移检测
    check_id = str(uuid.uuid4())
    try:
        result = check_drift(
            reference_df=reference_df,
            current_df=current_df_filtered,
            reference_id=reference_id,
            model_id=model_id,
            check_id=check_id,
            psi_threshold=threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 保存检测历史
    history = DriftCheckHistory(
        user_id=current_user,
        reference_id=reference_id,
        model_id=model_id,
        check_id=check_id,
        row_count=result.row_count,
        psi_overall=result.psi_overall,
        psi_features=result.psi_features,
        ks_features=result.ks_features,
        drift_level=result.drift_level,
        alerted=result.alerted,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    # 触发告警
    if result.alerted and alert_rule:
        drifted_features = [
            f for f, psi in result.psi_features.items()
            if not math.isnan(psi) and psi > threshold
        ]
        success, err = send_feishu_alert(
            webhook_url=alert_rule.webhook_url,
            model_id=model_id or 0,
            model_name=f"Model-{model_id}" if model_id else "Unknown",
            check_time=history.recorded_at.isoformat(),
            drift_level=result.drift_level,
            psi_overall=result.psi_overall,
            threshold=threshold,
            drifted_features=drifted_features,
        )
        # 记录告警历史
        alert_history = DriftAlertHistory(
            alert_rule_id=alert_rule.id,
            check_history_id=history.id,
            status="sent" if success else "failed",
            error_message=err,
        )
        db.add(alert_history)

        # 更新 history 告警规则 ID
        history.alert_rule_id = alert_rule.id
        db.commit()

    return DriftCheckResponse(
        check_id=check_id,
        reference_id=reference_id,
        model_id=model_id,
        recorded_at=history.recorded_at.isoformat(),
        row_count=result.row_count,
        psi_overall=result.psi_overall,
        psi_features=result.psi_features,
        ks_features={k: KSFeatureDetail(**v) for k, v in result.ks_features.items()},
        drift_level=result.drift_level,
        alerted=result.alerted,
        alert_rule_id=history.alert_rule_id,
        warnings=result.warnings,
    )


@router.get("/report/{model_id}", response_model=DriftReportResponse)
async def get_drift_report(
    model_id: int,
    days: int = Query(default=30, ge=1, le=365),
    format: str = Query(default="json", pattern="^(json|pdf)$"),
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取漂移报告"""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    history_records = db.query(DriftCheckHistory).filter(
        DriftCheckHistory.model_id == model_id,
        DriftCheckHistory.recorded_at >= cutoff,
    ).order_by(DriftCheckHistory.recorded_at.desc()).all()

    if not history_records:
        raise HTTPException(
            status_code=404,
            detail=f"模型 {model_id} 在最近 {days} 天内无检测记录",
        )

    # 最新检测
    latest = history_records[0]

    # PSI Top-K 特征
    top_features = []
    ks_drifted = []
    psi_sorted = sorted(
        latest.psi_features.items(),
        key=lambda x: x[1] if not math.isnan(x[1]) else -999,
        reverse=True,
    )
    for feat, psi_val in psi_sorted[:5]:
        if math.isnan(psi_val):
            continue
        ks_info = latest.ks_features.get(feat, {})
        if ks_info.get("drifted"):
            ks_drifted.append(feat)
        top_features.append(TopFeatureItem(
            feature=feat,
            psi=psi_val,
            ks_stat=ks_info.get("stat", 0.0),
            ks_pvalue=ks_info.get("pvalue", 1.0),
            recommendation=_psi_recommendation(psi_val, ks_info.get("drifted", False)),
        ))

    # 漂移等级汇总
    level_counts = {"none": 0, "mild": 0, "moderate": 0, "severe": 0}
    for rec in history_records:
        level = rec.drift_level or "none"
        if level in level_counts:
            level_counts[level] += 1

    recommendations = []
    if level_counts["severe"] > 0:
        recommendations.append("严重漂移频繁出现，建议立即触发模型重训练")
    elif level_counts["moderate"] > 0:
        recommendations.append("中度漂移出现，建议检查数据管道")
    elif level_counts["mild"] > 0:
        recommendations.append("轻度漂移，建议持续监控")

    return DriftReportResponse(
        model_id=model_id,
        report_time=datetime.now(timezone.utc).isoformat(),
        period_days=days,
        total_checks=len(history_records),
        drift_level=latest.drift_level,
        psi_current=latest.psi_overall,
        psi_top_features=top_features,
        ks_drifted_features=ks_drifted,
        recommendations=recommendations,
        drift_history_summary=level_counts,
    )


@router.get("/trend/{model_id}", response_model=DriftTrendResponse)
async def get_drift_trend(
    model_id: int,
    days: int = Query(default=30, ge=1, le=365),
    metric: str = Query(default="psi", pattern="^(psi|ks|accuracy)$"),
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取历史漂移趋势数据"""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    records = db.query(DriftCheckHistory).filter(
        DriftCheckHistory.model_id == model_id,
        DriftCheckHistory.recorded_at >= cutoff,
    ).order_by(DriftCheckHistory.recorded_at.asc()).all()

    data = []
    for rec in records:
        if metric == "psi":
            psi_overall = rec.psi_overall or 0.0
        elif metric == "ks":
            # KS 用最大漂移特征的平均 stat
            ks_vals = [v["stat"] for v in rec.ks_features.values() if "stat" in v]
            psi_overall = sum(ks_vals) / len(ks_vals) if ks_vals else 0.0
        else:
            psi_overall = 0.0  # accuracy 暂不支持

        data.append(TrendDataPoint(
            timestamp=rec.recorded_at.isoformat(),
            psi_overall=round(psi_overall, 6),
            psi_features=rec.psi_features,
        ))

    return DriftTrendResponse(
        model_id=model_id,
        metric=metric,
        days=days,
        data=data,
    )


@router.post("/alerts", response_model=DriftAlertResponse)
async def create_alert(
    alert: DriftAlertCreate,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """配置告警规则"""
    if not alert.webhook_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="WebHook URL 必须使用 HTTPS")

    db_alert = DriftAlert(
        user_id=current_user,
        name=alert.name,
        model_id=alert.model_id,
        metric=alert.metric,
        threshold=alert.threshold,
        webhook_url=alert.webhook_url,
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)

    return DriftAlertResponse(
        id=db_alert.id,
        name=db_alert.name,
        model_id=db_alert.model_id,
        metric=db_alert.metric,
        threshold=db_alert.threshold,
        webhook_url=db_alert.webhook_url,
        enabled=db_alert.enabled,
        created_at=db_alert.created_at.isoformat(),
    )


@router.get("/alerts", response_model=DriftAlertListResponse)
async def list_alerts(
    model_id: Optional[int] = Query(default=None),
    enabled: Optional[bool] = Query(default=None),
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询告警规则"""
    query = db.query(DriftAlert).filter(DriftAlert.user_id == current_user)
    if model_id is not None:
        query = query.filter(DriftAlert.model_id == model_id)
    if enabled is not None:
        query = query.filter(DriftAlert.enabled == enabled)

    alerts = query.order_by(DriftAlert.created_at.desc()).all()
    return DriftAlertListResponse(
        total=len(alerts),
        alerts=[
            DriftAlertResponse(
                id=a.id,
                name=a.name,
                model_id=a.model_id,
                metric=a.metric,
                threshold=a.threshold,
                webhook_url=a.webhook_url,
                enabled=a.enabled,
                created_at=a.created_at.isoformat(),
            )
            for a in alerts
        ],
    )


@router.patch("/alerts/{rule_id}", response_model=DriftAlertResponse)
async def update_alert(
    rule_id: int,
    update: DriftAlertUpdate,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新告警规则"""
    alert = db.query(DriftAlert).filter(
        DriftAlert.id == rule_id,
        DriftAlert.user_id == current_user,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警规则不存在")

    if update.threshold is not None:
        alert.threshold = update.threshold
    if update.enabled is not None:
        alert.enabled = update.enabled
    if update.webhook_url is not None:
        if not update.webhook_url.startswith("https://"):
            raise HTTPException(status_code=400, detail="WebHook URL 必须使用 HTTPS")
        alert.webhook_url = update.webhook_url

    db.commit()
    db.refresh(alert)

    return DriftAlertResponse(
        id=alert.id,
        name=alert.name,
        model_id=alert.model_id,
        metric=alert.metric,
        threshold=alert.threshold,
        webhook_url=alert.webhook_url,
        enabled=alert.enabled,
        created_at=alert.created_at.isoformat(),
    )
