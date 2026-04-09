# -*- coding: utf-8 -*-
"""
特征缩放器 - Scaler

支持：
- StandardScaler: 标准化 (均值0, 方差1)
- MinMaxScaler: 归一化 (0-1范围)
- RobustScaler: 鲁棒缩放 (中位数/四分位)
- QuantileTransformer: 分位数变换
- PowerTransformer: 幂变换
"""

from typing import Optional, Union
import numpy as np
from scipy import stats

from mlkit.preprocessing.base import BaseTransformer


class StandardScaler(BaseTransformer):
    """
    标准化缩放器
    
    将特征转换为均值为0，标准差为1的分布
    
    transform = (X - mean) / std
    """

    order = 2  # 在 Imputer, Encoder 之后

    def __init__(self, with_mean: bool = True, with_std: bool = True):
        """
        Args:
            with_mean: 是否中心化
            with_std: 是否缩放到单位方差
        """
        super().__init__()
        self.with_mean = with_mean
        self.with_std = with_std
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.n_features_in_: Optional[int] = None

    def fit(self, X, y=None):
        """学习均值和标准差"""
        X = self._validate_X(X)
        self.n_features_in_ = X.shape[1]
        
        if self.with_mean:
            self.mean_ = np.mean(X, axis=0)
        else:
            self.mean_ = np.zeros(X.shape[1])
        
        if self.with_std:
            self.std_ = np.std(X, axis=0)
            # 避免除零
            self.std_[self.std_ == 0] = 1.0
        else:
            self.std_ = np.ones(X.shape[1])
        
        self._fitted = True
        return self

    def transform(self, X):
        """应用标准化"""
        X = self._validate_X(X)
        
        if self.with_mean:
            X = X - self.mean_
        
        if self.with_std:
            X = X / self.std_
        
        return X

    def inverse_transform(self, X):
        """逆变换"""
        X = self._validate_X(X)
        return X * self.std_ + self.mean_

    def _validate_X(self, X: np.ndarray) -> np.ndarray:
        """验证输入"""
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        return X

    def get_params(self) -> dict:
        return {
            'with_mean': self.with_mean,
            'with_std': self.with_std,
        }


class MinMaxScaler(BaseTransformer):
    """
    最小最大缩放器
    
    将特征缩放到 [0, 1] 范围
    
    transform = (X - min) / (max - min)
    """

    order = 2

    def __init__(self, feature_range: tuple = (0, 1)):
        """
        Args:
            feature_range: 目标范围
        """
        super().__init__()
        self.feature_range = feature_range
        self.min_: Optional[np.ndarray] = None
        self.max_: Optional[np.ndarray] = None
        self.n_features_in_: Optional[int] = None
        self.scale_: Optional[np.ndarray] = None

    def fit(self, X, y=None):
        """学习最小值和最大值"""
        X = self._validate_X(X)
        self.n_features_in_ = X.shape[1]
        
        self.min_ = np.min(X, axis=0)
        self.max_ = np.max(X, axis=0)
        
        # 计算缩放因子
        self.scale_ = self.max_ - self.min_
        # 避免除零
        self.scale_[self.scale_ == 0] = 1.0
        
        self._fitted = True
        return self

    def transform(self, X):
        """应用归一化"""
        X = self._validate_X(X)
        X_scaled = (X - self.min_) / self.scale_
        
        # 应用目标范围
        min_val, max_val = self.feature_range
        X_scaled = X_scaled * (max_val - min_val) + min_val
        
        return X_scaled

    def inverse_transform(self, X):
        """逆变换"""
        X = self._validate_X(X)
        
        min_val, max_val = self.feature_range
        X = (X - min_val) / (max_val - min_val)
        X = X * self.scale_ + self.min_
        
        return X

    def _validate_X(self, X: np.ndarray) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        return X

    def get_params(self) -> dict:
        return {
            'feature_range': self.feature_range,
        }


class RobustScaler(BaseTransformer):
    """
    鲁棒缩放器
    
    使用中位数和四分位距，对异常值更鲁棒
    
    transform = (X - median) / IQR
    """

    order = 2

    def __init__(self, with_centering: bool = True, with_scaling: bool = True):
        """
        Args:
            with_centering: 是否中心化
            with_scaling: 是否缩放
        """
        super().__init__()
        self.with_centering = with_centering
        self.with_scaling = with_scaling
        self.center_: Optional[np.ndarray] = None
        self.scale_: Optional[np.ndarray] = None
        self.n_features_in_: Optional[int] = None

    def fit(self, X, y=None):
        """学习中位数和四分位距"""
        X = self._validate_X(X)
        self.n_features_in_ = X.shape[1]
        
        if self.with_centering:
            self.center_ = np.median(X, axis=0)
        else:
            self.center_ = np.zeros(X.shape[1])
        
        if self.with_scaling:
            q75 = np.percentile(X, 75, axis=0)
            q25 = np.percentile(X, 25, axis=0)
            self.scale_ = q75 - q25
            self.scale_[self.scale_ == 0] = 1.0
        else:
            self.scale_ = np.ones(X.shape[1])
        
        self._fitted = True
        return self

    def transform(self, X):
        """应用鲁棒缩放"""
        X = self._validate_X(X)
        return (X - self.center_) / self.scale_

    def inverse_transform(self, X):
        """逆变换"""
        X = self._validate_X(X)
        return X * self.scale_ + self.center_

    def _validate_X(self, X: np.ndarray) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        return X

    def get_params(self) -> dict:
        return {
            'with_centering': self.with_centering,
            'with_scaling': self.with_scaling,
        }


class QuantileTransformer(BaseTransformer):
    """
    分位数变换器 (Quantile Transformer)
    
    将特征映射到指定的分布（uniform 或 normal）。
    使用分位数信息进行变换，对异常值鲁棒。
    
    变换过程:
    1. 计算每个特征的 rank
    2. 将 rank 映射到 [0, 1] 区间 (n_quantiles)
    3. 使用逆 CDF 映射到目标分布
    
    Example:
        X = [[1, 2], [2, 3], [3, 4], [4, 5]]
        -> uniform: [0.125, 0.375, 0.625, 0.875] (默认 n_quantiles=4)
    """

    order = 2

    def __init__(
        self,
        n_quantiles: int = 1000,
        output_distribution: str = 'uniform',
        ignore_implicit_zeros: bool = False
    ):
        """
        Args:
            n_quantiles: 分位数数量，必须小于等于样本数。
                默认值为 1000。
            output_distribution: 输出分布类型。
                - 'uniform': 均匀分布 [0, 1]
                - 'normal': 标准正态分布
                默认值为 'uniform'。
            ignore_implicit_zeros: 是否忽略隐含的零值（用于稀疏矩阵）。
                默认值为 False。
        """
        super().__init__()
        
        valid_distributions = ['uniform', 'normal']
        if output_distribution not in valid_distributions:
            raise ValueError(
                f"output_distribution must be one of {valid_distributions}, "
                f"got {output_distribution}"
            )
        
        self.n_quantiles = n_quantiles
        self.output_distribution = output_distribution
        self.ignore_implicit_zeros = ignore_implicit_zeros
        
        self.quantiles_: Optional[np.ndarray] = None
        self.references_: Optional[np.ndarray] = None
        self.n_features_in_: Optional[int] = None

    def fit(self, X, y=None):
        """
        学习分位数
        
        Args:
            X: 训练数据
            y: 忽略（API 兼容）
            
        Returns:
            self
        """
        X = self._validate_X(X).astype(float)
        
        n_samples, n_features = X.shape
        self.n_features_in_ = n_features
        
        # 确定分位数数量
        self.n_quantiles = min(self.n_quantiles, n_samples)
        
        # 计算参考值 (使用中点)
        self.references_ = np.linspace(0, 1, self.n_quantiles)
        
        # 计算每个特征的分位数
        self.quantiles_ = np.zeros((self.n_quantiles, n_features))
        
        for col in range(n_features):
            col_data = X[:, col]
            valid_data = col_data[~np.isnan(col_data)]
            
            if len(valid_data) == 0:
                self.quantiles_[:, col] = 0
            else:
                self.quantiles_[:, col] = np.quantile(valid_data, self.references_)
        
        self._fitted = True
        return self

    def transform(self, X):
        """
        应用分位数变换
        
        Args:
            X: 输入数据
            
        Returns:
            变换后的数据
        """
        X = self._validate_X(X).astype(float)
        
        if self.quantiles_ is None:
            raise ValueError("QuantileTransformer not fitted")
        
        X_transformed = np.zeros_like(X)
        
        for col in range(X.shape[1]):
            col_data = X[:, col]
            valid_mask = ~np.isnan(col_data)
            
            if not np.any(valid_mask):
                X_transformed[:, col] = np.nan
                continue
            
            valid_data = col_data[valid_mask]
            
            # 使用与 inverse_transform 一致的插值方法
            # 使用 references_ 作为输入，使用 quantiles_ 作为输出
            if self.output_distribution == 'uniform':
                # 对于 uniform，直接用 references_ 插值
                X_transformed[valid_mask, col] = np.interp(
                    valid_data,
                    self.quantiles_[:, col],
                    self.references_
                )
            else:  # normal
                # 对于 normal，先转到 uniform，再应用 ppf
                uniform_values = np.interp(
                    valid_data,
                    self.quantiles_[:, col],
                    self.references_
                )
                # 避免极端值
                uniform_values = np.clip(uniform_values, 1e-10, 1 - 1e-10)
                X_transformed[valid_mask, col] = stats.norm.ppf(uniform_values)
        
        return X_transformed

    def fit_transform(self, X, y=None):
        """拟合并转换"""
        return self.fit(X, y).transform(X)

    def inverse_transform(self, X):
        """
        逆变换 - 从变换后的分布恢复到原始分布
        
        Args:
            X: 变换后的数据
            
        Returns:
            原始空间的数据
        """
        X = self._validate_X(X).astype(float)
        
        if self.quantiles_ is None:
            raise ValueError("QuantileTransformer not fitted")
        
        X_inv = np.zeros_like(X)
        
        for col in range(X.shape[1]):
            col_data = X[:, col]
            valid_mask = ~np.isnan(col_data)
            
            if not np.any(valid_mask):
                continue
            
            valid_data = col_data[valid_mask]
            
            # 从目标分布映射回 uniform
            if self.output_distribution == 'uniform':
                uniform_values = valid_data
            else:  # normal
                uniform_values = stats.norm.cdf(valid_data)
            
            # 从 uniform 映射到原始值
            X_inv[valid_mask, col] = np.interp(
                uniform_values,
                self.references_,
                self.quantiles_[:, col]
            )
        
        return X_inv

    def _validate_X(self, X: np.ndarray) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return X

    def get_params(self) -> dict:
        return {
            'n_quantiles': self.n_quantiles,
            'output_distribution': self.output_distribution,
            'ignore_implicit_zeros': self.ignore_implicit_zeros,
        }



class PowerTransformer(BaseTransformer):
    """
    幂变换器 (Power Transformer)
    
    通过应用幂变换使特征更接近高斯分布。
    支持两种方法:
    - Box-Cox: 要求数据严格为正 (x > 0)
    - Yeo-Johnson: 可以处理零值和负值
    
    Example:
        X = [[1, 2], [2, 3], [3, 4], [4, 5]]
        -> 更接近正态分布
    """

    order = 2

    def __init__(
        self,
        method: str = 'yeo-johnson',
        standardize: bool = True
    ):
        """
        Args:
            method: 幂变换方法
                - 'box-cox': Box-Cox 变换，要求输入严格为正
                - 'yeo-johnson': Yeo-Johnson 变换，可以处理零和负值
                默认值为 'yeo-johnson'。
            standardize: 是否在变换后进行标准化。
                默认值为 True。
        """
        super().__init__()
        
        valid_methods = ['box-cox', 'yeo-johnson']
        if method not in valid_methods:
            raise ValueError(
                f"method must be one of {valid_methods}, got {method}"
            )
        
        self.method = method
        self.standardize = standardize
        
        self.lambdas_: Optional[np.ndarray] = None
        self.tmu_: Optional[np.ndarray] = None  # 标准化参数
        self.tstd_: Optional[np.ndarray] = None
        self.n_features_in_: Optional[int] = None

    def fit(self, X, y=None):
        """
        学习最优 lambda 参数
        
        Args:
            X: 训练数据
            y: 忽略（API 兼容）
            
        Returns:
            self
        """
        X = self._validate_X(X).astype(float)
        
        n_samples, n_features = X.shape
        self.n_features_in_ = n_features
        
        self.lambdas_ = np.zeros(n_features)
        self.tmu_ = np.zeros(n_features)
        self.tstd_ = np.ones(n_features)
        
        for col in range(n_features):
            col_data = X[:, col]
            valid_data = col_data[~np.isnan(col_data)]
            
            if len(valid_data) == 0:
                self.lambdas_[col] = 0
                continue
            
            if self.method == 'yeo-johnson':
                self.lambdas_[col] = self._find_lambda_yj(valid_data)
            else:  # box-cox
                self.lambdas_[col] = self._find_lambda_bc(valid_data)
            
            # 如果需要标准化，拟合标准化参数
            if self.standardize:
                # 计算变换后的均值和标准差
                transformed = self._transform_col(valid_data, self.lambdas_[col])
                self.tmu_[col] = np.mean(transformed)
                self.tstd_[col] = np.std(transformed)
                if self.tstd_[col] == 0:
                    self.tstd_[col] = 1
        
        self._fitted = True
        return self

    def transform(self, X):
        """
        应用幂变换
        
        Args:
            X: 输入数据
            
        Returns:
            变换后的数据
        """
        X = self._validate_X(X).astype(float)
        
        if self.lambdas_ is None:
            raise ValueError("PowerTransformer not fitted")
        
        X_transformed = np.zeros_like(X)
        
        for col in range(X.shape[1]):
            col_data = X[:, col]
            valid_mask = ~np.isnan(col_data)
            valid_data = col_data[valid_mask]
            
            if len(valid_data) == 0:
                continue
            
            # 应用幂变换
            transformed = self._transform_col(valid_data, self.lambdas_[col])
            
            # 标准化
            if self.standardize:
                transformed = (transformed - self.tmu_[col]) / self.tstd_[col]
            
            X_transformed[valid_mask, col] = transformed
        
        return X_transformed

    def fit_transform(self, X, y=None):
        """拟合并转换"""
        return self.fit(X, y).transform(X)

    def inverse_transform(self, X):
        """
        逆变换
        
        Args:
            X: 变换后的数据
            
        Returns:
            原始数据
        """
        X = self._validate_X(X).astype(float)
        
        if self.lambdas_ is None:
            raise ValueError("PowerTransformer not fitted")
        
        X_inv = np.zeros_like(X)
        
        for col in range(X.shape[1]):
            col_data = X[:, col]
            valid_mask = ~np.isnan(col_data)
            valid_data = col_data[valid_mask]
            
            if len(valid_data) == 0:
                continue
            
            # 逆标准化
            if self.standardize:
                valid_data = valid_data * self.tstd_[col] + self.tmu_[col]
            
            # 逆幂变换
            X_inv[valid_mask, col] = self._inverse_transform_col(
                valid_data, self.lambdas_[col]
            )
        
        return X_inv

    def _find_lambda_yj(self, x: np.ndarray) -> float:
        """使用最大似然估计找到最优 lambda (Yeo-Johnson)"""
        def neg_log_likelihood(lmbda, x):
            t = self._transform_col(x, lmbda)
            n = len(t)
            # 使用数值稳定的方式
            if np.std(t) == 0:
                return np.inf
            return n / 2 * np.log(np.var(t)) + (1 + lmbda / 2) * np.sum(np.log(np.abs(x) + 1))
        
        # 网格搜索
        best_lambda = 0
        best_ll = np.inf
        
        for lmbda in np.linspace(-2, 2, 21):
            ll = neg_log_likelihood(lmbda, x)
            if ll < best_ll:
                best_ll = ll
                best_lambda = lmbda
        
        return best_lambda

    def _find_lambda_bc(self, x: np.ndarray) -> float:
        """使用最大似然估计找到最优 lambda (Box-Cox)"""
        x_pos = x[x > 0]
        if len(x_pos) < 2:
            return 1.0
        
        def neg_log_likelihood(lmbda, x):
            if abs(lmbda) < 1e-10:
                t = np.log(x)
            else:
                t = (np.power(x, lmbda) - 1) / lmbda
            n = len(t)
            if np.var(t) == 0:
                return np.inf
            return n / 2 * np.log(np.var(t)) + (lmbda - 1) * np.sum(np.log(x))
        
        # 网格搜索
        best_lambda = 1
        best_ll = np.inf
        
        for lmbda in np.linspace(-2, 5, 41):
            if lmbda <= 0:
                continue
            ll = neg_log_likelihood(lmbda, x_pos)
            if ll < best_ll:
                best_ll = ll
                best_lambda = lmbda
        
        return best_lambda

    def _transform_col(self, x: np.ndarray, lmbda: float) -> np.ndarray:
        """对单列应用幂变换"""
        if self.method == 'yeo-johnson':
            return self._yj_transform(x, lmbda)
        else:
            return self._bc_transform(x, lmbda)

    def _yj_transform(self, x: np.ndarray, lmbda: float) -> np.ndarray:
        """Yeo-Johnson 变换"""
        if abs(lmbda) < 1e-10:
            return np.log1p(x)
        
        # 处理不同的情况
        pos_mask = x >= 0
        neg_mask = x < 0
        
        result = np.zeros_like(x, dtype=float)
        
        if np.any(pos_mask):
            result[pos_mask] = (np.power(x[pos_mask] + 1, lmbda) - 1) / lmbda
        
        if np.any(neg_mask):
            # 对于负值，使用不同的公式
            if abs(lmbda - 2) < 1e-10:
                result[neg_mask] = -np.log1p(-x[neg_mask])
            else:
                result[neg_mask] = -(
                    np.power(-x[neg_mask] + 1, 2 - lmbda) - 1
                ) / (2 - lmbda)
        
        return result

    def _bc_transform(self, x: np.ndarray, lmbda: float) -> np.ndarray:
        """Box-Cox 变换 - 要求输入严格为正"""
        x = x[x > 0]
        if len(x) == 0:
            return np.array([])
        
        if abs(lmbda) < 1e-10:
            return np.log(x)
        
        return (np.power(x, lmbda) - 1) / lmbda

    def _inverse_transform_col(self, x: np.ndarray, lmbda: float) -> np.ndarray:
        """对单列应用逆幂变换"""
        if self.method == 'yeo-johnson':
            return self._yj_inverse_transform(x, lmbda)
        else:
            return self._bc_inverse_transform(x, lmbda)

    def _yj_inverse_transform(self, x: np.ndarray, lmbda: float) -> np.ndarray:
        """Yeo-Johnson 逆变换"""
        if abs(lmbda) < 1e-10:
            return np.expm1(x)
        
        # 处理不同的情况
        # y >= 0 时
        mask = x >= 0
        result = np.zeros_like(x, dtype=float)
        
        if np.any(mask):
            result[mask] = np.power(x[mask] * lmbda + 1, 1/lmbda) - 1
        
        # y < 0 时
        if np.any(~mask):
            result[~mask] = 1 - np.power(-(2 - lmbda) * x[~mask] + 1, 1/(2 - lmbda))
        
        return result

    def _bc_inverse_transform(self, x: np.ndarray, lmbda: float) -> np.ndarray:
        """Box-Cox 逆变换"""
        if abs(lmbda) < 1e-10:
            return np.exp(x)
        
        return np.power(lmbda * x + 1, 1/lmbda)

    def _validate_X(self, X: np.ndarray) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return X

    def get_params(self) -> dict:
        return {
            'method': self.method,
            'standardize': self.standardize,
        }
