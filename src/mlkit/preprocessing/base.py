# -*- coding: utf-8 -*-
"""
预处理模块基础类
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Optional, Union

import numpy as np


class StageMode(Enum):
    """执行模式"""
    SERIAL = "serial"  # 串行
    PARALLEL = "parallel"  # 并行


class BaseTransformer(ABC):
    """
    所有预处理器基类
    
    设计原则：
    - fit/transform 分离
    - 支持 fit_transform 便捷方法
    - 支持逆变换 (inverse_transform)
    - 支持可视化 (plot)
    """

    # 依赖阶段：必须在哪些阶段之后执行
    depends_on: List[str] = []
    
    # 互斥阶段：不能和哪些阶段同时执行
    conflicts_with: List[str] = []
    
    # 执行模式：串行或并行
    mode: StageMode = StageMode.SERIAL
    
    # 执行顺序：数字越小越靠前
    order: int = 0

    def __init__(self):
        self._fitted = False
        self._n_features_in: Optional[int] = None

    def fit(self, X, y=None):
        """
        学习变换参数
        
        Args:
            X: 输入数据
            y: 标签 (可选)
            
        Returns:
            self
        """
        self._n_features_in = self._get_n_features(X)
        self._fitted = True
        return self

    @abstractmethod
    def transform(self, X):
        """
        应用变换
        
        Args:
            X: 输入数据
            
        Returns:
            变换后的数据
        """
        pass

    def fit_transform(self, X, y=None):
        """
        拟合并转换 (便捷方法)
        
        Args:
            X: 输入数据
            y: 标签 (可选)
            
        Returns:
            变换后的数据
        """
        return self.fit(X, y).transform(X)

    def inverse_transform(self, X):
        """
        逆变换
        
        Args:
            X: 变换后的数据
            
        Returns:
            原始数据
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support inverse_transform"
        )

    def is_fitted(self) -> bool:
        """是否已拟合"""
        return self._fitted

    def _get_n_features(self, X) -> int:
        """获取特征数"""
        if hasattr(X, 'shape'):
            return X.shape[1] if len(X.shape) > 1 else 1
        return 1

    def get_params(self) -> dict:
        """获取参数"""
        return {}

    def set_params(self, **params):
        """设置参数"""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def plot(self, X, **kwargs):
        """
        可视化
        
        Args:
            X: 输入数据
            **kwargs: 可视化参数
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support plot"
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class FitMixin:
    """提供 fit 方法的 Mixin"""

    def fit(self, X, y=None):
        """学习变换参数"""
        self._n_features_in = self._get_n_features(X)
        self._fitted = True
        return self

    def _get_n_features(self, X) -> int:
        if hasattr(X, 'shape'):
            return X.shape[1] if len(X.shape) > 1 else 1
        return 1


class TransformMixin:
    """提供 transform 方法的 Mixin"""

    @abstractmethod
    def transform(self, X):
        """应用变换"""
        pass
