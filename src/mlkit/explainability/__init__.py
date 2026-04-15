"""
mlkit.explainability — 模型可解释性核心包

提供 SHAP 值计算和 ICE 曲线生成功能。
支持 TreeExplainer、GradientExplainer、KernelExplainer 自动选择。

Usage:
    from mlkit.explainability import compute_global_shap, compute_local_shap

    shap_result = compute_global_shap(model, X_test, model_type="xgboost")
    local_result = compute_local_shap(model, sample, feature_names=["f1", "f2"])
"""

from mlkit.explainability.core import (
    SHAPResult,
    LocalSHAPResult,
    FeatureContribution,
    FeatureImportance,
    get_explainer,
    compute_global_shap,
    compute_local_shap,
    is_tree_model,
    is_neural_network,
    detect_model_type,
)

from mlkit.explainability.plots import (
    SHAPPlotResult,
    generate_beeswarm_plot,
    generate_bar_plot,
    generate_waterfall_plot,
    shap_values_to_base64,
)

from mlkit.explainability.ice import (
    ICEResult,
    ICECurve,
    ICEPoint,
    compute_ice_curves,
)

__version__ = "1.0.0"
__all__ = [
    # core
    "SHAPResult",
    "LocalSHAPResult",
    "FeatureContribution",
    "FeatureImportance",
    "get_explainer",
    "compute_global_shap",
    "compute_local_shap",
    "is_tree_model",
    "is_neural_network",
    "detect_model_type",
    # plots
    "SHAPPlotResult",
    "generate_beeswarm_plot",
    "generate_bar_plot",
    "generate_waterfall_plot",
    "shap_values_to_base64",
    # ice
    "ICEResult",
    "ICECurve",
    "ICEPoint",
    "compute_ice_curves",
]
