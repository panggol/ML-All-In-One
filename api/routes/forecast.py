"""
时序预测 API 路由
Constitution: 结构化 JSON 日志, Depends(get_current_user), Library-First
"""
from __future__ import annotations

import json
import logging
import math
import os
import pickle
import tempfile
import time
import uuid
from datetime import datetime, timezone
from io import StringIO
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, JSON, Boolean, Text, ForeignKey
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from api.auth import get_current_user
from api.services.log_aggregator import get_request_id, set_request_context
from api.database import Base, SessionLocal, engine, get_db

# Library-First: 所有 ML 逻辑在 src.mlkit.forecast
from src.mlkit.forecast import (
    detect_frequency,
    ForecastEngine,
    ForecastResult,
    TrainResult,
    DecomposeResult,
    CrossValResult,
    FoldMetrics,
    decompose_prophet,
    decompose_arima,
    decompose_lightgbm,
    cross_validate,
    infer_freq_str,
    infer_period_for_seasonality,
)

router = APIRouter(prefix="/api/forecast", tags=["forecast"])
logger = logging.getLogger(__name__)


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ 数据库表 ============

class ForecastDataset(Base):
    """时序数据集表"""
    __tablename__ = "forecast_datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    timestamp_col = Column(String(100), default="timestamp")
    value_col = Column(String(100), default="value")
    freq = Column(String(20), nullable=False)   # daily/weekly/monthly/...
    freq_confidence = Column(Float, default=0.0)
    detected_freq = Column(String(20), nullable=True)
    time_range_start = Column(String(50), nullable=True)
    time_range_end = Column(String(50), nullable=True)
    row_count = Column(Integer, default=0)
    missing_ratio = Column(Float, default=0.0)
    duplicate_count = Column(Integer, default=0)
    feature_names = Column(JSON, nullable=False)
    data_blob = Column(Text, nullable=True)   # JSON serialized DataFrame
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ForecastModelBinary(Base):
    """预测模型二进制表"""
    __tablename__ = "forecast_model_binaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("forecast_datasets.id"), nullable=True)
    model_type = Column(String(20), nullable=False)   # prophet / arima / lightgbm
    model_name = Column(String(100), nullable=False)
    params = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=True)
    train_time_seconds = Column(Float, default=0.0)
    model_blob = Column(Text, nullable=False)  # pickle-serialized model
    feature_names = Column(JSON, nullable=True)  # lightgbm 用
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ForecastTask(Base):
    """预测任务表（支持异步训练/CV）"""
    __tablename__ = "forecast_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    task_id = Column(String(36), nullable=False, unique=True, index=True)
    task_type = Column(String(20), nullable=False)  # train / crossval
    model_id = Column(Integer, nullable=True)
    dataset_id = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")  # pending / running / completed / failed
    progress = Column(Float, default=0.0)
    current_phase = Column(String(50), nullable=True)
    result_blob = Column(Text, nullable=True)  # JSON result
    error_message = Column(Text, nullable=True)
    logs = Column(Text, nullable=True)  # accumulated log lines
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# 确保表存在
Base.metadata.create_all(bind=engine)


# ============ Pydantic 模型 ============

class PrepareResponse(BaseModel):
    dataset_id: int
    name: str
    freq: str
    detected_freq: str
    freq_confidence: float
    time_range_start: str
    time_range_end: str
    row_count: int
    missing_ratio: float
    duplicate_count: int
    feature_names: list[str]
    warnings: list[str]


class TrainRequest(BaseModel):
    dataset_id: int
    model_type: Literal["prophet", "arima", "lightgbm"] = "prophet"
    # Prophet
    changepoint_prior_scale: float = 0.05
    seasonality_mode: str = "additive"
    growth: str = "linear"
    holidays: list[str] | None = None
    # ARIMA
    auto_arima: bool = True
    p: int | None = None
    d: int | None = None
    q: int | None = None
    search_timeout: int = 60
    # LightGBM
    lags: list[int] | None = None
    rolling_windows: list[int] | None = None
    n_estimators: int = 100
    early_stopping_rounds: int | None = None


class TrainResponse(BaseModel):
    task_id: str
    model_id: int | None
    model_type: str
    status: str
    progress: float
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    current_phase: str | None
    result: dict | None
    error: str | None
    logs: str | None


class PredictRequest(BaseModel):
    model_id: int
    steps: int = 30
    confidence: float = 0.95


class ForecastPoint(BaseModel):
    timestamp: str
    yhat: float
    yhat_lower: float
    yhat_upper: float
    confidence: float


class PredictResponse(BaseModel):
    model_id: int
    model_type: str
    steps: int
    confidence: float
    forecast: list[ForecastPoint]
    warnings: list[str]


class DecomposeResponse(BaseModel):
    model_type: str
    timestamps: list[str]
    trend: list[float]
    seasonal: list[float]
    residual: list[float] | None
    yearly: list[float] | None
    weekly: list[float] | None
    holidays: list[float] | None


class CrossValRequest(BaseModel):
    model_id: int
    initial_days: int = 90
    horizon: int = 30
    period: int = 30


class FoldMetricsOut(BaseModel):
    fold: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    n_train: int
    n_test: int
    mae: float
    rmse: float
    mape: float


class CrossValResponse(BaseModel):
    task_id: str
    status: str
    model_type: str
    model_id: int
    initial_days: int
    horizon: int
    period: int
    folds: list[FoldMetricsOut]
    mae_mean: float
    mae_std: float
    rmse_mean: float
    rmse_std: float
    mape_mean: float
    mape_std: float
    total_time_seconds: float


class CVProgressResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    current_fold: int
    current_metrics: FoldMetricsOut | None


# ============ 辅助函数 ============

def _parse_csv(file: UploadFile) -> pd.DataFrame:
    """解析 CSV"""
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


def _serialize_model(model_obj) -> str:
    """序列化模型为字符串"""
    return pickle.dumps(model_obj).hex()


def _deserialize_model(blob: str):
    """反序列化模型"""
    return pickle.loads(bytes.fromhex(blob))


def _append_log(task: ForecastTask, line: str, db: Session):
    """追加日志行"""
    current = task.logs or ""
    lines = current.split("\n")
    if len(lines) > 500:
        lines = lines[-500:]
    lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
    task.logs = "\n".join(lines)
    db.commit()


# ============ API 端点 ============

@router.post("/prepare", response_model=PrepareResponse)
async def prepare_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
    timestamp_col: str = Form("timestamp"),
    value_col: str = Form(None),
    freq: str = Form(None),  # 用户指定的频率
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    上传时序 CSV，自动检测频率，返回数据集 ID
    """
    request_id = str(uuid.uuid4())
    set_request_context(request_id, str(current_user), module="forecast")
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "prepare",
        "module": "forecast"
    }))

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持 CSV 文件")

    df = _parse_csv(file)

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV 文件为空")
    if len(df) < 30:
        raise HTTPException(status_code=422, detail="数据量不足，至少需要 30 条记录")

    # 找时间戳列
    if timestamp_col not in df.columns:
        raise HTTPException(
            status_code=422,
            detail=f"时间戳列 '{timestamp_col}' 不存在，可选列: {list(df.columns)}",
        )

    # 解析时间戳
    ts_series = pd.to_datetime(df[timestamp_col], errors="coerce")
    invalid_count = ts_series.isna().sum()
    if invalid_count == len(df):
        raise HTTPException(status_code=422, detail="时间戳列无法解析为有效日期，请检查格式（支持 ISO 8601 / Unix timestamp / YYYY-MM-DD）")

    # 去重：保留最后一条
    df["_ts"] = ts_series
    before_dedup = len(df)
    df = df.drop_duplicates(subset=[timestamp_col], keep="last")
    duplicate_count = before_dedup - len(df)

    # 自动检测频率
    detected_freq, confidence = detect_frequency(ts_series)
    final_freq = freq or detected_freq

    # 选择数值列
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != "_ts"]
    if not numeric_cols:
        raise HTTPException(status_code=422, detail="CSV 中没有可识别的数值列")
    final_value_col = value_col if value_col and value_col in numeric_cols else numeric_cols[0]

    # 填充缺失日期（forward fill）
    ts_clean = ts_series.dropna().sort_values()
    missing_count = 0
    if len(ts_clean) > 1:
        full_range = pd.date_range(start=ts_clean.iloc[0], end=ts_clean.iloc[-1], freq=infer_freq_str(final_freq))
        missing_count = len(full_range) - len(ts_clean)

    missing_ratio = missing_count / len(full_range) if len(full_range) > 0 else 0.0

    # 保存数据
    data_to_save = df[[timestamp_col, final_value_col]].copy()
    data_blob = data_to_save.to_json(orient="records", date_format="iso")

    dataset = ForecastDataset(
        user_id=current_user,
        name=name or file.filename,
        timestamp_col=timestamp_col,
        value_col=final_value_col,
        freq=final_freq,
        freq_confidence=confidence,
        detected_freq=detected_freq,
        time_range_start=str(ts_series.min()),
        time_range_end=str(ts_series.max()),
        row_count=len(df),
        missing_ratio=round(missing_ratio, 4),
        duplicate_count=duplicate_count,
        feature_names=numeric_cols,
        data_blob=data_blob,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    warnings = []
    if missing_ratio > 0.2:
        warnings.append(f"缺失率 {missing_ratio:.1%} > 20%，已填充")
    if duplicate_count > 0:
        warnings.append(f"已去重 {duplicate_count} 条重复记录")

    return PrepareResponse(
        dataset_id=dataset.id,
        name=dataset.name,
        freq=dataset.freq,
        detected_freq=detected_freq,
        freq_confidence=confidence,
        time_range_start=dataset.time_range_start,
        time_range_end=dataset.time_range_end,
        row_count=dataset.row_count,
        missing_ratio=missing_ratio,
        duplicate_count=duplicate_count,
        feature_names=numeric_cols,
        warnings=warnings,
    )


def _run_train_task(
    task_id: str,
    dataset_id: int,
    model_type: str,
    params: dict,
    current_user: int,
):
    """后台训练任务"""
    db = SessionLocal()
    try:
        task = db.query(ForecastTask).filter(ForecastTask.task_id == task_id).first()
        if not task:
            return
        task.status = "running"
        db.commit()

        # 加载数据
        dataset = db.query(ForecastDataset).filter(
            ForecastDataset.id == dataset_id,
            ForecastDataset.user_id == current_user,
        ).first()
        if not dataset:
            task.status = "failed"
            task.error_message = "数据集不存在"
            db.commit()
            return

        df = pd.read_json(dataset.data_blob, orient="records")
        df.columns = [dataset.timestamp_col, dataset.value_col]
        df[dataset.timestamp_col] = pd.to_datetime(df[dataset.timestamp_col], errors="coerce")
        df = df.dropna()

        _append_log(task, f"数据加载完成: {len(df)} 条", db)

        # 训练
        if model_type == "prophet":
            trained, train_result = ForecastEngine.train(
                "prophet",
                df,
                target_col=dataset.value_col,
                timestamp_col=dataset.timestamp_col,
                value_col=dataset.value_col,
                changepoint_prior_scale=params.get("changepoint_prior_scale", 0.05),
                seasonality_mode=params.get("seasonality_mode", "additive"),
                growth=params.get("growth", "linear"),
            )
        elif model_type == "arima":
            trained, train_result = ForecastEngine.train(
                "arima",
                df,
                target_col=dataset.value_col,
                timestamp_col=dataset.timestamp_col,
                value_col=dataset.value_col,
                auto=params.get("auto_arima", True),
                p=params.get("p"),
                d=params.get("d"),
                q=params.get("q"),
                search_timeout=params.get("search_timeout", 60),
            )
        else:  # lightgbm
            trained, train_result = ForecastEngine.train(
                "lightgbm",
                df,
                target_col=dataset.value_col,
                timestamp_col=dataset.timestamp_col,
                value_col=dataset.value_col,
                lags=params.get("lags", [1, 7, 14, 30]),
                rolling_windows=params.get("rolling_windows", [7, 30]),
                n_estimators=params.get("n_estimators", 100),
            )

        _append_log(task, f"训练完成: {train_result.train_time_seconds}s, metrics={train_result.metrics}", db)

        # 保存模型
        model_blob = _serialize_model(trained)
        feature_names = None
        if model_type == "lightgbm":
            _, feature_names = trained

        model_record = ForecastModelBinary(
            user_id=current_user,
            dataset_id=dataset_id,
            model_type=model_type,
            model_name=f"{model_type}_{dataset.name}",
            params=params,
            metrics=train_result.metrics,
            train_time_seconds=train_result.train_time_seconds,
            model_blob=model_blob,
            feature_names=feature_names,
        )
        db.add(model_record)
        db.commit()
        db.refresh(model_record)

        task.status = "completed"
        task.progress = 1.0
        task.model_id = model_record.id
        task.result_blob = json.dumps({
            "model_id": model_record.id,
            "train_time": train_result.train_time_seconds,
            "metrics": train_result.metrics,
        })
        task.current_phase = "完成"
        db.commit()

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.progress = 0.0
        db.commit()
    finally:
        db.close()


@router.post("/train", response_model=TrainResponse)
async def train_model(
    req: TrainRequest,
    background_tasks: BackgroundTasks,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    训练时序预测模型（异步）
    """
    request_id = str(uuid.uuid4())
    set_request_context(request_id, str(current_user), module="forecast")
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "train",
        "module": "forecast"
    }))

    # 验证数据集存在
    dataset = db.query(ForecastDataset).filter(
        ForecastDataset.id == req.dataset_id,
        ForecastDataset.user_id == current_user,
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"数据集 {req.dataset_id} 不存在")

    # 构建任务
    task_id = str(uuid.uuid4())
    params = {
        "changepoint_prior_scale": req.changepoint_prior_scale,
        "seasonality_mode": req.seasonality_mode,
        "growth": req.growth,
        "holidays": req.holidays,
        "auto_arima": req.auto_arima,
        "p": req.p,
        "d": req.d,
        "q": req.q,
        "search_timeout": req.search_timeout,
        "lags": req.lags,
        "rolling_windows": req.rolling_windows,
        "n_estimators": req.n_estimators,
        "early_stopping_rounds": req.early_stopping_rounds,
    }

    task = ForecastTask(
        user_id=current_user,
        task_id=task_id,
        task_type="train",
        dataset_id=req.dataset_id,
        status="pending",
        progress=0.0,
        current_phase="等待开始",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    background_tasks.add_task(
        _run_train_task,
        task_id,
        req.dataset_id,
        req.model_type,
        params,
        current_user,
    )

    return TrainResponse(
        task_id=task_id,
        model_id=None,
        model_type=req.model_type,
        status="pending",
        progress=0.0,
        message=f"训练任务已创建，请通过 GET /api/forecast/train/{task_id}/status 查询进度",
    )


@router.get("/train/{task_id}/status", response_model=TaskStatusResponse)
async def get_train_status(
    task_id: str,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询训练任务状态"""
    request_id = get_request_id() or str(uuid.uuid4())
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "train_status",
        "module": "forecast"
    }))

    task = db.query(ForecastTask).filter(
        ForecastTask.task_id == task_id,
        ForecastTask.user_id == current_user,
        ForecastTask.task_type == "train",
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")

    result = json.loads(task.result_blob) if task.result_blob else None

    return TaskStatusResponse(
        task_id=task_id,
        status=task.status,
        progress=task.progress,
        current_phase=task.current_phase,
        result=result,
        error=task.error_message,
        logs=task.logs,
    )


@router.post("/predict", response_model=PredictResponse)
async def predict_forecast(
    req: PredictRequest,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    预测未来 N 个时间步
    """
    request_id = get_request_id() or str(uuid.uuid4())
    set_request_context(request_id, str(current_user), module="forecast")
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "predict",
        "module": "forecast"
    }))

    model_rec = db.query(ForecastModelBinary).filter(
        ForecastModelBinary.id == req.model_id,
        ForecastModelBinary.user_id == current_user,
    ).first()
    if not model_rec:
        raise HTTPException(status_code=404, detail=f"模型 {req.model_id} 不存在")

    # 加载模型
    model = _deserialize_model(model_rec.model_blob)
    model_type = model_rec.model_type

    # 加载数据
    dataset = db.query(ForecastDataset).filter(
        ForecastDataset.id == model_rec.dataset_id,
    ).first() if model_rec.dataset_id else None

    if dataset:
        df = pd.read_json(dataset.data_blob, orient="records")
        df.columns = [dataset.timestamp_col, dataset.value_col]
    else:
        # 无关联数据集时用空 DataFrame
        df = pd.DataFrame()

    warnings = []
    if req.steps > 365:
        warnings.append("预测步长超过 365 天，长期预测置信区间较大，结果仅供参考")

    # 预测
    freq_str = infer_freq_str(dataset.freq) if dataset else "D"
    result = ForecastEngine.predict(
        model_type,
        model,
        df,
        steps=req.steps,
        freq=dataset.detected_freq if dataset else "daily",
        confidence=req.confidence,
        freq_str=freq_str,
    )

    forecast_points = [
        ForecastPoint(
            timestamp=result.timestamps[i],
            yhat=result.yhat[i],
            yhat_lower=result.yhat_lower[i],
            yhat_upper=result.yhat_upper[i],
            confidence=req.confidence,
        )
        for i in range(len(result.timestamps))
    ]

    return PredictResponse(
        model_id=req.model_id,
        model_type=model_type,
        steps=req.steps,
        confidence=req.confidence,
        forecast=forecast_points,
        warnings=warnings,
    )


@router.get("/decompose", response_model=DecomposeResponse)
async def decompose_dataset(
    dataset_id: int,
    model_type: str = Query("arima", pattern="^(prophet|arima|lightgbm)$"),
    model_id: int = Query(None),
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    季节性分解
    - 如果有 model_id 且 model_type=prophet，使用模型分解
    - 否则使用 statsmodels 加法分解
    """
    request_id = get_request_id() or str(uuid.uuid4())
    set_request_context(request_id, str(current_user), module="forecast")
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "decompose",
        "module": "forecast"
    }))

    dataset = db.query(ForecastDataset).filter(
        ForecastDataset.id == dataset_id,
        ForecastDataset.user_id == current_user,
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"数据集 {dataset_id} 不存在")

    df = pd.read_json(dataset.data_blob, orient="records")
    df.columns = [dataset.timestamp_col, dataset.value_col]
    df[dataset.timestamp_col] = pd.to_datetime(df[dataset.timestamp_col], errors="coerce")
    df = df.dropna()

    freq: str = dataset.detected_freq or dataset.freq

    if model_type == "prophet" and model_id:
        model_rec = db.query(ForecastModelBinary).filter(
            ForecastModelBinary.id == model_id,
            ForecastModelBinary.user_id == current_user,
        ).first()
        if not model_rec:
            raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在")
        trained = _deserialize_model(model_rec.model_blob)
        result: DecomposeResult = decompose_prophet(trained, df, dataset.timestamp_col, dataset.value_col)
    elif model_type == "arima":
        result = decompose_arima(df, dataset.timestamp_col, dataset.value_col, freq)
    else:
        result = decompose_lightgbm(df, dataset.timestamp_col, dataset.value_col, freq)

    return DecomposeResponse(
        model_type=model_type,
        timestamps=result.timestamps,
        trend=result.trend,
        seasonal=result.seasonal,
        residual=result.residual,
        yearly=result.yearly,
        weekly=result.weekly,
        holidays=result.holidays,
    )


def _run_cv_task(
    task_id: str,
    model_id: int,
    initial_days: int,
    horizon: int,
    period: int,
    current_user: int,
):
    """后台交叉验证任务"""
    db = SessionLocal()
    try:
        task = db.query(ForecastTask).filter(ForecastTask.task_id == task_id).first()
        if not task:
            return
        task.status = "running"
        db.commit()

        # 加载模型和数据
        model_rec = db.query(ForecastModelBinary).filter(
            ForecastModelBinary.id == model_id,
            ForecastModelBinary.user_id == current_user,
        ).first()
        if not model_rec:
            task.status = "failed"
            task.error_message = "模型不存在"
            db.commit()
            return

        dataset = db.query(ForecastDataset).filter(
            ForecastDataset.id == model_rec.dataset_id,
        ).first()
        df = pd.read_json(dataset.data_blob, orient="records")
        df.columns = [dataset.timestamp_col, dataset.value_col]
        df[dataset.timestamp_col] = pd.to_datetime(df[dataset.timestamp_col], errors="coerce")
        df = df.dropna().reset_index(drop=True)

        model = _deserialize_model(model_rec.model_blob)
        model_type = model_rec.model_type

        _append_log(task, f"开始交叉验证: {model_type}, initial={initial_days}, horizon={horizon}, period={period}", db)

        # 进度回调
        def progress_cb(fold, total, metrics):
            progress = fold / total if total > 0 else 0.0
            task.progress = progress
            task.current_phase = f"Fold {fold}/{total}"
            _append_log(
                task,
                f"Fold {fold}: MAE={metrics.mae:.4f}, RMSE={metrics.rmse:.4f}, MAPE={metrics.mape:.2f}%",
                db,
            )

        if model_type == "prophet":
            def cv_train_fn(tdf):
                m, _ = ForecastEngine.train("prophet", tdf,
                    target_col=dataset.value_col, timestamp_col=dataset.timestamp_col,
                    value_col=dataset.value_col,
                    changepoint_prior_scale=model_rec.params.get("changepoint_prior_scale", 0.05),
                    seasonality_mode=model_rec.params.get("seasonality_mode", "additive"),
                    growth=model_rec.params.get("growth", "linear"),
                )
                return m
            def cv_pred_fn(m, steps):
                r = ForecastEngine.predict("prophet", m, None, steps=steps,
                    freq=dataset.detected_freq or "daily",
                    confidence=0.95, freq_str=infer_freq_str(dataset.freq))
                return r.yhat

        elif model_type == "arima":
            def cv_train_fn(tdf):
                m, _ = ForecastEngine.train("arima", tdf,
                    target_col=dataset.value_col, timestamp_col=dataset.timestamp_col,
                    value_col=dataset.value_col,
                    auto=model_rec.params.get("auto_arima", True),
                    p=model_rec.params.get("p"),
                    d=model_rec.params.get("d"),
                    q=model_rec.params.get("q"),
                )
                return m
            def cv_pred_fn(m, steps):
                r = ForecastEngine.predict("arima", m, None, steps, confidence=0.95)
                return r.yhat
        else:
            def cv_train_fn(tdf):
                m, _ = ForecastEngine.train("lightgbm", tdf,
                    target_col=dataset.value_col, timestamp_col=dataset.timestamp_col,
                    value_col=dataset.value_col,
                    lags=model_rec.params.get("lags"),
                    rolling_windows=model_rec.params.get("rolling_windows"),
                )
                return m
            def cv_pred_fn(m, steps):
                r = ForecastEngine.predict("lightgbm", m, None, steps, confidence=0.95)
                return r.yhat

        cv_result: CrossValResult = cross_validate(
            model_type=model_type,
            df=df,
            timestamp_col=dataset.timestamp_col,
            value_col=dataset.value_col,
            model_train_fn=cv_train_fn,
            model_predict_fn=cv_pred_fn,
            model_id=model_id,
            initial_days=initial_days,
            horizon=horizon,
            period=period,
            freq=infer_freq_str(dataset.freq),
            progress_callback=progress_cb,
        )

        task.status = "completed"
        task.progress = 1.0
        task.current_phase = "完成"
        task.result_blob = json.dumps({
            "model_type": cv_result.model_type,
            "model_id": cv_result.model_id,
            "initial_days": cv_result.initial_days,
            "horizon": cv_result.horizon,
            "period": cv_result.period,
            "folds": [
                {
                    "fold": f.fold,
                    "train_start": f.train_start,
                    "train_end": f.train_end,
                    "test_start": f.test_start,
                    "test_end": f.test_end,
                    "n_train": f.n_train,
                    "n_test": f.n_test,
                    "mae": f.mae,
                    "rmse": f.rmse,
                    "mape": f.mape,
                }
                for f in cv_result.folds
            ],
            "mae_mean": cv_result.mae_mean,
            "mae_std": cv_result.mae_std,
            "rmse_mean": cv_result.rmse_mean,
            "rmse_std": cv_result.rmse_std,
            "mape_mean": cv_result.mape_mean,
            "mape_std": cv_result.mape_std,
            "total_time_seconds": cv_result.total_time_seconds,
        })
        _append_log(task, f"交叉验证完成: MAE均值={cv_result.mae_mean:.4f}, RMSE均值={cv_result.rmse_mean:.4f}", db)
        db.commit()

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        db.commit()
    finally:
        db.close()


@router.get("/cross-validate", response_model=CrossValResponse)
async def start_cross_validate(
    req: CrossValRequest,
    background_tasks: BackgroundTasks,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    启动时序交叉验证（异步）
    """
    request_id = get_request_id() or str(uuid.uuid4())
    set_request_context(request_id, str(current_user), module="forecast")
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "cross_validate",
        "module": "forecast"
    }))

    # 验证模型存在
    model_rec = db.query(ForecastModelBinary).filter(
        ForecastModelBinary.id == req.model_id,
        ForecastModelBinary.user_id == current_user,
    ).first()
    if not model_rec:
        raise HTTPException(status_code=404, detail=f"模型 {req.model_id} 不存在")

    task_id = str(uuid.uuid4())
    task = ForecastTask(
        user_id=current_user,
        task_id=task_id,
        task_type="crossval",
        model_id=req.model_id,
        dataset_id=model_rec.dataset_id,
        status="pending",
        progress=0.0,
        current_phase="等待开始",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    background_tasks.add_task(
        _run_cv_task,
        task_id,
        req.model_id,
        req.initial_days,
        req.horizon,
        req.period,
        current_user,
    )

    return CrossValResponse(
        task_id=task_id,
        status="pending",
        model_type=model_rec.model_type,
        model_id=req.model_id,
        initial_days=req.initial_days,
        horizon=req.horizon,
        period=req.period,
        folds=[],
        mae_mean=0.0, mae_std=0.0,
        rmse_mean=0.0, rmse_std=0.0,
        mape_mean=0.0, mape_std=0.0,
        total_time_seconds=0.0,
    )


@router.get("/cross-validate/{task_id}/progress", response_model=CVProgressResponse)
async def get_cv_progress(
    task_id: str,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询交叉验证进度"""
    request_id = get_request_id() or str(uuid.uuid4())
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "cross_validate_progress",
        "module": "forecast"
    }))

    task = db.query(ForecastTask).filter(
        ForecastTask.task_id == task_id,
        ForecastTask.user_id == current_user,
        ForecastTask.task_type == "crossval",
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="交叉验证任务不存在")

    current_fold = 0
    current_metrics = None
    if task.result_blob:
        try:
            data = json.loads(task.result_blob)
            current_fold = len(data.get("folds", []))
            if data.get("folds") and len(data["folds"]) > 0:
                last = data["folds"][-1]
                current_metrics = FoldMetricsOut(**last)
        except Exception:
            pass

    return CVProgressResponse(
        task_id=task_id,
        status=task.status,
        progress=task.progress,
        current_fold=current_fold,
        current_metrics=current_metrics,
    )


@router.get("/cross-validate/{task_id}/result", response_model=CrossValResponse)
async def get_cv_result(
    task_id: str,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取交叉验证最终结果"""
    request_id = get_request_id() or str(uuid.uuid4())
    set_request_context(request_id, str(current_user), module="forecast")
    logger.info(json.dumps({
        "request_id": request_id,
        "user_id": str(current_user),
        "operation": "cross_validate_result",
        "module": "forecast"
    }))

    task = db.query(ForecastTask).filter(
        ForecastTask.task_id == task_id,
        ForecastTask.user_id == current_user,
        ForecastTask.task_type == "crossval",
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="交叉验证任务不存在")

    if task.status == "pending" or task.status == "running":
        raise HTTPException(status_code=202, detail="交叉验证尚未完成，请稍后查询")

    if task.status == "failed":
        raise HTTPException(status_code=500, detail=f"交叉验证失败: {task.error_message}")

    if not task.result_blob:
        raise HTTPException(status_code=500, detail="结果数据缺失")

    data = json.loads(task.result_blob)
    return CrossValResponse(**data)
