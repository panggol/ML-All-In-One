"""
mlkit.explainability.plots — SHAP 可视化图生成

将 shap.Explainer 的输出转换为 base64 编码的 PNG 图片，
供前端通过 <img src="data:image/png;base64,..." /> 直接渲染。

支持图类型：beeswarm / bar / waterfall
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class SHAPPlotResult:
    """SHAP 可视化图结果"""
    image_base64: str
    image_type: str  # "beeswarm" | "bar" | "waterfall" | "force"
    width_px: int
    height_px: int
    computation_time_ms: float


# =============================================================================
# 辅助函数
# =============================================================================

def _import_shap() -> Any:
    """导入 shap 库"""
    try:
        import shap
        return shap
    except ImportError:
        raise ImportError(
            "shap 库未安装。请运行：pip install shap"
        )


def shap_values_to_base64(
    shap_values: Any,
    expected_value: Union[float, List[float]],
    features: Optional[Any] = None,
    feature_names: Optional[List[str]] = None,
    plot_type: str = "beeswarm",
    max_display: int = 20,
    figsize: tuple = (12, 8),
) -> SHAPPlotResult:
    """
    将 SHAP 值转换为 base64 编码的 PNG 图片。

    参数：
        shap_values: shap.Explainer.shap_values() 的返回值
        expected_value: 基准值（截距）
        features: 特征数据矩阵（numpy array，shape 同 shap_values）
        feature_names: 特征名列表
        plot_type: 图类型，"beeswarm" | "bar" | "waterfall"
        max_display: 最多显示特征数（bar 图有效）
        figsize: 图表尺寸（宽, 高）

    返回：
        SHAPPlotResult（含 base64 编码的 PNG 图片）
    """
    start_time = time.perf_counter()

    shap_lib = _import_shap()
    plt = _import_matplotlib()

    shap_values = np.array(shap_values)
    if shap_values.ndim == 1:
        shap_values = shap_values.reshape(1, -1)

    # 设置特征名
    if feature_names is None:
        n_features = shap_values.shape[1]
        feature_names = [f"feature_{i}" for i in range(n_features)]

    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })

    buffer = io.BytesIO()

    try:
        if plot_type == "beeswarm":
            # 蜂群图：展示特征值与 SHAP 值的关系
            plt.figure(figsize=figsize)

            # shap 0.51+：将 shap_values 包装为 Explanation 对象
            # base_values 需要是 1D 数组格式，否则 shap 内部报错
            _bv = np.array([float(expected_value)]) if isinstance(expected_value, (int, float)) else np.array(expected_value)
            explanation = shap_lib.Explanation(
                values=shap_values,
                base_values=_bv,
                data=features,
                feature_names=feature_names,
            )
            if features is not None:
                shap_lib.plots.beeswarm(
                    explanation,
                    show=False,
                    max_display=max_display,
                )
            else:
                # 无特征值数据时使用条形图替代
                logger.warning("无 features 数据，beeswarm 图降级为 bar 图")
                plot_type = "bar"
                plt.figure(figsize=(10, max_display * 0.4 + 2))
                shap_lib.plots.bar(
                    explanation,
                    show=False,
                    max_display=max_display,
                )

        elif plot_type == "bar":
            # 柱状图：全局特征重要性
            plt.figure(figsize=(10, max_display * 0.4 + 2))
            _bv = np.array([float(expected_value)]) if isinstance(expected_value, (int, float)) else np.array(expected_value)
            explanation = shap_lib.Explanation(
                values=shap_values,
                base_values=_bv,
                data=features,
                feature_names=feature_names,
            )
            shap_lib.plots.bar(
                explanation,
                show=False,
                max_display=max_display,
            )

        elif plot_type == "waterfall":
            # 瀑布图：单样本解释
            if shap_values.shape[0] > 1:
                # 多样本时取第一个样本
                sv = shap_values[0:1]
            else:
                sv = shap_values

            if features is not None:
                feat = features[0:1] if hasattr(features, "__len__") else features
            else:
                feat = None

            plt.figure(figsize=figsize)
            shap_lib.plots.waterfall(
                shap_lib.Explanation(
                    values=sv.ravel(),
                    base_values=float(expected_value) if isinstance(expected_value, (int, float)) else float(expected_value[0]),
                    data=feat.ravel() if feat is not None else None,
                    feature_names=feature_names,
                ),
                show=False,
                max_display=max_display,
            )

        elif plot_type == "force":
            # 力图：单样本（将多样本转为力图）
            plt.figure(figsize=(20, 4))
            shap_lib.plots.force(
                float(expected_value) if isinstance(expected_value, (int, float)) else float(expected_value[0]),
                shap_values[0].ravel() if shap_values.shape[0] > 0 else shap_values.ravel(),
                features[0].ravel() if features is not None and hasattr(features, "__len__") else None,
                feature_names=feature_names,
                matplotlib=True,
                show=False,
            )

        else:
            raise ValueError(f"不支持的 plot_type：{plot_type}，支持：beeswarm / bar / waterfall / force")

        # 保存到 buffer
        plt.savefig(
            buffer,
            format="png",
            bbox_inches="tight",
            dpi=100,
            facecolor="white",
            edgecolor="none",
        )
        buffer.seek(0)

        # 编码为 base64
        import base64
        img_bytes = buffer.getvalue()
        b64_str = base64.b64encode(img_bytes).decode("utf-8")

        # 获取图片尺寸
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(img_bytes))
        width_px, height_px = img.size

        plt.close("all")

    except Exception as e:
        plt.close("all")
        raise RuntimeError(f"SHAP 图生成失败（{plot_type}）：{e}") from e
    finally:
        buffer.close()

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"SHAP {plot_type} 图生成完成：{elapsed_ms:.1f}ms，尺寸={width_px}×{height_px}")

    return SHAPPlotResult(
        image_base64=b64_str,
        image_type=plot_type,
        width_px=width_px,
        height_px=height_px,
        computation_time_ms=elapsed_ms,
    )


def _import_matplotlib() -> Any:
    """导入 matplotlib"""
    try:
        import matplotlib
        matplotlib.use("Agg")  # 非交互式后端
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        raise ImportError(
            "matplotlib 库未安装。请运行：pip install matplotlib"
        )


# =============================================================================
# 便捷函数
# =============================================================================

def generate_beeswarm_plot(
    shap_values: Any,
    expected_value: float,
    features: Optional[Any] = None,
    feature_names: Optional[List[str]] = None,
    max_display: int = 20,
) -> SHAPPlotResult:
    """生成蜂群图（Beeswarm Plot）"""
    return shap_values_to_base64(
        shap_values=shap_values,
        expected_value=expected_value,
        features=features,
        feature_names=feature_names,
        plot_type="beeswarm",
        max_display=max_display,
    )


def generate_bar_plot(
    shap_values: Any,
    expected_value: float,
    feature_names: Optional[List[str]] = None,
    max_display: int = 20,
) -> SHAPPlotResult:
    """生成柱状图（Bar Plot）"""
    return shap_values_to_base64(
        shap_values=shap_values,
        expected_value=expected_value,
        features=None,
        feature_names=feature_names,
        plot_type="bar",
        max_display=max_display,
    )


def generate_waterfall_plot(
    shap_values: Any,
    expected_value: float,
    feature_values: Optional[Any] = None,
    feature_names: Optional[List[str]] = None,
    max_display: int = 20,
) -> SHAPPlotResult:
    """生成瀑布图（Waterfall Plot）— 单样本解释"""
    return shap_values_to_base64(
        shap_values=shap_values,
        expected_value=expected_value,
        features=feature_values,
        feature_names=feature_names,
        plot_type="waterfall",
        max_display=max_display,
    )
