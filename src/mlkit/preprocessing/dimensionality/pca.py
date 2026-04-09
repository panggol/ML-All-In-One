# -*- coding: utf-8 -*-
"""
降维模块 - Dimensionality Reduction

支持：
- PCA: 主成分分析
"""

from typing import Optional, Union
import numpy as np

from mlkit.preprocessing.base import BaseTransformer


class PCA(BaseTransformer):
    """
    主成分分析 (Principal Component Analysis)
    
    将高维数据投影到低维空间，保留最大方差
    
    Example:
        X.shape = (100, 10) -> X_reduced.shape = (100, 2)
    """

    order = 10  # 在缩放/编码之后

    def __init__(self, n_components: Optional[Union[int, float]] = None):
        """
        Args:
            n_components: 主成分数量
                - int: 保留的前 n_components 个主成分
                - float (0-1): 保留解释方差比例
                - None: 保留所有主成分
        """
        super().__init__()
        self.n_components = n_components
        self.components_: Optional[np.ndarray] = None
        self.explained_variance_: Optional[np.ndarray] = None
        self.explained_variance_ratio_: Optional[np.ndarray] = None
        self.mean_: Optional[np.ndarray] = None
        self.n_components_: Optional[int] = None

    def fit(self, X, y=None):
        """
        学习主成分
        
        Args:
            X: 训练数据，形状为 (n_samples, n_features)
            y: 忽略（API 兼容）
        """
        X = self._validate_X(X)
        
        n_samples, n_features = X.shape
        
        # 中心化
        self.mean_ = np.mean(X, axis=0)
        X_centered = X - self.mean_
        
        # 计算协方差矩阵
        cov = np.cov(X_centered, rowvar=False)
        
        # 特征值分解
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # 排序（从大到小）
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        self.explained_variance_ = eigenvalues
        self.explained_variance_ratio_ = eigenvalues / np.sum(eigenvalues)
        self.components_ = eigenvectors
        
        # 确定主成分数量
        self.n_components_ = self._get_n_components(n_features)
        
        return self

    def transform(self, X):
        """
        投影数据到主成分空间
        
        Args:
            X: 数据，形状为 (n_samples, n_features)
            
        Returns:
            降维后的数据，形状为 (n_samples, n_components_)
        """
        X = self._validate_X(X)
        
        if self.components_ is None:
            raise ValueError("PCA not fitted")
        
        # 中心化
        X_centered = X - self.mean_
        
        # 投影
        return X_centered @ self.components_[:, :self.n_components_]

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)

    def inverse_transform(self, X):
        """
        将降维数据恢复到原始空间
        
        Args:
            X: 降维后的数据
            
        Returns:
            原始空间的数据
        """
        if self.components_ is None:
            raise ValueError("PCA not fitted")
        
        return X @ self.components_[:, :self.n_components_].T + self.mean_

    def _validate_X(self, X):
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return X

    def _get_n_components(self, n_features: int) -> int:
        """确定保留的主成分数量"""
        if self.n_components is None:
            return n_features
        
        if isinstance(self.n_components, int):
            if self.n_components > n_features:
                raise ValueError(
                    f"n_components={self.n_components} cannot be larger "
                    f"than n_features={n_features}"
                )
            return self.n_components
        
        if isinstance(self.n_components, float):
            if not 0 < self.n_components <= 1:
                raise ValueError(
                    f"n_components must be between 0 and 1, got {self.n_components}"
                )
            # 找到满足解释方差比例的主成分数量
            cumsum = np.cumsum(self.explained_variance_ratio_)
            n_comp = np.searchsorted(cumsum, self.n_components) + 1
            return max(1, n_comp)
        
        raise ValueError(f"Invalid n_components: {self.n_components}")

    def get_params(self) -> dict:
        return {"n_components": self.n_components}

    def score(self, X) -> float:
        """
        计算重构误差（负均方误差，越大越好）
        """
        X_transformed = self.transform(X)
        X_reconstructed = self.inverse_transform(X_transformed)
        return -np.mean((X - X_reconstructed) ** 2)
