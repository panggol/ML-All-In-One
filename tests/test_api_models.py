"""
模型管理 API 测试 - test_api_models.py

覆盖 inference_tab 模块全部 4 个端点：
- GET  /api/models/           — 模型列表
- GET  /api/models/{model_id}  — 模型详情
- POST /api/models/{model_id}/predict — 推理
- DELETE /api/models/{model_id}  — 删除模型

使用 FastAPI TestClient + 内存数据库 + mock 认证。
"""
import os
import sys
import secrets
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import joblib

# Set test environment BEFORE any api imports
os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MODELS_DIR"] = tempfile.mkdtemp()
os.environ["API_SECRET_KEY"] = os.environ.get("API_SECRET_KEY") or secrets.token_hex(32)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import Base, TrainedModel, User, get_db
from api.auth import get_current_user
from api.main import app


# ========================================================================
# Fixtures
# ========================================================================

@pytest.fixture(autouse=True)
def _setup_db():
    """每个测试前创建独立 in-memory 数据库，完成后销毁"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    def override_get_current_user():
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        return user

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield session, TestingSession, engine

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(_setup_db):
    """FastAPI TestClient"""
    return TestClient(app)


@pytest.fixture
def db_session(_setup_db):
    return _setup_db[0]


@pytest.fixture
def other_user_session(_setup_db):
    """另一个用户的 session（id=2）"""
    session = _setup_db[0]
    other_user = User(
        id=2,
        username="otheruser",
        email="other@example.com",
        password_hash="dummy",
    )
    session.add(other_user)
    session.commit()
    return session


@pytest.fixture
def trained_model_record(db_session):
    """创建一条属于用户 1 的 TrainedModel 记录"""
    from sklearn.ensemble import RandomForestClassifier

    # 训练一个简单模型
    X = np.random.randn(50, 3)
    y = (X[:, 0] > 0).astype(int)
    clf = RandomForestClassifier(n_estimators=5, random_state=42)
    clf.fit(X, y)

    model_dir = os.environ["MODELS_DIR"]
    model_path = os.path.join(model_dir, "test_model_1.joblib")
    joblib.dump(clf, model_path)

    record = TrainedModel(
        id=1,
        user_id=1,
        name="test_model",
        model_type="sklearn",
        model_path=model_path,
        metrics={"accuracy": 0.92},
    )
    db_session.add(record)
    db_session.commit()
    return record


@pytest.fixture
def other_user_model(other_user_session):
    """创建一条属于用户 2 的 TrainedModel 记录"""
    from sklearn.ensemble import RandomForestClassifier

    X = np.random.randn(30, 3)
    y = (X[:, 0] > 0).astype(int)
    clf = RandomForestClassifier(n_estimators=5, random_state=42)
    clf.fit(X, y)

    model_dir = os.environ["MODELS_DIR"]
    model_path = os.path.join(model_dir, "test_model_2.joblib")
    joblib.dump(clf, model_path)

    record = TrainedModel(
        id=2,
        user_id=2,
        name="other_user_model",
        model_type="sklearn",
        model_path=model_path,
        metrics={"accuracy": 0.88},
    )
    other_user_session.add(record)
    other_user_session.commit()
    return record


@pytest.fixture
def model_missing_file(db_session):
    """TrainedModel 记录，但模型文件不存在"""
    record = TrainedModel(
        id=3,
        user_id=1,
        name="missing_file_model",
        model_type="sklearn",
        model_path="/nonexistent/path/model.joblib",
        metrics={},
    )
    db_session.add(record)
    db_session.commit()
    return record


# ========================================================================
# GET /api/models/ — 模型列表
# ========================================================================

class TestListModels:
    def test_list_models_normal(self, client, trained_model_record):
        """正常返回模型列表"""
        response = client.get("/api/models/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "test_model"
        assert data[0]["model_type"] == "sklearn"
        assert "metrics" in data[0]
        assert "created_at" in data[0]

    def test_list_models_empty(self, client):
        """用户没有任何模型时返回空数组"""
        response = client.get("/api/models/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_models_user_isolation(self, client, trained_model_record, other_user_model):
        """用户只能看到自己的模型，不能看到其他用户的"""
        response = client.get("/api/models/")
        assert response.status_code == 200
        data = response.json()
        names = [m["name"] for m in data]
        assert "test_model" in names
        assert "other_user_model" not in names


# ========================================================================
# GET /api/models/{model_id} — 模型详情
# ========================================================================

class TestGetModel:
    def test_get_model_normal(self, client, trained_model_record):
        """正常获取模型详情"""
        response = client.get("/api/models/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "test_model"
        assert data["model_type"] == "sklearn"
        assert "metrics" in data

    def test_get_model_not_found(self, client):
        """模型不存在 → 404"""
        response = client.get("/api/models/999")
        assert response.status_code == 404
        assert "模型不存在" in response.json()["detail"]

    def test_get_model_other_user(self, client, other_user_model):
        """其他用户的模型 → 404（不暴露存在性）"""
        response = client.get("/api/models/2")
        assert response.status_code == 404


# ========================================================================
# POST /api/models/{model_id}/predict — 推理
# ========================================================================

class TestPredict:
    def test_predict_normal_classification(self, client, trained_model_record):
        """正常推理（分类模型，返回概率）"""
        response = client.post(
            "/api/models/1/predict",
            json={"data": [{"f1": 1.0, "f2": 2.0, "f3": 0.0}]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert isinstance(data["predictions"], list)
        assert len(data["predictions"]) == 1
        # 分类应有 probabilities
        assert "probabilities" in data

    def test_predict_multiple_rows(self, client, trained_model_record):
        """批量推理多行数据"""
        rows = [
            {"f1": 1.0, "f2": 2.0, "f3": 0.0},
            {"f1": -1.0, "f2": -2.0, "f3": 1.0},
            {"f1": 0.5, "f2": 0.5, "f3": 0.0},
        ]
        response = client.post("/api/models/1/predict", json={"data": rows})
        assert response.status_code == 200
        data = response.json()
        assert len(data["predictions"]) == 3

    def test_predict_empty_data(self, client, trained_model_record):
        """空数组 → 422 Pydantic 验证失败"""
        response = client.post("/api/models/1/predict", json={"data": []})
        assert response.status_code == 422

    def test_predict_model_not_found(self, client):
        """模型不存在 → 404"""
        response = client.post(
            "/api/models/999/predict",
            json={"data": [{"f1": 1.0}]}
        )
        assert response.status_code == 404

    def test_predict_other_user_model(self, client, other_user_model):
        """其他用户的模型 → 404"""
        response = client.post(
            "/api/models/2/predict",
            json={"data": [{"f1": 1.0}]}
        )
        assert response.status_code == 404

    def test_predict_model_file_missing(self, client, model_missing_file):
        """模型文件不存在 → 500"""
        response = client.post(
            "/api/models/3/predict",
            json={"data": [{"f1": 1.0}]}
        )
        assert response.status_code == 500
        assert "模型加载失败" in response.json()["detail"]

    def test_predict_error_message_no_internal_leak(self, client, model_missing_file):
        """错误消息不泄露内部路径或堆栈"""
        response = client.post(
            "/api/models/3/predict",
            json={"data": [{"f1": 1.0}]}
        )
        detail = response.json()["detail"]
        # 不能包含文件路径、异常类型等内部信息
        assert "/nonexistent" not in detail
        assert "FileNotFoundError" not in detail
        assert "OSError" not in detail


# ========================================================================
# DELETE /api/models/{model_id} — 删除模型
# ========================================================================

class TestDeleteModel:
    def test_delete_model_normal(self, client, trained_model_record, db_session):
        """正常删除模型"""
        # 模型文件应存在
        assert os.path.exists(trained_model_record.model_path)

        response = client.delete("/api/models/1")
        assert response.status_code == 200
        assert "已删除" in response.json()["message"]

        # DB 记录应删除
        remaining = db_session.query(TrainedModel).filter(TrainedModel.id == 1).first()
        assert remaining is None

    def test_delete_model_not_found(self, client):
        """模型不存在 → 404"""
        response = client.delete("/api/models/999")
        assert response.status_code == 404

    def test_delete_model_other_user(self, client, other_user_model):
        """其他用户的模型 → 404"""
        response = client.delete("/api/models/2")
        assert response.status_code == 404

    def test_delete_model_file_already_gone(self, client, db_session):
        """模型记录存在但文件已删除 → 正常处理（不报错）"""
        record = TrainedModel(
            id=10,
            user_id=1,
            name="gone_file_model",
            model_type="sklearn",
            model_path="/tmp/this_file_definitely_does_not_exist.joblib",
            metrics={},
        )
        db_session.add(record)
        db_session.commit()

        response = client.delete("/api/models/10")
        assert response.status_code == 200
        assert "已删除" in response.json()["message"]


# ========================================================================
# Unauthorized access
# ========================================================================

class TestUnauthorized:
    def test_no_auth_returns_401(self):
        """移除认证覆盖后访问受保护端点 → 401"""
        # 清空 override，模拟未认证
        from api.auth import get_current_user
        app.dependency_overrides.clear()

        client = TestClient(app)
        response = client.get("/api/models/")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
