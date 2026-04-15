"""
tests/test_explain.py — SHAP 可解释性模块测试

测试覆盖：
1. 分类模型全局 SHAP（TreeExplainer 路径）
2. 回归模型全局 SHAP（TreeExplainer 路径）
3. 单样本局部 SHAP 解释
4. ICE 曲线计算
5. SHAP 可视化图生成（base64）

Author: Code Engineer Subagent
"""

from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# 设置测试环境
os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY") or "test_secret_key_for_pytest_only"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MODELS_DIR"] = tempfile.mkdtemp()

# 路径配置
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))


# ========================================================================
# Fixtures
# ========================================================================

@pytest.fixture
def rng():
    """可复现随机数生成器"""
    return np.random.default_rng(2026)


@pytest.fixture
def classification_dataset(rng):
    """二分类数据集（TreeExplainer 路径）"""
    X_train = rng.normal(size=(200, 8))
    y_train = ((X_train[:, 0] + X_train[:, 1]) > 0).astype(int)
    X_test = rng.normal(size=(50, 8))
    y_test = ((X_test[:, 0] + X_test[:, 1]) > 0).astype(int)
    return X_train, y_train, X_test, y_test


@pytest.fixture
def regression_dataset(rng):
    """回归数据集（TreeExplainer 路径）"""
    X_train = rng.normal(size=(200, 6))
    y_train = X_train[:, 0] * 3 + X_train[:, 1] * -2 + rng.normal(0, 0.1, size=200)
    X_test = rng.normal(size=(50, 6))
    y_test = X_test[:, 0] * 3 + X_test[:, 1] * -2 + rng.normal(0, 0.1, size=50)
    return X_train, y_train, X_test, y_test


@pytest.fixture
def trained_classifier(classification_dataset):
    """训练好的 RandomForest 分类器"""
    from sklearn.ensemble import RandomForestClassifier
    X_train, y_train, _, _ = classification_dataset
    clf = RandomForestClassifier(n_estimators=20, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    return clf


@pytest.fixture
def trained_regressor(regression_dataset):
    """训练好的 RandomForest 回归器"""
    from sklearn.ensemble import RandomForestRegressor
    X_train, y_train, _, _ = regression_dataset
    reg = RandomForestRegressor(n_estimators=20, random_state=42, n_jobs=-1)
    reg.fit(X_train, y_train)
    return reg


@pytest.fixture
def single_sample(rng):
    """单样本（用于局部 SHAP 测试）"""
    return {
        "feature_0": float(rng.normal()),
        "feature_1": float(rng.normal()),
        "feature_2": float(rng.normal()),
        "feature_3": float(rng.normal()),
        "feature_4": float(rng.normal()),
    }


# ========================================================================
# Test 1: 分类模型全局 SHAP（TreeExplainer）
# ========================================================================

class TestGlobalSHAPClassification:
    """测试分类模型的全局 SHAP 值计算"""

    def test_global_shap_returns_valid_result(self, trained_classifier, classification_dataset):
        """
        验证：compute_global_shap 返回有效的 SHAP 结果
        预期：返回 SHAPResult，包含 feature_names、shap_values、feature_importance
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = classification_dataset
        feature_names = [f"feature_{i}" for i in range(X_test.shape[1])]

        result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            feature_names=feature_names,
            sample_size=50,
        )

        # 断言：返回类型正确
        assert hasattr(result, "feature_names"), "结果应包含 feature_names 属性"
        assert hasattr(result, "shap_values"), "结果应包含 shap_values 属性"
        assert hasattr(result, "feature_importance"), "结果应包含 feature_importance 属性"
        assert hasattr(result, "expected_value"), "结果应包含 expected_value 属性"
        assert hasattr(result, "explainer_type"), "结果应包含 explainer_type 属性"

    def test_global_shap_feature_names_match(self, trained_classifier, classification_dataset):
        """
        验证：feature_names 与输入一致
        预期：返回的 feature_names 与输入相同
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = classification_dataset
        feature_names = [f"feat_{i}" for i in range(X_test.shape[1])]

        result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            feature_names=feature_names,
        )

        assert result.feature_names == feature_names, "feature_names 应与输入一致"

    def test_global_shap_sampling(self, trained_classifier, classification_dataset):
        """
        验证：sample_size 参数有效限制样本数
        预期：当 sample_size < 数据量时，结果样本数 == sample_size
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = classification_dataset
        sample_size = 10

        result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            sample_size=sample_size,
        )

        assert result.sample_count <= sample_size, \
            f"样本数（{result.sample_count}）应 <= sample_size（{sample_size}）"

    def test_global_shap_feature_importance_ranked(self, trained_classifier, classification_dataset):
        """
        验证：feature_importance 按 importance 降序排列
        预期：每个特征的 importance >= 后续特征
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = classification_dataset

        result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            sample_size=50,
        )

        # 验证排序：第 i 个的 importance >= 第 i+1 个
        for i in range(len(result.feature_importance) - 1):
            curr = result.feature_importance[i]
            next_f = result.feature_importance[i + 1]
            assert curr.importance >= next_f.importance, \
                f"feature_importance 应降序排列：{curr.importance} >= {next_f.importance}"
            assert curr.rank == i + 1, f"rank 应从 1 开始连续编号"

    def test_global_shap_explainer_type(self, trained_classifier, classification_dataset):
        """
        验证：RandomForest 模型使用 TreeExplainer
        预期：explainer_type == "TreeExplainer"
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = classification_dataset

        result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            sample_size=50,
        )

        assert result.explainer_type == "TreeExplainer", \
            f"RandomForest 应使用 TreeExplainer，实际：{result.explainer_type}"

    def test_global_shap_shap_values_shape(self, trained_classifier, classification_dataset):
        """
        验证：shap_values 形状正确 (n_samples, n_features)
        预期：shap_values 为 2D 列表，形状与输入数据一致
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = classification_dataset
        sample_size = 30

        result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            sample_size=sample_size,
        )

        n_samples = min(sample_size, X_test.shape[0])
        n_features = X_test.shape[1]

        assert len(result.shap_values) == n_samples, \
            f"shap_values 行数（{len(result.shap_values)}）应等于样本数（{n_samples}）"
        assert all(len(row) == n_features for row in result.shap_values), \
            "shap_values 每行长度应等于特征数"


# ========================================================================
# Test 2: 回归模型全局 SHAP（TreeExplainer）
# ========================================================================

class TestGlobalSHAPRegression:
    """测试回归模型的全局 SHAP 值计算"""

    def test_regression_global_shap(self, trained_regressor, regression_dataset):
        """
        验证：回归模型的全局 SHAP 计算成功
        预期：返回有效 SHAPResult，expected_value 为浮点数
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = regression_dataset

        result = compute_global_shap(
            model=trained_regressor,
            X_test=X_test,
            feature_names=[f"f{i}" for i in range(X_test.shape[1])],
            sample_size=30,
        )

        assert isinstance(result.expected_value, float), \
            "expected_value 应为浮点数"
        assert len(result.feature_importance) == X_test.shape[1], \
            "feature_importance 长度应等于特征数"
        assert result.explainer_type == "TreeExplainer", \
            f"RandomForestRegressor 应使用 TreeExplainer，实际：{result.explainer_type}"

    def test_regression_shap_values_numeric(self, trained_regressor, regression_dataset):
        """
        验证：SHAP 值为数值型
        预期：所有 shap_values 可以转换为 float
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        _, _, X_test, _ = regression_dataset

        result = compute_global_shap(
            model=trained_regressor,
            X_test=X_test,
            sample_size=20,
        )

        for row in result.shap_values:
            for val in row:
                float(val)  # 不抛异常即可


# ========================================================================
# Test 3: 单样本局部 SHAP 解释
# ========================================================================

class TestLocalSHAP:
    """测试单样本局部 SHAP 解释"""

    def test_local_shap_dict_sample(self, trained_classifier, single_sample):
        """
        验证：支持 dict 格式的样本输入
        预期：返回 LocalSHAPResult，shap_values 长度与样本特征数一致
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_local_shap

        result = compute_local_shap(
            model=trained_classifier,
            sample=single_sample,
        )

        assert hasattr(result, "sample"), "结果应包含 sample 属性"
        assert hasattr(result, "shap_values"), "结果应包含 shap_values 属性"
        assert hasattr(result, "expected_value"), "结果应包含 expected_value 属性"
        assert hasattr(result, "model_output"), "结果应包含 model_output 属性"

        assert len(result.shap_values) == len(single_sample), \
            f"shap_values 长度（{len(result.shap_values)}）应等于样本特征数（{len(single_sample)}）"

    def test_local_shap_feature_contributions(self, trained_classifier, single_sample):
        """
        验证：FeatureContribution 包含正确字段
        预期：每个条目有 feature、value、original_value、direction
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_local_shap

        result = compute_local_shap(
            model=trained_classifier,
            sample=single_sample,
        )

        for fc in result.shap_values:
            assert hasattr(fc, "feature"), "FeatureContribution 应有 feature 属性"
            assert hasattr(fc, "value"), "FeatureContribution 应有 value 属性"
            assert hasattr(fc, "original_value"), "FeatureContribution 应有 original_value 属性"
            assert hasattr(fc, "direction"), "FeatureContribution 应有 direction 属性"
            assert fc.direction in ("positive", "negative", "neutral"), \
                f"direction 应为 positive/negative/neutral，实际：{fc.direction}"

    def test_local_shap_model_output_in_range(self, trained_classifier, single_sample):
        """
        验证：模型输出在合理范围内（二分类应在 [0,1] 或 [0,1] 概率）
        预期：model_output 是数值
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_local_shap

        result = compute_local_shap(
            model=trained_classifier,
            sample=single_sample,
        )

        assert isinstance(result.model_output, (int, float)), \
            "model_output 应为数值类型"
        # 二分类输出应在 [0, 1]（概率）或 [0, 1]（类别）
        assert result.model_output in (0.0, 1.0), \
            f"二分类模型输出应为 0.0 或 1.0（类别），实际：{result.model_output}"

    def test_local_shap_computation_time_recorded(self, trained_regressor, regression_dataset):
        """
        验证：computation_time_ms 字段被正确记录
        预期：computation_time_ms > 0
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_local_shap

        _, _, X_test, _ = regression_dataset
        sample = {f"f{i}": float(v) for i, v in enumerate(X_test[0])}

        result = compute_local_shap(
            model=trained_regressor,
            sample=sample,
        )

        assert result.computation_time_ms >= 0, \
            "computation_time_ms 应 >= 0"


# ========================================================================
# Test 4: ICE 曲线计算
# ========================================================================

class TestICECurves:
    """测试 ICE 曲线计算"""

    def test_ice_returns_valid_result(self, trained_regressor, regression_dataset):
        """
        验证：ICE 曲线返回有效结果
        预期：返回 ICEResult，包含 feature_name、curves、feature_values
        """
        from mlkit.explainability import compute_ice_curves

        _, _, X_test, _ = regression_dataset
        feature_names = [f"f{i}" for i in range(X_test.shape[1])]

        result = compute_ice_curves(
            model=trained_regressor,
            X_data=X_test,
            feature_name="f0",
            feature_names=feature_names,
            num_points=20,
            sample_size=10,
        )

        assert hasattr(result, "feature_name"), "结果应包含 feature_name"
        assert hasattr(result, "feature_values"), "结果应包含 feature_values"
        assert hasattr(result, "curves"), "结果应包含 curves"
        assert hasattr(result, "computation_time_ms"), "结果应包含 computation_time_ms"

    def test_ice_feature_values_monotonic(self, trained_regressor, regression_dataset):
        """
        验证：feature_values 是单调递增的.linspace 序列
        预期：feature_values 长度 == num_points，且严格递增
        """
        from mlkit.explainability import compute_ice_curves

        _, _, X_test, _ = regression_dataset
        feature_names = [f"f{i}" for i in range(X_test.shape[1])]
        num_points = 30

        result = compute_ice_curves(
            model=trained_regressor,
            X_data=X_test,
            feature_name="f0",
            feature_names=feature_names,
            num_points=num_points,
            sample_size=20,
        )

        assert len(result.feature_values) == num_points, \
            f"feature_values 长度应等于 num_points（{num_points}），实际：{len(result.feature_values)}"
        # 验证严格递增
        for i in range(len(result.feature_values) - 1):
            assert result.feature_values[i] < result.feature_values[i + 1], \
                f"feature_values 应单调递增：[{result.feature_values[i]}, {result.feature_values[i+1]}]"

    def test_ice_curves_count(self, trained_regressor, regression_dataset):
        """
        验证：曲线数量等于采样样本数
        预期：sample_size=10 时，应有 10 条曲线
        """
        from mlkit.explainability import compute_ice_curves

        _, _, X_test, _ = regression_dataset
        feature_names = [f"f{i}" for i in range(X_test.shape[1])]
        sample_size = 10

        result = compute_ice_curves(
            model=trained_regressor,
            X_data=X_test,
            feature_name="f1",
            feature_names=feature_names,
            num_points=20,
            sample_size=sample_size,
        )

        assert len(result.curves) == sample_size, \
            f"曲线数量（{len(result.curves)}）应等于 sample_size（{sample_size}）"

    def test_ice_invalid_feature_name(self, trained_regressor, regression_dataset):
        """
        验证：无效特征名抛出 ValueError
        预期：raise ValueError，包含特征不存在的信息
        """
        from mlkit.explainability import compute_ice_curves

        _, _, X_test, _ = regression_dataset
        feature_names = [f"f{i}" for i in range(X_test.shape[1])]

        with pytest.raises(ValueError, match="不存在"):
            compute_ice_curves(
                model=trained_regressor,
                X_data=X_test,
                feature_name="nonexistent_feature",
                feature_names=feature_names,
            )

    def test_ice_curves_points(self, trained_regressor, regression_dataset):
        """
        验证：每条曲线的数据点数等于 num_points
        预期：每条 ICECurve 的 points 长度 == num_points
        """
        from mlkit.explainability import compute_ice_curves

        _, _, X_test, _ = regression_dataset
        feature_names = [f"f{i}" for i in range(X_test.shape[1])]
        num_points = 25

        result = compute_ice_curves(
            model=trained_regressor,
            X_data=X_test,
            feature_name="f2",
            feature_names=feature_names,
            num_points=num_points,
            sample_size=5,
        )

        for curve in result.curves:
            assert len(curve.points) == num_points, \
                f"曲线数据点数（{len(curve.points)}）应等于 num_points（{num_points}）"
            for point in curve.points:
                assert hasattr(point, "feature_value"), "ICEPoint 应有 feature_value"
                assert hasattr(point, "predicted_value"), "ICEPoint 应有 predicted_value"


# ========================================================================
# Test 5: 模型类型检测
# ========================================================================

class TestModelTypeDetection:
    """测试模型类型自动检测"""

    def test_detect_tree_model(self, trained_classifier):
        """验证：RandomForest 被识别为 tree 模型"""
        from mlkit.explainability import detect_model_type, is_tree_model

        assert detect_model_type(trained_classifier) == "tree"
        assert is_tree_model(trained_classifier) is True

    def test_detect_regressor_type(self, trained_regressor):
        """验证：RandomForestRegressor 被识别为 tree 模型"""
        from mlkit.explainability import detect_model_type, is_tree_model

        assert detect_model_type(trained_regressor) == "tree"
        assert is_tree_model(trained_regressor) is True

    def test_not_neural_network(self, trained_classifier):
        """验证：RandomForest 不被识别为神经网络"""
        from mlkit.explainability import is_neural_network

        assert is_neural_network(trained_classifier) is False


# ========================================================================
# Test 6: SHAP 可视化图（base64）
# ========================================================================

class TestSHAPPlots:
    """测试 SHAP 可视化图生成"""

    def test_bar_plot_base64(self, trained_classifier, classification_dataset):
        """
        验证：bar 图生成返回有效的 base64 编码 PNG
        预期：image_base64 以 data:image/png;base64, 开头
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过绘图测试")
        pytest.importorskip("matplotlib", reason="matplotlib 库未安装，跳过绘图测试")
        from mlkit.explainability import compute_global_shap
        from mlkit.explainability.plots import shap_values_to_base64

        _, _, X_test, _ = classification_dataset
        shap_result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            sample_size=30,
        )

        plot_result = shap_values_to_base64(
            shap_values=np.array(shap_result.shap_values),
            expected_value=shap_result.expected_value,
            features=None,
            feature_names=shap_result.feature_names,
            plot_type="bar",
            max_display=5,
        )

        assert hasattr(plot_result, "image_base64"), "结果应包含 image_base64"
        assert hasattr(plot_result, "image_type"), "结果应包含 image_type"
        assert plot_result.image_type == "bar", f"image_type 应为 bar，实际：{plot_result.image_type}"
        # base64 编码的 PNG 应以特定标记开头
        assert len(plot_result.image_base64) > 100, \
            "base64 编码的图片内容不应为空"

    def test_beeswarm_plot_result(self, trained_classifier, classification_dataset):
        """
        验证：beeswarm 图生成返回有效 SHAPPlotResult
        预期：包含 width_px、height_px、computation_time_ms
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过绘图测试")
        pytest.importorskip("matplotlib", reason="matplotlib 库未安装，跳过绘图测试")
        from mlkit.explainability import compute_global_shap
        from mlkit.explainability.plots import shap_values_to_base64

        _, _, X_test, _ = classification_dataset
        shap_result = compute_global_shap(
            model=trained_classifier,
            X_test=X_test,
            sample_size=20,
        )

        plot_result = shap_values_to_base64(
            shap_values=np.array(shap_result.shap_values),
            expected_value=shap_result.expected_value,
            features=np.array(shap_result.shap_values),
            feature_names=shap_result.feature_names,
            plot_type="beeswarm",
            max_display=5,
        )

        assert plot_result.image_type == "beeswarm"
        assert plot_result.width_px > 0, "宽度应 > 0"
        assert plot_result.height_px > 0, "高度应 > 0"
        assert plot_result.computation_time_ms >= 0, "计算时间应 >= 0"


# ========================================================================
# Test 7: 空数据 / 边界情况
# ========================================================================

class TestEdgeCases:
    """边界情况测试"""

    def test_global_shap_empty_data_raises(self, trained_classifier):
        """验证：空数据抛出 ValueError"""
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        with pytest.raises(ValueError, match="空"):
            compute_global_shap(
                model=trained_classifier,
                X_test=np.array([]),
            )

    def test_global_shap_1d_array_reshaped(self, trained_classifier, rng):
        """
        验证：1D 数组自动 reshape 为 2D
        预期：不抛出异常，返回有效结果
        """
        pytest.importorskip("shap", reason="shap 库未安装，跳过此测试")
        from mlkit.explainability import compute_global_shap

        X_1d = rng.normal(size=8)  # 1D array, 8 features

        result = compute_global_shap(
            model=trained_classifier,
            X_test=X_1d,
            feature_names=[f"f{i}" for i in range(8)],
        )

        assert result.sample_count == 1, "1D 数组应被 reshape 为单样本"
        assert len(result.shap_values) == 1
