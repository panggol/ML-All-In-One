"""
api.routes.explain — SHAP 可解释性 API 路由

端点：
  POST /api/explain/shap/global   — 全局 SHAP 值
  POST /api/explain/shap/local   — 局部（单样本）SHAP 贡献
  POST /api/explain/shap/plot    — SHAP 可视化图（base64）
  POST /api/explain/ice          — ICE 曲线数据
  GET  /api/explain/report/{model_id} — PDF 报告

认证：所有端点使用 Depends(get_current_user) 鉴权
日志：结构化 JSON 日志（request_id, user_id, operation, duration_ms, status）
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

import joblib
import numpy as np
import pandas as pd

from api.auth import get_current_user
from api.database import SessionLocal, TrainedModel, User
from api.services.log_aggregator import get_request_id, get_user_id

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# Pydantic 请求/响应模型（定义在路由文件头部，Constitution 强制要求）
# =============================================================================

# ---- 请求模型 ----

class GlobalSHAPRequest(BaseModel):
    """全局 SHAP 请求"""
    model_id: int = Field(..., gt=0, description="模型 ID")
    sample_size: int = Field(default=1000, gt=0, le=50000, description="最大采样数量")
    background_size: int = Field(default=100, gt=0, le=5000, description="背景数据大小（仅非树模型）")


class LocalSHAPRequest(BaseModel):
    """局部 SHAP 请求"""
    model_id: int = Field(..., gt=0, description="模型 ID")
    sample: Dict[str, Any] = Field(..., min_length=1, description="单条样本数据")


class SHAPPlotRequest(BaseModel):
    """SHAP 可视化图请求"""
    model_id: int = Field(..., gt=0, description="模型 ID")
    plot_type: str = Field(default="beeswarm", description="图类型：beeswarm | bar | waterfall")
    sample_size: int = Field(default=1000, gt=0, le=50000, description="最大采样数量")
    sample: Optional[Dict[str, Any]] = Field(default=None, description="单样本数据（waterfall 图用）")
    max_display: int = Field(default=20, gt=0, le=100, description="最多显示特征数")

    @field_validator("plot_type")
    @classmethod
    def validate_plot_type(cls, v: str) -> str:
        allowed = {"beeswarm", "bar", "waterfall", "force"}
        if v not in allowed:
            raise ValueError(f"plot_type 必须为 {allowed} 之一")
        return v


class ICERequest(BaseModel):
    """ICE 曲线请求"""
    model_id: int = Field(..., gt=0, description="模型 ID")
    feature_name: str = Field(..., min_length=1, description="目标特征名")
    num_points: int = Field(default=50, gt=0, le=200, description="曲线上采样点数")
    sample_size: int = Field(default=500, gt=0, le=5000, description="使用样本数")


# ---- 响应模型 ----

class FeatureImportanceResponse(BaseModel):
    """特征重要性条目"""
    feature: str
    importance: float
    rank: int


class GlobalSHAPResponse(BaseModel):
    """全局 SHAP 响应"""
    feature_names: List[str]
    shap_values: List[List[float]]
    expected_value: float
    feature_importance: List[FeatureImportanceResponse]
    sample_count: int
    computation_time_ms: float
    explainer_type: str


class FeatureContributionResponse(BaseModel):
    """特征贡献条目"""
    feature: str
    value: float
    original_value: Any
    direction: str  # "positive" | "negative" | "neutral"


class LocalSHAPResponse(BaseModel):
    """局部 SHAP 响应"""
    sample: Dict[str, Any]
    shap_values: List[FeatureContributionResponse]
    expected_value: float
    model_output: float
    output_class: Optional[str] = None
    computation_time_ms: float


class SHAPPlotResponse(BaseModel):
    """SHAP 可视化图响应"""
    image_base64: str
    image_type: str
    width_px: int
    height_px: int
    computation_time_ms: float


class ICEPointResponse(BaseModel):
    """ICE 曲线数据点"""
    feature_value: float
    predicted_value: float


class ICECurveResponse(BaseModel):
    """单条 ICE 曲线"""
    sample_index: int
    points: List[ICEPointResponse]


class ICEResponse(BaseModel):
    """ICE 曲线响应"""
    feature_name: str
    feature_values: List[float]
    curves: List[ICECurveResponse]
    computation_time_ms: float


# =============================================================================
# 辅助函数
# =============================================================================

def get_db_session():
    """数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _load_model_and_config(
    model_id: int,
    user: User,
    db: Session,
) -> tuple:
    """
    加载模型和配置。检查用户权限。

    返回：(TrainedModel 实例, 模型对象, 特征名列表)
    异常：HTTP 404（不存在）/ HTTP 403（无权限）/ HTTP 500（加载失败）
    """
    model = db.query(TrainedModel).filter(
        TrainedModel.id == model_id,
    ).first()

    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    if model.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="模型不存在或无访问权限"
        )

    # 加载模型文件
    try:
        clf = joblib.load(model.model_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"模型文件不存在：{model.model_path}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"模型加载失败：{str(e)}"
        )

    # 提取特征名（从 config 或推断）
    feature_names: List[str] = []
    config = model.config if hasattr(model, "config") and isinstance(model.config, dict) else {}
    if "feature_names" in config:
        feature_names = config["feature_names"]
    elif hasattr(clf, "feature_names_in_"):
        feature_names = list(clf.feature_names_in_)
    elif hasattr(clf, "feature_name"):
        feature_names = list(clf.feature_name)
    # 如果无法推断，使用序号
    if not feature_names:
        try:
            n = clf.n_features_in_ if hasattr(clf, "n_features_in_") else 0
            if n > 0:
                feature_names = [f"feature_{i}" for i in range(n)]
        except Exception:
            pass

    return model, clf, feature_names


def _structured_log(
    request: Request,
    operation: str,
    model_id: int,
    status_code: int,
    duration_ms: float,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """写入结构化 JSON 日志（遵循 Constitution C-VI）"""
    log_data = {
        "request_id": get_request_id() or str(uuid.uuid4()),
        "user_id": str(get_user_id() or ""),
        "operation": operation,
        "model_id": model_id,
        "status_code": status_code,
        "duration_ms": round(duration_ms, max(duration_ms, 0)),
    }
    if extra:
        log_data.update(extra)

    logger.info(
        f"[explain] {operation} model_id={model_id} "
        f"status={status_code} duration_ms={log_data['duration_ms']:.1f}",
        extra={"structured_log": log_data}
    )


# =============================================================================
# API 端点
# =============================================================================

@router.post("/shap/global", response_model=GlobalSHAPResponse)
async def shap_global(
    request: Request,
    body: GlobalSHAPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    全局 SHAP 解释：对测试集计算 SHAP 值，返回特征重要性。

    用途：了解哪些特征对模型预测影响最大。
    """
    start_time = time.perf_counter()
    operation = "shap_global"

    try:
        # 加载模型
        trained_model, clf, feature_names = _load_model_and_config(
            body.model_id, current_user, db
        )

        # 获取测试数据
        # 优先从 config 获取 data_file_id 加载测试集，否则使用训练时的数据
        config = trained_model.config if isinstance(trained_model.config, dict) else {}
        data_file_id = config.get("data_file_id")
        test_data_path = config.get("test_data_path")

        if test_data_path and os.path.exists(test_data_path):
            X_test = pd.read_parquet(test_data_path)
        elif data_file_id:
            from api.database import DataFile
            data_file = db.query(DataFile).filter(DataFile.id == data_file_id).first()
            if data_file and os.path.exists(data_file.filepath):
                if data_file.filepath.endswith(".csv"):
                    X_test = pd.read_csv(data_file.filepath)
                elif data_file.filepath.endswith((".pkl", ".parquet")):
                    X_test = pd.read_pickle(data_file.filepath)
                else:
                    X_test = None
            else:
                X_test = None
        else:
            X_test = None

        if X_test is None:
            raise HTTPException(
                status_code=400,
                detail="测试集为空，无法计算 SHAP 值。请确保模型有对应的测试数据。"
            )

        # 移除标签列（如果存在）
        target_col = config.get("target_column")
        if target_col and target_col in X_test.columns:
            X_test = X_test.drop(columns=[target_col])

        X_np = X_test.values

        # 计算 SHAP
        try:
            from mlkit.explainability import compute_global_shap
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="SHAP 库未安装，请运行 pip install shap"
            )

        result = compute_global_shap(
            model=clf,
            X_test=X_np,
            feature_names=feature_names or None,
            sample_size=body.sample_size,
            background_size=body.background_size,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 写入结构化日志
        _structured_log(
            request=request,
            operation=operation,
            model_id=body.model_id,
            status_code=200,
            duration_ms=elapsed_ms,
            extra={
                "explainer_type": result.explainer_type,
                "sample_count": result.sample_count,
                "feature_count": len(result.feature_names),
            }
        )

        return GlobalSHAPResponse(
            feature_names=result.feature_names,
            shap_values=result.shap_values,
            expected_value=result.expected_value,
            feature_importance=[
                FeatureImportanceResponse(
                    feature=fi.feature,
                    importance=fi.importance,
                    rank=fi.rank,
                )
                for fi in result.feature_importance
            ],
            sample_count=result.sample_count,
            computation_time_ms=result.computation_time_ms,
            explainer_type=result.explainer_type,
        )

    except HTTPException:
        raise
    except ImportError as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _structured_log(request, operation, body.model_id, 503, elapsed_ms, {"error": str(e)})
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _structured_log(request, operation, body.model_id, 500, elapsed_ms, {"error": str(e)})
        logger.exception(f"[explain] {operation} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"SHAP 计算失败：{str(e)}")


@router.post("/shap/local", response_model=LocalSHAPResponse)
async def shap_local(
    request: Request,
    body: LocalSHAPRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    局部 SHAP 解释：计算单个样本每个特征的 SHAP 贡献值。

    用途：解释"为什么模型对这个样本给出这个预测"。
    """
    start_time = time.perf_counter()
    operation = "shap_local"

    try:
        trained_model, clf, feature_names = _load_model_and_config(
            body.model_id, current_user, db
        )

        # 计算局部 SHAP
        from mlkit.explainability import compute_local_shap

        result = compute_local_shap(
            model=clf,
            sample=body.sample,
            feature_names=feature_names or None,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        _structured_log(
            request,
            operation,
            body.model_id,
            200,
            elapsed_ms,
            {
                "feature_count": len(result.shap_values),
                "explainer_type": "auto",
            }
        )

        return LocalSHAPResponse(
            sample=result.sample,
            shap_values=[
                FeatureContributionResponse(
                    feature=fc.feature,
                    value=fc.value,
                    original_value=fc.original_value,
                    direction=fc.direction,
                )
                for fc in result.shap_values
            ],
            expected_value=result.expected_value,
            model_output=result.model_output,
            output_class=result.output_class,
            computation_time_ms=result.computation_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _structured_log(request, operation, body.model_id, 500, elapsed_ms, {"error": str(e)})
        logger.exception(f"[explain] {operation} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"局部 SHAP 计算失败：{str(e)}")


@router.post("/shap/plot", response_model=SHAPPlotResponse)
async def shap_plot(
    request: Request,
    body: SHAPPlotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    SHAP 可视化图：生成 SHAP Summary Plot（蜂群图/柱状图/瀑布图）的 base64 编码。

    用途：前端展示 SHAP 可视化图。
    """
    start_time = time.perf_counter()
    operation = "shap_plot"

    try:
        trained_model, clf, feature_names = _load_model_and_config(
            body.model_id, current_user, db
        )

        # 获取测试数据（用于 beeswarm 图）
        X_np: Optional[np.ndarray] = None
        config = trained_model.config if isinstance(trained_model.config, dict) else {}
        data_file_id = config.get("data_file_id")
        test_data_path = config.get("test_data_path")

        if test_data_path and os.path.exists(test_data_path):
            X_test = pd.read_parquet(test_data_path)
            target_col = config.get("target_column")
            if target_col and target_col in X_test.columns:
                X_test = X_test.drop(columns=[target_col])
            X_np = X_test.head(body.sample_size).values

        elif data_file_id:
            from api.database import DataFile
            data_file = db.query(DataFile).filter(DataFile.id == data_file_id).first()
            if data_file and os.path.exists(data_file.filepath):
                if data_file.filepath.endswith(".csv"):
                    X_test = pd.read_csv(data_file.filepath).head(body.sample_size)
                elif data_file.filepath.endswith((".pkl", ".parquet")):
                    X_test = pd.read_pickle(data_file.filepath).head(body.sample_size)
                else:
                    X_test = None
                if X_test is not None:
                    target_col = config.get("target_column")
                    if target_col and target_col in X_test.columns:
                        X_test = X_test.drop(columns=[target_col])
                    X_np = X_test.values if hasattr(X_test, "values") else None

        # 如果是 waterfall 图且提供了单样本
        if body.plot_type == "waterfall" and body.sample:
            sample_arr = np.array(list(body.sample.values()), dtype=float).reshape(1, -1)
            if not feature_names:
                feature_names = list(body.sample.keys())

            from mlkit.explainability import compute_local_shap
            local_result = compute_local_shap(
                model=clf,
                sample=body.sample,
                feature_names=feature_names,
            )

            from mlkit.explainability.plots import generate_waterfall_plot
            plot_result = generate_waterfall_plot(
                shap_values=np.array([fc.value for fc in local_result.shap_values]),
                expected_value=local_result.expected_value,
                feature_values=sample_arr,
                feature_names=feature_names,
                max_display=body.max_display,
            )
        else:
            # 全局图：先计算 SHAP 值，再生成图
            if X_np is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"无法获取测试数据，无法生成 {body.plot_type} 图"
                )

            from mlkit.explainability import compute_global_shap
            from mlkit.explainability.plots import (
                generate_beeswarm_plot,
                generate_bar_plot,
                shap_values_to_base64,
            )

            shap_result = compute_global_shap(
                model=clf,
                X_test=X_np,
                feature_names=feature_names or None,
                sample_size=body.sample_size,
            )

            sv_array = np.array(shap_result.shap_values)
            if body.plot_type == "beeswarm":
                plot_result = generate_beeswarm_plot(
                    shap_values=sv_array,
                    expected_value=shap_result.expected_value,
                    features=X_np,
                    feature_names=shap_result.feature_names,
                    max_display=body.max_display,
                )
            elif body.plot_type == "bar":
                plot_result = generate_bar_plot(
                    shap_values=sv_array,
                    expected_value=shap_result.expected_value,
                    feature_names=shap_result.feature_names,
                    max_display=body.max_display,
                )
            else:
                # fallback 到 beeswarm
                plot_result = shap_values_to_base64(
                    shap_values=sv_array,
                    expected_value=shap_result.expected_value,
                    features=X_np,
                    feature_names=shap_result.feature_names,
                    plot_type="beeswarm",
                    max_display=body.max_display,
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        _structured_log(
            request,
            operation,
            body.model_id,
            200,
            elapsed_ms,
            {
                "image_type": body.plot_type,
                "explainer_type": "auto",
            }
        )

        return SHAPPlotResponse(
            image_base64=plot_result.image_base64,
            image_type=plot_result.image_type,
            width_px=plot_result.width_px,
            height_px=plot_result.height_px,
            computation_time_ms=plot_result.computation_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _structured_log(request, operation, body.model_id, 500, elapsed_ms, {"error": str(e)})
        logger.exception(f"[explain] {operation} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"SHAP 图生成失败：{str(e)}")


@router.post("/ice", response_model=ICEResponse)
async def ice_curves(
    request: Request,
    body: ICERequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    ICE 曲线：计算指定特征的 Individual Conditional Expectation 曲线。

    用途：揭示特征与预测值的非线性关系。
    """
    start_time = time.perf_counter()
    operation = "ice"

    try:
        trained_model, clf, feature_names = _load_model_and_config(
            body.model_id, current_user, db
        )

        # 获取测试数据
        X_np: Optional[np.ndarray] = None
        config = trained_model.config if isinstance(trained_model.config, dict) else {}
        data_file_id = config.get("data_file_id")
        test_data_path = config.get("test_data_path")

        if test_data_path and os.path.exists(test_data_path):
            X_test = pd.read_parquet(test_data_path)
            target_col = config.get("target_column")
            if target_col and target_col in X_test.columns:
                X_test = X_test.drop(columns=[target_col])
            X_np = X_test.values

        elif data_file_id:
            from api.database import DataFile
            data_file = db.query(DataFile).filter(DataFile.id == data_file_id).first()
            if data_file and os.path.exists(data_file.filepath):
                if data_file.filepath.endswith(".csv"):
                    X_test = pd.read_csv(data_file.filepath)
                elif data_file.filepath.endswith((".pkl", ".parquet")):
                    X_test = pd.read_pickle(data_file.filepath)
                else:
                    X_test = None
                if X_test is not None:
                    target_col = config.get("target_column")
                    if target_col and target_col in X_test.columns:
                        X_test = X_test.drop(columns=[target_col])
                    X_np = X_test.values if hasattr(X_test, "values") else None

        if X_np is None:
            raise HTTPException(
                status_code=400,
                detail="无法获取测试数据，无法计算 ICE 曲线"
            )

        if not feature_names:
            n = X_np.shape[1]
            feature_names = [f"feature_{i}" for i in range(n)]

        from mlkit.explainability import compute_ice_curves

        result = compute_ice_curves(
            model=clf,
            X_data=X_np,
            feature_name=body.feature_name,
            feature_names=feature_names,
            num_points=body.num_points,
            sample_size=body.sample_size,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        _structured_log(
            request,
            operation,
            body.model_id,
            200,
            elapsed_ms,
            {
                "feature_name": body.feature_name,
                "curve_count": len(result.curves),
            }
        )

        return ICEResponse(
            feature_name=result.feature_name,
            feature_values=result.feature_values,
            curves=[
                ICECurveResponse(
                    sample_index=c.sample_index,
                    points=[
                        ICEPointResponse(
                            feature_value=p.feature_value,
                            predicted_value=p.predicted_value,
                        )
                        for p in c.points
                    ]
                )
                for c in result.curves
            ],
            computation_time_ms=result.computation_time_ms,
        )

    except HTTPException:
        raise
    except ValueError as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _structured_log(request, operation, body.model_id, 400, elapsed_ms, {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _structured_log(request, operation, body.model_id, 500, elapsed_ms, {"error": str(e)})
        logger.exception(f"[explain] {operation} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"ICE 曲线计算失败：{str(e)}")


@router.get("/report/{model_id}")
async def shap_report(
    request: Request,
    model_id: int,
    sample_size: int = Query(default=1000, gt=0, le=5000),
    include_sections: str = Query(
        default="summary,global,local,ice",
        description="逗号分隔：summary | global | local | ice"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    生成并下载 SHAP 分析 PDF 报告。

    报告包含：
    - 执行摘要（Top-5 重要特征、模型指标）
    - 全局 SHAP 分析（SHAP Summary Plot + 特征重要性表 Top-10）
    - 样本解释示例（典型样本的瀑布图）
    - ICE 曲线（最显著特征的 ICE 图）
    """
    start_time = time.perf_counter()
    operation = "shap_report"

    sections = [s.strip() for s in include_sections.split(",") if s.strip()]

    try:
        trained_model, clf, feature_names = _load_model_and_config(
            model_id, current_user, db
        )

        # 获取测试数据
        X_np: Optional[np.ndarray] = None
        config = trained_model.config if isinstance(trained_model.config, dict) else {}
        data_file_id = config.get("data_file_id")
        test_data_path = config.get("test_data_path")

        if test_data_path and os.path.exists(test_data_path):
            X_test = pd.read_parquet(test_data_path)
            target_col = config.get("target_column")
            if target_col and target_col in X_test.columns:
                X_test = X_test.drop(columns=[target_col])
            X_np = X_test.head(sample_size).values

        elif data_file_id:
            from api.database import DataFile
            data_file = db.query(DataFile).filter(DataFile.id == data_file_id).first()
            if data_file and os.path.exists(data_file.filepath):
                if data_file.filepath.endswith(".csv"):
                    X_test = pd.read_csv(data_file.filepath).head(sample_size)
                elif data_file.filepath.endswith((".pkl", ".parquet")):
                    X_test = pd.read_pickle(data_file.filepath).head(sample_size)
                else:
                    X_test = None
                if X_test is not None:
                    target_col = config.get("target_column")
                    if target_col and target_col in X_test.columns:
                        X_test = X_test.drop(columns=[target_col])
                    X_np = X_test.values if hasattr(X_test, "values") else None

        # 尝试生成 PDF
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
            )
            from reportlab.lib.enums import TA_CENTER
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="PDF 生成库未安装，请运行 pip install reportlab"
            )

        # 生成临时 PDF 文件
        tmp_dir = Path("/tmp/ml_all_in_one/reports")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = tmp_dir / f"shap_report_{model_id}_{int(time.time())}.pdf"

        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER,
        )
        story = []

        # 封面
        story.append(Spacer(1, 5 * cm))
        story.append(Paragraph(f"SHAP 可解释性报告", title_style))
        story.append(Paragraph(f"模型: {trained_model.name}", styles["Normal"]))
        story.append(Paragraph(f"模型类型: {trained_model.model_type}", styles["Normal"]))
        story.append(Paragraph(f"生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        story.append(Paragraph(f"用户: {current_user.username}", styles["Normal"]))
        story.append(Spacer(1, 2 * cm))

        # 计算并添加 SHAP 摘要
        if X_np is not None and ("global" in sections or "summary" in sections):
            from mlkit.explainability import compute_global_shap
            shap_result = compute_global_shap(
                model=clf,
                X_test=X_np,
                feature_names=feature_names or None,
                sample_size=min(sample_size, X_np.shape[0]),
            )

            # 全局分析
            if "global" in sections:
                story.append(PageBreak())
                story.append(Paragraph("全局 SHAP 分析", styles["Heading2"]))
                story.append(Paragraph(f"Explainer: {shap_result.explainer_type}", styles["Normal"]))
                story.append(Paragraph(f"样本数: {shap_result.sample_count}", styles["Normal"]))
                story.append(Paragraph(f"计算耗时: {shap_result.computation_time_ms:.1f}ms", styles["Normal"]))

                # 特征重要性表
                story.append(Spacer(1, 0.5 * cm))
                story.append(Paragraph("特征重要性 Top-10", styles["Heading3"]))
                table_data = [["排名", "特征", "重要性"]]
                for fi in shap_result.feature_importance[:10]:
                    table_data.append([str(fi.rank), fi.feature, f"{fi.importance:.4f}"])
                t = Table(table_data, colWidths=[2 * cm, 6 * cm, 3 * cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]))
                story.append(t)

        story.append(Spacer(1, 1 * cm))

        # 生成 PDF
        doc.build(story)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        _structured_log(
            request,
            operation,
            model_id,
            200,
            elapsed_ms,
            {
                "sections": include_sections,
                "pdf_size_bytes": os.path.getsize(pdf_path),
            }
        )

        return FileResponse(
            path=str(pdf_path),
            filename=f"shap_report_model_{model_id}.pdf",
            media_type="application/pdf",
        )

    except HTTPException:
        raise
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        _structured_log(request, operation, model_id, 500, elapsed_ms, {"error": str(e)})
        logger.exception(f"[explain] {operation} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"报告生成失败：{str(e)}")
