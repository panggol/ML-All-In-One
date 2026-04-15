"""
PSI (Population Stability Index) 计算引擎
Library-First: 可独立测试的纯函数
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

# histogram 分箱辅助


def _to_array(data) -> np.ndarray:
    """统一转换为 numpy array，过滤 NaN"""
    if isinstance(data, pd.Series):
        arr = data.dropna().values
    elif isinstance(data, np.ndarray):
        arr = np.asarray(data).flatten()
        arr = arr[~np.isnan(arr)]
    else:
        arr = np.asarray(data).flatten()
        arr = arr[~np.isnan(arr.astype(float))]
    return arr


def compute_psi(
    reference: np.ndarray,
    current: np.ndarray,
    n_bins: int = 10,
    binning: str = "quantile",
) -> float:
    """
    计算 PSI（Population Stability Index）

    PSI = Σ [(Current% - Reference%) * ln(Current% / Reference%)]

    等频分箱（quantile）：与 Evidently AI 一致
    等宽分箱（uniform）：传统方法

    参数
    ----
    reference : array-like 基准数据（训练数据）
    current  : array-like 当前数据
    n_bins   : int 分箱数，默认 10
    binning  : str "quantile"（等频）或 "uniform"（等宽）

    返回
    ----
    float: PSI 值
           - 相同分布 → 0
           - 完全偏移 → 大（无上限）
           - 无法计算 → NaN（如全常数）

    算法
    ----
    1. 用 reference 构建分箱边界
    2. 分别计算 reference 和 current 在各箱中的占比
    3. 避免 0 占比：用 min(epsilon, 1/n_bins) 替换
    4. 计算 PSI 求和
    """
    ref_arr = _to_array(reference)
    cur_arr = _to_array(current)

    # 样本量检查
    if len(ref_arr) < 2 or len(cur_arr) < 2:
        return float("nan")

    # 全常数检查
    ref_std = np.std(ref_arr)
    if ref_std == 0:
        return float("nan")

    EPS = 1e-10  # 避免 log(0)

    if binning == "quantile":
        # 等频分箱：用 reference 的分位数确定边界
        try:
            # 用 numpy percentile 做等频分箱
            quantiles = np.linspace(0, 1, n_bins + 1)
            bin_edges = np.quantile(ref_arr, quantiles)
            # 确保边界唯一
            bin_edges = np.unique(bin_edges)
            if len(bin_edges) < 2:
                return float("nan")
        except Exception:
            return float("nan")
    else:
        # 等宽分箱
        min_val = min(np.min(ref_arr), np.min(cur_arr))
        max_val = max(np.max(ref_arr), np.max(cur_arr))
        if min_val == max_val:
            return float("nan")
        bin_edges = np.linspace(min_val, max_val, n_bins + 1)

    # 计算各箱占比
    ref_counts = np.histogram(ref_arr, bins=bin_edges)[0]
    cur_counts = np.histogram(cur_arr, bins=bin_edges)[0]

    # 转百分比（加 EPS 防止 0）
    ref_pct = (ref_counts + EPS) / (ref_counts.sum() + EPS * len(ref_counts))
    cur_pct = (cur_counts + EPS) / (cur_counts.sum() + EPS * len(cur_counts))

    # PSI 公式
    psi_values = (cur_pct - ref_pct) * np.log(cur_pct / ref_pct)
    psi = float(np.sum(psi_values))

    # 数值稳定性：负数极小值截断
    if psi < -0.1:
        psi = 0.0

    return round(psi, 6)


def compute_psi_batch(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    n_bins: int = 10,
    binning: str = "quantile",
) -> dict[str, float]:
    """
    批量计算多个特征的 PSI

    参数
    ----
    reference_df : DataFrame 基准数据
    current_df  : DataFrame 当前数据
    n_bins     : int 分箱数
    binning    : str 分箱策略

    返回
    ----
    dict[str, float]: {特征名: psi_value}
    """
    results: dict[str, float] = {}
    for col in reference_df.columns:
        if col not in current_df.columns:
            results[col] = float("nan")
            continue
        psi = compute_psi(
            reference_df[col].values,
            current_df[col].values,
            n_bins=n_bins,
            binning=binning,
        )
        results[col] = psi
    return results


def get_psi_level(psi: float) -> str:
    """
    根据 PSI 值返回漂移等级

    等级划分（与需求文档一致）：
    - none:     PSI < 0.1
    - mild:     0.1 ≤ PSI < 0.2
    - moderate: 0.2 ≤ PSI < 0.25
    - severe:   PSI ≥ 0.25
    """
    if math.isnan(psi):
        return "undefined"
    if psi < 0.1:
        return "none"
    elif psi <= 0.2:   # 0.1 ≤ PSI ≤ 0.2 → mild（包含 0.2）
        return "mild"
    elif psi <= 0.25:  # 0.2 < PSI ≤ 0.25 → moderate
        return "moderate"
    else:
        return "severe"


def compute_overall_psi(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    n_bins: int = 10,
) -> float:
    """
    计算整体 PSI（所有特征 PSI 的均值加权）
    """
    psi_features = compute_psi_batch(reference_df, current_df, n_bins=n_bins)
    valid_psis = [v for v in psi_features.values() if not math.isnan(v)]
    if not valid_psis:
        return float("nan")
    return round(float(np.mean(valid_psis)), 6)
