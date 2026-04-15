"""
漂移检测协调器
Library-First: 串联 PSI + KS，阈值判断，告警触发
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd

from src.mlkit.drift.psi import (
    compute_psi,
    compute_psi_batch,
    compute_overall_psi,
    get_psi_level,
)
from src.mlkit.drift.ks import compute_ks, compute_ks_batch, KSResult


@dataclass
class FeatureDriftResult:
    """单个特征的漂移结果"""
    feature: str
    psi: float
    ks_stat: float
    ks_pvalue: float
    ks_drifted: bool
    drift_level: str


@dataclass
class DriftCheckResult:
    """整体漂移检测结果"""
    check_id: str
    reference_id: int
    model_id: Optional[int]
    row_count: int
    psi_overall: float
    psi_features: dict[str, float]
    ks_features: dict[str, dict]
    drift_level: str
    feature_results: list[FeatureDriftResult]
    warnings: list[str] = field(default_factory=list)
    alerted: bool = False
    alert_rule_id: Optional[int] = None


def check_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    reference_id: int,
    model_id: Optional[int] = None,
    check_id: Optional[str] = None,
    n_bins: int = 10,
    psi_threshold: float = 0.2,
    ks_alpha: float = 0.05,
) -> DriftCheckResult:
    """
    漂移检测主函数

    流程：
    1. 样本量检查（< 1000 条返回警告）
    2. 特征一致性检查
    3. 数值特征过滤
    4. 批量计算 PSI + KS
    5. 计算整体漂移等级
    6. 判断是否触发告警

    参数
    ----
    reference_df : DataFrame 基准数据
    current_df   : DataFrame 当前数据
    reference_id  : int 基准数据集 ID
    model_id      : int 可选，模型 ID
    check_id      : str 可选，检测批次 ID（UUID）
    n_bins        : int PSI 分箱数
    psi_threshold : float PSI 告警阈值
    ks_alpha      : float KS 显著性水平

    返回
    ----
    DriftCheckResult
    """
    import uuid

    if check_id is None:
        check_id = str(uuid.uuid4())

    warnings: list[str] = []

    # 样本量检查
    if len(current_df) < 1000:
        warnings.append(f"样本量 {len(current_df)} < 1000，PSI 计算可能不准确，建议至少 1000 条")

    # 特征一致性检查
    ref_cols = set(reference_df.columns)
    cur_cols = set(current_df.columns)
    missing = ref_cols - cur_cols
    extra = cur_cols - ref_cols
    if missing:
        raise ValueError(f"当前数据缺少基准特征: {list(missing)}")
    if extra:
        warnings.append(f"当前数据包含多余特征（将被忽略）: {list(extra)}")

    # 只保留共同特征（按基准顺序）
    common_cols = [c for c in reference_df.columns if c in current_df.columns]
    ref_filtered = reference_df[common_cols]
    cur_filtered = current_df[common_cols]

    # 数值特征过滤
    numeric_cols: list[str] = []
    for col in common_cols:
        ref_col = ref_filtered[col]
        cur_col = cur_filtered[col]
        if pd.api.types.is_numeric_dtype(ref_col) and pd.api.types.is_numeric_dtype(cur_col):
            numeric_cols.append(col)
        else:
            warnings.append(f"跳过非数值特征: {col}（当前版本仅支持数值特征）")

    if not numeric_cols:
        raise ValueError("没有可检测的数值特征")

    ref_num = ref_filtered[numeric_cols]
    cur_num = cur_filtered[numeric_cols]

    # 批量计算 PSI 和 KS
    psi_features = compute_psi_batch(ref_num, cur_num, n_bins=n_bins)
    ks_features_raw = compute_ks_batch(ref_num, cur_num, alpha=ks_alpha)

    # 构建 KS 结果 dict
    ks_features: dict[str, dict] = {}
    feature_results: list[FeatureDriftResult] = []

    for col in numeric_cols:
        psi_val = psi_features[col]
        ks_result: KSResult = ks_features_raw[col]
        level = get_psi_level(psi_val) if not math.isnan(psi_val) else "undefined"
        ks_features[col] = {
            "stat": ks_result.stat,
            "pvalue": ks_result.pvalue,
            "drifted": ks_result.drifted,
        }
        feature_results.append(FeatureDriftResult(
            feature=col,
            psi=psi_val,
            ks_stat=ks_result.stat,
            ks_pvalue=ks_result.pvalue,
            ks_drifted=ks_result.drifted,
            drift_level=level,
        ))

    # 计算整体 PSI
    psi_overall = compute_overall_psi(ref_num, cur_num, n_bins=n_bins)
    drift_level = get_psi_level(psi_overall)

    # 判断是否触发告警（任意特征 PSI > 阈值）
    alerted = False
    alert_rule_id: Optional[int] = None
    for col, psi_val in psi_features.items():
        if not math.isnan(psi_val) and psi_val > psi_threshold:
            alerted = True
            break

    return DriftCheckResult(
        check_id=check_id,
        reference_id=reference_id,
        model_id=model_id,
        row_count=len(current_df),
        psi_overall=psi_overall,
        psi_features=psi_features,
        ks_features=ks_features,
        drift_level=drift_level,
        feature_results=feature_results,
        warnings=warnings,
        alerted=alerted,
        alert_rule_id=alert_rule_id,
    )


def compute_feature_stats(df: pd.DataFrame) -> dict[str, dict]:
    """
    计算 DataFrame 中每个数值特征的统计量

    返回
    ----
    dict[str, dict]: {特征名: {mean, std, q25, q50, q75, min, max}}
    """
    stats: dict[str, dict] = {}
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        col_data = df[col].dropna()
        if len(col_data) == 0:
            continue
        stats[col] = {
            "mean": round(float(np.mean(col_data)), 6),
            "std": round(float(np.std(col_data)), 6),
            "q25": round(float(np.percentile(col_data, 25)), 6),
            "q50": round(float(np.percentile(col_data, 50)), 6),
            "q75": round(float(np.percentile(col_data, 75)), 6),
            "min": round(float(np.min(col_data)), 6),
            "max": round(float(np.max(col_data)), 6),
        }
    return stats
