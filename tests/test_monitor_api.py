"""
系统监控 API 测试（TC-01 ~ TC-07）
覆盖 api/routes/monitor.py 所有端点

TC-01: GET /api/monitor/overview — 系统概览返回所有指标
TC-02: GET /api/monitor/cpu — CPU 使用率正常返回
TC-03: GET /api/monitor/memory — 内存信息正常返回
TC-04: GET /api/monitor/gpu — GPU 信息（可用/不可用均正确处理）
TC-05: GET /api/monitor/disk — 磁盘分区信息正常返回
TC-06: GET /api/monitor/network — 网络流量正常返回
TC-07: GET /api/monitor/jobs — 训练任务统计正常返回
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 必须在导入 api 模块之前设置 DATABASE_URL
from api.database import Base
from api.main import app
from api.routes import monitor
from api.auth import get_current_user
from api.database import get_db


# ============ Fixtures ============

@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(mock_user, db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ============ TC-01: 系统概览 ============

class TestMonitorOverview:
    """TC-01: GET /api/monitor/overview 返回所有指标"""

    def test_overview_returns_200(self, client):
        """响应状态码 200"""
        response = client.get("/api/monitor/overview")
        assert response.status_code == 200

    def test_overview_contains_all_sections(self, client):
        """响应包含 cpu/memory/gpu/disk/network/system/jobs"""
        response = client.get("/api/monitor/overview")
        data = response.json()
        assert "cpu" in data
        assert "memory" in data
        assert "gpu" in data
        assert "disk" in data
        assert "network" in data
        assert "system" in data
        assert "jobs" in data

    def test_overview_cpu_fields(self, client):
        """cpu 字段包含 usage_percent/core_count/per_core_usage"""
        response = client.get("/api/monitor/overview")
        cpu = response.json()["cpu"]
        assert "usage_percent" in cpu
        assert "core_count" in cpu
        assert "per_core_usage" in cpu
        assert isinstance(cpu["usage_percent"], (int, float))
        assert 0 <= cpu["usage_percent"] <= 100

    def test_overview_memory_fields(self, client):
        """memory 字段包含 total_gb/used_gb/available_gb/usage_percent"""
        response = client.get("/api/monitor/overview")
        mem = response.json()["memory"]
        assert "total_gb" in mem
        assert "used_gb" in mem
        assert "available_gb" in mem
        assert "usage_percent" in mem
        assert mem["total_gb"] > 0
        assert 0 <= mem["usage_percent"] <= 100

    def test_overview_gpu_fields(self, client):
        """gpu 字段包含 available/count/devices"""
        response = client.get("/api/monitor/overview")
        gpu = response.json()["gpu"]
        assert "available" in gpu
        assert "count" in gpu
        assert "devices" in gpu
        assert isinstance(gpu["available"], bool)
        assert isinstance(gpu["devices"], list)

    def test_overview_disk_fields(self, client):
        """disk 字段包含 partitions 列表"""
        response = client.get("/api/monitor/overview")
        disk = response.json()["disk"]
        assert "partitions" in disk
        assert isinstance(disk["partitions"], list)
        if disk["partitions"]:
            p = disk["partitions"][0]
            assert "mountpoint" in p
            assert "total_gb" in p
            assert "usage_percent" in p

    def test_overview_network_fields(self, client):
        """network 字段包含流量和速率"""
        response = client.get("/api/monitor/overview")
        net = response.json()["network"]
        assert "bytes_sent_mb" in net
        assert "bytes_recv_mb" in net
        assert "send_rate_mbps" in net
        assert "recv_rate_mbps" in net
        assert net["bytes_sent_mb"] >= 0
        assert net["bytes_recv_mb"] >= 0

    def test_overview_jobs_fields(self, client):
        """jobs 字段包含 running/pending/completed/failed"""
        response = client.get("/api/monitor/overview")
        jobs = response.json()["jobs"]
        assert "running" in jobs
        assert "pending" in jobs
        assert "completed" in jobs
        assert "failed" in jobs
        assert all(isinstance(v, int) for v in jobs.values())

    def test_overview_timestamp_present(self, client):
        """响应包含 timestamp"""
        response = client.get("/api/monitor/overview")
        assert "timestamp" in response.json()


# ============ TC-02: CPU ============

class TestMonitorCPU:
    """TC-02: GET /api/monitor/cpu"""

    def test_cpu_returns_200(self, client):
        response = client.get("/api/monitor/cpu")
        assert response.status_code == 200

    def test_cpu_usage_percent_valid_range(self, client):
        """usage_percent 在 0-100 之间"""
        response = client.get("/api/monitor/cpu")
        data = response.json()
        assert 0 <= data["usage_percent"] <= 100

    def test_cpu_core_count_positive(self, client):
        """core_count 为正整数"""
        response = client.get("/api/monitor/cpu")
        assert response.json()["core_count"] > 0

    def test_cpu_per_core_usage_list(self, client):
        """per_core_usage 是列表，每个值在 0-100 之间，长度 > 0"""
        response = client.get("/api/monitor/cpu")
        data = response.json()
        per_core = data["per_core_usage"]
        assert isinstance(per_core, list)
        assert len(per_core) > 0, "per_core_usage 不应为空"
        for usage in per_core:
            assert 0 <= usage <= 100, f"per_core_usage 值 {usage} 不在 0-100 范围内"


# ============ TC-03: 内存 ============

class TestMonitorMemory:
    """TC-03: GET /api/monitor/memory"""

    def test_memory_returns_200(self, client):
        response = client.get("/api/monitor/memory")
        assert response.status_code == 200

    def test_memory_usage_percent_valid_range(self, client):
        """usage_percent 在 0-100 之间"""
        response = client.get("/api/monitor/memory")
        data = response.json()
        assert 0 <= data["usage_percent"] <= 100

    def test_memory_total_positive(self, client):
        """total_gb 为正数"""
        response = client.get("/api/monitor/memory")
        assert response.json()["total_gb"] > 0

    def test_memory_used_plus_available_equal_total(self, client):
        """used_gb + available_gb ≈ total_gb（允许浮点误差）"""
        response = client.get("/api/monitor/memory")
        data = response.json()
        total = data["total_gb"]
        used = data["used_gb"]
        avail = data["available_gb"]
        assert abs(used + avail - total) < 0.1, f"{used} + {avail} != {total}"


# ============ TC-04: GPU ============

class TestMonitorGPU:
    """TC-04: GET /api/monitor/gpu"""

    def test_gpu_returns_200(self, client):
        response = client.get("/api/monitor/gpu")
        assert response.status_code == 200

    def test_gpu_available_boolean(self, client):
        """available 是布尔值"""
        response = client.get("/api/monitor/gpu")
        assert isinstance(response.json()["available"], bool)

    def test_gpu_count_non_negative(self, client):
        """count 为非负整数"""
        response = client.get("/api/monitor/gpu")
        assert response.json()["count"] >= 0

    def test_gpu_devices_empty_when_unavailable(self, client):
        """available=False 时 devices 应为空列表"""
        response = client.get("/api/monitor/gpu")
        data = response.json()
        if not data["available"]:
            assert data["devices"] == []
            assert data["count"] == 0


# ============ TC-05: 磁盘 ============

class TestMonitorDisk:
    """TC-05: GET /api/monitor/disk"""

    def test_disk_returns_200(self, client):
        response = client.get("/api/monitor/disk")
        assert response.status_code == 200

    def test_disk_partitions_list(self, client):
        """partitions 是列表"""
        response = client.get("/api/monitor/disk")
        assert isinstance(response.json()["partitions"], list)

    def test_disk_partition_usage_percent_valid(self, client):
        """每个分区的 usage_percent 在 0-100 之间"""
        response = client.get("/api/monitor/disk")
        partitions = response.json()["partitions"]
        for p in partitions:
            assert 0 <= p["usage_percent"] <= 100

    def test_disk_partition_total_positive(self, client):
        """每个分区的 total_gb 为正数"""
        response = client.get("/api/monitor/disk")
        partitions = response.json()["partitions"]
        for p in partitions:
            assert p["total_gb"] > 0


# ============ TC-06: 网络 ============

class TestMonitorNetwork:
    """TC-06: GET /api/monitor/network"""

    def test_network_returns_200(self, client):
        response = client.get("/api/monitor/network")
        assert response.status_code == 200

    def test_network_bytes_non_negative(self, client):
        """bytes_sent_mb 和 bytes_recv_mb 为非负数"""
        response = client.get("/api/monitor/network")
        data = response.json()
        assert data["bytes_sent_mb"] >= 0
        assert data["bytes_recv_mb"] >= 0

    def test_network_rates_non_negative(self, client):
        """send_rate_mbps 和 recv_rate_mbps 为非负数"""
        response = client.get("/api/monitor/network")
        data = response.json()
        assert data["send_rate_mbps"] >= 0
        assert data["recv_rate_mbps"] >= 0


# ============ TC-07: 训练任务统计 ============

class TestMonitorJobs:
    """TC-07: GET /api/monitor/jobs"""

    def test_jobs_returns_200(self, client):
        response = client.get("/api/monitor/jobs")
        assert response.status_code == 200

    def test_jobs_all_counts_non_negative(self, client):
        """所有任务计数为非负整数"""
        response = client.get("/api/monitor/jobs")
        data = response.json()
        assert all(v >= 0 for v in data.values())
        assert all(isinstance(v, int) for v in data.values())

    def test_jobs_running_plus_pending_plus_completed_plus_failed_total(
        self, client, db_session
    ):
        """任务计数之和与数据库记录一致"""
        response = client.get("/api/monitor/jobs")
        counts = response.json()

        from api.database import TrainingJob

        total_jobs = db_session.query(TrainingJob).count()
        sum_counts = (
            counts["running"]
            + counts["pending"]
            + counts["completed"]
            + counts["failed"]
        )
        # 新数据库为空，所有计数应为 0
        assert sum_counts == 0
        assert counts["running"] == 0


# ============ 认证保护 ============

class TestMonitorAuth:
    """所有端点需要认证"""

    def test_overview_requires_auth(self):
        """未认证请求返回 401"""
        from api.main import app

        app.dependency_overrides.clear()
        with TestClient(app) as c:
            response = c.get("/api/monitor/overview")
            assert response.status_code == 401
