"""
数据处理模块 - Data Processing

支持：
- 大数据分块读取
- 样本不均衡处理
- 数据增强
- 数据验证
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# imblearn 为可选依赖
try:
    from imblearn.combine import SMOTEENN, SMOTETomek
    from imblearn.ensemble import BalancedBaggingClassifier, BalancedRandomForestClassifier
    from imblearn.over_sampling import ADASYN, SMOTE, RandomOverSampler
    from imblearn.under_sampling import NearMiss, RandomUnderSampler, TomekLinks
    IMBLEARN_AVAILABLE = True
except ImportError:
    IMBLEARN_AVAILABLE = False
    SMOTEENN = SMOTETomek = BalancedBaggingClassifier = BalancedRandomForestClassifier = None
    ADASYN = SMOTE = RandomOverSampler = None
    NearMiss = RandomUnderSampler = TomekLinks = None


@dataclass
class Dataset:
    """数据集容器"""

    X: np.ndarray
    y: np.ndarray
    feature_names: list[str] | None = None
    target_names: list[str] | None = None
    meta: dict | None = None

    def __post_init__(self):
        if self.meta is None:
            self.meta = {}

    @property
    def shape(self) -> tuple[int, int]:
        return self.X.shape

    @property
    def n_features(self) -> int:
        return self.X.shape[1] if len(self.X.shape) > 1 else 1

    @property
    def n_samples(self) -> int:
        return self.X.shape[0]


class DataLoader:
    """
    数据加载器

    支持：
    - 大数据分块读取
    - 数据验证
    - 自动类型推断
    """

    def __init__(
        self,
        file_path: str | None = None,
        chunksize: int | None = None,
        **read_kwargs,
    ):
        """
        初始化数据加载器

        Args:
            file_path: 数据文件路径
            chunksize: 分块大小 (用于大数据)
            **read_kwargs: pandas read_csv/read_parquet 等参数
        """
        self.file_path = file_path
        self.chunksize = chunksize
        self.read_kwargs = read_kwargs

        # 自动推断文件格式
        if file_path:
            self.file_format = self._infer_format(file_path)
        else:
            self.file_format = None

    def _infer_format(self, file_path: str) -> str:
        """推断文件格式"""
        path = Path(file_path)
        suffix = path.suffix.lower()

        format_map = {
            ".csv": "csv",
            ".parquet": "parquet",
            ".json": "json",
            ".pkl": "pickle",
            ".pickle": "pickle",
            ".feather": "feather",
        }

        return format_map.get(suffix, "csv")

    def load(self, **kwargs) -> Dataset:
        """
        加载数据

        Args:
            **kwargs: 额外的读取参数，会覆盖默认参数

        Returns:
            Dataset 对象
        """
        if not self.file_path:
            raise ValueError("file_path is required")

        read_kwargs = {**self.read_kwargs, **kwargs}

        # 根据格式选择加载方式
        if self.file_format == "csv":
            return self._load_csv(**read_kwargs)
        elif self.file_format == "parquet":
            return self._load_parquet(**read_kwargs)
        elif self.file_format == "json":
            return self._load_json(**read_kwargs)
        elif self.file_format == "pickle":
            return self._load_pickle(**read_kwargs)
        else:
            raise ValueError(f"Unsupported format: {self.file_format}")

    def load_chunked(self) -> Iterator[pd.DataFrame]:
        """
        分块加载数据（用于大数据）

        Yields:
            DataFrame chunks
        """
        if self.file_format == "csv":
            yield from pd.read_csv(
                self.file_path, chunksize=self.chunksize, **self.read_kwargs
            )
        else:
            # 其他格式不支持分块，一次性加载后分块
            df = self.load()
            for i in range(0, len(df), self.chunksize):
                yield df.iloc[i : i + self.chunksize]

    def _load_csv(self, **kwargs) -> Dataset:
        """加载 CSV"""
        if self.chunksize:
            # 分块读取并合并（适用于中等规模数据）
            chunks = []
            for chunk in pd.read_csv(
                self.file_path, chunksize=self.chunksize, **kwargs
            ):
                chunks.append(chunk)

            if len(chunks) == 1:
                df = chunks[0]
            else:
                df = pd.concat(chunks, ignore_index=True)
        else:
            df = pd.read_csv(self.file_path, **kwargs)

        return self._dataframe_to_dataset(df, kwargs.get("target_column"))

    def _load_parquet(self, **kwargs) -> Dataset:
        """加载 Parquet"""
        df = pd.read_parquet(self.file_path, **kwargs)
        return self._dataframe_to_dataset(df, kwargs.get("target_column"))

    def _load_json(self, **kwargs) -> Dataset:
        """加载 JSON"""
        df = pd.read_json(self.file_path, **kwargs)
        return self._dataframe_to_dataset(df, kwargs.get("target_column"))

    def _load_pickle(self, **kwargs) -> Dataset:
        """加载 Pickle"""
        obj = pd.read_pickle(self.file_path, **kwargs)

        if isinstance(obj, pd.DataFrame):
            return self._dataframe_to_dataset(obj, kwargs.get("target_column"))
        elif isinstance(obj, tuple) and len(obj) == 2:
            X, y = obj
            return Dataset(X, y)
        else:
            raise ValueError("Unsupported pickle format")

    def _dataframe_to_dataset(
        self, df: pd.DataFrame, target_column: str | None = None
    ) -> Dataset:
        """将 DataFrame 转换为 Dataset"""
        # 分离特征和标签
        if target_column and target_column in df.columns:
            y = df[target_column].values
            X = df.drop(columns=[target_column]).values
            feature_names = [c for c in df.columns if c != target_column]
        else:
            # 假设最后一列是标签
            if len(df.columns) > 1:
                y = df.iloc[:, -1].values
                X = df.iloc[:, :-1].values
                feature_names = list(df.columns[:-1])
                target_names = [df.columns[-1]]
            else:
                X = df.values
                y = None
                feature_names = list(df.columns)
                target_names = None

        # 处理特征名
        if feature_names is not None and any(isinstance(f, int) for f in feature_names):
            feature_names = [f"feature_{i}" for i in range(len(feature_names))]

        return Dataset(X=X, y=y, feature_names=feature_names, target_names=target_names)


class ImbalanceHandler:
    """
    样本不均衡处理器

    支持多种处理方法：
    - 过采样: SMOTE, ADASYN, RandomOverSampler
    - 欠采样: RandomUnderSampler, TomekLinks, NearMiss
    - 混合: SMOTEENN, SMOTETomek
    - 集成: BalancedBagging, BalancedRandomForest
    """

    # 方法映射
    METHODS = {
        # 过采样
        "smote": SMOTE,
        "adasyn": ADASYN,
        "oversample": RandomOverSampler,
        # 欠采样
        "undersample": RandomUnderSampler,
        "tomek": TomekLinks,
        "nearmiss": NearMiss,
        # 混合
        "smoteenn": SMOTEENN,
        "smotetomek": SMOTETomek,
        # 集成
        "balanced_bagging": BalancedBaggingClassifier,
        "balanced_rf": BalancedRandomForestClassifier,
    }

    @classmethod
    def handle(
        cls, X: np.ndarray, y: np.ndarray, method: str = "smote", **kwargs
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        处理样本不均衡

        Args:
            X: 特征数据
            y: 标签数据
            method: 处理方法 ('smote', 'adasyn', 'oversample', 'undersample', etc.)
            **kwargs: 方法的额外参数

        Returns:
            (X_resampled, y_resampled)
        """
        if not IMBLEARN_AVAILABLE:
            raise ImportError(
                "imbalanced-learn is required for ImbalanceHandler. "
                "Install it with: pip install imbalanced-learn"
            )
        
        method_lower = method.lower()

        if method_lower not in cls.METHODS:
            raise ValueError(
                f"Unknown method: {method}. "
                f"Available methods: {list(cls.METHODS.keys())}"
            )

        sampler_class = cls.METHODS[method_lower]

        # 创建采样器实例
        sampler = sampler_class(**kwargs)

        # 执行采样
        X_resampled, y_resampled = sampler.fit_resample(X, y)

        return X_resampled, y_resampled

    @classmethod
    def list_methods(cls) -> list[str]:
        """列出所有可用的方法"""
        return list(cls.METHODS.keys())

    @classmethod
    def get_method_info(cls, method: str) -> str:
        """获取方法说明"""
        info = {
            "smote": "SMOTE: 合成少数类过采样",
            "adasyn": "ADASYN: 自适应合成过采样",
            "oversample": "随机过采样",
            "undersample": "随机欠采样",
            "tomek": "Tomek Links: 欠采样去除边界样本",
            "nearmiss": "NearMiss: 基于最近邻的欠采样",
            "smoteenn": "SMOTE + ENN: 过采样后清洗",
            "smotetomek": "SMOTE + Tomek: 过采样后清理",
            "balanced_bagging": "平衡 Bagging: 集成欠采样",
            "balanced_rf": "平衡随机森林: 自带类别平衡",
        }
        return info.get(method.lower(), "未知方法")


class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate(X: np.ndarray, y: np.ndarray | None = None) -> dict[str, Any]:
        """
        验证数据

        Args:
            X: 特征数据
            y: 标签数据

        Returns:
            验证报告
        """
        issues = []
        warnings = []

        # 检查 X
        if X is None or len(X) == 0:
            issues.append("数据为空")

        if X is not None:
            # 检查 NaN
            if np.isnan(X).any():
                warnings.append("数据包含 NaN 值")

            # 检查 Inf
            if np.isinf(X).any():
                warnings.append("数据包含 Inf 值")

            # 检查维度
            if len(X.shape) != 2:
                issues.append(f"数据维度错误: {X.shape}")

            # 检查常量特征
            if X.shape[1] > 0:
                std = np.std(X, axis=0)
                if (std == 0).any():
                    warnings.append("存在常量特征")

        # 检查 y
        if y is not None:
            # 检查类别分布
            unique, counts = np.unique(y, return_counts=True)
            min_count = counts.min()
            max_count = counts.max()

            if max_count / min_count > 10:
                warnings.append(f"类别严重不均衡: 最小={min_count}, 最大={max_count}")

            # 检查 NaN
            if np.isnan(y).any():
                issues.append("标签包含 NaN 值")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "statistics": {
                "n_samples": len(X) if X is not None else 0,
                "n_features": X.shape[1] if X is not None and len(X.shape) > 1 else 0,
                "class_distribution": (
                    dict(zip(unique.tolist(), counts.tolist()))
                    if y is not None
                    else None
                ),
            },
        }
