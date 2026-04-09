# -*- coding: utf-8 -*-
"""
缺失值处理器 - Imputer

支持：
- SimpleImputer: 简单填充（均值/中位数/众数/常量）
- KNNImputer: K近邻填充
- IterativeImputer: 迭代填充 (MICE)
"""

from typing import Optional, Union
import numpy as np
from abc import ABC, abstractmethod

from mlkit.preprocessing.base import BaseTransformer


class BaseEstimator(ABC):
    """简单估计器基类"""
    
    @abstractmethod
    def fit(self, X, y=None):
        pass
    
    @abstractmethod
    def predict(self, X):
        pass
    
    @abstractmethod
    def predict_proba(self, X):
        pass


class SimpleImputer(BaseTransformer):
    """
    简单缺失值填充器
    
    使用均值、中位数、众数或常量填充缺失值
    
    Example:
        np.array([[1, np.nan], [3, 4]]) 
        -> 均值填充: [[1, 3.5], [3, 4]]
    """

    order = 0  # 最早执行

    def __init__(self, strategy: str = 'mean', fill_value: Optional[float] = None):
        """
        Args:
            strategy: 填充策略 ('mean', 'median', 'most_frequent', 'constant')
            fill_value: 常量填充值 (strategy='constant' 时使用)
        """
        super().__init__()
        
        valid_strategies = ['mean', 'median', 'most_frequent', 'constant']
        if strategy not in valid_strategies:
            raise ValueError(f"strategy must be one of {valid_strategies}")
        
        self.strategy = strategy
        self.fill_value = fill_value
        self.statistics_: Optional[np.ndarray] = None

    def fit(self, X, y=None):
        """学习填充值"""
        X = self._validate_X(X)
        
        # 检查数据类型
        self.is_string_ = X.dtype.kind in ['U', 'S', 'O']
        
        # 计算每列的统计值
        self.statistics_ = np.zeros(X.shape[1])
        
        for col in range(X.shape[1]):
            if self.is_string_:
                # 字符串类型：找出非空的
                col_data = X[:, col]
                valid_data = col_data[col_data != np.nan]
                # 处理字符串 'nan' 或 None
                valid_data = np.array([v for v in col_data if str(v).lower() != 'nan' and v is not None])
            else:
                # 数值类型
                col_data = X[:, col]
                valid_data = col_data[~np.isnan(col_data.astype(float))]
            
            if len(valid_data) == 0:
                if self.strategy == 'constant':
                    self.statistics_[col] = self.fill_value or 0
                else:
                    self.statistics_[col] = 0
                continue
            
            if self.strategy == 'mean':
                self.statistics_[col] = float(np.mean(valid_data.astype(float)))
            elif self.strategy == 'median':
                self.statistics_[col] = float(np.median(valid_data.astype(float)))
            elif self.strategy == 'most_frequent':
                # 众数
                if self.is_string_:
                    values, counts = np.unique(valid_data, return_counts=True)
                else:
                    values, counts = np.unique(valid_data.astype(float), return_counts=True)
                self.statistics_[col] = values[np.argmax(counts)]
            elif self.strategy == 'constant':
                self.statistics_[col] = self.fill_value or 0
        
        self._fitted = True
        return self

    def transform(self, X):
        """填充缺失值"""
        X = self._validate_X(X)
        
        if self.statistics_ is None:
            raise ValueError("Imputer not fitted")
        
        X_copy = X.copy()
        
        for col in range(X_copy.shape[1]):
            mask = np.isnan(X_copy[:, col])
            X_copy[mask, col] = self.statistics_[col]
        
        return X_copy

    def _validate_X(self, X) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        return X

    def get_params(self) -> dict:
        return {
            'strategy': self.strategy,
            'fill_value': self.fill_value,
        }


class KNNImputer(BaseTransformer):
    """
    K近邻缺失值填充器
    
    使用 K 个最近邻的值来填充缺失值
    
    Example:
        使用 3 个最近邻的均值填充
    """

    order = 0

    def __init__(self, n_neighbors: int = 5, weights: str = 'distance'):
        """
        Args:
            n_neighbors: 近邻数量
            weights: 权重方式 ('uniform', 'distance')
        """
        super().__init__()
        self.n_neighbors = n_neighbors
        self.weights = weights

    def fit(self, X, y=None):
        """学习训练数据"""
        X = self._validate_X(X).astype(float)
        
        # 移除包含 NaN 的行来计算距离
        mask = ~np.any(np.isnan(X), axis=1)
        self.train_data_ = X[mask]
        
        if len(self.train_data_) == 0:
            raise ValueError("No valid data found in X")
        
        self._fitted = True
        return self

    def transform(self, X):
        """填充缺失值"""
        X = self._validate_X(X).astype(float)
        
        if self.train_data_ is None:
            raise ValueError("Imputer not fitted")
        
        X_copy = X.copy()
        
        # 对每个包含 NaN 的样本
        for i in range(X_copy.shape[0]):
            if np.any(np.isnan(X_copy[i])):
                # 找到有效特征的位置
                valid_features = ~np.isnan(X_copy[i])
                
                if np.sum(valid_features) == 0:
                    # 所有特征都是 NaN，使用均值填充
                    for col in range(X_copy.shape[1]):
                        X_copy[i, col] = np.mean(self.train_data_[:, col])
                    continue
                
                # 只用有效特征计算距离
                distances = np.full(len(self.train_data_), np.inf)
                for j, train_row in enumerate(self.train_data_):
                    valid_train = valid_features & ~np.isnan(train_row)
                    if np.sum(valid_train) > 0:
                        diff = (train_row[valid_features] - X_copy[i, valid_features])
                        distances[j] = np.sqrt(np.sum(diff ** 2))
                
                # 找到 K 个最近邻
                nearest_idx = np.argsort(distances)[:self.n_neighbors]
                nearest_neighbors = self.train_data_[nearest_idx]
                
                # 计算填充值
                for col in range(X_copy.shape[1]):
                    if np.isnan(X_copy[i, col]):
                        X_copy[i, col] = np.mean(nearest_neighbors[:, col])
        
        return X_copy

    def _validate_X(self, X) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        return X

    def get_params(self) -> dict:
        return {
            'n_neighbors': self.n_neighbors,
            'weights': self.weights,
        }


class IterativeImputer(BaseTransformer):
    """
    迭代缺失值填充器 (Iterative Imputer / MICE)
    
    使用多变量方法迭代填充缺失值。
    每次迭代中，使用其他特征来预测当前特征的缺失值。
    
    工作原理:
    1. 用简单填充（均值）初始化缺失值
    2. 轮流将每个特征作为目标，其他特征作为特征
    3. 使用指定的估计器进行预测
    4. 用预测值替换缺失值
    5. 重复指定次数的迭代
    
    Example:
        X = [[1, 2, np.nan], [3, np.nan, 4], [np.nan, 5, 6]]
        -> 使用贝叶斯岭回归迭代填充
    """

    order = 0

    def __init__(
        self,
        estimator: Optional[object] = None,
        max_iter: int = 10,
        tol: float = 1e-3,
        initial_strategy: str = 'mean',
        imputation_order: str = 'ascending'
    ):
        """
        Args:
            estimator: 用于预测的估计器。
                如果为 None，则使用 BayesianRidge。
                估计器需要有 fit 和 predict 方法。
            max_iter: 最大迭代次数。
                默认值为 10。
            tol: 收敛容忍度。当两次迭代的差异小于此值时停止。
                默认值为 1e-3。
            initial_strategy: 初始填充策略。
                - 'mean': 均值填充
                - 'median': 中位数填充
                - 'most_frequent': 众数填充
                默认值为 'mean'。
            imputation_order: 填充顺序。
                - 'ascending': 从缺失值最少的特征开始
                - 'descending': 从缺失值最多的特征开始
                - 'random': 随机顺序
                默认值为 'ascending'。
        """
        super().__init__()
        
        self.estimator = estimator
        self.max_iter = max_iter
        self.tol = tol
        self.initial_strategy = initial_strategy
        self.imputation_order = imputation_order
        
        self.initial_imputer_: Optional[SimpleImputer] = None
        self.n_features_in_: Optional[int] = None
        self.missing_features_: Optional[np.ndarray] = None

    def fit(self, X, y=None):
        """
        学习填充参数
        
        Args:
            X: 训练数据
            y: 忽略（API 兼容）
            
        Returns:
            self
        """
        X = self._validate_X(X).astype(float)
        
        self.n_features_in_ = X.shape[1]
        
        # 确定每个特征的缺失状态
        self.missing_features_ = np.any(np.isnan(X), axis=0)
        
        # 初始化估计器
        if self.estimator is None:
            self.estimator_ = BayesianRidgeEstimator()
        else:
            self.estimator_ = self.estimator
        
        # 初始化初始填充器
        self.initial_imputer_ = SimpleImputer(strategy=self.initial_strategy)
        
        # 填充顺序
        self._compute_imputation_order(X)
        
        self._fitted = True
        return self

    def transform(self, X):
        """
        填充缺失值
        
        Args:
            X: 输入数据
            
        Returns:
            填充后的数据
        """
        X = self._validate_X(X).astype(float)
        
        if not self._fitted:
            raise ValueError("IterativeImputer not fitted")
        
        # 复制数据
        X_filled = X.copy()
        
        # 对所有列进行初始填充（使用 SimpleImputer）
        # 需要为每一列单独处理
        for col in range(X_filled.shape[1]):
            col_data = X_filled[:, col]
            nan_mask = np.isnan(col_data)
            if np.any(nan_mask):
                if self.initial_strategy == 'mean':
                    fill_value = np.nanmean(col_data) if not np.all(nan_mask) else 0
                elif self.initial_strategy == 'median':
                    fill_value = np.nanmedian(col_data) if not np.all(nan_mask) else 0
                else:
                    fill_value = 0
                col_data[nan_mask] = fill_value
                X_filled[:, col] = col_data
        
        # 迭代填充
        X_old = X_filled.copy()
        
        for iteration in range(self.max_iter):
            # 按照填充顺序处理每个特征
            for feature_idx in self._imputation_order:
                if not self.missing_features_[feature_idx]:
                    continue  # 该特征没有缺失值
                
                # 找到有值的样本（使用原始 X）
                mask = ~np.isnan(X[:, feature_idx])
                
                if np.sum(mask) < 2:
                    # 没有足够的样本来训练，用均值填充
                    X_filled[np.isnan(X[:, feature_idx]), feature_idx] = np.nanmean(X_filled[:, feature_idx])
                    continue
                
                # 准备特征和目标
                X_train = X_filled[mask, :]
                y_train = X[mask, feature_idx]  # 使用原始值作为目标
                
                X_predict = X_filled[~mask, :]
                
                if len(X_predict) == 0:
                    continue
                
                try:
                    # 训练估计器
                    self.estimator_.fit(X_train, y_train)
                    
                    # 预测缺失值
                    predicted = self.estimator_.predict(X_predict)
                    
                    # 更新填充值
                    X_filled[~mask, feature_idx] = predicted
                except Exception:
                    # 如果预测失败，使用均值填充
                    mean_val = np.nanmean(X_filled[:, feature_idx])
                    if np.isnan(mean_val):
                        mean_val = 0
                    X_filled[~mask, feature_idx] = mean_val
            
            # 检查收敛
            diff = np.nanmax(np.abs(X_filled - X_old))
            if diff < self.tol:
                break
            
            X_old = X_filled.copy()
        
        # 最终保底填充：确保没有 NaN
        for col in range(X_filled.shape[1]):
            nan_mask = np.isnan(X_filled[:, col])
            if np.any(nan_mask):
                if self.initial_strategy == 'mean':
                    fill_value = np.nanmean(X_filled[:, col])
                elif self.initial_strategy == 'median':
                    fill_value = np.nanmedian(X_filled[:, col])
                else:
                    fill_value = 0
                if np.isnan(fill_value):
                    fill_value = 0
                X_filled[nan_mask, col] = fill_value
        
        return X_filled

    def fit_transform(self, X, y=None):
        """拟合并填充"""
        return self.fit(X, y).transform(X)

    def _compute_imputation_order(self, X: np.ndarray):
        """计算填充顺序"""
        # 计算每个特征的缺失比例
        missing_ratio = np.sum(np.isnan(X), axis=0) / X.shape[0]
        
        if self.imputation_order == 'ascending':
            self._imputation_order = np.argsort(missing_ratio)
        elif self.imputation_order == 'descending':
            self._imputation_order = np.argsort(-missing_ratio)
        else:  # random
            self._imputation_order = np.random.permutation(X.shape[1])

    def _validate_X(self, X) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        return X

    def get_params(self) -> dict:
        return {
            'max_iter': self.max_iter,
            'tol': self.tol,
            'initial_strategy': self.initial_strategy,
            'imputation_order': self.imputation_order,
        }


class BayesianRidgeEstimator:
    """
    简单贝叶斯岭回归估计器
    
    这是一个简化的贝叶斯岭回归实现，用于 IterativeImputer。
    """

    def __init__(self):
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0
        self._fitted = False

    def fit(self, X, y):
        """
        拟合模型
        
        Args:
            X: 特征矩阵 (n_samples, n_features)
            y: 目标值 (n_samples,)
        """
        X = np.array(X)
        y = np.array(y).ravel()
        
        # 移除 NaN
        valid_mask = ~np.isnan(y)
        X = X[valid_mask]
        y = y[valid_mask]
        
        if len(y) < 2:
            self._fitted = False
            return self
        
        # 添加偏置
        X_with_bias = np.column_stack([np.ones(len(X)), X])
        
        try:
            # 使用岭回归（带正则化的最小二乘）
            alpha = 1.0  # 正则化参数
            XtX = X_with_bias.T @ X_with_bias
            XtX += alpha * np.eye(XtX.shape[0])
            Xty = X_with_bias.T @ y
            
            # 求解
            coeffs = np.linalg.solve(XtX, Xty)
            self.intercept_ = coeffs[0]
            self.coef_ = coeffs[1:]
            self._fitted = True
        except np.linalg.LinAlgError:
            # 如果求解失败，使用简单均值
            self._fitted = False
        
        return self

    def predict(self, X):
        """
        预测
        
        Args:
            X: 特征矩阵
            
        Returns:
            预测值
        """
        X = np.array(X)
        
        if not self._fitted:
            # 返回均值
            return np.full(X.shape[0], np.nanmean(X, axis=0)[0] if X.shape[1] > 0 else 0)
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        return X @ self.coef_ + self.intercept_

    def predict_proba(self, X):
        """返回预测概率（返回 None，不支持）"""
        return None
