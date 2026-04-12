"""
Train API 单元测试

覆盖 train 路由全部 5 个端点：
- POST /api/train          — 创建训练任务
- GET  /api/train          — 列出训练任务
- GET  /api/train/{job_id}/status  — 查询训练状态
- POST /api/train/{job_id}/stop    — 停止训练
- POST /api/train/{job_id}/predict — 推理

使用 FastAPI TestClient + 内存数据库 + mock 认证。
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Set test database BEFORE any api imports
import secrets
os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MODELS_DIR"] = "/tmp/ml_models_test"
os.environ["API_SECRET_KEY"] = os.environ.get("API_SECRET_KEY") or secrets.token_hex(32)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Reset training manager state
import api.routes.train as train_module


@pytest.fixture(autouse=True)
def reset_training_manager():
    """每个测试前重置 TrainingManager 状态"""
    train_module.training_mgr._jobs.clear()
    train_module.training_mgr._stop_events.clear()
    train_module.training_mgr._runners.clear()
    yield
    train_module.training_mgr._jobs.clear()
    train_module.training_mgr._stop_events.clear()
    train_module.training_mgr._runners.clear()


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
    """创建测试数据文件记录（放在 uploads 目录 + 真实 CSV）"""
    from api.database import DataFile

    uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
    uploads_dir.mkdir(exist_ok=True)
    filepath = uploads_dir / "train_test.csv"

    data = {
        "feature_a": list(np.random.randn(100)),
        "feature_b": list(np.random.randn(100)),
        "feature_c": list(np.random.randn(100)),
        "target": list(np.random.randint(0, 2, 100)),
    }
    pd.DataFrame(data).to_csv(filepath, index=False)

    record = DataFile(
        id=1,
        user_id=1,
        filename="train_test.csv",
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


@pytest.fixture
def regression_data_file(app):
    """创建回归测试数据文件"""
    from api.database import DataFile

    uploads_dir = Path("/home/gem/workspace/agent/workspace/ml-all-in-one/uploads")
    uploads_dir.mkdir(exist_ok=True)
    filepath = uploads_dir / "train_regression.csv"

    rng = np.random.default_rng(42)
    data = {
        "feat_x": list(rng.normal(size=100)),
        "feat_y": list(rng.normal(size=100)),
        "target": list(rng.normal(size=100)),
    }
    pd.DataFrame(data).to_csv(filepath, index=False)

    record = DataFile(
        id=2,
        user_id=1,
        filename="train_regression.csv",
        filepath=str(filepath),
        columns=["feat_x", "feat_y", "target"],
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
# 缺陷 1 修复：覆盖 train 路由全部 5 个端点
# =============================================================================

class TestTrainCreate:
    """POST /api/train — 创建训练任务"""

    def test_create_training_success(self, app, data_file_record):
        """测试成功创建训练任务（mock 防止真实训练）"""


        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {"n_estimators": 10, "max_depth": 3, "epochs": 1},
        }

        with patch("api.routes.train._run_training"):
            response = app.post("/api/train", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["model_name"] == "RandomForestClassifier"
        assert data["task_type"] == "classification"
        assert data["status"] == "pending"

    def test_create_training_data_file_not_found(self, app):
        """测试数据文件不存在"""
        payload = {
            "data_file_id": 99999,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b"],
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_create_training_missing_fields(self, app):
        """测试缺少必填字段"""
        payload = {
            "data_file_id": 1,
            # 缺少 target_column, task_type, model_type, model_name
        }

        response = app.post("/api/train", json=payload)
        assert response.status_code == 422  # Validation error

    def test_create_training_regression_task(self, app, regression_data_file):
        """测试回归任务创建"""


        payload = {
            "data_file_id": regression_data_file.id,
            "target_column": "target",
            "task_type": "regression",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feat_x", "feat_y"],
            "params": {},
        }

        with patch("api.routes.train._run_training"):
            response = app.post("/api/train", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "regression"

    def test_create_training_with_feature_columns(self, app, data_file_record):
        """测试指定特征列创建训练任务"""


        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b"],
            "params": {"n_estimators": 5},
        }

        with patch("api.routes.train._run_training"):
            response = app.post("/api/train", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data


class TestTrainList:
    """GET /api/train — 列出训练任务"""

    def test_list_jobs_empty(self, app):
        """测试空列表"""
        response = app.get("/api/train")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_jobs_with_jobs(self, app, data_file_record):
        """测试列出训练任务"""


        # 创建两个任务
        for _ in range(2):
            payload = {
                "data_file_id": data_file_record.id,
                "target_column": "target",
                "task_type": "classification",
                "model_type": "sklearn",
                "model_name": "RandomForestClassifier",
                "params": {"epochs": 1},
                "feature_columns": ["feature_a", "feature_b", "feature_c"],
            }
            with patch("api.routes.train._run_training"):
                app.post("/api/train", json=payload)

        response = app.get("/api/train")
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 2
        # 最新的在前面
        assert jobs[0]["model_name"] == "RandomForestClassifier"


class TestTrainStatus:
    """GET /api/train/{job_id}/status — 查询训练状态"""

    def test_get_status_success(self, app, data_file_record):
        """测试查询训练状态（mock background_tasks 防止真实训练）"""


        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {"epochs": 1},
        }

        with patch("api.routes.train._run_training"):
            create_resp = app.post("/api/train", json=payload)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]

        # 查询状态
        status_resp = app.get(f"/api/train/{job_id}/status")
        assert status_resp.status_code == 200
        status = status_resp.json()

        assert status["id"] == job_id
        assert "status" in status
        assert "progress" in status
        assert "metrics" in status
        assert "metrics_curve" in status
        assert "logs" in status

    def test_get_status_not_found(self, app):
        """测试任务不存在"""
        response = app.get("/api/train/99999/status")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]


class TestTrainStop:
    """POST /api/train/{job_id}/stop — 停止训练"""

    def test_stop_success(self, app, data_file_record):
        """测试成功停止训练（mock 防止真实训练执行）"""


        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {"epochs": 1},
        }

        with patch("api.routes.train._run_training"):
            create_resp = app.post("/api/train", json=payload)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]

        # 停止任务
        stop_resp = app.post(f"/api/train/{job_id}/stop")
        assert stop_resp.status_code == 200
        assert "停止" in stop_resp.json()["message"]

    def test_stop_not_found(self, app):
        """测试停止不存在的任务"""
        response = app.post("/api/train/99999/stop")
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_stop_already_completed(self, app, data_file_record):
        """测试停止已完成的训练任务（应返回 400）"""


        # 创建一个已完成的任务
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {"epochs": 1},
        }

        with patch("api.routes.train._run_training"):
            create_resp = app.post("/api/train", json=payload)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]

        # 模拟任务已完成
        from api.database import TrainingJob
        from sqlalchemy.orm import Session
        db: Session = app.db
        job = db.get(TrainingJob, job_id)
        job.status = "completed"
        db.commit()

        stop_resp = app.post(f"/api/train/{job_id}/stop")
        assert stop_resp.status_code == 400
        assert "完成" in stop_resp.json()["detail"] or "停止" in stop_resp.json()["detail"]


class TestTrainPredict:
    """POST /api/train/{job_id}/predict — 推理"""

    def test_predict_success(self, app, data_file_record):
        """测试成功推理（使用已训练模型）"""
        import joblib
        import os

        # 跳过真实训练，直接在测试 fixture 的 db 中设置完成状态
        from api.database import TrainingJob, DataFile
        from mlkit.model import create_model
        from sklearn.model_selection import train_test_split
        import pandas as pd
        from sqlalchemy.orm import Session

        # 1. 通过 API 创建训练任务（训练会被 patch 跳过）
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {"n_estimators": 5, "max_depth": 3, "epochs": 1},
        }

        # 直接 patch _run_training 让它什么都不做
        with patch("api.routes.train._run_training"):
            create_resp = app.post("/api/train", json=payload)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]

        # 2. 直接在 app.db 中设置完成状态和模型文件
        db: Session = app.db
        job = db.get(TrainingJob, job_id)
        data_file = db.get(DataFile, data_file_record.id)

        df = pd.read_csv(data_file.filepath)
        X = df[["feature_a", "feature_b", "feature_c"]].values
        y = df["target"].values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        model = create_model(
            "sklearn", model_class="RandomForestClassifier",
            n_estimators=5, max_depth=3
        )
        model.fit(X_train, y_train)

        os.makedirs("/tmp/ml_models_test", exist_ok=True)
        model_path = "/tmp/ml_models_test/test_model.joblib"
        model.save(model_path)

        job.status = "completed"
        job.progress = 100
        job.checkpoint_path = model_path
        job.metrics = {"accuracy": 0.9}
        job.metrics_curve = {
            "epochs": [1],
            "train_loss": [0.1],
            "val_loss": [0.1],
            "train_accuracy": [0.95],
            "val_accuracy": [0.9],
        }
        db.commit()

        # 同时更新内存状态，否则 status 端点返回 pending（优先读内存）
        train_module.training_mgr.update(
            job_id,
            status="completed",
            progress=100,
            metrics_curve=job.metrics_curve,
        )

        # 3. 验证状态
        status_resp = app.get(f"/api/train/{job_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"

        # 4. 推理
        predict_payload = {
            "data": [
                {"feature_a": 0.1, "feature_b": -0.2, "feature_c": 0.3},
                {"feature_a": -0.5, "feature_b": 0.8, "feature_c": -0.1},
            ]
        }
        predict_resp = app.post(f"/api/train/{job_id}/predict", json=predict_payload)
        assert predict_resp.status_code == 200
        result = predict_resp.json()
        assert "predictions" in result
        assert len(result["predictions"]) == 2

    def test_predict_not_found(self, app):
        """测试推理不存在的任务"""
        payload = {"data": [{"feature_a": 0.1}]}
        response = app.post("/api/train/99999/predict", json=payload)
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]

    def test_predict_not_completed(self, app, data_file_record):
        """测试训练未完成时推理（应返回 400）"""
        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {"epochs": 1},
        }

        with patch("api.routes.train._run_training"):
            create_resp = app.post("/api/train", json=payload)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]

        # 训练未完成，尝试推理
        predict_payload = {"data": [{"feature_a": 0.1, "feature_b": 0.2, "feature_c": 0.3}]}
        predict_resp = app.post(f"/api/train/{job_id}/predict", json=predict_payload)
        assert predict_resp.status_code == 400
        assert "完成" in predict_resp.json()["detail"]

    def test_predict_model_file_missing(self, app, data_file_record):
        """测试模型文件缺失时的推理"""
        from api.database import TrainingJob

        payload = {
            "data_file_id": data_file_record.id,
            "target_column": "target",
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": ["feature_a", "feature_b", "feature_c"],
            "params": {"epochs": 1},
        }

        with patch("api.routes.train._run_training"):
            create_resp = app.post("/api/train", json=payload)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["id"]

        # 手动标记为已完成但无模型文件
        from sqlalchemy.orm import Session
        db: Session = app.db
        job = db.get(TrainingJob, job_id)
        job.status = "completed"
        job.checkpoint_path = "/nonexistent/model.joblib"
        db.commit()

        predict_payload = {"data": [{"feature_a": 0.1, "feature_b": 0.2, "feature_c": 0.3}]}
        predict_resp = app.post(f"/api/train/{job_id}/predict", json=predict_payload)
        assert predict_resp.status_code == 404
        assert "不存在" in predict_resp.json()["detail"]
