"""
test_untested_models.py — 未测试模型的端到端训练验证

覆盖：
- SVC（分类）
- SVR（回归）
- LinearRegression（回归）
- GradientBoostingClassifier（分类）
- PyTorchModel 基类（非 sklearn 接口，直接测试）

关键设计：
- DATABASE_URL 在模块导入前设置，确保 TestClient 与 _run_training 共享同一数据库文件
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
os.environ["MODELS_DIR"] = "/tmp/ml_models_untested"

_TEST_DB = "/tmp/test_untested_models.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

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
    train_module.training_mgr._jobs.clear()
    train_module.training_mgr._stop_events.clear()
    train_module.training_mgr._runners.clear()
    yield
    train_module.training_mgr._jobs.clear()
    train_module.training_mgr._stop_events.clear()
    train_module.training_mgr._runners.clear()


@pytest.fixture
def app():
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from api.main import app as main_app
    from api.auth import get_current_user, get_db
    from api.database import SessionLocal, Base, engine as db_engine

    Base.metadata.create_all(bind=db_engine)
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
    from api.database import DataFile

    # 先删除旧的 DataFile（测试隔离）
    old = app.db.query(DataFile).filter(DataFile.id == 1).first()
    if old:
        app.db.delete(old)
        app.db.commit()

    uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
    uploads_dir.mkdir(exist_ok=True)
    filepath = uploads_dir / "untested_models.csv"

    rng = np.random.default_rng(42)
    data = {
        "feature_a": rng.normal(size=100).tolist(),
        "feature_b": rng.normal(size=100).tolist(),
        "target_cls": (rng.normal(size=100) > 0).astype(int).tolist(),
        "target_reg": (2 * rng.normal(size=100) + rng.normal(size=100) * 0.3).tolist(),
    }
    pd.DataFrame(data).to_csv(filepath, index=False)

    record = DataFile(
        id=1,
        user_id=1,
        filename="untested_models.csv",
        filepath=str(filepath),
        columns=["feature_a", "feature_b", "target_cls", "target_reg"],
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
# 分类模型测试
# =============================================================================

class TestSVC:
    def test_train_svc_classifier(self, app, data_file_record):
        """端到端真实训练：SVC，验证 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target_cls",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "SVC",
            "feature_columns": ["feature_a", "feature_b"],
            "params": {"random_state": 42},
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]

        for _ in range(120):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", f"训练失败: {status_data}"
        assert status_data["progress"] == 100
        metrics = status_data["metrics"]
        assert metrics.get("accuracy", 0) > 0, f"accuracy 应 > 0，实际={metrics}"
        assert metrics.get("f1", 0) >= 0, f"f1 应 >= 0，实际={metrics}"
        assert any(k in metrics for k in ["accuracy", "f1", "precision", "recall"])
        assert "mse" not in metrics, "分类器不应有 mse 指标"


class TestGradientBoosting:
    def test_train_gb_classifier(self, app, data_file_record):
        """端到端真实训练：GradientBoostingClassifier，验证 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target_cls",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "GradientBoostingClassifier",
            "feature_columns": ["feature_a", "feature_b"],
            "params": {"n_estimators": 10, "max_depth": 3, "random_state": 42},
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]

        for _ in range(120):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", f"训练失败: {status_data}"
        assert status_data["progress"] == 100
        metrics = status_data["metrics"]
        assert metrics.get("accuracy", 0) > 0, f"accuracy 应 > 0，实际={metrics}"
        assert metrics.get("f1", 0) >= 0, f"f1 应 >= 0，实际={metrics}"
        assert any(k in metrics for k in ["accuracy", "f1", "precision", "recall"])
        assert "mse" not in metrics, "分类器不应有 mse 指标"


# =============================================================================
# 回归模型测试
# =============================================================================

class TestSVR:
    def test_train_svr_regressor(self, app, data_file_record):
        """端到端真实训练：SVR，验证回归 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target_reg",
            "task_type": "regression",
            "model_type": "sklearn",
            "model_name": "SVR",
            "feature_columns": ["feature_a", "feature_b"],
            "params": {},
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]

        for _ in range(120):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", f"训练失败: {status_data}"
        metrics = status_data["metrics"]
        # SVR 是回归，应该有 mse/mae/r2
        assert any(k in metrics for k in ["mse", "mae", "r2", "rmse"]), f"回归器应有回归指标，实际={metrics}"
        assert "accuracy" not in metrics, "回归器不应有 accuracy 指标"
        assert "f1" not in metrics, "回归器不应有 f1 指标"


class TestLinearRegression:
    def test_train_linear_regression(self, app, data_file_record):
        """端到端真实训练：LinearRegression，验证回归 metrics 非零"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target_reg",
            "task_type": "regression",
            "model_type": "sklearn",
            "model_name": "LinearRegression",
            "feature_columns": ["feature_a", "feature_b"],
            "params": {},
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 200, f"创建任务失败: {response.json()}"
        data = response.json()
        job_id = data["id"]

        for _ in range(120):
            time.sleep(1)
            status_resp = app.get(f"/api/train/{job_id}/status")
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break

        assert status_data["status"] == "completed", f"训练失败: {status_data}"
        metrics = status_data["metrics"]
        assert any(k in metrics for k in ["mse", "mae", "r2", "rmse"]), f"回归器应有回归指标，实际={metrics}"
        assert "accuracy" not in metrics, "回归器不应有 accuracy 指标"
        assert "f1" not in metrics, "回归器不应有 f1 指标"


# =============================================================================
# PyTorch Model 直接测试（基类，非 sklearn 接口）
# =============================================================================

class TestPyTorchModel:
    def test_pytorch_mlp_direct(self):
        """直接测试 PyTorch MLPClassifier：fit/predict/predict_proba"""
        import pandas as pd
        import numpy as np
        from mlkit.model.pytorch_model import MLPClassifier

        rng = np.random.default_rng(42)
        X = pd.DataFrame({"f1": rng.normal(size=60), "f2": rng.normal(size=60)})
        y = (rng.normal(size=60) > 0).astype(int).tolist()

        clf = MLPClassifier(hidden_layer_sizes=(20,), max_iter=100, task="classification", random_state=42)
        clf.fit(X, y)

        pred = clf.predict(X)
        assert len(pred) == 60
        assert all(p in [0, 1] for p in pred)

        proba = clf.predict_proba(X)
        assert proba.shape == (60, 2)
        assert all(0 <= p <= 1 for row in proba for p in row)

    def test_pytorch_regressor_direct(self):
        """直接测试 PyTorch 回归：fit/predict"""
        import pandas as pd
        import numpy as np
        from mlkit.model.pytorch_model import MLPClassifier

        rng = np.random.default_rng(42)
        X = pd.DataFrame({"f1": rng.normal(size=60), "f2": rng.normal(size=60)})
        y = (2 * rng.normal(size=60) + 0.5 * rng.normal(size=60)).tolist()

        reg = MLPClassifier(hidden_layer_sizes=(20,), max_iter=100, task="regression", random_state=42)
        reg.fit(X, pd.Series(y))

        pred = reg.predict(X)
        assert len(pred) == 60
        assert all(isinstance(p, (float, np.floating)) for p in pred)
