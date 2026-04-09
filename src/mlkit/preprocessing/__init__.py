# -*- coding: utf-8 -*-
"""
预处理模块 - Preprocessing

支持：
- 表格数据预处理 (缩放、编码、缺失值)
- 文本预处理 (分词、向量化)
- 降维 (PCA)
- 可训练预处理
- Pipeline 管道
- 可视化
"""

# Base
from mlkit.preprocessing.base import (
    BaseTransformer,
    FitMixin,
    TransformMixin,
    StageMode,
)

# Tabular
from mlkit.preprocessing.tabular import (
    StandardScaler,
    MinMaxScaler,
    RobustScaler,
    LabelEncoder,
    OneHotEncoder,
    OrdinalEncoder,
    SimpleImputer,
    KNNImputer,
)

# Text
from mlkit.preprocessing.text import (
    BaseTokenizer,
    WhitespaceTokenizer,
    CharacterTokenizer,
    BaseVectorizer,
    CountVectorizer,
    TFIDFVectorizer,
)

# Dimensionality
from mlkit.preprocessing.dimensionality import PCA

# Trainable
from mlkit.preprocessing.trainable import (
    TrainablePreprocessor,
    EmbeddingPreprocessor,
    LearnedTokenizer,
    ParameterizedAugmentation,
    FeatureLearner,
    HybridPipeline,
)

# Pipeline
from mlkit.preprocessing.pipeline import Pipeline

# Visualization
from mlkit.preprocessing.visualization import (
    plot_distribution,
    plot_boxplot,
    plot_pairplot,
    plot_pipeline,
    plot_pca_2d,
    plot_explained_variance,
)

__all__ = [
    # Base
    "BaseTransformer",
    "FitMixin", 
    "TransformMixin",
    "StageMode",
    # Tabular
    "StandardScaler",
    "MinMaxScaler", 
    "RobustScaler",
    "LabelEncoder",
    "OneHotEncoder",
    "OrdinalEncoder",
    "SimpleImputer",
    "KNNImputer",
    # Text
    "BaseTokenizer",
    "WhitespaceTokenizer",
    "CharacterTokenizer",
    "BaseVectorizer",
    "CountVectorizer",
    "TFIDFVectorizer",
    # Dimensionality
    "PCA",
    # Trainable
    "TrainablePreprocessor",
    "EmbeddingPreprocessor",
    "LearnedTokenizer",
    "ParameterizedAugmentation",
    "FeatureLearner",
    "HybridPipeline",
    # Pipeline
    "Pipeline",
    # Visualization
    "plot_distribution",
    "plot_boxplot",
    "plot_pairplot",
    "plot_pipeline",
    "plot_pca_2d",
    "plot_explained_variance",
]
