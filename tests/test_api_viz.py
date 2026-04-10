"""
可视化 API（viz.py）单元测试

使用 FastAPI TestClient + 内存数据库 + mock 认证，
无需真实文件系统或后台线程。
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture
def app():
    """构建 FastAPI 测试应用"""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from api.database import Base
    from api.main import app
    from api.auth import get_current_user
    from api.database import get_db

    # 使用 StaticPool 确保所有连接共享同一个内存数据库
    # 并设置 check_same_thread=False 避免跨线程问题
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db_session = TestingSession()

    def override_get_current_user():
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        return user

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    client.db = db_session
    yield client

    db_session.close()
    app.dependency_overrides.clear()


@pytest.fixture
def sample_csv_path():
    """创建临时 CSV 数据文件（放在 uploads 目录以通过路径安全检查）"""
    # viz.py 只允许 ./uploads 和 /home/gem/workspace/agent/workspace/ml-all-in-one/uploads
    uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
    uploads_dir.mkdir(exist_ok=True)

    data = {
        "id": list(range(100)),
        "feature_a": list(np.random.randn(100)),
        "feature_b": list(np.random.randn(100)),
        "target": list(np.random.randint(0, 2, 100)),
    }
    df = pd.DataFrame(data)

    filepath = uploads_dir / "test_viz_data.csv"
    df.to_csv(filepath, index=False)

    yield str(filepath)

    if filepath.exists():
        filepath.unlink()


@pytest.fixture
def data_file_record(app, sample_csv_path):
    """在测试数据库中创建 DataFile 记录（注意字段名是 filename）"""
    from api.database import DataFile

    record = DataFile(
        id=1,
        user_id=1,
        filename="test_data.csv",   # 注意：DataFile 用 filename，不是 name
        filepath=sample_csv_path,
        columns=["id", "feature_a", "feature_b", "target"],
        rows=100,
        size=1024,
    )
    app.db.add(record)
    app.db.commit()
    app.db.refresh(record)
    return record


@pytest.fixture
def experiment_record(app):
    """在测试数据库中创建 Experiment 记录"""
    from api.database import Experiment

    exp = Experiment(
        id=1,
        user_id=1,
        name="test_exp",
        status="completed",
        params={
            "model_type": "random_forest",
            "task_type": "classification",
            "feature_importance": {
                "feature_a": 0.5,
                "feature_b": 0.3,
                "id": 0.2,
            },
        },
        metrics={
            "accuracy": 0.85,
            "val_loss": 0.15,
            "y_true": [0, 1, 0, 1, 0],
            "y_pred": [0, 1, 0, 0, 1],
            "y_proba": [0.1, 0.9, 0.2, 0.6, 0.7],
            "train_loss_history": [0.9, 0.7, 0.5, 0.3, 0.2],
            "val_loss_history": [0.95, 0.75, 0.55, 0.35, 0.25],
            "feature_importance": {
                "feature_a": 0.5,
                "feature_b": 0.3,
            },
        },
    )
    app.db.add(exp)
    app.db.commit()
    app.db.refresh(exp)
    return exp


class TestVizDataDistributions:
    """数据分布 API 测试"""

    def test_viz_get_distributions_success(self, app, data_file_record):
        """测试成功获取数据分布"""
        response = app.get(f"/api/viz/data/{data_file_record.id}/distributions")

        assert response.status_code == 200
        data = response.json()

        assert "dataset_info" in data
        assert "plots" in data
        assert data["dataset_info"]["rows"] == 100
        assert data["dataset_info"]["columns"] == 4

        # 验证每个特征的统计信息
        assert len(data["plots"]) == 4
        for plot in data["plots"]:
            assert "feature" in plot
            assert "stats" in plot
            assert "count" in plot["stats"]
            assert "missing" in plot["stats"]

    def test_viz_get_distributions_with_features_filter(self, app, data_file_record):
        """测试指定特征过滤"""
        response = app.get(
            f"/api/viz/data/{data_file_record.id}/distributions"
            "?features=feature_a,feature_b"
        )

        assert response.status_code == 200
        data = response.json()
        # 只返回请求的特征
        feature_names = [p["feature"] for p in data["plots"]]
        assert "feature_a" in feature_names
        assert "feature_b" in feature_names
        assert "id" not in feature_names

    def test_viz_get_distributions_numeric_histogram(self, app, data_file_record):
        """测试数值特征直方图"""
        response = app.get(
            f"/api/viz/data/{data_file_record.id}/distributions"
            "?plot_type=histogram"
        )

        assert response.status_code == 200
        data = response.json()

        # feature_a 是数值型，应该有 histogram
        fa_plot = next(p for p in data["plots"] if p["feature"] == "feature_a")
        assert "histogram" in fa_plot["stats"]
        assert "bins" in fa_plot["stats"]["histogram"]
        assert "counts" in fa_plot["stats"]["histogram"]

    def test_viz_get_distributions_numeric_boxplot(self, app, data_file_record):
        """测试数值特征箱线图"""
        response = app.get(
            f"/api/viz/data/{data_file_record.id}/distributions"
            "?plot_type=boxplot"
        )

        assert response.status_code == 200
        data = response.json()

        fa_plot = next(p for p in data["plots"] if p["feature"] == "feature_a")
        assert "boxplot" in fa_plot["stats"]
        # 箱线图关键统计量
        bp = fa_plot["stats"]["boxplot"]
        for key in ["q1", "median", "q3", "whisker_low", "whisker_high"]:
            assert key in bp

    def test_viz_get_distributions_categorical(self, app, data_file_record):
        """测试类别特征统计（整数列被 pandas 识别为数值型，返回直方图）"""
        response = app.get(f"/api/viz/data/{data_file_record.id}/distributions")

        assert response.status_code == 200
        data = response.json()

        # target 是整数（0/1），pandas is_numeric_dtype 认为是数值型，返回直方图
        target_plot = next(p for p in data["plots"] if p["feature"] == "target")
        stats = target_plot["stats"]
        # 整数列被 pandas 识别为数值型，有 histogram 或 basic numeric stats
        assert "histogram" in stats or ("mean" in stats and "median" in stats)

    def test_viz_get_distributions_not_found(self, app):
        """测试数据文件不存在"""
        response = app.get("/api/viz/data/99999/distributions")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_viz_get_distributions_correlation_matrix(self, app, data_file_record):
        """测试相关性矩阵计算（>=2 个数值特征时）"""
        response = app.get(f"/api/viz/data/{data_file_record.id}/distributions")

        assert response.status_code == 200
        data = response.json()

        # 有多个数值特征，应该有 correlation_matrix
        assert "correlation_matrix" in data
        assert "features" in data["correlation_matrix"]
        assert "matrix" in data["correlation_matrix"]

    def test_viz_get_distributions_missing_values(self, app):
        """测试缺失值统计"""
        # 创建一个有缺失值的 CSV，放在 uploads 目录
        uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
        uploads_dir.mkdir(exist_ok=True)
        filepath = uploads_dir / "missing_data.csv"
        df = pd.DataFrame({
            "a": [1.0, 2.0, None, 4.0],
            "b": [None, 2.0, 3.0, 4.0],
        })
        df.to_csv(filepath, index=False)

        try:
            from api.database import DataFile

            record = DataFile(
                id=2,
                user_id=1,
                filename="missing_data.csv",
                filepath=str(filepath),
                columns=["a", "b"],
                rows=4,
                size=100,
            )
            app.db.add(record)
            app.db.commit()

            response = app.get("/api/viz/data/2/distributions")
            assert response.status_code == 200
            data = response.json()
            assert "missing_values" in data
            assert len(data["missing_values"]) == 2  # a 和 b 都有缺失
        finally:
            if filepath.exists():
                filepath.unlink()


class TestVizDataSummary:
    """数据摘要 API 测试"""

    def test_viz_get_data_summary(self, app, data_file_record):
        """测试获取数据摘要"""
        response = app.get(f"/api/viz/data/{data_file_record.id}/summary")

        assert response.status_code == 200
        data = response.json()

        assert data["rows"] == 100
        assert data["columns"] == 4
        assert "numeric_features" in data
        assert "categorical_features" in data
        assert "numeric_columns" in data

    def test_viz_get_data_summary_not_found(self, app):
        """测试数据文件不存在"""
        response = app.get("/api/viz/data/99999/summary")
        assert response.status_code == 404


class TestVizFeatureImportance:
    """特征重要性 API 测试"""

    def test_viz_get_feature_importance_success(self, app, experiment_record):
        """测试成功获取特征重要性"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/feature-importance"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["experiment_id"] == experiment_record.id
        assert data["model_type"] == "random_forest"
        assert "importance" in data
        assert len(data["importance"]) > 0

        # 验证排序（重要性降序）
        importances = [item["importance"] for item in data["importance"]]
        assert importances == sorted(importances, reverse=True)

    def test_viz_get_feature_importance_top_k(self, app, experiment_record):
        """测试 top_k 参数"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/feature-importance"
            "?top_k=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["importance"]) <= 1

    def test_viz_get_feature_importance_not_found(self, app):
        """测试实验不存在"""
        response = app.get("/api/viz/experiments/99999/feature-importance")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_viz_get_feature_importance_no_data(self, app):
        """测试实验无特征重要性数据"""
        from api.database import Experiment

        exp = Experiment(
            id=2,
            user_id=1,
            name="no_importance",
            status="completed",
            params={},
            metrics={},
        )
        app.db.add(exp)
        app.db.commit()

        response = app.get("/api/viz/experiments/2/feature-importance")
        assert response.status_code == 200
        data = response.json()
        assert data["importance"] == []


class TestVizTrainingCurves:
    """训练曲线 API 测试"""

    def test_viz_get_training_curves_success(self, app, experiment_record):
        """测试成功获取训练曲线"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/training-curves"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["experiment_id"] == experiment_record.id
        assert "epochs" in data
        assert "curves" in data
        assert len(data["curves"]) >= 1

    def test_viz_get_training_curves_with_real_data(self, app, experiment_record):
        """测试有真实曲线数据时返回真实数据"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/training-curves"
        )

        assert response.status_code == 200
        data = response.json()

        # 有 train_loss_history 和 val_loss_history
        curve_names = [c["name"] for c in data["curves"]]
        assert "train_loss" in curve_names
        assert "val_loss" in curve_names

    def test_viz_get_training_curves_not_found(self, app):
        """测试实验不存在"""
        response = app.get("/api/viz/experiments/99999/training-curves")
        assert response.status_code == 404

    def test_viz_get_training_curves_fallback_mock_data(self, app):
        """测试无曲线数据时返回模拟数据"""
        from api.database import Experiment

        exp = Experiment(
            id=3,
            user_id=1,
            name="no_curves",
            status="completed",
            params={},
            metrics={},  # 无曲线数据
        )
        app.db.add(exp)
        app.db.commit()

        response = app.get("/api/viz/experiments/3/training-curves")
        assert response.status_code == 200
        data = response.json()
        # 应该返回模拟曲线
        assert len(data["curves"]) >= 1


class TestVizEvaluation:
    """实验评估可视化 API 测试"""

    def test_viz_get_evaluation_classification(self, app, experiment_record):
        """测试分类实验的评估数据"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/evaluation"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["experiment_id"] == experiment_record.id
        assert data["task_type"] == "classification"
        assert "plots" in data
        # 应该有混淆矩阵
        plot_types = [p["type"] for p in data["plots"]]
        assert "confusion_matrix" in plot_types

    def test_viz_get_evaluation_with_roc_curve(self, app, experiment_record):
        """测试有 y_proba 时返回 ROC 曲线"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/evaluation"
        )

        assert response.status_code == 200
        data = response.json()

        plot_types = [p["type"] for p in data["plots"]]
        assert "roc_curve" in plot_types

        # 验证 ROC 数据结构
        roc_plot = next(p for p in data["plots"] if p["type"] == "roc_curve")
        assert "fpr" in roc_plot["data"]
        assert "tpr" in roc_plot["data"]
        assert "auc" in roc_plot["data"]

    def test_viz_get_evaluation_not_found(self, app):
        """测试实验不存在"""
        response = app.get("/api/viz/experiments/99999/evaluation")
        assert response.status_code == 404

    def test_viz_get_evaluation_regression(self, app):
        """测试回归实验的评估数据"""
        from api.database import Experiment

        exp = Experiment(
            id=4,
            user_id=1,
            name="regression_test",
            status="completed",
            params={"task_type": "regression"},
            metrics={
                "y_true": [1.0, 2.0, 3.0, 4.0, 5.0],
                "y_pred": [1.1, 2.1, 2.9, 4.2, 4.8],
            },
        )
        app.db.add(exp)
        app.db.commit()

        response = app.get("/api/viz/experiments/4/evaluation")
        assert response.status_code == 200
        data = response.json()

        assert data["task_type"] == "regression"
        plot_types = [p["type"] for p in data["plots"]]
        assert "true_vs_predicted" in plot_types
        assert "residual_histogram" in plot_types


class TestVizChartImage:
    """图表渲染 API 测试"""

    def test_viz_get_chart_png(self, app, experiment_record):
        """测试图表 PNG 渲染"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/chart/loss_curve"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_viz_get_chart_confusion_matrix(self, app, experiment_record):
        """测试混淆矩阵图表"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/chart/confusion_matrix"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_viz_get_chart_roc_curve(self, app, experiment_record):
        """测试 ROC 曲线图表"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/chart/roc_curve"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_viz_get_chart_importance(self, app, experiment_record):
        """测试特征重要性图表"""
        response = app.get(
            f"/api/viz/experiments/{experiment_record.id}/chart/importance"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_viz_get_chart_not_found(self, app):
        """测试实验不存在"""
        response = app.get("/api/viz/experiments/99999/chart/loss_curve")
        assert response.status_code == 404
