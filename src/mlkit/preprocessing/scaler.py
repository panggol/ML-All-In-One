# -*- coding: utf-8 -*-
"""
特征缩放器 - Scaler

已迁移到 mlkit.preprocessing.tabular
此文件保留用于向后兼容
"""

from mlkit.preprocessing.tabular.scaler import (
    StandardScaler,
    MinMaxScaler,
    RobustScaler,
    QuantileTransformer,
    PowerTransformer,
)

__all__ = [
    "StandardScaler",
    "MinMaxScaler",
    "RobustScaler",
    "QuantileTransformer",
    "PowerTransformer",
]
