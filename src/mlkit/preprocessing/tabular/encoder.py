# -*- coding: utf-8 -*-
"""
特征编码器 - Encoder

支持：
- LabelEncoder: 标签编码
- OneHotEncoder: 独热编码
- OrdinalEncoder: 序数编码
- TargetEncoder: 目标编码
"""

from typing import Dict, List, Optional, Union
import numpy as np

from mlkit.preprocessing.base import BaseTransformer


class LabelEncoder(BaseTransformer):
    """
    标签编码器
    
    将离散标签转换为 0 到 n_classes-1 的整数
    
    Example:
        ['cat', 'dog', 'cat'] -> [0, 1, 0]
    """

    order = 1  # 在 Imputer 之后

    def __init__(self):
        super().__init__()
        self.classes_: Optional[np.ndarray] = None
        self.class_to_index_: Dict = {}

    def fit(self, y):
        """
        学习所有类别
        
        Args:
            y: 标签数组
        """
        y = np.array(y).ravel()
        self.classes_ = np.unique(y)
        self.class_to_index_ = {cls: idx for idx, cls in enumerate(self.classes_)}
        self._fitted = True
        return self

    def transform(self, y):
        """转换为整数编码"""
        y = np.array(y).ravel()
        
        if self.class_to_index_ is None:
            raise ValueError("Encoder not fitted")
        
        indices = np.array([self.class_to_index_.get(cls, -1) for cls in y])
        
        if np.any(indices == -1):
            unknown_classes = set(y) - set(self.classes_)
            raise ValueError(f"Unknown classes: {unknown_classes}")
        
        return indices

    def inverse_transform(self, y):
        """逆变换"""
        y = np.array(y).ravel()
        return self.classes_[y]

    def get_params(self) -> dict:
        return {}

    def fit_transform(self, y):
        return self.fit(y).transform(y)


class OneHotEncoder(BaseTransformer):
    """
    独热编码器
    
    将分类特征转换为独热向量
    
    Example:
        ['cat', 'dog', 'cat'] -> [[1,0], [0,1], [1,0]]
    """

    order = 1

    def __init__(self, sparse_output: bool = False, handle_unknown: str = 'ignore'):
        """
        Args:
            sparse_output: 是否返回稀疏矩阵
            handle_unknown: 未知类别的处理方式
        """
        super().__init__()
        self.sparse_output = sparse_output
        self.handle_unknown = handle_unknown
        self.categories_: Optional[List[np.ndarray]] = None

    def fit(self, X, y=None):
        """
        学习所有类别
        
        Args:
            X: 二维数组，每列一个特征
            y: 忽略（API 兼容）
        """
        X = self._validate_X(X)
        
        self.categories_ = []
        for col in range(X.shape[1]):
            unique_vals = np.unique(X[:, col])
            self.categories_.append(unique_vals)
        
        self._fitted = True
        return self

    def transform(self, X):
        """转换为独热编码"""
        X = self._validate_X(X)
        
        if self.categories_ is None:
            raise ValueError("Encoder not fitted")
        
        # 计算输出列数
        n_output_cols = sum(len(cats) for cats in self.categories_)
        result = np.zeros((X.shape[0], n_output_cols))
        
        col_offset = 0
        for col_idx, categories in enumerate(self.categories_):
            for cat_idx, cat in enumerate(categories):
                mask = X[:, col_idx] == cat
                result[mask, col_offset + cat_idx] = 1
            col_offset += len(categories)
        
        return result

    def _validate_X(self, X):
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X

    def get_params(self) -> dict:
        return {
            'sparse_output': self.sparse_output,
            'handle_unknown': self.handle_unknown,
        }


class OrdinalEncoder(BaseTransformer):
    """
    序数编码器
    
    将分类特征转换为连续的整数
    
    Example:
        ['low', 'medium', 'high'] -> [0, 1, 2]
    """

    order = 1

    def __init__(self):
        super().__init__()
        self.categories_: Optional[List[np.ndarray]] = None

    def fit(self, X, y=None):
        """学习所有类别"""
        X = self._validate_X(X)
        
        self.categories_ = []
        for col in range(X.shape[1]):
            unique_vals = np.unique(X[:, col])
            self.categories_.append(unique_vals)
        
        self._fitted = True
        return self

    def transform(self, X):
        """转换为序数编码"""
        X = self._validate_X(X)
        
        if self.categories_ is None:
            raise ValueError("Encoder not fitted")
        
        result = np.zeros(X.shape, dtype=int)
        
        for col_idx, categories in enumerate(self.categories_):
            cat_to_idx = {cat: idx for idx, cat in enumerate(categories)}
            for row_idx, val in enumerate(X[:, col_idx]):
                if val in cat_to_idx:
                    result[row_idx, col_idx] = cat_to_idx[val]
        
        return result

    def _validate_X(self, X):
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X

    def get_params(self) -> dict:
        return {}


class TargetEncoder(BaseTransformer):
    """
    目标编码器 (Target Encoder)
    
    使用目标变量的统计信息对分类特征进行编码。
    支持平滑处理以防止过拟合。
    
    编码公式:
        encoded = (n * category_mean + smoothing * global_mean) / (n + smoothing)
    
    其中:
        - n: 该类别在训练集中的出现次数
        - category_mean: 该类别的目标均值
        - global_mean: 全局目标均值
        - smoothing: 平滑参数，越大越趋向于全局均值
    
    Example:
        X = [['cat'], ['dog'], ['cat'], ['mouse']]
        y = [1, 0, 1, 0]
        -> encoded = [[mean_cat], [mean_dog], [mean_cat], [mean_mouse]]
    """

    order = 1  # 在 Imputer 之后

    def __init__(self, smoothing: float = 1.0, min_samples_leaf: int = 1):
        """
        Args:
            smoothing: 平滑参数，控制类别均值向全局均值的偏移程度。
                值越大，平滑效果越强，防止过拟合。
                默认值为 1.0。
            min_samples_leaf: 叶节点最小样本数，用于计算平滑。
                默认值为 1。
        """
        super().__init__()
        self.smoothing = smoothing
        self.min_samples_leaf = min_samples_leaf
        self.encodings_: Optional[Dict[int, Dict]] = None
        self.global_mean_: Optional[float] = None
        self.n_features_in_: Optional[int] = None

    def fit(self, X, y):
        """
        学习目标编码
        
        Args:
            X: 二维数组，每列一个分类特征
            y: 目标变量，一维数组
            
        Returns:
            self
        """
        X = self._validate_X(X)
        y = np.array(y).ravel()
        
        if X.shape[0] != len(y):
            raise ValueError(
                f"X.shape[0]={X.shape[0]} must match len(y)={len(y)}"
            )
        
        self.n_features_in_ = X.shape[1]
        self.global_mean_ = np.mean(y)
        
        self.encodings_ = {}
        
        for col in range(X.shape[1]):
            col_encodings = {}
            unique_categories = np.unique(X[:, col])
            
            for category in unique_categories:
                mask = X[:, col] == category
                category_y = y[mask]
                n = len(category_y)
                
                if n >= self.min_samples_leaf:
                    category_mean = np.mean(category_y)
                    # 应用平滑
                    smoothed_mean = (
                        n * category_mean + self.smoothing * self.global_mean_
                    ) / (n + self.smoothing)
                else:
                    smoothed_mean = self.global_mean_
                
                col_encodings[category] = {
                    'mean': smoothed_mean,
                    'count': n,
                }
            
            self.encodings_[col] = col_encodings
        
        self._fitted = True
        return self

    def transform(self, X):
        """
        应用目标编码
        
        Args:
            X: 二维数组，每列一个分类特征
            
        Returns:
            编码后的数组，形状与输入相同
        """
        X = self._validate_X(X)
        
        if self.encodings_ is None:
            raise ValueError("TargetEncoder not fitted")
        
        X_encoded = np.zeros_like(X, dtype=float)
        
        for col in range(X.shape[1]):
            for row in range(X.shape[0]):
                category = X[row, col]
                if category in self.encodings_[col]:
                    X_encoded[row, col] = self.encodings_[col][category]['mean']
                else:
                    # 未知类别使用全局均值
                    X_encoded[row, col] = self.global_mean_
        
        return X_encoded

    def fit_transform(self, X, y):
        """拟合并转换"""
        return self.fit(X, y).transform(X)

    def get_params(self) -> dict:
        return {
            'smoothing': self.smoothing,
            'min_samples_leaf': self.min_samples_leaf,
        }

    def _validate_X(self, X):
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return X
