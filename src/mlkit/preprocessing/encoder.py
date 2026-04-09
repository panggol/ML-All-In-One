# -*- coding: utf-8 -*-
"""
特征编码器 - Encoder

已迁移到 mlkit.preprocessing.tabular
此文件保留用于向后兼容
"""

from mlkit.preprocessing.tabular.encoder import (
    LabelEncoder,
    OneHotEncoder,
    OrdinalEncoder,
    TargetEncoder,
)

__all__ = [
    "LabelEncoder",
    "OneHotEncoder",
    "OrdinalEncoder",
    "TargetEncoder",
]
