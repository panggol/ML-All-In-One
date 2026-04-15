"""
mlkit.explainability.core — SHAP 值计算核心逻辑

Explainer 自动选择策略：
1. TreeExplainer（优先）：XGBoost / LightGBM / CatBoost / RandomForest / ExtraTrees / sklearn GBDT
2. GradientExplainer：MLP / PyTorch 神经网络
3. KernelExplainer（兜底）：其他所有模型

Author: Code Engineer Subagent
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# 数据类
# =============================================================================


@dataclass
class FeatureImportance:
    """单个特征的重要性条目"""
    feature: str
    importance: float  # 均值绝对 SHAP 值
    rank: int


@dataclass
class FeatureContribution:
    """单个特征的 SHAP 贡献"""
    feature: str
    value: float
    original_value: Any
    direction: str  # "positive" | "negative" | "neutral"

    def __post_init__(self):
        if self.direction not in ("positive", "negative", "neutral"):
            if self.value > 0.001:
                self.direction = "positive"
            elif self.value < -0.001:
                self.direction = "negative"
            else:
                self.direction = "neutral"


@dataclass
class SHAPResult:
    """全局 SHAP 计算结果"""
    feature_names: List[str]
    shap_values: List[List[float]]  # (n_samples, n_features)
    expected_value: float
    feature_importance: List[FeatureImportance]
    sample_count: int
    computation_time_ms: float
    explainer_type: str


@dataclass
class LocalSHAPResult:
    """局部（单样本）SHAP 计算结果"""
    sample: Dict[str, Any]
    shap_values: List[FeatureContribution]
    expected_value: float
    model_output: float
    output_class: Optional[str] = None
    computation_time_ms: float = 0.0


# =============================================================================
# 模型类型检测
# =============================================================================

# 已知的树模型类型（类名的特征子串）
TREE_MODEL_TYPES = frozenset({
    "xgboost", "xgbclassifier", "xgbregressor",
    "lightgbm", "lgbclassifier", "lgbregressor",
    "catboost", "cbclassifier", "cbregressor",
    "randomforest", "randomforestclassifier", "randomforestregressor",
    "extratrees", "extratreesclassifier", "extratreesregressor",
    "gradientboosting", "gradientboostingclassifier", "gradientboostingregressor",
    "histgradientboosting", "histgradientboostingclassifier", "histgradientboostingregressor",
    "adaboost", "adaboostclassifier",
    "decisiontree", "decisiontreeclassifier", "decisiontreeregressor",
})

# 已知的神经网络类型
NEURAL_NETWORK_TYPES = frozenset({
    "mlpclassifier", "mlpregressor",
    "pytorch", "torch", "neuralnetwork",
})


def _safe_get_model_name(model: Any) -> str:
    """安全获取模型类型名（小写化）"""
    try:
        name = type(model).__name__.lower()
        return name
    except Exception:
        return ""


def detect_model_type(model: Any) -> str:
    """
    检测模型类型。

    返回值：
        "tree" — 树模型（XGBoost/LightGBM/RF/GBDT 等）
        "neural_network" — 神经网络（MLP/PyTorch）
        "linear" — 线性模型（LogisticRegression/LinearRegression）
        "unknown" — 未知类型（使用 KernelExplainer）
    """
    name = _safe_get_model_name(model)

    if name in TREE_MODEL_TYPES:
        return "tree"
    if name in NEURAL_NETWORK_TYPES:
        return "neural_network"

    # 检查模块路径（某些包装器可能改变类名）
    module = type(model).__module__.lower()
    if any(t in module for t in ("xgboost", "lightgbm", "catboost", "sklearn.ensemble", "sklearn.tree")):
        if "forest" in module or "forest" in name:
            return "tree"
        if "boost" in module or "boost" in name:
            return "tree"

    if any(t in module for t in ("torch", "keras", "tensorflow")):
        return "neural_network"

    return "unknown"


def is_tree_model(model: Any) -> bool:
    """判断是否为树模型"""
    return detect_model_type(model) == "tree"


def is_neural_network(model: Any) -> bool:
    """判断是否为神经网络"""
    return detect_model_type(model) == "neural_network"


# =============================================================================
# SHAP Explainer 工厂
# =============================================================================

def _import_shap() -> Any:
    """尝试导入 shap 库，失败时抛出 ImportError"""
    try:
        import shap  # noqa: F401
        return shap
    except ImportError:
        raise ImportError(
            "shap 库未安装。请运行：pip install shap\n"
            "推荐安装带 tree 支持的版本：pip install shap[tree]"
        )


def get_explainer(
    model: Any,
    background_data: Optional[np.ndarray] = None,
    model_output: str = "raw",
) -> Tuple[Any, str]:
    """
    根据模型类型自动选择并创建 SHAP Explainer。

    参数：
        model: 训练好的模型对象
        background_data: 背景数据集（用于 KernelExplainer，可为 None）
        model_output: 模型输出模式，"raw" | "probability"

    返回：
        (explainer, explainer_type) 元组
    """
    shap = _import_shap()
    model_type = detect_model_type(model)

    if model_type == "tree":
        try:
            explainer = shap.TreeExplainer(model)
            logger.info(f"使用 TreeExplainer（模型类型：{type(model).__name__}）")
            return explainer, "TreeExplainer"
        except Exception as e:
            logger.warning(f"TreeExplainer 失败，降级为 KernelExplainer: {e}")

    elif model_type == "neural_network":
        try:
            # GradientExplainer 需要输入数据和模型
            # 由于我们不知道模型的输入格式，尝试用 masker
            if background_data is not None:
                masker = shap.maskers.Independent(background_data)
                explainer = shap.GradientExplainer(model, background_data)
            else:
                # 使用默认 masker
                explainer = shap.GradientExplainer(model, np.zeros((1, 1)))  # 占位
            logger.info(f"使用 GradientExplainer（模型类型：{type(model).__name__}）")
            return explainer, "GradientExplainer"
        except Exception as e:
            logger.warning(f"GradientExplainer 失败，降级为 KernelExplainer: {e}")

    # 兜底：KernelExplainer
    if background_data is None:
        raise ValueError(
            f"模型类型 '{type(model).__name__}' 不支持 TreeExplainer/GradientExplainer，"
            "需要提供 background_data 用于 KernelExplainer"
        )

    # 选择预测函数
    try:
        predict_fn = getattr(model, "predict_proba", None)
        if predict_fn is not None:
            # 对于分类模型，预测函数取第一列（类1的概率）或最后一列
            def fn(X):
                p = predict_fn(X)
                return p[:, 1] if hasattr(p, "shape") and p.ndim == 2 and p.shape[1] == 2 else p
        else:
            fn = model.predict
    except Exception:
        fn = model.predict

    explainer = shap.KernelExplainer(fn, background_data)
    logger.info(f"使用 KernelExplainer（模型类型：{type(model).__name__}，背景数据 shape={background_data.shape}）")
    return explainer, "KernelExplainer"


# =============================================================================
# 全局 SHAP 计算
# =============================================================================

def _sample_data(data: np.ndarray, max_samples: int) -> np.ndarray:
    """对数据进行随机采样（保留随机种子用于复现性）"""
    if data.shape[0] <= max_samples:
        return data
    indices = np.random.default_rng(42).choice(data.shape[0], max_samples, replace=False)
    return data[indices]


def compute_global_shap(
    model: Any,
    X_test: np.ndarray,
    feature_names: Optional[List[str]] = None,
    sample_size: int = 1000,
    background_size: int = 100,
) -> SHAPResult:
    """
    计算全局 SHAP 值（测试集所有样本）。

    参数：
        model: 训练好的 sklearn/XGBoost/PyTorch 模型
        X_test: 测试数据（numpy array，shape (n_samples, n_features)）
        feature_names: 特征名列表（可选，默认用 f0, f1, ...）
        sample_size: 最大采样数量（超过此值自动采样）
        background_size: KernelExplainer 背景数据大小（仅非树模型）

    返回：
        SHAPResult 对象

    异常：
        ValueError: X_test 为空或模型不支持
        ImportError: shap 库未安装
    """
    start_time = time.perf_counter()

    if X_test is None or (hasattr(X_test, "__len__") and len(X_test) == 0):
        raise ValueError("测试集为空，无法计算 SHAP 值")

    X_test = np.array(X_test)
    if X_test.ndim == 1:
        X_test = X_test.reshape(1, -1)

    # 自动采样
    if X_test.shape[0] > sample_size:
        X_test = _sample_data(X_test, sample_size)
        logger.info(f"数据集过大（{X_test.shape[0]}），已采样至 {sample_size} 样本")

    n_samples, n_features = X_test.shape

    # 生成特征名
    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    # 生成背景数据（用于 KernelExplainer）
    background_data: Optional[np.ndarray] = None
    model_type = detect_model_type(model)
    if model_type != "tree":
        bg_size = min(background_size, n_samples)
        background_data = _sample_data(X_test, bg_size)

    # 获取 Explainer
    try:
        explainer, explainer_type = get_explainer(model, background_data)
    except ImportError:
        raise

    # 计算 SHAP 值
    logger.info(f"开始计算 SHAP 值：{n_samples} 样本 × {n_features} 特征，使用 {explainer_type}")
    try:
        shap_output = explainer.shap_values(X_test, check_additivity=False)

        # 处理分类模型的输出格式（有些返回 list of arrays，有些返回 2D/3D array）
        if isinstance(shap_output, list):
            # list of arrays（常见于多分类 sklearn 模型）
            shap_values: np.ndarray = shap_output[0] if len(shap_output) > 0 else np.array(shap_output).reshape(n_samples, n_features)
        else:
            shap_output = np.array(shap_output)
            if shap_output.ndim == 3:
                # 多分类 numpy array：shape (n_samples, n_features, n_classes)
                # 取二分类的正类（class=1）或多分类的均值
                if shap_output.shape[2] == 2:
                    # 二分类：取正类 SHAP 值，shape (n_samples, n_features)
                    shap_values = shap_output[:, :, 1]
                else:
                    # 多分类：取各类别 SHAP 绝对值的均值
                    shap_values = np.abs(shap_output).mean(axis=2)  # shape: (n_samples, n_features)
            else:
                shap_values = shap_output

        # 确保 shap_values 是 2D
        if shap_values.ndim == 1:
            shap_values = shap_values.reshape(n_samples, n_features)

    except Exception as e:
        raise RuntimeError(f"SHAP 计算失败：{e}") from e

    # 计算 expected_value（基准值）
    try:
        expected_value = float(explainer.expected_value)
    except Exception:
        expected_value = 0.0

    # 计算特征重要性（按均值绝对值排序）
    mean_abs = np.abs(shap_values).mean(axis=0)
    sorted_indices = np.argsort(mean_abs)[::-1]
    feature_names_arr = np.array(feature_names)  # numpy数组才支持数组索引
    feature_importance = [
        FeatureImportance(
            feature=str(feature_names_arr[idx]),
            importance=float(mean_abs[idx]),
            rank=i + 1,
        )
        for i, idx in enumerate(sorted_indices)
    ]

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"SHAP 计算完成：{elapsed_ms:.1f}ms，样本数={n_samples}，特征数={n_features}")

    return SHAPResult(
        feature_names=feature_names,
        shap_values=shap_values.tolist(),
        expected_value=expected_value,
        feature_importance=feature_importance,
        sample_count=n_samples,
        computation_time_ms=elapsed_ms,
        explainer_type=explainer_type,
    )


# =============================================================================
# 局部 SHAP 计算
# =============================================================================

def compute_local_shap(
    model: Any,
    sample: Union[Dict[str, Any], np.ndarray, List],
    feature_names: Optional[List[str]] = None,
    background_size: int = 100,
) -> LocalSHAPResult:
    """
    计算单个样本的局部 SHAP 贡献值。

    参数：
        model: 训练好的模型
        sample: 单条样本数据（dict 或 array-like）
        feature_names: 特征名列表（可选）
        background_size: KernelExplainer 背景数据大小

    返回：
        LocalSHAPResult 对象

    异常：
        ValueError: 样本为空或模型不支持
        ImportError: shap 库未安装
    """
    start_time = time.perf_counter()

    # 转换为 numpy array
    if isinstance(sample, dict):
        if feature_names is None:
            feature_names = list(sample.keys())
        sample_arr = np.array(list(sample.values()), dtype=float).reshape(1, -1)
    else:
        sample_arr = np.array(sample, dtype=float).reshape(1, -1)
        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(sample_arr.shape[1])]

    n_features = sample_arr.shape[1]
    if len(feature_names) != n_features:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    # 背景数据
    background_data: Optional[np.ndarray] = None
    model_type = detect_model_type(model)
    if model_type != "tree":
        # 使用单样本作为背景（实际应用中应使用代表性样本）
        background_data = sample_arr

    # 获取 Explainer
    explainer, explainer_type = get_explainer(model, background_data)

    # 计算 SHAP 值
    shap_output = explainer.shap_values(sample_arr, check_additivity=False)

    if isinstance(shap_output, list):
        shap_vals = np.array(shap_output[0]) if len(shap_output) > 0 else np.array(shap_output).ravel()
    else:
        shap_vals = np.array(shap_output).ravel()

    # 模型预测值
    try:
        preds = model.predict(sample_arr)
        model_output = float(preds.ravel()[0])
    except Exception:
        model_output = 0.0

    # 基准值
    try:
        expected_value = float(explainer.expected_value)
    except Exception:
        expected_value = 0.0

    # 预测类别（仅分类）
    output_class: Optional[str] = None
    if hasattr(model, "predict"):
        try:
            pred_label = model.predict(sample_arr)[0]
            if hasattr(pred_label, "__str__"):
                output_class = str(pred_label)
        except Exception:
            pass

    # 构建 FeatureContribution 列表
    original_values = sample_arr.ravel()
    shap_contributions = []
    for i, fname in enumerate(feature_names):
        val = float(shap_vals[i]) if i < len(shap_vals) else 0.0
        direction = "positive" if val > 0.001 else ("negative" if val < -0.001 else "neutral")
        shap_contributions.append(FeatureContribution(
            feature=fname,
            value=val,
            original_value=original_values[i],
            direction=direction,
        ))

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return LocalSHAPResult(
        sample=sample if isinstance(sample, dict) else {f: v for f, v in zip(feature_names, original_values.tolist())},
        shap_values=shap_contributions,
        expected_value=expected_value,
        model_output=model_output,
        output_class=output_class,
        computation_time_ms=elapsed_ms,
    )
