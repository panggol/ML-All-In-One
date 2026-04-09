# -*- coding: utf-8 -*-
"""
预处理可视化模块 - Preprocessing Visualization

支持：
- 特征分布可视化
- 管道可视化
- 降维可视化
"""

from mlkit.preprocessing.visualization.distribution import (
    plot_distribution,
    plot_boxplot,
    plot_pairplot,
)

from mlkit.preprocessing.visualization.pipeline_viz import (
    plot_pipeline,
)

from mlkit.preprocessing.visualization.dimensionality import (
    plot_pca_2d,
    plot_explained_variance,
)

__all__ = [
    # Distribution
    "plot_distribution",
    "plot_boxplot",
    "plot_pairplot",
    # Pipeline
    "plot_pipeline",
    # Dimensionality Reduction
    "plot_pca_2d",
    "plot_explained_variance",
]
