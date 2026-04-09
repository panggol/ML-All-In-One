# -*- coding: utf-8 -*-
"""
特征分布可视化

支持：
- 直方图
- 箱线图
- 成对关系图
"""

import numpy as np
from typing import Optional, List, Union, Tuple
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns


def plot_distribution(
    X: np.ndarray,
    feature_names: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (12, 4),
    title: str = "Feature Distributions",
    save_path: Optional[str] = None,
    **kwargs
) -> plt.Figure:
    """
    绘制特征分布直方图
    
    Args:
        X: 数据，形状 (n_samples, n_features)
        feature_names: 特征名称列表
        figsize: 图形大小
        title: 标题
        save_path: 保存路径
        **kwargs: seaborn.histplot 参数
        
    Returns:
        matplotlib Figure
    """
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    
    n_features = X.shape[1]
    if feature_names is None:
        feature_names = [f"Feature {i}" for i in range(n_features)]
    
    fig, axes = plt.subplots(1, min(n_features, 4), figsize=figsize)
    if n_features == 1:
        axes = [axes]
    
    for i, ax in enumerate(axes):
        sns.histplot(X[:, i], ax=ax, kde=True, **kwargs)
        ax.set_title(feature_names[i])
        ax.set_xlabel("")
    
    fig.suptitle(title, y=1.02)
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig


def plot_boxplot(
    X: np.ndarray,
    feature_names: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (12, 4),
    title: str = "Feature Box Plots",
    save_path: Optional[str] = None,
    **kwargs
) -> plt.Figure:
    """
    绘制特征箱线图
    
    Args:
        X: 数据，形状 (n_samples, n_features)
        feature_names: 特征名称列表
        figsize: 图形大小
        title: 标题
        save_path: 保存路径
        **kwargs: seaborn.boxplot 参数
        
    Returns:
        matplotlib Figure
    """
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    
    n_features = X.shape[1]
    if feature_names is None:
        feature_names = [f"Feature {i}" for i in range(n_features)]
    
    # 转为 DataFrame 便于绘图
    import pandas as pd
    df = pd.DataFrame(X[:, :min(n_features, 10)], columns=feature_names[:min(n_features, 10)])
    
    fig, ax = plt.subplots(figsize=figsize)
    sns.boxplot(data=df, ax=ax, **kwargs)
    ax.set_title(title)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig


def plot_pairplot(
    X: np.ndarray,
    y: Optional[np.ndarray] = None,
    feature_names: Optional[List[str]] = None,
    max_features: int = 4,
    figsize: Tuple[int, int] = (10, 10),
    title: str = "Pairwise Feature Plot",
    save_path: Optional[str] = None,
    **kwargs
) -> plt.Figure:
    """
    绘制成对关系图（散点图矩阵）
    
    Args:
        X: 数据，形状 (n_samples, n_features)
        y: 标签（用于着色）
        feature_names: 特征名称列表
        max_features: 最大显示特征数
        figsize: 图形大小
        title: 标题
        save_path: 保存路径
        **kwargs: seaborn.pairplot 参数
        
    Returns:
        matplotlib Figure
    """
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    
    # 只取前 max_features 个特征
    n_plot = min(X.shape[1], max_features)
    X_plot = X[:, :n_plot]
    
    if feature_names is None:
        feature_names = [f"Feature {i}" for i in range(n_plot)]
    
    import pandas as pd
    df = pd.DataFrame(X_plot, columns=feature_names)
    
    if y is not None:
        df['label'] = y
    
    kwargs.setdefault('diag_kind', 'kde')
    kwargs.setdefault('corner', True)
    
    g = sns.pairplot(data=df, **kwargs)
    g.fig.suptitle(title, y=1.02)
    
    if save_path:
        g.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return g.fig
