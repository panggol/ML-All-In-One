"""
季节性分解模块
Library-First: Prophet / ARIMA / STL 分解实现
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from src.mlkit.forecast.detector import FrequencyType, infer_period_for_seasonality


@dataclass
class DecomposeResult:
    """分解结果"""
    timestamps: list[str]
    trend: list[float]
    seasonal: list[float]
    residual: list[float] | None
    yearly: list[float] | None = None
    weekly: list[float] | None = None
    holidays: list[float] | None = None


def decompose_prophet(
    model,
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    target_col: str = "value",
) -> DecomposeResult:
    """
    Prophet 分解：提取 trend / yearly / weekly / holidays 分量

    参数
    ----
    model        : Prophet 已训练模型
    df           : 原始 DataFrame（训练数据）
    timestamp_col: 时间戳列名
    target_col   : 目标值列名

    返回
    ----
    DecomposeResult
    """
    from prophet import Prophet

    prophet_df = df[[timestamp_col, target_col]].copy()
    prophet_df.columns = ["ds", "y"]
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"], errors="coerce")
    prophet_df = prophet_df.dropna()

    # Prophet 内置 decomposition
    m: Prophet = model
    # 用模型预测（包含各分量）
    future = m.make_future_dataframe(periods=0)
    forecast = m.predict(future)

    n = min(len(forecast), len(df))

    return DecomposeResult(
        timestamps=[str(ts) for ts in forecast["ds"].iloc[:n]],
        trend=[round(float(v), 4) for v in forecast["trend"].iloc[:n]],
        seasonal=[round(float(v), 4) for v in forecast["yearly"].iloc[:n]],
        residual=None,
        yearly=[round(float(v), 4) for v in forecast["yearly"].iloc[:n]] if "yearly" in forecast.columns else None,
        weekly=[round(float(v), 4) for v in forecast["weekly"].iloc[:n]] if "weekly" in forecast.columns else None,
        holidays=[round(float(v), 4) for v in forecast["holidays"].iloc[:n]] if "holidays" in forecast.columns else None,
    )


def decompose_arima(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    target_col: str = "value",
    freq: FrequencyType = "daily",
) -> DecomposeResult:
    """
    ARIMA / STL 分解：trend + seasonal + residual

    使用 statsmodels.tsa.seasonal_decompose（加法/乘法模型）
    """
    from statsmodels.tsa.seasonal import seasonal_decompose

    ts_df = df[[timestamp_col, target_col]].copy()
    ts_df.columns = ["timestamp", "y"]
    ts_df["timestamp"] = pd.to_datetime(ts_df["timestamp"], errors="coerce")
    ts_df = ts_df.dropna().set_index("timestamp").sort_index()

    if len(ts_df) < 2 * 7:  # 至少 2 个完整周期
        raise ValueError(f"数据量 {len(ts_df)} 不足进行季节性分解（需要至少 2 个完整周期）")

    period = infer_period_for_seasonality(freq)

    # 自动调整 period 确保合理
    if period > len(ts_df) // 2:
        period = min(7, len(ts_df) // 2)  # fallback 到周季节性

    try:
        result = seasonal_decompose(ts_df["y"], model="additive", period=period, extrapolate_trend="freq")
    except Exception:
        # fallback: 简单移动平均趋势
        trend = ts_df["y"].rolling(7, center=True, min_periods=1).mean()
        seasonal = ts_df["y"] - trend
        residual = ts_df["y"] - trend - seasonal
        return DecomposeResult(
            timestamps=[str(ts) for ts in ts_df.index],
            trend=[round(float(v), 4) for v in trend.values],
            seasonal=[round(float(v), 4) for v in seasonal.values],
            residual=[round(float(v), 4) for v in residual.values],
        )

    return DecomposeResult(
        timestamps=[str(ts) for ts in ts_df.index],
        trend=[round(float(v), 4) if not (v is None or (isinstance(v, float) and np.isnan(v))) else 0.0 for v in result.trend.values],
        seasonal=[round(float(v), 4) if not (v is None or (isinstance(v, float) and np.isnan(v))) else 0.0 for v in result.seasonal.values],
        residual=[round(float(v), 4) if v is not None and not (isinstance(v, float) and np.isnan(v)) else 0.0 for v in result.resid.values] if result.resid is not None else None,
    )


def decompose_lightgbm(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    target_col: str = "value",
    freq: FrequencyType = "daily",
) -> DecomposeResult:
    """
    LightGBM 本身不可解释，返回 Prophet 分解作为参考
    使用 statsmodels 加法分解
    """
    return decompose_arima(df, timestamp_col, target_col, freq)
