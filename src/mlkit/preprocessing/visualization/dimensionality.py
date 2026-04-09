# -*- coding: utf-8 -*-
"""
降维可视化

支持：
- PCA 2D 散点图
- 解释方差比例图
"""

import numpy as np
from typing import Optional, List, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


def plot_pca_2d(
    X: np.ndarray,
    y: Optional[np.ndarray] = None,
    pca=None,
    n_components: int = 2,
    figsize: Tuple[int, int] = (8, 6),
    title: str = "PCA 2D Visualization",
    save_path: Optional[str] = None,
    **kwargs
) -> plt.Figure:
    """
    绘制 PCA 2D 散点图
    
    Args:
        X: 原始数据，形状 (n_samples, n_features)
        y: 标签（用于着色）
        pca: 已拟合的 PCA 实例，如果为 None 则自动拟合
        n_components: 保留的主成分数
        figsize: 图形大小
        title: 标题
        save_path: 保存路径
        **kwargs: seaborn.scatterplot 参数
        
    Returns:
        matplotlib Figure
    """
    from mlkit.preprocessing.dimensionality import PCA
    
    if pca is None:
        pca = PCA(n_components=n_components)
        X_transformed = pca.fit_transform(X)
    else:
        X_transformed = pca.transform(X)
    
    # 取前2个主成分
    X_2d = X_transformed[:, :2]
    
    fig, ax = plt.subplots(figsize=figsize)
    
    if y is not None:
        df = {
            'PC1': X_2d[:, 0],
            'PC2': X_2d[:, 1],
            'label': y.astype(str)
        }
        sns.scatterplot(data=df, x='PC1', y='PC2', hue='label', ax=ax, **kwargs)
    else:
        sns.scatterplot(x=X_2d[:, 0], y=X_2d[:, 1], ax=ax, **kwargs)
    
    # 添加方差解释比例
    if pca.explained_variance_ratio_ is not None:
        var_ratio = pca.explained_variance_ratio_[:2]
        ax.set_xlabel(f'PC1 ({var_ratio[0]*100:.1f}%)')
        ax.set_ylabel(f'PC2 ({var_ratio[1]*100:.1f}%)')
    
    ax.set_title(title)
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig


def plot_explained_variance(
    pca,
    figsize: Tuple[int, int] = (10, 4),
    title: str = "Explained Variance Ratio",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    绘制 PCA 解释方差比例图
    
    Args:
        pca: 已拟合的 PCA 实例
        figsize: 图形大小
        title: 标题
        save_path: 保存路径
        
    Returns:
        matplotlib Figure
    """
    if pca.explained_variance_ratio_ is None:
        raise ValueError("PCA not fitted")
    
    n_components = len(pca.explained_variance_ratio_)
    
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    
    # 单独的方差比例
    ax1 = axes[0]
    ax1.bar(range(1, n_components + 1), pca.explained_variance_ratio_, alpha=0.7)
    ax1.set_xlabel('Principal Component')
    ax1.set_ylabel('Explained Variance Ratio')
    ax1.set_title('Individual')
    
    # 累计方差比例
    ax2 = axes[1]
    cumsum = np.cumsum(pca.explained_variance_ratio_)
    ax2.plot(range(1, n_components + 1), cumsum, 'bo-')
    ax2.axhline(y=0.95, color='r', linestyle='--', label='95%')
    ax2.axhline(y=0.99, color='g', linestyle='--', label='99%')
    ax2.set_xlabel('Number of Components')
    ax2.set_ylabel('Cumulative Explained Variance')
    ax2.set_title('Cumulative')
    ax2.legend()
    
    fig.suptitle(title, y=1.02)
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig
