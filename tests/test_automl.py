"""AutoML 模块测试"""
import numpy as np
import pytest


def test_search_space_add():
    """测试搜索空间定义"""
    from mlkit.automl import SearchSpace

    space = SearchSpace()
    space.add("model_type", ["rf", "xgb"])
    space.add_int("n_estimators", 50, 200)
    space.add_float("lr", 0.01, 0.3, log=True)

    assert len(space.choices()) == 3
    assert space.choices()[0]["type"] == "choice"
    assert space.choices()[1]["type"] == "int"
    assert space.choices()[2]["type"] == "float"


def test_search_space_random_point():
    """测试随机采样"""
    from mlkit.automl import SearchSpace

    space = SearchSpace()
    space.add("model_type", ["rf", "xgb"])
    space.add_int("n_estimators", 50, 200)

    rng = np.random.default_rng(42)
    point = space.random_point(rng)

    assert point["model_type"] in ["rf", "xgb"]
    assert 50 <= point["n_estimators"] <= 200


def test_automl_engine_random_search():
    """测试 Random Search"""
    from mlkit.automl import AutoMLEngine

    # 生成测试数据
    rng = np.random.default_rng(42)
    X_train = rng.normal(size=(200, 10))
    y_train = (X_train[:, 0] > 0).astype(int)
    X_val = rng.normal(size=(50, 10))
    y_val = (X_val[:, 0] > 0).astype(int)

    engine = AutoMLEngine(
        task_type="classification",
        X_train=X_train, y_train=y_train,
        X_val=X_val, y_val=y_val,
        strategy="random",
        n_trials=5,
    )

    result = engine.run()

    assert len(result.trials) == 5
    assert result.best_val_score >= 0.0
    assert result.strategy == "random"
    assert result.best_params is not None

    # 报告生成
    report = engine.generate_report()
    assert "AutoML" in report
    assert "Top-3" in report


def test_automl_engine_regression():
    """测试回归任务"""
    from mlkit.automl import AutoMLEngine

    rng = np.random.default_rng(42)
    X_train = rng.normal(size=(200, 5))
    y_train = X_train[:, 0] * 2 + X_train[:, 1]
    X_val = rng.normal(size=(50, 5))
    y_val = X_val[:, 0] * 2 + X_val[:, 1]

    engine = AutoMLEngine(
        task_type="regression",
        X_train=X_train, y_train=y_train,
        X_val=X_val, y_val=y_val,
        strategy="random",
        n_trials=3,
    )
    result = engine.run()

    assert len(result.trials) == 3
    assert result.best_val_score is not None
