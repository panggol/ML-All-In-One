"""
Experiments API 单元测试

使用 FastAPI TestClient + 内存数据库 + mock 认证，
测试实验列表、对比、曲线对比等端点。
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

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
def sample_experiments(app):
    """创建多个示例实验记录"""
    from api.database import Experiment

    now = datetime.now(timezone.utc)
    experiments = []
    for i in range(1, 4):
        exp = Experiment(
            id=i,
            user_id=1,
            name=f"experiment_{i}",
            description=f"测试实验 {i}",
            params={"lr": 0.01 * i, "epochs": 10 * i},
            metrics={
                "accuracy": 0.8 + i * 0.05,
                "f1": 0.75 + i * 0.04,
                "train_loss_history": [0.9 - i * 0.05] * 5,
                "val_loss_history": [0.95 - i * 0.04] * 5,
            },
            status="completed",
            created_at=now,
            finished_at=now,
        )
        app.db.add(exp)
        experiments.append(exp)

    app.db.commit()
    for exp in experiments:
        app.db.refresh(exp)
    return experiments


# ============================================================
# GET /api/experiments/ — 列表测试
# ============================================================

class TestListExperiments:
    """GET /api/experiments/ 测试"""

    def test_list_experiments_empty(self, app):
        """测试空列表"""
        response = app.get("/api/experiments/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_experiments_with_data(self, app, sample_experiments):
        """测试返回实验列表"""
        response = app.get("/api/experiments/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        # 验证返回字段
        exp = data[0]
        assert "id" in exp
        assert "name" in exp
        assert "description" in exp
        assert "params" in exp
        assert "metrics" in exp
        assert "status" in exp
        assert "created_at" in exp
        assert "finished_at" in exp

    def test_list_experiments_order(self, app, sample_experiments):
        """测试列表按创建时间倒序"""
        from api.database import Experiment
        from datetime import timedelta

        # 添加一个更新的实验
        newer = Experiment(
            id=99,
            user_id=1,
            name="newest_experiment",
            description="最新实验",
            params={},
            metrics={},
            status="running",
            created_at=datetime.now(timezone.utc) + timedelta(hours=1),
            finished_at=None,
        )
        app.db.add(newer)
        app.db.commit()

        response = app.get("/api/experiments/")
        assert response.status_code == 200
        data = response.json()
        # 最新创建的应在最前
        assert data[0]["name"] == "newest_experiment"
        assert data[0]["id"] == 99

    def test_list_experiments_only_own(self, app, sample_experiments):
        """测试只返回当前用户的实验"""
        from api.database import Experiment

        # 添加一个属于其他用户的实验
        other_exp = Experiment(
            id=888,
            user_id=999,  # 不同的 user_id
            name="other_user_exp",
            description="其他用户的实验",
            params={},
            metrics={},
            status="completed",
            created_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        app.db.add(other_exp)
        app.db.commit()

        response = app.get("/api/experiments/")
        assert response.status_code == 200
        data = response.json()
        # 不应包含其他用户的实验
        ids = [exp["id"] for exp in data]
        assert 888 not in ids


# ============================================================
# GET /api/experiments/{exp_id} — 详情测试
# ============================================================

class TestGetExperiment:
    """GET /api/experiments/{exp_id} 测试"""

    def test_get_experiment_success(self, app, sample_experiments):
        """测试成功获取实验详情"""
        response = app.get("/api/experiments/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "experiment_1"
        assert data["status"] == "completed"

    def test_get_experiment_not_found(self, app):
        """测试实验不存在"""
        response = app.get("/api/experiments/99999")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


# ============================================================
# POST /api/experiments/compare — 实验对比测试
# ============================================================

class TestCompareExperiments:
    """POST /api/experiments/compare 测试"""

    def test_compare_experiments_success(self, app, sample_experiments):
        """测试成功对比多个实验"""
        response = app.post(
            "/api/experiments/compare",
            json={"experiment_ids": [1, 2]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "experiments" in data
        assert len(data["experiments"]) == 2
        # 验证返回字段
        exp = data["experiments"][0]
        assert "id" in exp
        assert "name" in exp
        assert "metrics" in exp
        assert "params" in exp
        assert "status" in exp
        assert "created_at" in exp
        assert "finished_at" in exp

    def test_compare_experiments_single(self, app, sample_experiments):
        """测试对比单个实验"""
        response = app.post(
            "/api/experiments/compare",
            json={"experiment_ids": [1]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["experiments"]) == 1
        assert data["experiments"][0]["id"] == 1

    def test_compare_experiments_not_found(self, app, sample_experiments):
        """测试部分实验不存在"""
        response = app.post(
            "/api/experiments/compare",
            json={"experiment_ids": [1, 99999]},
        )
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_compare_experiments_empty_list(self, app, sample_experiments):
        """测试空列表 — 返回空 experiments 数组"""
        response = app.post(
            "/api/experiments/compare",
            json={"experiment_ids": []},
        )
        # 空列表查不到任何实验，查询结果为空
        assert response.status_code == 200
        assert response.json() == {"experiments": []}

    def test_compare_experiments_empty_db(self, app):
        """测试数据库为空时返回 404"""
        response = app.post(
            "/api/experiments/compare",
            json={"experiment_ids": [1, 2]},
        )
        assert response.status_code == 404


# ============================================================
# POST /api/experiments/compare-curves — 曲线对比测试
# ============================================================

class TestCompareCurves:
    """POST /api/experiments/compare-curves 测试"""

    def test_compare_curves_success(self, app, sample_experiments):
        """测试成功对比多条训练曲线"""
        response = app.post(
            "/api/experiments/compare-curves",
            json={"experiment_ids": [1, 2]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "experiments" in data
        assert len(data["experiments"]) == 2
        # 验证曲线数据结构
        curve_data = data["experiments"][0]
        assert "experiment_id" in curve_data
        assert "experiment_name" in curve_data
        assert "color" in curve_data
        assert "epochs" in curve_data
        assert "curves" in curve_data
        # 验证 curves 包含 4 个指标
        curve_names = {c["name"] for c in curve_data["curves"]}
        assert curve_names == {"train_loss", "val_loss", "train_metric", "val_metric"}

    def test_compare_curves_single(self, app, sample_experiments):
        """测试对比单个实验的曲线"""
        response = app.post(
            "/api/experiments/compare-curves",
            json={"experiment_ids": [1]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["experiments"]) == 1

    def test_compare_curves_no_history_generates_synthetic(self, app):
        """测试没有历史数据时生成模拟曲线"""
        from api.database import Experiment

        # 创建没有历史曲线的实验
        exp = Experiment(
            id=100,
            user_id=1,
            name="no_history_exp",
            description="无历史曲线",
            params={},
            metrics={},  # 没有 train_loss_history 等
            status="completed",
            created_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        app.db.add(exp)
        app.db.commit()

        response = app.post(
            "/api/experiments/compare-curves",
            json={"experiment_ids": [100]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["experiments"]) == 1
        curve_data = data["experiments"][0]
        # 应该有模拟生成的曲线
        assert len(curve_data["curves"]) == 4

    def test_compare_curves_empty_db(self, app):
        """测试数据库为空时返回 404"""
        response = app.post(
            "/api/experiments/compare-curves",
            json={"experiment_ids": [1]},
        )
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_compare_curves_not_found(self, app, sample_experiments):
        """测试实验不存在"""
        response = app.post(
            "/api/experiments/compare-curves",
            json={"experiment_ids": [99999]},
        )
        assert response.status_code == 404


# ============================================================
# GET /api/experiments/{exp_id}/metrics — 指标历史测试
# ============================================================

class TestGetExperimentMetrics:
    """GET /api/experiments/{exp_id}/metrics 测试"""

    def test_get_metrics_success(self, app, sample_experiments):
        """测试成功获取指标历史"""
        response = app.get("/api/experiments/1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "train_loss" in data
        assert "val_loss" in data
        assert "train_acc" in data
        assert "val_acc" in data
        assert "iterations" in data

    def test_get_metrics_not_found(self, app):
        """测试实验不存在"""
        response = app.get("/api/experiments/99999/metrics")
        assert response.status_code == 404
