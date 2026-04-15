"""
mlkit.explainability.ice — ICE 曲线计算

Individual Conditional Expectation (ICE) 曲线：
对于选定特征 f，将该特征从最小值改到最大值，保持其他特征不变，
记录每个样本的预测值变化，从而揭示特征与预测值的非线性关系。

实现策略：
1. 对每个样本，将目标特征从 min(f) 遍历到 max(f)（num_points 个采样点）
2. 保持其他特征值不变，调用模型预测
3. 收集所有样本的曲线数据
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class ICEPoint:
    """ICE 曲线上的单个数据点"""
    feature_value: float  # 特征取值
    predicted_value: float  # 模型预测值


@dataclass
class ICECurve:
    """单条 ICE 曲线（对应一个样本）"""
    sample_index: int
    points: List[ICEPoint] = field(default_factory=list)


@dataclass
class ICEResult:
    """ICE 曲线计算结果"""
    feature_name: str
    feature_values: List[float]  # 特征取值范围（所有曲线共享）
    curves: List[ICECurve]
    computation_time_ms: float


# =============================================================================
# ICE 曲线计算
# =============================================================================

def _sample_data(data: np.ndarray, max_samples: int) -> np.ndarray:
    """随机采样"""
    if data.shape[0] <= max_samples:
        return data
    indices = np.random.default_rng(42).choice(data.shape[0], max_samples, replace=False)
    return data[indices]


def compute_ice_curves(
    model: Any,
    X_data: np.ndarray,
    feature_name: str,
    feature_names: List[str],
    num_points: int = 50,
    sample_size: int = 500,
) -> ICEResult:
    """
    计算指定特征的 ICE 曲线。

    参数：
        model: 训练好的模型（支持 sklearn 接口）
        X_data: 原始数据矩阵（numpy array，shape (n_samples, n_features)）
        feature_name: 目标特征名
        feature_names: 所有特征名列表
        num_points: 曲线上采样点数（从 min 到 max 的取值数）
        sample_size: 使用样本数（超过此值自动采样）

    返回：
        ICEResult 对象

    异常：
        ValueError: feature_name 不存在于 feature_names 中，或 X_data 为空
    """
    start_time = time.perf_counter()

    X_data = np.array(X_data)
    if X_data.ndim == 1:
        raise ValueError("X_data 必须是 2D 矩阵（n_samples, n_features）")

    # 查找特征索引
    try:
        feature_idx = feature_names.index(feature_name)
    except ValueError:
        raise ValueError(
            f"特征 '{feature_name}' 不存在于模型输入特征中。"
            f"可用特征：{feature_names}"
        )

    # 采样
    if X_data.shape[0] > sample_size:
        X_data = _sample_data(X_data, sample_size)
        logger.info(f"ICE 数据集过大，已采样至 {sample_size} 样本")

    n_samples = X_data.shape[0]

    # 计算特征取值范围
    col = X_data[:, feature_idx]
    feature_min = float(np.nanmin(col))
    feature_max = float(np.nanmax(col))

    # 生成特征取值序列
    feature_values = np.linspace(feature_min, feature_max, num_points).tolist()

    # 逐样本计算 ICE 曲线
    curves: List[ICECurve] = []
    for sample_idx in range(n_samples):
        base_sample = X_data[sample_idx].copy()
        points: List[ICEPoint] = []

        for fv in feature_values:
            perturbed = base_sample.copy()
            perturbed[feature_idx] = fv

            try:
                pred = model.predict(perturbed.reshape(1, -1))
                pred_value = float(pred.ravel()[0])
            except Exception as e:
                logger.warning(f"预测失败（sample={sample_idx}, fv={fv}）：{e}")
                pred_value = 0.0

            points.append(ICEPoint(feature_value=fv, predicted_value=pred_value))

        curves.append(ICECurve(sample_index=sample_idx, points=points))

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        f"ICE 曲线计算完成：特征={feature_name}，样本数={n_samples}，"
        f"采样点={num_points}，耗时={elapsed_ms:.1f}ms"
    )

    return ICEResult(
        feature_name=feature_name,
        feature_values=feature_values,
        curves=curves,
        computation_time_ms=elapsed_ms,
    )
