"""
KS（Kolmogorov-Smirnov）检验引擎
Library-First: 可独立测试的纯函数
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd
from scipy.stats import kstest


class KSResult(NamedTuple):
    """KS 检验结果"""
    stat: float      # KS 统计量 [0, 1]
    pvalue: float    # p 值 [0, 1]
    drifted: bool    # 是否漂移（p < 0.05）


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


def compute_ks(
    reference: np.ndarray,
    current: np.ndarray,
    alpha: float = 0.05,
) -> KSResult:
    """
    计算 KS 检验

    使用 scipy.stats.kstest，two-sided 检验：
    H0: reference 和 current 来自同一分布
    H1: 两者分布不同

    参数
    ----
    reference : array-like 基准数据
    current  : array-like 当前数据
    alpha    : float 显著性水平，默认 0.05

    返回
    ----
    KSResult: {stat, pvalue, drifted}
    """
    ref_arr = _to_array(reference)
    cur_arr = _to_array(current)

    if len(ref_arr) < 2 or len(cur_arr) < 2:
        return KSResult(stat=float("nan"), pvalue=float("nan"), drifted=False)

    # 全常数检查
    if np.std(ref_arr) == 0 and np.std(cur_arr) == 0:
        if np.mean(ref_arr) != np.mean(cur_arr):
            return KSResult(stat=1.0, pvalue=0.0, drifted=True)
        return KSResult(stat=0.0, pvalue=1.0, drifted=False)

    try:
        # 使用 two-sided KS 检验，与 scipy 默认一致
        result = kstest(ref_arr, cur_arr, alternative="two-sided")
        stat = float(result.statistic)
        pvalue = float(result.pvalue)
        drifted = pvalue < alpha
        return KSResult(
            stat=round(stat, 6),
            pvalue=round(pvalue, 6),
            drifted=drifted,
        )
    except Exception:
        return KSResult(stat=float("nan"), pvalue=float("nan"), drifted=False)


def compute_ks_batch(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    alpha: float = 0.05,
) -> dict[str, KSResult]:
    """
    批量计算多个特征的 KS 检验

    参数
    ----
    reference_df : DataFrame 基准数据
    current_df  : DataFrame 当前数据
    alpha       : float 显著性水平

    返回
    ----
    dict[str, KSResult]: {特征名: KSResult}
    """
    results: dict[str, KSResult] = {}
    for col in reference_df.columns:
        if col not in current_df.columns:
            results[col] = KSResult(stat=float("nan"), pvalue=float("nan"), drifted=False)
            continue
        results[col] = compute_ks(
            reference_df[col].values,
            current_df[col].values,
            alpha=alpha,
        )
    return results
