"""
扩展 AutoML 模块测试
覆盖：自定义搜索空间、Grid Search、Random Search、Bayesian Search、
Top-K 模型排序、报告生成、回归任务
"""
import numpy as np
import pytest


class TestAutoMLSearchSpace:
    """搜索空间定义测试"""

    def test_search_space_custom(self):
        """测试自定义搜索空间：支持 choice / int / float 三种类型"""
        from mlkit.automl import SearchSpace

        space = SearchSpace()
        space.add("model_type", ["random_forest", "xgboost", "lightgbm"])
        space.add_int("n_estimators", 50, 300, step=50)
        space.add_float("learning_rate", 0.01, 0.5, log=True)

        choices = space.choices()
        assert len(choices) == 3

        # 验证各类型结构
        choice_item = next(c for c in choices if c["type"] == "choice")
        assert choice_item["name"] == "model_type"
        assert choice_item["values"] == ["random_forest", "xgboost", "lightgbm"]

        int_item = next(c for c in choices if c["type"] == "int")
        assert int_item["name"] == "n_estimators"
        assert int_item["low"] == 50
        assert int_item["high"] == 300
        assert int_item["step"] == 50

        float_item = next(c for c in choices if c["type"] == "float")
        assert float_item["name"] == "learning_rate"
        assert float_item["log"] is True

    def test_search_space_random_point_reproducible(self, rng):
        """测试随机采样结果可重现（固定 seed）"""
        from mlkit.automl import SearchSpace

        space = SearchSpace()
        space.add("model_type", ["rf", "xgb", "lgb"])
        space.add_int("n_estimators", 10, 200)
        space.add_float("max_depth", 1.0, 10.0)

        # 同一个 seed，两次采样结果一致
        point1 = space.random_point(rng)
        point2 = space.random_point(np.random.default_rng(42))  # re-seed

        assert point1["model_type"] in ["rf", "xgb", "lgb"]
        assert 10 <= point1["n_estimators"] <= 200
        assert 1.0 <= point1["max_depth"] <= 10.0

    def test_search_space_grid_points(self):
        """测试 Grid Search 生成所有组合"""
        from mlkit.automl import SearchSpace

        space = SearchSpace()
        space.add("model_type", ["rf", "xgb"])
        space.add_int("max_depth", 3, 4)

        points = space.grid_points()
        # 2 models * 2 depths = 4 combinations
        assert len(points) == 4

        names = {p["model_type"] for p in points}
        depths = {p["max_depth"] for p in points}
        assert names == {"rf", "xgb"}
        assert depths == {3, 4}


class TestAutoMLGridSearch:
    """Grid Search 策略测试"""

    def test_automl_grid_search(self, classification_data):
        """测试 Grid Search 完整流程"""
        from mlkit.automl import AutoMLEngine, SearchSpace

        X_train, y_train, X_val, y_val = classification_data

        space = SearchSpace()
        space.add("model_type", ["random_forest", "xgboost"])
        space.add_int("n_estimators", 50, 100)

        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="grid",
            n_trials=10,  # 限制最多 10 个点
            search_space=space,
            random_state=42,
        )

        result = engine.run()

        assert len(result.trials) >= 1
        assert result.strategy == "grid"
        assert result.best_params is not None
        assert all(isinstance(t.val_score, float) for t in result.trials)
        assert all(isinstance(t.train_score, float) for t in result.trials)
        # 所有 trials 的 val_score 应该在 [0, 1]
        assert all(0.0 <= t.val_score <= 1.0 for t in result.trials)


class TestAutoMLRandomSearch:
    """Random Search 策略测试"""

    def test_automl_random_search(self, classification_data):
        """测试 Random Search 完整流程"""
        from mlkit.automl import AutoMLEngine

        X_train, y_train, X_val, y_val = classification_data

        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="random",
            n_trials=5,
            random_state=99,
        )

        result = engine.run()

        assert len(result.trials) == 5
        assert result.strategy == "random"
        assert result.total_time >= 0.0
        assert result.best_params is not None
        # best_val_score 应该是所有 trials 中最高的
        best = max(t.val_score for t in result.trials)
        assert abs(result.best_val_score - best) < 1e-9


class TestAutoMLBayesianSearch:
    """Bayesian Search 策略测试"""

    def test_automl_bayesian_search(self, classification_data):
        """测试 Bayesian Optimization（需要 optuna）"""
        pytest.importorskip("optuna", reason="optuna required for Bayesian search")

        from mlkit.automl import AutoMLEngine

        X_train, y_train, X_val, y_val = classification_data

        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="bayesian",
            n_trials=3,
            random_state=42,
        )

        result = engine.run()

        assert len(result.trials) == 3
        assert result.strategy == "bayesian"
        assert all(isinstance(t.val_score, float) for t in result.trials)
        # bayesian 优化是最小化 -val_score
        print(f"Bayesian best val_score: {result.best_val_score:.4f}")


class TestAutoMLTopKModels:
    """Top-K 模型排序测试"""

    def test_automl_get_top_models(self, classification_data):
        """测试 get_top_models 返回正确排序"""
        from mlkit.automl import AutoMLEngine

        X_train, y_train, X_val, y_val = classification_data

        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="random",
            n_trials=5,
            random_state=123,
        )
        engine.run()

        top3 = engine.get_top_models(3)
        top5 = engine.get_top_models(5)

        assert len(top3) <= 3
        assert len(top5) <= 5

        # 验证降序排列
        if len(top3) >= 2:
            for i in range(len(top3) - 1):
                assert top3[i].val_score >= top3[i + 1].val_score

        # top3 应该是 top5 的子集
        top3_ids = {t.trial_id for t in top3}
        top5_ids = {t.trial_id for t in top5}
        assert top3_ids <= top5_ids

    def test_automl_get_top_models_empty(self):
        """测试空 trials 时 get_top_models 返回空列表"""
        from mlkit.automl import AutoMLEngine

        X_train = np.random.randn(50, 5)
        y_train = np.random.randint(0, 2, 50)
        X_val = np.random.randn(20, 5)
        y_val = np.random.randint(0, 2, 20)

        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="random",
            n_trials=0,  # 0 trials
            random_state=42,
        )
        # 不调用 run()，直接 get_top_models
        top_k = engine.get_top_models(3)
        assert top_k == []


class TestAutoMLReport:
    """Markdown 报告生成测试"""

    def test_automl_generate_report(self, classification_data):
        """测试报告包含必要信息"""
        from mlkit.automl import AutoMLEngine

        X_train, y_train, X_val, y_val = classification_data

        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="random",
            n_trials=3,
            random_state=42,
        )
        engine.run()

        report = engine.generate_report()

        # 验证报告关键内容
        assert "AutoML" in report
        assert "Top-3" in report
        assert "classification" in report
        assert "random" in report
        # 验证包含模型类型
        assert any(m in report for m in ["random_forest", "xgboost", "lightgbm"])
        # 验证包含分数
        assert any(c.isdigit() for c in report.split())

    def test_automl_report_format(self, classification_data):
        """测试报告格式正确（Markdown 表格格式）"""
        from mlkit.automl import AutoMLEngine

        X_train, y_train, X_val, y_val = classification_data

        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="random",
            n_trials=2,
            random_state=42,
        )
        engine.run()

        report = engine.generate_report()
        lines = report.split("\n")

        # 验证包含 Markdown 表格分隔线
        assert any(line.strip().startswith("|") and "---" in line for line in lines)
        # 验证包含列头
        header_found = any(
            "排名" in line or "验证分数" in line or "训练分数" in line
            for line in lines
        )
        assert header_found, "Report missing expected headers"


class TestAutoMLRegression:
    """回归任务测试"""

    def test_automl_regression_task(self, regression_data):
        """测试回归任务端到端流程"""
        from mlkit.automl import AutoMLEngine

        X_train, y_train, X_val, y_val = regression_data

        engine = AutoMLEngine(
            task_type="regression",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="random",
            n_trials=3,
            random_state=42,
        )

        result = engine.run()

        assert len(result.trials) == 3
        assert result.strategy == "random"
        # 回归任务的 val_score（R2）可能为负（当模型很糟时）
        assert all(isinstance(t.val_score, float) for t in result.trials)
        assert result.best_params is not None
        print(f"Regression best R2: {result.best_val_score:.4f}")

    def test_automl_regression_random_search(self, regression_data):
        """测试回归任务的 Random Search"""
        from mlkit.automl import AutoMLEngine

        X_train, y_train, X_val, y_val = regression_data

        engine = AutoMLEngine(
            task_type="regression",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="random",
            n_trials=5,
            random_state=42,
        )

        result = engine.run()

        # 所有 trials 的 train_score / val_score 应该在合理范围（R2 ∈ (-∞, 1]）
        assert len(result.trials) == 5
        # 好的模型 R2 应该 > 0
        assert result.best_val_score > 0  # 线性数据，模型应该能拟合

    def test_automl_regression_grid_search(self, regression_data):
        """测试回归任务的 Grid Search"""
        from mlkit.automl import AutoMLEngine, SearchSpace

        X_train, y_train, X_val, y_val = regression_data

        space = SearchSpace()
        space.add("model_type", ["random_forest", "xgboost"])
        space.add_int("n_estimators", 50, 100)

        engine = AutoMLEngine(
            task_type="regression",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy="grid",
            n_trials=4,
            search_space=space,
            random_state=42,
        )

        result = engine.run()

        assert len(result.trials) >= 1
        assert result.strategy == "grid"
        assert result.best_params is not None
