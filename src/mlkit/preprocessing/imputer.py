# -*- coding: utf-8 -*-
"""
缺失值填充器 - Imputer

已迁移到 mlkit.preprocessing.tabular
此文件保留用于向后兼容
"""

from mlkit.preprocessing.tabular.imputer import (
    SimpleImputer,
    KNNImputer,
    IterativeImputer,
)

__all__ = [
    "SimpleImputer",
    "KNNImputer",
    "IterativeImputer",
]
