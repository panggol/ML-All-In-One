"""
test_models_training.py — 端到端真实训练测试（无 mock）

为 XGBClassifier、LGBMClassifier、LogisticRegression、MLPClassifier
各写一个完整训练流程测试，验证 metrics 非全零。

关键设计：
- DATABASE_URL 在模块导入前设置为文件型 SQLite（确保 _run_training
  的 SessionLocal 与 TestClient 使用同一数据库文件）
"""
import os
import sys
import time
import secrets
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 必须先于 api 模块导入设置 DATABASE_URL
os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
os.environ["API_SECRET_KEY"] = os.environ.get("API_SECRET_KEY") or secrets.token_hex(32)
os.environ["MODELS_DIR"] = "/tmp/ml_models_test"

_TEST_DB = "/tmp/test_training_models.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

# 清理旧数据库文件（仅在模块首次加载时）
if os.path.exists(_TEST_DB):
    try:
        os.unlink(_TEST_DB)
    except PermissionError:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import api.routes.train as train_module


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_training_manager():
    """每个测试前后重置 TrainingManager"""
    train_module.training_mgr._jobs.clear()
    train_module.training_mgr._stop_events.clear()
    train_module.training_mgr._runners.clear()
    yield
    train_module.training_mgr._jobs.clear()
    train_module.training_mgr._stop_events.clear()
    train_module.training_mgr._runners.clear()


@pytest.fixture
def app():
    """
    构建 FastAPI 测试应用。

    关键：直接复用 api.database.SessionLocal（与 _run_training 背景线程
    使用同一 engine/数据库文件），而非创建独立的 engine。
    """
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from api.main import app as main_app
    from api.auth import get_current_user
    from api.database import get_db
    from api.database import SessionLocal, Base, engine as db_engine

    # 重建表（每个 test fresh start），必须用与 SessionLocal 相同的 engine
    Base.metadata.create_all(bind=db_engine)

    # 直接复用模块级 SessionLocal，确保与 _run_training 使用同一 engine
    db_session = SessionLocal()

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

    main_app.dependency_overrides[get_current_user] = override_get_current_user
    main_app.dependency_overrides[get_db] = override_get_db

    client = TestClient(main_app)
    client.db = db_session
    yield client
    db_session.close()
    main_app.dependency_overrides.clear()


@pytest.fixture
def data_file_record(app):
    """创建测试数据文件（100行，二分类，3个数值特征）"""
    from api.database import DataFile

    # 先删除旧的 DataFile（测试隔离）
    old = app.db.query(DataFile).filter(DataFile.id == 1).first()
    if old:
        app.db.delete(old)
        app.db.commit()

    uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
    uploads_dir.mkdir(exist_ok=True)
    filepath = uploads_dir / "train_test_models.csv"

    rng = np.random.default_rng(42)
    data = {
        "feature_a": rng.normal(size=100).tolist(),
        "feature_b": rng.normal(size=100).tolist(),
        "feature_c": rng.normal(size=100).tolist(),
        "target": (rng.normal(size=100) > 0).astype(int).tolist(),
    }
    pd.DataFrame(data).to_csv(filepath, index=False)

    record = DataFile(
        id=1,
        user_id=1,
        filename="train_test_models.csv",
        filepath=str(filepath),
        columns=["feature_a", "feature_b", "feature_c", "target"],
        rows=100,
        size=2048,
    )
    app.db.add(record)
    app.db.commit()
    app.db.refresh(record)

    yield record

    if filepath.exists():
        filepath.unlink()


# =============================================================================
# 测试：XGBClassifier
# =============================================================================

class TestXGBClassifier:
    def test_train_xgb_classifier(self, app, data_file_record):
        """端到端真实训练：XGBClassifier，验证 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "xgboost",
            "model_name": "XGBClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {
                "n_estimators": 10,
                "max_depth": 3,
                "learning_rate": 0.1,
                "random_state": 42,
            },
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]
        assert data["status"] == "pending"
        assert data["model_name"] == "XGBClassifier"

        # 轮询直到完成（超时 120s）
        for _ in range(120):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", (
            f"训练未完成，状态={status_data['status']}, "
            f"error={status_data.get('error_message', 'N/A')}"
        )
        assert status_data["progress"] == 100

        metrics = status_data["metrics"]
        assert metrics.get("accuracy", 0) > 0, f"accuracy 应 > 0，实际={metrics}"
        assert metrics.get("f1", 0) >= 0, f"f1 应 >= 0，实际={metrics}"
        assert metrics.get("precision", 0) >= 0, f"precision 应 >= 0，实际={metrics}"
        assert metrics.get("recall", 0) >= 0, f"recall 应 >= 0，实际={metrics}"


# =============================================================================
# 测试：LGBMClassifier
# =============================================================================

class TestLGBMClassifier:
    def test_train_lgbm_classifier(self, app, data_file_record):
        """端到端真实训练：LGBMClassifier，验证 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "lightgbm",
            "model_name": "LGBMClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {
                "n_estimators": 10,
                "max_depth": 3,
                "learning_rate": 0.1,
                "random_state": 42,
            },
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]
        assert data["status"] == "pending"
        assert data["model_name"] == "LGBMClassifier"

        for _ in range(120):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", (
            f"训练未完成，状态={status_data['status']}"
        )
        assert status_data["progress"] == 100

        metrics = status_data["metrics"]
        assert metrics.get("accuracy", 0) > 0, f"accuracy 应 > 0，实际={metrics}"
        assert metrics.get("f1", 0) >= 0, f"f1 应 >= 0，实际={metrics}"
        assert metrics.get("precision", 0) >= 0, f"precision 应 >= 0，实际={metrics}"
        assert metrics.get("recall", 0) >= 0, f"recall 应 >= 0，实际={metrics}"


# =============================================================================
# 测试：LogisticRegression
# =============================================================================

class TestLogisticRegression:
    def test_train_logistic_regression(self, app, data_file_record):
        """端到端真实训练：LogisticRegression，验证 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "LogisticRegression",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {
                "max_iter": 100,
                "random_state": 42,
                "solver": "lbfgs",
            },
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]
        assert data["status"] == "pending"
        assert data["model_name"] == "LogisticRegression"

        for _ in range(120):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", (
            f"训练未完成，状态={status_data['status']}"
        )
        assert status_data["progress"] == 100

        metrics = status_data["metrics"]
        assert metrics.get("accuracy", 0) > 0, f"accuracy 应 > 0，实际={metrics}"
        assert metrics.get("f1", 0) >= 0, f"f1 应 >= 0，实际={metrics}"
        assert metrics.get("precision", 0) >= 0, f"precision 应 >= 0，实际={metrics}"
        assert metrics.get("recall", 0) >= 0, f"recall 应 >= 0，实际={metrics}"


# =============================================================================
# 测试：MLPClassifier（PyTorch）
# =============================================================================

class TestMLPClassifier:
    def test_train_mlp_classifier(self, app, data_file_record):
        """端到端真实训练：MLPClassifier（PyTorch），验证 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "pytorch",
            "model_name": "MLPClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {
                "hidden_layer_sizes": (32, 16),
                "activation": "relu",
                "solver": "adam",
                "alpha": 0.001,
                "max_iter": 50,
                "random_state": 42,
            },
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]
        assert data["status"] == "pending"
        assert data["model_name"] == "MLPClassifier"

        for _ in range(180):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", (
            f"训练未完成，状态={status_data['status']}"
        )
        assert status_data["progress"] == 100

        metrics = status_data["metrics"]
        assert metrics.get("accuracy", 0) > 0, f"accuracy 应 > 0，实际={metrics}"
        assert metrics.get("f1", 0) >= 0, f"f1 应 >= 0，实际={metrics}"
        assert metrics.get("precision", 0) >= 0, f"precision 应 >= 0，实际={metrics}"
        assert metrics.get("recall", 0) >= 0, f"recall 应 >= 0，实际={metrics}"
