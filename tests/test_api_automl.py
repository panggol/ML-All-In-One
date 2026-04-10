"""
AutoML API（automl.py）单元测试

使用 FastAPI TestClient + 内存数据库 + mock 认证，
测试请求参数校验、任务不存在、停止任务等场景。
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# 全局 job manager 状态需要重置
import api.routes.automl as automl_module


@pytest.fixture(autouse=True)
def reset_job_manager():
    """每个测试前重置 AutoMLJobManager 状态"""
    automl_module.job_mgr._jobs.clear()
    yield
    automl_module.job_mgr._jobs.clear()


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
def data_file_record(app):
    """创建测试数据文件记录（使用 uploads 目录 + 真实 CSV）"""
    from api.database import DataFile

    # CSV 必须放在 uploads 目录以通过路径安全检查
    uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
    uploads_dir.mkdir(exist_ok=True)
    filepath = uploads_dir / "automl_test.csv"

    data = {
        "feature_a": list(np.random.randn(100)),
        "feature_b": list(np.random.randn(100)),
        "target": list(np.random.randint(0, 2, 100)),
    }
    pd.DataFrame(data).to_csv(filepath, index=False)

    record = DataFile(
        id=1,
        user_id=1,
        filename="automl_test.csv",
        filepath=str(filepath),
        columns=["feature_a", "feature_b", "target"],
        rows=100,
        size=2048,
    )
    app.db.add(record)
    app.db.commit()
    app.db.refresh(record)

    yield record

    if filepath.exists():
        filepath.unlink()


@pytest.fixture
def regression_data_file(app):
    """创建回归测试数据文件（放在 uploads 目录）"""
    from api.database import DataFile

    uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
    uploads_dir.mkdir(exist_ok=True)
    filepath = uploads_dir / "automl_regression.csv"

    rng = np.random.default_rng(42)
    data = {
        "feature_a": list(rng.normal(size=100)),
        "feature_b": list(rng.normal(size=100)),
        "target": list(rng.normal(size=100)),
    }
    pd.DataFrame(data).to_csv(filepath, index=False)

    record = DataFile(
        id=2,
        user_id=1,
        filename="automl_regression.csv",
        filepath=str(filepath),
        columns=["feature_a", "feature_b", "target"],
        rows=100,
        size=2048,
    )
    app.db.add(record)
    app.db.commit()
    app.db.refresh(record)

    yield record

    if filepath.exists():
        filepath.unlink()


class TestAutoMLStartValidation:
    """AutoML 启动请求参数校验测试"""

    def test_automl_start_success(self, app, data_file_record):
        """测试成功创建 AutoML 任务"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "strategy": "random",
            "n_trials": 2,
            "timeout": 60,
        }

        response = app.post("/api/automl/start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] in ("pending", "running")
        assert data["n_trials"] == 2

    def test_automl_start_data_file_not_found(self, app):
        """测试数据文件不存在"""
        payload = {
            "data_file_id": 99999,
            "target_column": "target",
            "task_type": "classification",
            "strategy": "random",
            "n_trials": 2,
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 404
        detail = response.json()["detail"]
        # "数据文件不存在" 或 "任务不存在或已过期"
        assert "不存在" in detail or "已过期" in detail or "不在" in detail

    def test_automl_start_invalid_task_type(self, app, data_file_record):
        """测试无效的 task_type"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "clustering",  # 无效类型
            "strategy": "random",
            "n_trials": 2,
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 400
        assert "classification" in response.json()["detail"] or "regression" in response.json()["detail"]

    def test_automl_start_invalid_strategy(self, app, data_file_record):
        """测试无效的 strategy"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "strategy": "genetic",  # 无效策略
            "n_trials": 2,
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 400

    def test_automl_start_target_column_not_found(self, app, data_file_record):
        """测试目标列不存在"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "nonexistent_column",
            "task_type": "classification",
            "strategy": "random",
            "n_trials": 2,
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 400
        detail = response.json()["detail"]
        # "数据文件不存在" 或 "任务不存在或已过期"
        assert "不存在" in detail or "已过期" in detail or "不在" in detail

    def test_automl_start_custom_search_space(self, app, data_file_record):
        """测试自定义搜索空间"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "strategy": "random",
            "n_trials": 2,
            "search_space": [
                {
                    "name": "model_type",
                    "type": "choice",
                    "values": ["random_forest", "xgboost"],
                },
                {
                    "name": "n_estimators",
                    "type": "int",
                    "low": 50,
                    "high": 100,
                },
            ],
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    def test_automl_start_grid_strategy(self, app, data_file_record):
        """测试 Grid Search 策略"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "strategy": "grid",
            "n_trials": 4,
            "search_space": [
                {
                    "name": "model_type",
                    "type": "choice",
                    "values": ["random_forest", "xgboost"],
                },
                {
                    "name": "max_depth",
                    "type": "int",
                    "low": 3,
                    "high": 5,
                },
            ],
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["n_trials"] == 4

    def test_automl_start_bayesian_strategy(self, app, data_file_record):
        """测试 Bayesian 策略"""
        pytest.importorskip("optuna", reason="optuna required for Bayesian search")

        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "strategy": "bayesian",
            "n_trials": 2,
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    def test_automl_start_regression_task(self, app, regression_data_file):
        """测试回归任务"""
        payload = {
            "data_file_id": regression_data_file.id,
            "target_column": "target",
            "task_type": "regression",
            "strategy": "random",
            "n_trials": 2,
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    def test_automl_start_n_trials_validation(self, app, data_file_record):
        """测试 n_trials 边界值"""
        # n_trials = 0 应该被 Pydantic 拒绝 (ge=1)
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "strategy": "random",
            "n_trials": 0,
        }

        response = app.post("/api/automl/start", json=payload)
        assert response.status_code == 422  # Validation error


class TestAutoMLStatus:
    """AutoML 任务状态查询测试"""

    def test_automl_status_success(self, app, data_file_record):
        """测试成功查询任务状态（mock 防止任务执行）"""
        from fastapi import BackgroundTasks

        def mock_add_task(task_fn, *args, **kwargs):
            pass  # 不执行，防止任务因文件不存在而失败

        with patch("api.routes.automl.SessionLocal") as mock_sl:
            mock_sl.return_value = app.db
            with patch.object(BackgroundTasks, "add_task", mock_add_task):
                create_payload = {
                    "data_file_id": data_file_record.id,
                    "target_column": "target",
                    "task_type": "classification",
                    "strategy": "random",
                    "n_trials": 1,
                    "timeout": 60,
                }
                create_resp = app.post("/api/automl/start", json=create_payload)
                assert create_resp.status_code == 200
                job_id = create_resp.json()["job_id"]

        # 任务未执行，job 状态为 pending
        status_resp = app.get(f"/api/automl/status/{job_id}")
        assert status_resp.status_code == 200
        status = status_resp.json()

        assert status["job_id"] == job_id
        assert "status" in status
        assert "progress" in status
        assert "current_trial" in status

    def test_automl_status_not_found(self, app):
        """测试任务不存在"""
        response = app.get("/api/automl/status/nonexistent-job-id")
        assert response.status_code == 404
        detail = response.json()["detail"]
        # "数据文件不存在" 或 "任务不存在或已过期"
        assert "不存在" in detail or "已过期" in detail or "不在" in detail

    def test_automl_status_pending_job(self, app, data_file_record):
        """测试待处理状态任务"""
        from fastapi import BackgroundTasks

        def mock_add_task(task_fn, *args, **kwargs):
            pass  # 阻止任务执行

        with patch("api.routes.automl.SessionLocal") as mock_sl:
            mock_sl.return_value = app.db
            with patch.object(BackgroundTasks, "add_task", mock_add_task):
                create_payload = {
                    "data_file_id": data_file_record.id,
                    "target_column": "target",
                    "task_type": "classification",
                    "strategy": "random",
                    "n_trials": 1,
                    "timeout": 60,
                }
                create_resp = app.post("/api/automl/start", json=create_payload)
                assert create_resp.status_code == 200
                job_id = create_resp.json()["job_id"]

        # 任务未执行，状态为 pending
        status_resp = app.get(f"/api/automl/status/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] in ("pending",)


class TestAutoMLReport:
    """AutoML 报告查询测试"""

    def test_automl_report_not_found(self, app):
        """测试报告不存在"""
        response = app.get("/api/automl/report/nonexistent-job-id")
        assert response.status_code == 404
        detail = response.json()["detail"]
        # "数据文件不存在" 或 "任务不存在或已过期"
        assert "不存在" in detail or "已过期" in detail or "不在" in detail

    def test_automl_report_pending_job(self, app, data_file_record):
        """测试待处理任务的报告（mock 防止任务执行）"""
        from fastapi import BackgroundTasks

        def mock_add_task(task_fn, *args, **kwargs):
            pass  # 不执行任务

        with patch("api.routes.automl.SessionLocal") as mock_sl:
            mock_sl.return_value = app.db
            with patch.object(BackgroundTasks, "add_task", mock_add_task):
                create_payload = {
                    "data_file_id": data_file_record.id,
                    "target_column": "target",
                    "task_type": "classification",
                    "strategy": "random",
                    "n_trials": 1,
                    "timeout": 60,
                }
                create_resp = app.post("/api/automl/start", json=create_payload)
                assert create_resp.status_code == 200
                job_id = create_resp.json()["job_id"]

        # 任务未执行，报告应返回默认状态
        report_resp = app.get(f"/api/automl/report/{job_id}")
        assert report_resp.status_code in (200, 404)


class TestAutoMLStop:
    """AutoML 停止任务测试"""

    def test_automl_stop_success(self, app, data_file_record):
        """测试成功停止任务（mock background_tasks.add_task 防止任务立即执行）"""
        from fastapi import BackgroundTasks

        captured_tasks = []

        def mock_add_task(task_fn, *args, **kwargs):
            captured_tasks.append((task_fn, args, kwargs))

        with patch("api.routes.automl.SessionLocal") as mock_sl:
            mock_sl.return_value = app.db
            # Mock background_tasks.add_task 防止任务同步执行
            with patch.object(BackgroundTasks, "add_task", mock_add_task):
                create_payload = {
                    "data_file_id": data_file_record.id,
                    "target_column": "target",
                    "task_type": "classification",
                    "strategy": "random",
                    "n_trials": 10,
                }
                create_resp = app.post("/api/automl/start", json=create_payload)
                assert create_resp.status_code == 200
                job_id = create_resp.json()["job_id"]

        # 任务未执行（被 mock），状态应为 pending/running
        status_resp = app.get(f"/api/automl/status/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] in ("pending", "running")

        # 停止任务
        stop_resp = app.post(f"/api/automl/stop/{job_id}")
        assert stop_resp.status_code == 200
        assert "停止" in stop_resp.json()["message"]

    def test_automl_stop_not_found(self, app):
        """测试停止不存在的任务"""
        response = app.post("/api/automl/stop/nonexistent-job-id")
        assert response.status_code == 404
        detail = response.json()["detail"]
        # "数据文件不存在" 或 "任务不存在或已过期"
        assert "不存在" in detail or "已过期" in detail or "不在" in detail

    def test_automl_stop_forbidden_other_user(self, app):
        """测试无权访问其他用户的任务"""
        # 创建一个属于其他用户的任务
        other_user_job_id = automl_module.job_mgr.create()
        automl_module.job_mgr.update(
            other_user_job_id,
            user_id=999,  # 不同的 user_id
            status="running",
            n_trials=5,
        )

        response = app.post(f"/api/automl/stop/{other_user_job_id}")
        # 无权访问，应该被拒绝
        assert response.status_code == 403


class TestAutoMLRequestValidation:
    """AutoML 请求模型验证测试"""

    def test_search_space_item_choice(self):
        """测试 SearchSpaceItem Pydantic 模型 - choice 类型"""
        from api.routes.automl import SearchSpaceItem

        item = SearchSpaceItem(
            name="model_type",
            type="choice",
            values=["rf", "xgb"],
        )
        assert item.name == "model_type"
        assert item.type == "choice"
        assert item.values == ["rf", "xgb"]

    def test_search_space_item_int(self):
        """测试 SearchSpaceItem Pydantic 模型 - int 类型"""
        from api.routes.automl import SearchSpaceItem

        item = SearchSpaceItem(
            name="n_estimators",
            type="int",
            low=50,
            high=200,
            step=10,
        )
        assert item.name == "n_estimators"
        assert item.type == "int"
        assert item.low == 50
        assert item.high == 200
        assert item.step == 10

    def test_search_space_item_float(self):
        """测试 SearchSpaceItem Pydantic 模型 - float 类型"""
        from api.routes.automl import SearchSpaceItem

        item = SearchSpaceItem(
            name="learning_rate",
            type="float",
            low=0.01,
            high=0.3,
            log=True,
        )
        assert item.name == "learning_rate"
        assert item.type == "float"
        assert item.log is True

    def test_search_space_item_defaults(self):
        """测试 SearchSpaceItem 默认值"""
        from api.routes.automl import SearchSpaceItem

        item = SearchSpaceItem(name="lr", type="float", low=0.01, high=0.3)
        assert item.step == 1
        assert item.log is False

    def test_automl_request_defaults(self):
        """测试 AutoMLStartRequest 默认值"""
        from api.routes.automl import AutoMLStartRequest

        # 只提供必填字段
        req = AutoMLStartRequest(
            data_file_id=1,
            target_column="target",
            task_type="classification",
        )
        assert req.strategy == "random"  # 默认值
        assert req.n_trials == 10  # 默认值
        assert req.timeout == 300  # 默认值
        assert req.search_space == []  # 默认空列表

    def test_automl_response_model(self):
        """测试 AutoMLJobResponse 模型"""
        from api.routes.automl import AutoMLJobResponse

        resp = AutoMLJobResponse(
            job_id="abc123",
            status="running",
            progress=50,
            current_trial=5,
            n_trials=10,
            logs="Trial 5 done",
        )
        assert resp.job_id == "abc123"
        assert resp.status == "running"
        assert resp.progress == 50
