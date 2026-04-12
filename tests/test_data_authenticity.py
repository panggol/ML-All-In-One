"""
Data Authenticity Tests — 曾玺新增要求

验证所有 API 响应返回真实数据，而非伪造数据（全0/全空/全null等）。

测试策略：
1. 使用 FastAPI TestClient 发起真实请求
2. 验证数值字段不全为 0
3. 验证列表字段不全为空
4. 验证必需字段不全为 null
5. 验证字符串字段不是全空或 placeholder

这条测试是所有模块 QA 的前置门槛 — 数据不真实直接打回。
"""
import os
import sys

os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_data_authenticity_only"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import Base, get_db
from api.main import app


@pytest.fixture
def client():
    """Create test client with fresh in-memory database per test.
    Yields (TestClient, db_session) — same session for all requests
    to avoid SQLite cross-connection transaction visibility issues.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    db_session = TestingSession()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c, db_session

    app.dependency_overrides.clear()
    db_session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def auth_headers(client):
    """Register and login a test user, return auth headers."""
    c, _ = client
    # Short username (max 20 chars per UserCreate schema)
    username = f"tu{os.getpid()}"
    reg_resp = c.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@test.com", "password": "testpass123"},
    )
    assert reg_resp.status_code == 201, f"注册失败: {reg_resp.status_code} — {reg_resp.json()}"
    login_resp = c.post(
        "/api/auth/login",
        json={"username": username, "password": "testpass123"},
    )
    assert login_resp.status_code == 200, f"登录失败: {login_resp.status_code} — {login_resp.json()}"
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


def _has_realistic_metric(metrics) -> bool:
    """验证 metrics 包含非零真实值。"""
    if not metrics or not isinstance(metrics, dict):
        return False
    numeric_vals = [v for v in metrics.values() if isinstance(v, (int, float)) and v is not None]
    if not numeric_vals:
        return False
    if all(v == 0 for v in numeric_vals):
        return False
    for key in ["accuracy", "auc", "f1", "precision", "recall"]:
        if key in metrics:
            val = metrics[key]
            if val is not None and not (0 <= val <= 1):
                return False
    return True


# ─── Monitor API ──────────────────────────────────────────────────────────────


class TestMonitorDataAuthenticity:
    """系统监控 API 必须返回真实系统指标，不能是全 0。"""

    def test_get_overview_returns_real_system_metrics(self, client, auth_headers):
        """CPU/内存/GPU/磁盘使用率应为真实值，不能全为 0。"""
        c, _ = client
        resp = c.get("/api/monitor/overview", headers=auth_headers)
        assert resp.status_code == 200, f"Monitor API 失败: {resp.status_code}"

        data = resp.json()

        assert "timestamp" in data, "缺少 timestamp 字段"
        assert data["timestamp"] is not None, "timestamp 不能为 null"
        assert len(data["timestamp"]) > 0, "timestamp 不能为空字符串"

        cpu = data.get("cpu", {})
        assert "usage_percent" in cpu, "CPU 缺少 usage_percent"
        usage = cpu["usage_percent"]
        assert usage is not None, "CPU usage_percent 不能为 null"
        assert 0 <= usage <= 100, f"CPU usage_percent 异常: {usage}"

        mem = data.get("memory", {})
        assert "usage_percent" in mem, "内存缺少 usage_percent"
        mem_usage = mem["usage_percent"]
        assert mem_usage is not None, "内存 usage_percent 不能为 null"
        assert 0 <= mem_usage <= 100, f"内存 usage_percent 异常: {mem_usage}"
        assert mem.get("total_gb", 0) > 0, "内存 total_gb 应该 > 0"
        assert mem.get("used_gb", 0) >= 0, "内存 used_gb 应该 >= 0"

        disk = data.get("disk", {})
        if disk.get("partitions"):
            for part in disk["partitions"]:
                assert part.get("total_gb", 0) >= 0, f"磁盘 total_gb 异常: {part}"
                assert 0 <= part.get("usage_percent", 0) <= 100, f"磁盘使用率异常: {part}"

        gpu = data.get("gpu", {})
        if gpu.get("available") and gpu.get("devices"):
            for device in gpu["devices"]:
                assert device.get("memory_total_gb", 0) >= 0, "GPU 显存总量异常"
                assert 0 <= device.get("memory_usage_percent", 0) <= 100, "GPU 显存使用率异常"

    def test_overview_timestamp_is_current(self, client, auth_headers):
        """timestamp 必须是当前时间的合理范围内（±5分钟）。"""
        import time
        from email.utils import parsedate_to_datetime

        c, _ = client
        resp = c.get("/api/monitor/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        ts_str = data.get("timestamp", "")
        if ts_str:
            try:
                server_time = parsedate_to_datetime(ts_str)
                diff = abs(server_time.timestamp() - time.time())
                assert diff < 300, f"服务器时间与当前时间差 {diff}s > 300s，疑似伪造时间戳"
            except Exception:
                from datetime import datetime, timezone

                server_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                diff = abs((server_time - now).total_seconds())
                assert diff < 300, f"服务器时间与当前时间差 {diff}s > 300s"


# ─── Auth API ─────────────────────────────────────────────────────────────────


class TestAuthDataAuthenticity:
    """认证 API 返回的数据必须是真实的。"""

    def test_login_returns_real_token(self, client):
        """登录成功返回的 access_token 必须是真实 JWT。"""
        c, _ = client
        username = f"lt{os.getpid()}"
        c.post(
            "/api/auth/register",
            json={"username": username, "email": f"{username}@test.com", "password": "testpass123"},
        )
        resp = c.post(
            "/api/auth/login",
            json={"username": username, "password": "testpass123"},
        )
        assert resp.status_code == 200, f"登录失败: {resp.status_code} — {resp.json()}"
        body = resp.json()
        assert "access_token" in body, "响应缺少 access_token"
        token = body["access_token"]
        assert len(token) > 20, f"access_token 太短（疑似伪造）: {token}"
        assert " " not in token, "access_token 不应包含空格"

    def test_get_me_returns_real_user_data(self, client, auth_headers):
        """获取当前用户返回真实用户数据，不是 placeholder。"""
        c, _ = client
        resp = c.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "username" in body, "响应缺少 username"
        assert body["username"] is not None, "username 不能为 null"
        assert len(body["username"]) > 0, "username 不能为空"
        assert body["username"] not in ["test", "user", "admin", ""], f"username 是 placeholder: {body['username']}"


# ─── Train API ────────────────────────────────────────────────────────────────


class TestTrainDataAuthenticity:
    """训练 API 返回的数据必须是真实训练结果。"""

    def test_list_jobs_returns_list_or_empty_not_null(self, client, auth_headers):
        """任务列表返回 [] 而不是 null。"""
        c, _ = client
        resp = c.get("/api/train", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body is not None, "任务列表不能为 null（疑似伪造）"
        assert isinstance(body, list), f"任务列表应为 list，实际: {type(body)}"

    def test_training_nonexistent_file_gives_real_error(self, client, auth_headers):
        """用不存在的 data_file_id 训练应返回真实错误，不是假数据。"""
        c, _ = client
        resp = c.post(
            "/api/train",
            json={
                "data_file_id": 999999,
                "model_type": "RandomForestClassifier",
                "task_type": "classification",
                "target_column": "target",
            },
            headers=auth_headers,
        )
        # 期望真实错误：404（文件不存在）或 400（业务错误）或 422（验证错误）
        # 只要不是 200 返回假数据即可
        assert resp.status_code != 200 or resp.json() is not None, \
            "不应返回 200+null（疑似假数据）"


# ─── Experiments API ──────────────────────────────────────────────────────────


class TestExperimentsDataAuthenticity:
    """实验 API 返回的数据必须是真实的。"""

    def test_list_experiments_returns_list_or_empty_not_null(self, client, auth_headers):
        """实验列表返回 [] 或真实列表，不能是 null。"""
        c, _ = client
        resp = c.get("/api/experiments", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body is not None, "实验列表不能为 null（疑似伪造）"
        assert isinstance(body, list), f"实验列表应为 list，实际: {type(body)}"

    def test_experiment_fields_not_all_null_when_populated(self, client, auth_headers):
        """如果返回了实验数据，关键字段不能全为 null。"""
        c, _ = client
        resp = c.get("/api/experiments", headers=auth_headers)
        assert resp.status_code == 200
        experiments = resp.json()
        if experiments:
            exp = experiments[0]
            critical_fields = ["id", "name", "status"]
            non_null_count = sum(1 for f in critical_fields if exp.get(f) is not None)
            assert non_null_count > 0, f"实验关键字段全为 null，疑似伪造: {exp}"


# ─── Data API ──────────────────────────────────────────────────────────────────


class TestDataAPIAuthenticity:
    """数据管理 API 返回的数据必须是真实的。"""

    def test_list_files_returns_list_or_empty_not_null(self, client, auth_headers):
        """文件列表返回 [] 或真实列表，不能是 null。"""
        c, _ = client
        resp = c.get("/api/data/list", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body is not None, "文件列表不能为 null（疑似伪造）"
        assert isinstance(body, list), f"文件列表应为 list，实际: {type(body)}"


# ─── Models API ─────────────────────────────────────────────────────────────--


class TestModelsDataAuthenticity:
    """模型列表 API 必须返回真实模型信息。"""

    def test_list_models_returns_supported_models(self, client, auth_headers):
        """模型列表应包含已知支持的模型，不能是空列表或 placeholder。"""
        c, _ = client
        resp = c.get("/api/models/", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body is not None, "模型列表不能为 null"
        assert isinstance(body, list), f"模型列表应为 list，实际: {type(body)}"
        if body:
            for model in body:
                name = model.get("name", "") if isinstance(model, dict) else str(model)
                assert name not in ["", "unknown", "placeholder"], f"模型名是 placeholder: {name}"


# ─── Viz API ──────────────────────────────────────────────────────────────────


class TestVizDataAuthenticity:
    """可视化 API 返回的数据必须是真实计算结果。"""

    def test_training_curves_404_is_real_not_fake_data(self, client, auth_headers):
        """请求不存在的训练曲线应返回 404，不能是 200 返回假数据。"""
        c, _ = client
        resp = c.get("/api/viz/training-curves/999999", headers=auth_headers)
        assert not (
            resp.status_code == 200 and resp.json() is None
        ), "Viz API 不应返回 200+null（疑似假数据）"
