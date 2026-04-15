"""
时序交叉验证模块
Library-First: 时间序列滚动窗口交叉验证
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class FoldMetrics:
    """单轮验证的指标"""
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


@dataclass
class CrossValResult:
    """交叉验证汇总结果"""
    model_type: str
    model_id: int
    params: dict
    initial_days: int
    horizon: int
    period: int
    folds: list[FoldMetrics]
    mae_mean: float
    mae_std: float
    rmse_mean: float
    rmse_std: float
    mape_mean: float
    mape_std: float
    total_time_seconds: float


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float, float]:
    """计算 MAE / RMSE / MAPE"""
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    # MAPE（避免除零）
    mask = y_true != 0
    if mask.sum() > 0:
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
    else:
        mape = float(np.nan)

    return mae, rmse, mape


def _get_date_range(start: pd.Timestamp, end: pd.Timestamp, freq: str = "D") -> pd.DatetimeIndex:
    """生成日期范围（按指定频率）"""
    return pd.date_range(start=start, end=end, freq=freq)


def cross_validate(
    model_type: str,
    df: pd.DataFrame,
    timestamp_col: str,
    value_col: str,
    model_train_fn,
    model_predict_fn,
    model_id: int = 0,
    initial_days: int = 90,
    horizon: int = 30,
    period: int = 30,
    freq: str = "D",
    progress_callback=None,
) -> CrossValResult:
    """
    时序交叉验证主函数（滚动窗口，不打乱时间顺序）

    参数
    ----
    model_type         : str   模型类型
    df                 : DataFrame，含 timestamp_col 和 value_col
    timestamp_col      : str   时间戳列名
    value_col          : str   数值列名
    model_train_fn     : callable(df_train) -> trained_model   训练函数
    model_predict_fn    : callable(trained_model, steps) -> list[float]  预测函数
    model_id           : int   模型 ID
    initial_days       : int   初始训练集大小（天数）
    horizon            : int   测试窗口大小（天数）
    period             : int   滚动间隔（天数）
    freq               : str   数据频率（pandas freq string）
    progress_callback  : callable(fold, total, metrics) -> None  进度回调

    返回
    ----
    CrossValResult
    """
    start_time = time.time()

    ts_df = df[[timestamp_col, value_col]].copy()
    ts_df.columns = ["timestamp", "y"]
    ts_df["timestamp"] = pd.to_datetime(ts_df["timestamp"], errors="coerce")
    ts_df = ts_df.dropna().set_index("timestamp").sort_index()

    dates = ts_df.index
    n_total = len(dates)

    if n_total < initial_days + horizon:
        raise ValueError(
            f"数据量不足：总 {n_total} 天，需要至少 initial_days({initial_days}) + horizon({horizon}) = {initial_days + horizon} 天"
        )

    folds: list[FoldMetrics] = []
    fold_num = 0

    # 滚动窗口：初始窗口 [0, initial_days)，然后每次向后移动 period 天
    current_end = initial_days

    while current_end + horizon <= n_total:
        train_end_idx = current_end
        test_end_idx = current_end + horizon

        train_df = ts_df.iloc[:train_end_idx]
        test_df = ts_df.iloc[train_end_idx:test_end_idx]

        fold_num += 1

        try:
            # 训练
            trained = model_train_fn(train_df.reset_index())

            # 预测
            preds = model_predict_fn(trained, horizon)

            # 计算指标
            y_true = test_df["y"].values
            y_pred = np.array(preds[:len(y_true)], dtype=float)

            mae, rmse, mape = _compute_metrics(y_true, y_pred)

        except Exception as e:
            # 单个 fold 失败不影响其他 fold
            mae = rmse = mape = float("nan")

        fold_metrics = FoldMetrics(
            fold=fold_num,
            train_start=str(dates[0]),
            train_end=str(dates[train_end_idx - 1]),
            test_start=str(dates[train_end_idx]),
            test_end=str(dates[test_end_idx - 1]),
            n_train=len(train_df),
            n_test=len(test_df),
            mae=round(mae, 4),
            rmse=round(rmse, 4),
            mape=round(mape, 4) if not np.isnan(mape) else 0.0,
        )
        folds.append(fold_metrics)

        # 进度回调
        if progress_callback:
            progress_callback(fold_num, fold_num, fold_metrics)

        current_end += period

    if not folds:
        raise ValueError("没有生成有效的验证窗口，请检查 initial_days / horizon / period 参数")

    # 汇总统计
    mae_vals = [f.mae for f in folds if not np.isnan(f.mae)]
    rmse_vals = [f.rmse for f in folds if not np.isnan(f.rmse)]
    mape_vals = [f.mape for f in folds if not np.isnan(f.mape)]

    def _safe_mean(vals):
        return round(float(np.mean(vals)), 4) if vals else 0.0

    def _safe_std(vals):
        return round(float(np.std(vals)), 4) if len(vals) > 1 else 0.0

    total_time = time.time() - start_time

    return CrossValResult(
        model_type=model_type,
        model_id=model_id,
        params={"initial_days": initial_days, "horizon": horizon, "period": period},
        initial_days=initial_days,
        horizon=horizon,
        period=period,
        folds=folds,
        mae_mean=_safe_mean(mae_vals),
        mae_std=_safe_std(mae_vals),
        rmse_mean=_safe_mean(rmse_vals),
        rmse_std=_safe_std(rmse_vals),
        mape_mean=_safe_mean(mape_vals),
        mape_std=_safe_std(mape_vals),
        total_time_seconds=round(total_time, 2),
    )
