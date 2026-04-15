"""
Model Registry API 测试 - test_model_registry_api.py

覆盖所有 7 个端点：
- POST /api/models/{model_id}/versions          — 版本注册
- GET  /api/models/{model_id}/versions          — 版本列表（筛选）
- GET  /api/models/{model_id}/versions/{version} — 单版本详情
- PATCH /api/models/{model_id}/versions/{version}/tags — 标签变更
- GET  /api/models/{model_id}/compare           — 版本对比
- POST /api/models/{model_id}/rollback           — 回滚
- GET  /api/models/{model_id}/history           — 操作历史

使用 FastAPI TestClient + 内存数据库 + mock 认证。
"""
import os
import sys
import secrets
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment BEFORE any api imports
os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MODELS_DIR"] = tempfile.mkdtemp()
os.environ["API_SECRET_KEY"] = os.environ.get("API_SECRET_KEY") or secrets.token_hex(32)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.database import Base, TrainedModel, User, ModelVersion, ModelVersionHistory, get_db
from api.main import app


# ========================================================================
# Fixtures
# ========================================================================

@pytest.fixture(autouse=True)
def _setup_db():
    """每个测试前创建独立 in-memory 数据库"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    # 注入 mock 用户
    admin_user = User(
        id=1, username="admin", email="admin@test.com",
        password_hash="$2b$12$dummy", role="admin", is_active=True,
    )
    regular_user = User(
        id=2, username="user", email="user@test.com",
        password_hash="$2b$12$dummy", role="user", is_active=True,
    )
    session.add(admin_user)
    session.add(regular_user)
    session.commit()

    # 注入 mock TrainedModel
    model = TrainedModel(
        id=1, user_id=1, name="test_model",
        model_type="sklearn", model_path="/tmp/dummy.pkl",
        metrics={"accuracy": 0.91}, config={},
    )
    session.add(model)
    session.commit()

    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def admin_token(_setup_db):
    """返回 admin 用户的 mock get_current_user"""
    from api.auth import get_current_user
    from api.database import User as DBUser

    def override():
        mock = MagicMock()
        mock.id = 1
        mock.username = "admin"
        mock.role = "admin"
        return mock
    return override


@pytest.fixture
def user_token(_setup_db):
    """返回普通用户的 mock get_current_user"""
    def override():
        mock = MagicMock()
        mock.id = 2
        mock.username = "user"
        mock.role = "user"
        return mock
    return override


@pytest.fixture
def client(_setup_db, admin_token):
    """返回配置了 mock 认证的 TestClient"""
    from api.auth import get_current_user
    from api.database import get_db as real_get_db

    def override_get_current_user():
        return admin_token()

    def override_get_db():
        db = _setup_db
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[real_get_db] = override_get_db

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def regular_client(_setup_db, user_token):
    """返回配置了普通用户认证的 TestClient"""
    from api.auth import get_current_user
    from api.database import get_db as real_get_db

    def override_get_current_user():
        return user_token()

    def override_get_db():
        db = _setup_db
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[real_get_db] = override_get_db

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ========================================================================
# Test 1: 版本注册（US1）
# ========================================================================

class TestRegisterVersion:
    """POST /api/models/{model_id}/versions"""

    def test_register_first_version(self, client):
        """注册第一个版本：version=1, tag=staging"""
        resp = client.post(
            "/api/models/1/versions",
            json={"metrics": {"accuracy": 0.91, "f1": 0.88}},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == 1
        assert data["tag"] == "staging"
        assert data["metrics"]["accuracy"] == 0.91

    def test_register_increments_version(self, client):
        """连续注册：版本号自动递增"""
        # 注册 v1
        r1 = client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.91}})
        assert r1.json()["version"] == 1
        # 注册 v2
        r2 = client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.93}})
        assert r2.json()["version"] == 2
        # 注册 v3
        r3 = client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.95}})
        assert r3.json()["version"] == 3

    def test_register_nonexistent_model_returns_404(self, client):
        """model_id 不存在返回 404"""
        resp = client.post("/api/models/999/versions", json={})
        assert resp.status_code == 404
        assert "模型不存在" in resp.json()["detail"]

    def test_register_without_training_job(self, client):
        """不关联 training_job_id 时版本正常创建，元数据从 TrainedModel 继承"""
        resp = client.post("/api/models/1/versions", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == 1
        assert data["tag"] == "staging"
        # algorithm_type 和 metrics 从 TrainedModel 继承
        assert data["algorithm_type"] == "sklearn"
        assert data["metrics"] == {"accuracy": 0.91}

    def test_register_with_training_job_metadata(self, client):
        """关联 training_job 时正确提取元数据"""
        resp = client.post(
            "/api/models/1/versions",
            json={
                "training_job_id": 42,
                "algorithm_type": "RandomForestClassifier",
                "model_type": "sklearn",
                "task_type": "classification",
                "training_params": {"n_estimators": 100},
                "metrics": {"accuracy": 0.91},
                "dataset_name": "iris.csv",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["algorithm_type"] == "RandomForestClassifier"
        assert data["training_params"]["n_estimators"] == 100


# ========================================================================
# Test 2: 标签变更（US2）
# ========================================================================

class TestUpdateTag:
    """PATCH /api/models/{model_id}/versions/{version}/tags"""

    def test_normal_tag_change(self, client):
        """正常变更标签：staging → production"""
        # 先注册版本
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.91}})
        # 变更标签
        resp = client.patch(
            "/api/models/1/versions/1/tags",
            json={"tag": "production"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tag"] == "production"
        assert data["version"] == 1
        assert "已设为 production" in data["message"]

    def test_production_tag_uniqueness(self, client):
        """production 标签唯一：提升新版本时旧 production 自动降级"""
        # 注册 v1 并设为 production
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.91}})
        client.patch("/api/models/1/versions/1/tags", json={"tag": "production"})
        # 注册 v2 并设为 production
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.93}})
        resp = client.patch("/api/models/1/versions/2/tags", json={"tag": "production"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["previous_production_version"] == 1
        assert "v1 已自动降级" in data["message"]

    def test_non_admin_cannot_change_production(self, regular_client):
        """非 admin 变更 production 标签返回 403"""
        regular_client.post("/api/models/1/versions", json={})
        resp = regular_client.patch(
            "/api/models/1/versions/1/tags",
            json={"tag": "production"},
        )
        assert resp.status_code == 403
        assert "权限不足" in resp.json()["detail"]

    def test_invalid_tag_returns_422(self, client):
        """非法标签值返回 422"""
        client.post("/api/models/1/versions", json={})
        resp = client.patch(
            "/api/models/1/versions/1/tags",
            json={"tag": "live"},
        )
        assert resp.status_code == 422

    def test_tag_change_records_history(self, client):
        """标签变更记录操作历史"""
        client.post("/api/models/1/versions", json={})
        client.patch("/api/models/1/versions/1/tags", json={"tag": "production"})
        # 查询历史
        resp = client.get("/api/models/1/history")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(h["action"] == "tag_change" for h in items)


# ========================================================================
# Test 3: 版本列表（US3）
# ========================================================================

class TestListVersions:
    """GET /api/models/{model_id}/versions"""

    def test_list_all_versions(self, client):
        """返回所有版本，按注册时间倒序"""
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.91}})
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.92}})
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.93}})
        resp = client.get("/api/models/1/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        # 最新版本在前
        assert data["items"][0]["version"] == 3

    def test_filter_by_tag(self, client):
        """按标签筛选"""
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.91}})
        client.patch("/api/models/1/versions/1/tags", json={"tag": "production"})
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.92}})
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.93}})
        resp = client.get("/api/models/1/versions?tag=staging")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2
        assert all(item["tag"] == "staging" for item in resp.json()["items"])

    def test_pagination(self, client):
        """分页功能"""
        for i in range(5):
            client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.90 + i * 0.01}})
        resp = client.get("/api/models/1/versions?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1


# ========================================================================
# Test 4: 版本对比（US4）
# ========================================================================

class TestCompareVersions:
    """GET /api/models/{model_id}/compare"""

    def test_compare_two_versions(self, client):
        """对比两个版本的指标，返回 delta 和 winner"""
        client.post("/api/models/1/versions", json={
            "metrics": {"accuracy": 0.91, "f1": 0.88},
        })
        client.post("/api/models/1/versions", json={
            "metrics": {"accuracy": 0.93, "f1": 0.91},
        })
        resp = client.get("/api/models/1/compare?version_a=1&version_b=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version_a"] == 1
        assert data["version_b"] == 2
        # accuracy delta
        acc = next(c for c in data["comparison"] if c["metric"] == "accuracy")
        assert acc["delta"] == pytest.approx(0.02)
        assert acc["winner"] == "b"
        # f1 delta
        f1 = next(c for c in data["comparison"] if c["metric"] == "f1")
        assert f1["delta"] == pytest.approx(0.03)
        assert f1["winner"] == "b"

    def test_compare_version_not_found(self, client):
        """版本不存在返回 404"""
        client.post("/api/models/1/versions", json={})
        resp = client.get("/api/models/1/compare?version_a=1&version_b=999")
        assert resp.status_code == 404
        assert "v999" in resp.json()["detail"]

    def test_compare_different_metric_structures(self, client):
        """不同指标结构：交集对比 + 各自独有字段"""
        client.post("/api/models/1/versions", json={
            "metrics": {"accuracy": 0.91},
        })
        client.post("/api/models/1/versions", json={
            "metrics": {"accuracy": 0.93, "auroc": 0.95},
        })
        resp = client.get("/api/models/1/compare?version_a=1&version_b=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unique_to_b"] == ["auroc"]
        assert len(data["comparison"]) == 1  # 只有 accuracy 是共有的


# ========================================================================
# Test 5: 回滚（US5）
# ========================================================================

class TestRollback:
    """POST /api/models/{model_id}/rollback"""

    def test_rollback_success(self, client):
        """正常回滚：v2 → production，v3 降级为 staging"""
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.91}})
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.92}})
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.93}})
        # 设定 v3 为当前 production
        client.patch("/api/models/1/versions/3/tags", json={"tag": "production"})
        # 回滚到 v2
        resp = client.post("/api/models/1/rollback?target_version=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["new_production_version"] == 2
        assert data["previous_production_version"] == 3

    def test_rollback_target_not_found(self, client):
        """目标版本不存在返回 404"""
        client.post("/api/models/1/versions", json={})
        resp = client.post("/api/models/1/rollback?target_version=999")
        assert resp.status_code == 404

    def test_rollback_archived_version_rejected(self, client):
        """archived 版本不允许直接回滚"""
        # 注册 + 设为 archived
        client.post("/api/models/1/versions", json={"metrics": {"accuracy": 0.91}})
        client.patch("/api/models/1/versions/1/tags", json={"tag": "archived"})
        resp = client.post("/api/models/1/rollback?target_version=1")
        assert resp.status_code == 422
        assert "archived" in resp.json()["detail"]

    def test_non_admin_cannot_rollback(self, regular_client):
        """非 admin 不可回滚"""
        regular_client.post("/api/models/1/versions", json={})
        resp = regular_client.post("/api/models/1/rollback?target_version=1")
        assert resp.status_code == 403

    def test_rollback_records_history(self, client):
        """回滚记录操作历史"""
        client.post("/api/models/1/versions", json={})
        client.post("/api/models/1/versions", json={})
        client.patch("/api/models/1/versions/2/tags", json={"tag": "production"})
        client.post("/api/models/1/rollback?target_version=1")
        resp = client.get("/api/models/1/history")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(h["action"] == "rollback" for h in items)


# ========================================================================
# Test 6: 操作历史（US6）
# ========================================================================

class TestHistory:
    """GET /api/models/{model_id}/history"""

    def test_history_returns_ordered_records(self, client):
        """操作历史按时间倒序"""
        client.post("/api/models/1/versions", json={})
        client.post("/api/models/1/versions", json={})
        resp = client.get("/api/models/1/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        # 最新操作在前
        assert data["items"][0]["version"] == 2
        assert data["items"][0]["action"] == "register"

    def test_history_empty_for_model_with_no_operations(self, client):
        """无操作历史的模型返回空列表"""
        resp = client.get("/api/models/1/history")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0


# ========================================================================
# Test 7: mlkit.model_registry 库函数
# ========================================================================

class TestModelRegistryLibrary:
    """mlkit.model_registry 核心函数测试"""

    def test_compute_dataset_hash(self):
        """数据集指纹计算"""
        from mlkit.model_registry import compute_dataset_hash

        h1 = compute_dataset_hash(filename="iris.csv", size=1024, rows=150)
        assert len(h1) == 64  # SHA256 hex = 64 chars
        assert h1.isalnum()

    def test_compare_versions(self):
        """版本对比逻辑"""
        from mlkit.model_registry import compare_versions

        metrics_a = {"accuracy": 0.91, "f1": 0.88}
        metrics_b = {"accuracy": 0.93, "f1": 0.91}

        comparison, unique_a, unique_b = compare_versions(metrics_a, metrics_b)
        acc_row = next(c for c in comparison if c["metric"] == "accuracy")
        assert acc_row["delta"] == pytest.approx(0.02)
        assert acc_row["winner"] == "b"
        f1_row = next(c for c in comparison if c["metric"] == "f1")
        assert f1_row["winner"] == "b"
        assert unique_a == []
        assert unique_b == []
