# -*- coding: utf-8 -*-
"""
预处理 API - 数据预处理流水线接口
"""
import os
import re
import pandas as pd
import numpy as np
from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))

from api.database import DataFile, User, SessionLocal, get_db
from api.auth import get_current_user
from api.services.log_aggregator import (
    set_request_context, get_request_id,
    log_preprocessing, log_error,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 预览行数限制
PREVIEW_ROWS = 1000

# ============ 安全工具函数 ============

def safe_filename(name: str) -> str:
    """
    过滤文件名中的危险字符，防止路径遍历攻击。
    - 过滤 .. 、 / 、 \\ 等路径分隔符
    - 只允许字母数字下划线连字符和点号
    - 限制最大长度为 200 字符
    """
    name = name.replace('..', '')
    name = re.sub(r'[\\/]', '_', name)
    name = re.sub(r'[^\w\-_.]', '_', name)
    return name[:200]


# 转换端点文件大小阈值（500MB）
TRANSFORM_MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


# ============ Pydantic 模型 ============

class ImputerConfig(BaseModel):
    enabled: bool = False
    strategy: Literal["mean", "median", "most_frequent", "constant"] = "mean"  # mean, median, most_frequent, constant


class ScalerConfig(BaseModel):
    enabled: bool = False
    type: Optional[str] = None  # minmax, standard


class FeatureSelectConfig(BaseModel):
    enabled: bool = False
    threshold: float = Field(0.0, ge=0.0)  # P2-3: 方差阈值不允许负数
    selected_columns: List[str] = []


class PreprocessingSteps(BaseModel):
    imputer: ImputerConfig = ImputerConfig()
    scaler: ScalerConfig = ScalerConfig()
    feature_select: FeatureSelectConfig = FeatureSelectConfig()


class PreviewRequest(BaseModel):
    data_file_id: int
    steps: PreprocessingSteps


class TransformRequest(BaseModel):
    data_file_id: int
    steps: PreprocessingSteps
    output_name: Optional[str] = None


class ColumnStats(BaseModel):
    column: str
    dtype: str
    # 原始统计
    original_mean: Optional[float] = None
    original_std: Optional[float] = None
    original_min: Optional[float] = None
    original_max: Optional[float] = None
    original_missing: int = 0
    # 处理后统计
    transformed_mean: Optional[float] = None
    transformed_std: Optional[float] = None
    transformed_min: Optional[float] = None
    transformed_max: Optional[float] = None
    transformed_missing: int = 0


class PreviewResponse(BaseModel):
    original_preview: List[List]
    transformed_preview: List[List]
    columns: List[str]
    stats: List[ColumnStats]
    shape: tuple


class TransformResponse(BaseModel):
    data_file_id: int
    filename: str
    rows: int
    columns: int


# ============ 后端预处理工具 ============

def _get_numeric_columns(df: pd.DataFrame) -> List[str]:
    """获取数值列"""
    return df.select_dtypes(include=[np.number]).columns.tolist()


def _apply_imputer(df: pd.DataFrame, config: ImputerConfig) -> pd.DataFrame:
    """应用缺失值填充"""
    if not config.enabled:
        return df
    
    df_copy = df.copy()
    numeric_cols = _get_numeric_columns(df_copy)
    
    for col in numeric_cols:
        if df_copy[col].isna().any():
            if config.strategy == "mean":
                df_copy[col] = df_copy[col].fillna(df_copy[col].mean())
            elif config.strategy == "median":
                df_copy[col] = df_copy[col].fillna(df_copy[col].median())
            elif config.strategy == "constant":
                df_copy[col] = df_copy[col].fillna(0)
    
    # 处理非数值列的众数填充
    non_numeric = df_copy.select_dtypes(exclude=[np.number]).columns
    for col in non_numeric:
        if df_copy[col].isna().any():
            if config.strategy == "most_frequent":
                mode_val = df_copy[col].mode()
                if len(mode_val) > 0:
                    df_copy[col] = df_copy[col].fillna(mode_val[0])
            elif config.strategy == "constant":
                df_copy[col] = df_copy[col].fillna("missing")
    
    return df_copy


def _apply_scaler(df: pd.DataFrame, config: ScalerConfig) -> pd.DataFrame:
    """应用缩放器"""
    if not config.enabled or not config.type:
        return df
    
    df_copy = df.copy()
    numeric_cols = _get_numeric_columns(df_copy)
    
    if len(numeric_cols) == 0:
        return df_copy
    
    data = df_copy[numeric_cols].values
    
    if config.type == "minmax":
        col_min = np.nanmin(data, axis=0)
        col_max = np.nanmax(data, axis=0)
        scale = col_max - col_min
        scale[scale == 0] = 1.0
        scaled = (data - col_min) / scale
        for i, col in enumerate(numeric_cols):
            df_copy[col] = scaled[:, i]
    
    elif config.type == "standard":
        col_mean = np.nanmean(data, axis=0)
        col_std = np.nanstd(data, axis=0)
        col_std[col_std == 0] = 1.0
        scaled = (data - col_mean) / col_std
        for i, col in enumerate(numeric_cols):
            df_copy[col] = scaled[:, i]
    
    return df_copy


def _apply_feature_select(df: pd.DataFrame, config: FeatureSelectConfig) -> pd.DataFrame:
    """应用特征选择"""
    if not config.enabled:
        return df
    
    # 如果指定了列，只保留这些列
    if config.selected_columns:
        # 只保留指定的列（且这些列在 df 中存在）
        available_cols = [c for c in config.selected_columns if c in df.columns]
        return df[available_cols]
    
    # 否则按方差阈值过滤数值列
    numeric_cols = _get_numeric_columns(df)
    if len(numeric_cols) == 0:
        return df
    
    variances = df[numeric_cols].var()
    selected = variances[variances > config.threshold].index.tolist()
    
    # 保留非数值列 + 通过阈值的数值列
    non_numeric = df.select_dtypes(exclude=[np.number]).columns.tolist()
    kept = non_numeric + selected
    
    return df[kept]


def _compute_stats(df_original: pd.DataFrame, df_transformed: pd.DataFrame) -> List[ColumnStats]:
    """计算列统计信息"""
    stats = []
    
    all_cols = list(df_transformed.columns)
    
    for col in all_cols:
        orig_col = df_original.get(col, None)
        trans_col = df_transformed[col]
        
        stat = ColumnStats(
            column=col,
            dtype=str(trans_col.dtype),
        )
        
        # 原始统计
        if orig_col is not None and pd.api.types.is_numeric_dtype(orig_col):
            stat.original_mean = float(orig_col.mean()) if not orig_col.isna().all() else None
            stat.original_std = float(orig_col.std()) if not orig_col.isna().all() else None
            stat.original_min = float(orig_col.min()) if not orig_col.isna().all() else None
            stat.original_max = float(orig_col.max()) if not orig_col.isna().all() else None
        stat.original_missing = int(orig_col.isna().sum()) if orig_col is not None else 0
        
        # 转换后统计
        if pd.api.types.is_numeric_dtype(trans_col):
            stat.transformed_mean = float(trans_col.mean()) if not trans_col.isna().all() else None
            stat.transformed_std = float(trans_col.std()) if not trans_col.isna().all() else None
            stat.transformed_min = float(trans_col.min()) if not trans_col.isna().all() else None
            stat.transformed_max = float(trans_col.max()) if not trans_col.isna().all() else None
        stat.transformed_missing = int(trans_col.isna().sum())
        
        stats.append(stat)
    
    return stats


# ============ API 路由 ============

@router.post("/preview", response_model=PreviewResponse)
async def preview_preprocessing(
    request: PreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """预览预处理效果（仅处理前 PREVIEW_ROWS 行，不保存）"""
    # 设置日志上下文
    set_request_context(get_request_id() or "", str(current_user.id), module="preprocessing")

    log_preprocessing(
        event="preview_start",
        data_file_id=request.data_file_id,
        user_id=str(current_user.id),
        detail={
            "imputer": request.steps.imputer.model_dump(),
            "scaler": request.steps.scaler.model_dump(),
            "feature_select": request.steps.feature_select.model_dump(),
        },
        level=logging.INFO,
    )

    # 获取数据文件
    data_file = db.query(DataFile).filter(
        DataFile.id == request.data_file_id,
        DataFile.user_id == current_user.id,
    ).first()

    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据文件不存在",
        )

    try:
        # 读取数据（限制行数用于预览）
        df = pd.read_csv(data_file.filepath, nrows=PREVIEW_ROWS + 1)
        if df.shape[0] > PREVIEW_ROWS:
            df = df.head(PREVIEW_ROWS)
    except Exception as e:
        log_preprocessing(
            event="preview_error",
            data_file_id=request.data_file_id,
            user_id=str(current_user.id),
            detail={"error": str(e), "error_type": type(e).__name__},
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"读取文件失败: {str(e)}",
        )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数据集为空",
        )

    # 保存原始数据用于对比
    df_original = df.copy()

    # 按顺序应用预处理步骤
    df_transformed = df.copy()

    # 1. 缺失值填充
    df_transformed = _apply_imputer(df_transformed, request.steps.imputer)

    # 2. 缩放（归一化/标准化）
    df_transformed = _apply_scaler(df_transformed, request.steps.scaler)

    # 3. 特征选择
    df_transformed = _apply_feature_select(df_transformed, request.steps.feature_select)

    # 转换数据为列表格式（处理特殊类型）
    def to_serializable(val):
        if pd.isna(val):
            return None
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
        if isinstance(val, (np.ndarray,)):
            return val.tolist()
        return val

    original_preview = [
        [to_serializable(v) for v in row]
        for row in df_original.head(10).values
    ]

    transformed_preview = [
        [to_serializable(v) for v in row]
        for row in df_transformed.head(10).values
    ]

    # 计算统计信息
    stats = _compute_stats(df_original, df_transformed)

    log_preprocessing(
        event="preview_complete",
        data_file_id=request.data_file_id,
        user_id=str(current_user.id),
        detail={
            "original_rows": PREVIEW_ROWS,
            "transformed_columns": len(df_transformed.columns),
            "steps_applied": "imputer, scaler, feature_select",
        },
        level=logging.INFO,
    )

    return PreviewResponse(
        original_preview=original_preview,
        transformed_preview=transformed_preview,
        columns=list(df_transformed.columns),
        stats=stats,
        shape=(len(df_transformed), len(df_transformed.columns)),
    )


@router.post("/transform", response_model=TransformResponse)
async def transform_and_save(
    request: TransformRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """应用预处理并保存为新数据集"""
    # 设置日志上下文
    set_request_context(get_request_id() or "", str(current_user.id), module="preprocessing")

    log_preprocessing(
        event="transform_start",
        data_file_id=request.data_file_id,
        user_id=str(current_user.id),
        detail={
            "imputer": request.steps.imputer.model_dump(),
            "scaler": request.steps.scaler.model_dump(),
            "feature_select": request.steps.feature_select.model_dump(),
            "output_name": request.output_name,
        },
        level=logging.INFO,
    )

    # 获取数据文件
    data_file = db.query(DataFile).filter(
        DataFile.id == request.data_file_id,
        DataFile.user_id == current_user.id,
    ).first()

    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据文件不存在",
        )

    try:
        df = pd.read_csv(data_file.filepath)
    except Exception as e:
        log_preprocessing(
            event="transform_error",
            data_file_id=request.data_file_id,
            user_id=str(current_user.id),
            detail={"error": str(e), "error_type": type(e).__name__},
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"读取文件失败: {str(e)}",
        )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数据集为空",
        )

    # 应用预处理
    df_transformed = df.copy()
    df_transformed = _apply_imputer(df_transformed, request.steps.imputer)
    df_transformed = _apply_scaler(df_transformed, request.steps.scaler)
    df_transformed = _apply_feature_select(df_transformed, request.steps.feature_select)

    # P1-2: 文件大小检查，防止 GB 级 CSV 导致 OOM
    file_size = os.path.getsize(data_file.filepath)
    if file_size > TRANSFORM_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过大小限制 ({TRANSFORM_MAX_FILE_SIZE // 1024 // 1024}MB)",
        )

    # P0: 安全过滤 output_name，防止路径遍历
    base_name = os.path.splitext(data_file.filename)[0]
    safe_name = safe_filename(request.output_name or f"{base_name}_preprocessed")
    output_filename = f"{safe_name}.csv"

    # 保存目录
    save_dir = os.path.join(os.path.dirname(data_file.filepath), "preprocessed")
    os.makedirs(save_dir, exist_ok=True)

    output_path = os.path.join(save_dir, output_filename)
    df_transformed.to_csv(output_path, index=False)

    # 在数据库中注册新文件
    new_data_file = DataFile(
        user_id=current_user.id,
        filename=output_filename,
        filepath=output_path,
        size=os.path.getsize(output_path),
        rows=len(df_transformed),
        columns=list(df_transformed.columns),
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_data_file)
    db.commit()
    db.refresh(new_data_file)

    log_preprocessing(
        event="transform_complete",
        data_file_id=new_data_file.id,
        user_id=str(current_user.id),
        detail={
            "input_file_id": request.data_file_id,
            "output_filename": output_filename,
            "rows": len(df_transformed),
            "columns": len(df_transformed.columns),
        },
        level=logging.INFO,
    )

    return TransformResponse(
        data_file_id=new_data_file.id,
        filename=output_filename,
        rows=len(df_transformed),
        columns=len(df_transformed.columns),
    )
