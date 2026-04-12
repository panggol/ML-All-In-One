"""
Iris 数据集端到端推理测试
验证 inference_tab 完整链路：训练 → 保存 → 注册 → 推理

覆盖：
- POST /api/models/          注册 iris RandomForest 模型
- GET  /api/models/{id}       获取模型详情
- POST /api/models/{id}/predict  端到端推理
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
import pandas as pd

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

from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

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
def iris_trained_model(db_session):
    """训练 iris RandomForestClassifier 并写入 DB"""
    # 加载 iris 数据集
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.2, random_state=42, stratify=iris.target
    )

    # 训练 RandomForest
    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X_train, y_train)

    # 保存模型
    model_dir = os.environ["MODELS_DIR"]
    model_path = os.path.join(model_dir, "iris_rf_model.joblib")
    joblib.dump(clf, model_path)

    # 写入 DB 记录
    record = TrainedModel(
        user_id=1,
        name="iris_random_forest",
        model_type="sklearn",
        model_path=model_path,
        metrics={
            "train_accuracy": float(clf.score(X_train, y_train)),
            "test_accuracy": float(clf.score(X_test, y_test)),
        },
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)

    return {
        "record": record,
        "clf": clf,
        "X_test": X_test,
        "y_test": y_test,
        "iris": iris,
    }


# ========================================================================
# Tests
# ========================================================================

def _to_dict_payload(X: np.ndarray) -> list[dict]:
    """将 numpy 数组转换为 API 期望的 List[dict] 格式
    列名必须与 pd.DataFrame(X).columns 一致，即 0/1/2/3
    （iris 数据集 DataFrame 列名是整数）
    """
    df = pd.DataFrame(X)
    # 列名转字符串以匹配 JSON dict key 格式
    df.columns = [str(c) for c in df.columns]
    return df.to_dict(orient="records")


class TestIrisModelRegistration:
    """模型注册与查询"""

    def test_register_and_get_model(self, client, iris_trained_model):
        """注册 iris 模型后可正常查询详情"""
        model_id = iris_trained_model["record"].id

        response = client.get(f"/api/models/{model_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "iris_random_forest"
        assert data["model_type"] == "sklearn"
        assert "metrics" in data
        assert "test_accuracy" in data["metrics"]

    def test_list_models_contains_iris(self, client, iris_trained_model):
        """模型列表包含 iris 模型"""
        response = client.get("/api/models/")
        assert response.status_code == 200
        names = [m["name"] for m in response.json()]
        assert "iris_random_forest" in names


class TestIrisInference:
    """端到端推理链路测试"""

    def test_predict_single_sample(self, client, iris_trained_model):
        """单样本推理：返回预测类别和概率，概率在 [0,1]"""
        model_id = iris_trained_model["record"].id
        iris = iris_trained_model["iris"]

        # 取一个测试样本，转换为 API 期望的 dict 格式
        payload = _to_dict_payload(iris.data[:1])

        response = client.post(
            f"/api/models/{model_id}/predict",
            json={"data": payload}
        )
        assert response.status_code == 200
        data = response.json()

        assert "predictions" in data
        assert "probabilities" in data
        assert len(data["predictions"]) == 1
        assert isinstance(data["predictions"][0], int)
        assert 0 <= data["predictions"][0] <= 2  # iris 有 3 类

        # 概率验证
        probs = data["probabilities"]
        assert probs is not None, "RandomForest 应返回概率"
        assert len(probs) == 1
        assert len(probs[0]) == 3  # 3 个类别
        assert all(0 <= p <= 1 for p in probs[0])
        assert abs(sum(probs[0]) - 1.0) < 1e-6  # 概率和为 1

    def test_predict_batch(self, client, iris_trained_model):
        """批量推理：返回与输入数量一致的预测结果"""
        model_id = iris_trained_model["record"].id
        X_test = iris_trained_model["X_test"]

        # 取 10 个测试样本
        batch = _to_dict_payload(X_test[:10])

        response = client.post(
            f"/api/models/{model_id}/predict",
            json={"data": batch}
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["predictions"]) == 10
        assert len(data["probabilities"]) == 10
        assert all(isinstance(p, int) for p in data["predictions"])

    def test_predict_all_iris_test_set(self, client, iris_trained_model):
        """完整测试集推理：验证与 sklearn 原生 predict 结果一致"""
        model_id = iris_trained_model["record"].id
        X_test = iris_trained_model["X_test"]
        y_test = iris_trained_model["y_test"]
        clf = iris_trained_model["clf"]

        batch = _to_dict_payload(X_test)
        response = client.post(
            f"/api/models/{model_id}/predict",
            json={"data": batch}
        )
        assert response.status_code == 200
        data = response.json()

        api_preds = np.array(data["predictions"])
        sklearn_preds = clf.predict(X_test)

        # 比对：API 返回的预测类别与 sklearn 原生结果完全一致
        assert np.array_equal(api_preds, sklearn_preds), (
            f"API 预测与 sklearn 预测不一致\n"
            f"API: {api_preds[:10]}\n"
            f"sklearn: {sklearn_preds[:10]}"
        )

        # 概率也应一致
        api_probs = np.array(data["probabilities"])
        sklearn_probs = clf.predict_proba(X_test)
        np.testing.assert_allclose(
            api_probs, sklearn_probs, rtol=1e-5,
            err_msg="概率输出与 sklearn 不一致"
        )

    def test_predict_accuracy_check(self, client, iris_trained_model):
        """推理准确率与记录 metrics 中的 test_accuracy 一致"""
        model_id = iris_trained_model["record"].id
        X_test = iris_trained_model["X_test"]
        y_test = iris_trained_model["y_test"]

        batch = _to_dict_payload(X_test)
        response = client.post(
            f"/api/models/{model_id}/predict",
            json={"data": batch}
        )
        assert response.status_code == 200
        data = response.json()

        api_preds = np.array(data["predictions"])
        accuracy = float(np.mean(api_preds == y_test))

        # 查询模型详情中的 test_accuracy
        detail = client.get(f"/api/models/{model_id}").json()
        recorded_acc = detail["metrics"]["test_accuracy"]

        np.testing.assert_almost_equal(
            accuracy, recorded_acc, decimal=5,
            err_msg="推理准确率与记录不一致"
        )

    def test_predict_invalid_model_id(self, client, iris_trained_model):
        """不存在的模型 ID → 404"""
        response = client.post(
            "/api/models/99999/predict",
            json={"data": _to_dict_payload(np.array([[5.1, 3.5, 1.4, 0.2]]))}
        )
        assert response.status_code == 404

    def test_predict_empty_data(self, client, iris_trained_model):
        """空数组 → 422"""
        model_id = iris_trained_model["record"].id
        response = client.post(
            f"/api/models/{model_id}/predict",
            json={"data": []}
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
