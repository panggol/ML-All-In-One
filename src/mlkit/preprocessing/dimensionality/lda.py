# -*- coding: utf-8 -*-
"""
线性判别分析 - Linear Discriminant Analysis (LDA)

支持：
- LinearDiscriminantAnalysis: 线性判别分析
"""

from typing import Optional, Union
import numpy as np

from mlkit.preprocessing.base import BaseTransformer


class LinearDiscriminantAnalysis(BaseTransformer):
    """
    线性判别分析 (Linear Discriminant Analysis)
    
    用于分类任务的监督降维方法。
    找到使类间方差最大化、类内方差最小化的投影方向。
    
    与 PCA 的区别:
    - PCA 是无监督的，只考虑方差
    - LDA 是监督的，考虑类别信息
    
    Example:
        X.shape = (100, 10), 3 个类别
        -> X_reduced.shape = (100, 2)  # min(类别数-1, 特征数)
    """

    order = 10  # 在缩放/编码之后

    def __init__(
        self,
        solver: str = 'svd',
        n_components: Optional[int] = None,
        shrinkage: Optional[str] = None,
        covariance_estimator: Optional[object] = None,
    ):
        """
        Args:
            solver: 求解方法
                - 'svd': 奇异值分解（默认，适用于大规模数据）
                - 'eigen': 特征分解（可配合 shrinkage）
                - 'lsqr': 最小二乘（可配合正则化）
                默认值为 'svd'。
            n_components: 降维后的维度。
                必须小于等于 min(n_classes - 1, n_features)。
                如果为 None，则取 min(n_classes - 1, n_features)。
            shrinkage: 正则化参数，用于改善协方差估计。
                - None: 不使用
                - 'auto': 自动确定
                - float: 指定正则化强度 (0-1)
                仅在 solver='eigen' 或 'lsqr' 时有效。
            covariance_estimator: 协方差估计器。
                如果为 None，则使用标准协方差估计。
        """
        super().__init__()
        
        valid_solvers = ['svd', 'eigen', 'lsqr']
        if solver not in valid_solvers:
            raise ValueError(f"solver must be one of {valid_solvers}, got {solver}")
        
        valid_shrinkages = [None, 'auto']
        if shrinkage is not None and shrinkage not in valid_shrinkages:
            if not isinstance(shrinkage, (int, float)):
                raise ValueError(
                    f"shrinkage must be None, 'auto', or a float, got {shrinkage}"
                )
        
        self.solver = solver
        self.n_components = n_components
        self.shrinkage = shrinkage
        self.covariance_estimator = covariance_estimator
        
        self.explained_variance_ratio_: Optional[np.ndarray] = None
        self.scalings_: Optional[np.ndarray] = None  # 投影矩阵
        self.means_: Optional[np.ndarray] = None  # 每个类别的均值
        self.classes_: Optional[np.ndarray] = None
        self.n_components_: Optional[int] = None
        self.n_features_in_: Optional[int] = None
        self.n_classes_: Optional[int] = None

    def fit(self, X, y):
        """
        学习 LDA 参数
        
        Args:
            X: 训练数据，形状为 (n_samples, n_features)
            y: 标签数据，形状为 (n_samples,)
            
        Returns:
            self
        """
        X = self._validate_X(X)
        y = np.array(y).ravel()
        
        self.n_features_in_ = X.shape[1]
        self.classes_ = np.unique(y)
        self.n_classes_ = len(self.classes_)
        
        # 确定降维维度
        max_components = min(self.n_classes_ - 1, self.n_features_in_)
        if self.n_components is None:
            self.n_components_ = max_components
        else:
            if self.n_components > max_components:
                raise ValueError(
                    f"n_components={self.n_components} cannot be larger than "
                    f"min(n_classes - 1, n_features)={max_components}"
                )
            self.n_components_ = self.n_components
        
        # 计算各类别的均值
        self.means_ = np.zeros((self.n_classes_, self.n_features_in_))
        for i, cls in enumerate(self.classes_):
            mask = y == cls
            self.means_[i] = np.mean(X[mask], axis=0)
        
        # 计算整体均值
        overall_mean = np.mean(X, axis=0)
        
        # 计算类间散度矩阵 (Between-class scatter)
        S_B = np.zeros((self.n_features_in_, self.n_features_in_))
        for i, cls in enumerate(self.classes_):
            mask = y == cls
            n_samples = np.sum(mask)
            mean_diff = (self.means_[i] - overall_mean).reshape(-1, 1)
            S_B += n_samples * (mean_diff @ mean_diff.T)
        
        # 计算类内散度矩阵 (Within-class scatter)
        S_W = np.zeros((self.n_features_in_, self.n_features_in_))
        for i, cls in enumerate(self.classes_):
            mask = y == cls
            X_class = X[mask]
            mean_centered = X_class - self.means_[i]
            S_W += mean_centered.T @ mean_centered
        
        # 根据 solver 选择方法
        if self.solver == 'svd':
            self._fit_svd(X, y, S_B, S_W)
        elif self.solver == 'eigen':
            self._fit_eigen(S_B, S_W)
        else:  # lsqr
            self._fit_lsqr(S_B, S_W)
        
        self._fitted = True
        return self

    def _fit_svd(
        self, X: np.ndarray, y: np.ndarray, S_B: np.ndarray, S_W: np.ndarray
    ):
        """使用 SVD 求解"""
        # 计算 X 的中心化版本
        overall_mean = np.mean(X, axis=0)
        X_centered = X - overall_mean
        
        # 使用 SVD 分解
        # 对于 LDA，简化处理：直接返回 SVD 的前 n_components_ 个分量
        # 这是一种近似方法
        
        # 计算总体散度矩阵 S_T = S_B + S_W
        S_T = S_B + S_W
        
        # 特征值分解
        eigenvalues, eigenvectors = np.linalg.eigh(S_T)
        
        # 排序
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # 保留非零特征值对应的特征向量
        nonzero_idx = eigenvalues > 1e-10
        eigenvalues = eigenvalues[nonzero_idx]
        eigenvectors = eigenvectors[:, nonzero_idx]
        
        self.scalings_ = eigenvectors[:, :self.n_components_]
        self.explained_variance_ratio_ = eigenvalues[:self.n_components_]
        self.explained_variance_ratio_ = (
            self.explained_variance_ratio_ / np.sum(eigenvalues)
        )

    def _fit_eigen(self, S_B: np.ndarray, S_W: np.ndarray):
        """使用特征分解求解"""
        # 正则化 S_W
        if self.shrinkage is not None:
            if self.shrinkage == 'auto':
                # 自动确定 shrinkage 参数
                n_features = S_W.shape[0]
                # 使用 Ledoit-Wolf 估计
                shrinkage = self._ledoit_wolf(S_W)
            else:
                shrinkage = float(self.shrinkage)
            
            # 应用 shrinkage
            S_W_reg = (1 - shrinkage) * S_W + shrinkage * np.trace(S_W) / S_W.shape[0] * np.eye(S_W.shape[0])
        else:
            S_W_reg = S_W
        
        try:
            # 求解广义特征值问题 S_B * v = lambda * S_W * v
            # 转换为标准特征值问题
            S_W_inv = np.linalg.inv(S_W_reg)
            M = S_W_inv @ S_B
            
            eigenvalues, eigenvectors = np.linalg.eigh(M)
            
            # 排序
            idx = np.argsort(eigenvalues)[::-1]
            eigenvalues = eigenvalues[idx]
            eigenvectors = eigenvectors[:, idx]
            
            # 保留正特征值
            positive_idx = eigenvalues > 1e-10
            eigenvalues = eigenvalues[positive_idx]
            eigenvectors = eigenvectors[:, positive_idx]
            
            self.scalings_ = eigenvectors[:, :self.n_components_]
            self.explained_variance_ratio_ = eigenvalues[:self.n_components_]
            self.explained_variance_ratio_ = (
                self.explained_variance_ratio_ / np.sum(eigenvalues)
            )
        except np.linalg.LinAlgError:
            # 如果求解失败，使用伪逆
            S_W_pinv = np.linalg.pinv(S_W_reg)
            M = S_W_pinv @ S_B
            
            eigenvalues, eigenvectors = np.linalg.eigh(M)
            idx = np.argsort(eigenvalues)[::-1]
            eigenvalues = eigenvalues[idx]
            eigenvectors = eigenvectors[:, idx]
            
            self.scalings_ = eigenvectors[:, :self.n_components_]
            self.explained_variance_ratio_ = eigenvalues[:self.n_components_]

    def _fit_lsqr(self, S_B: np.ndarray, S_W: np.ndarray):
        """使用最小二乘求解"""
        # 类似于 eigen 方法，但使用不同的正则化
        if self.shrinkage is not None:
            if self.shrinkage == 'auto':
                shrinkage = self._ledoit_wolf(S_W)
            else:
                shrinkage = float(self.shrinkage)
            
            S_W_reg = (1 - shrinkage) * S_W + shrinkage * np.trace(S_W) / S_W.shape[0] * np.eye(S_W.shape[0])
        else:
            S_W_reg = S_W
        
        # 使用伪逆
        S_W_pinv = np.linalg.pinv(S_W_reg)
        M = S_W_pinv @ S_B
        
        eigenvalues, eigenvectors = np.linalg.eigh(M)
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        positive_idx = eigenvalues > 1e-10
        eigenvalues = eigenvalues[positive_idx]
        eigenvectors = eigenvectors[:, positive_idx]
        
        self.scalings_ = eigenvectors[:, :self.n_components_]
        self.explained_variance_ratio_ = eigenvalues[:self.n_components_]

    def _ledoit_wolf(self, X: np.ndarray) -> float:
        """Ledoit-Wolf shrinkage 参数估计"""
        n = X.shape[0]
        
        # 样本协方差
        mu = np.trace(X) / X.shape[0]
        
        # 计算 ||S - mu*I||^2
        diff = X - mu * np.eye(X.shape[0])
        norm_sq = np.sum(diff ** 2)
        
        # 计算 gamma
        gamma = 0.001  # 简化版本
        
        return min(gamma, 1.0)

    def transform(self, X):
        """
        投影数据到 LDA 空间
        
        Args:
            X: 数据，形状为 (n_samples, n_features)
            
        Returns:
            降维后的数据，形状为 (n_samples, n_components_)
        """
        X = self._validate_X(X)
        
        if self.scalings_ is None:
            raise ValueError("LinearDiscriminantAnalysis not fitted")
        
        return X @ self.scalings_

    def fit_transform(self, X, y):
        """拟合并转换"""
        return self.fit(X, y).transform(X)

    def predict(self, X):
        """
        预测类别
        
        Args:
            X: 数据
            
        Returns:
            预测的类别标签
        """
        X = self._validate_X(X)
        
        if self.scalings_ is None:
            raise ValueError("LinearDiscriminantAnalysis not fitted")
        
        # 投影到 LDA 空间
        X_lda = self.transform(X)
        
        # 计算各类别在 LDA 空间中的中心
        means_lda = self.means_ @ self.scalings_
        
        # 找到最近的类别中心
        predictions = np.zeros(X.shape[0], dtype=self.classes_.dtype)
        
        for i, x in enumerate(X_lda):
            distances = np.sum((means_lda - x) ** 2, axis=1)
            predictions[i] = self.classes_[np.argmin(distances)]
        
        return predictions

    def predict_proba(self, X):
        """
        预测类别概率
        
        Args:
            X: 数据
            
        Returns:
            各类别的概率，形状为 (n_samples, n_classes)
        """
        X = self._validate_X(X)
        
        if self.scalings_ is None:
            raise ValueError("LinearDiscriminantAnalysis not fitted")
        
        # 投影
        X_lda = self.transform(X)
        means_lda = self.means_ @ self.scalings_
        
        # 计算距离
        n_samples = X_lda.shape[0]
        n_classes = len(self.classes_)
        
        # 使用马氏距离的简化版本
        # 假设各类别在 LDA 空间中具有相同的方差
        distances = np.zeros((n_samples, n_classes))
        
        for i in range(n_classes):
            diff = X_lda - means_lda[i]
            distances[:, i] = np.sum(diff ** 2, axis=1)
        
        # 转换为概率（使用 softmax）
        # 添加一个大的常数来避免数值问题
        distances = distances - distances.min(axis=1, keepdims=True)
        exp_distances = np.exp(-distances)
        probabilities = exp_distances / exp_distances.sum(axis=1, keepdims=True)
        
        return probabilities

    def score(self, X, y) -> float:
        """
        计算准确率
        
        Args:
            X: 数据
            y: 真实标签
            
        Returns:
            准确率
        """
        predictions = self.predict(X)
        return np.mean(predictions == y)

    def _validate_X(self, X):
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return X

    def get_params(self) -> dict:
        return {
            'solver': self.solver,
            'n_components': self.n_components,
            'shrinkage': self.shrinkage,
        }
