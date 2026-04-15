# -*- coding: utf-8 -*-
"""
调度器模块测试（pytest）
覆盖 cron_parser、models、API 路由的核心功能。
≥15 个测试用例。
"""
import os
import sys
import json
import uuid
from datetime import datetime, timezone as dt_tz
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

# 路径配置
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'api'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_scheduler"
os.environ["MLKIT_JWT_SECRET"] = "test_secret_scheduler"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """构建 FastAPI 测试应用（含调度器相关表）"""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from api.database import Base as DBBase

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # 创建所有表（共用 Base，scheduler_jobs.user_id FK 指向 users.id）
    DBBase.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(bind=engine)
    db_session = TestingSession()

    # 创建测试用户
    from api.database import User
    user = User(
        id=1,
        username="scheduler_test_user",
        email="scheduler_test@example.com",
        password_hash="dummy_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()

    # 构建 FastAPI 应用
    from api.main import app as fastapi_app
    from api.auth import get_current_user
    from api.database import get_db

    def override_get_current_user():
        u = MagicMock()
        u.id = 1
        u.username = "scheduler_test_user"
        u.email = "scheduler_test@example.com"
        u.role = "user"
        return u

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_current_user] = override_get_current_user
    fastapi_app.dependency_overrides[get_db] = override_get_db

    client = TestClient(fastapi_app)
    client.db = db_session
    client.engine = engine
    return client


# =============================================================================
# T1: cron_parser 测试
# =============================================================================

class TestCronParser:
    """Cron 表达式解析器测试"""

    def test_validate_cron_valid_standard(self):
        """T1.1: 标准 5 段式 Cron 表达式校验通过"""
        from src.mlkit.scheduler.cron_parser import validate_cron
        assert validate_cron("0 8 * * *") is True
        assert validate_cron("*/15 * * * *") is True
        assert validate_cron("0 0 1 * *") is True
        assert validate_cron("30 4 1,15 * *") is True

    def test_validate_cron_invalid_expression(self):
        """T1.2: 非法 Cron 表达式抛出 CronParseError"""
        from src.mlkit.scheduler.cron_parser import validate_cron, CronParseError
        with pytest.raises(CronParseError):
            validate_cron("not a cron")
        with pytest.raises(CronParseError):
            validate_cron("60 * * * *")  # 分钟超范围
        with pytest.raises(CronParseError):
            validate_cron("0 * *")  # 缺少字段

    def test_get_next_run_time_basic(self):
        """T1.3: 计算下次执行时间（基准时间已知）"""
        from src.mlkit.scheduler.cron_parser import get_next_run_time
        from datetime import datetime, timezone

        base = datetime(2026, 4, 13, 7, 0, 0, tzinfo=dt_tz.utc)
        next_run = get_next_run_time("0 8 * * *", base_time=base)
        assert next_run.hour == 8
        assert next_run.day == 13

    def test_get_next_run_time_cross_day(self):
        """T1.4: Cron 跨天计算（当天已过则次日执行）"""
        from src.mlkit.scheduler.cron_parser import get_next_run_time
        from datetime import datetime

        base = datetime(2026, 4, 13, 12, 0, 0)  # 中午12点
        next_run = get_next_run_time("0 8 * * *", base_time=base)
        # 8:00已过，下一个8:00是4月14日
        assert next_run.day == 14

    def test_get_prev_run_time(self):
        """T1.5: 计算上次执行时间"""
        from src.mlkit.scheduler.cron_parser import get_prev_run_time
        from datetime import datetime

        base = datetime(2026, 4, 13, 10, 0, 0)
        prev = get_prev_run_time("0 8 * * *", base_time=base)
        assert prev.day == 13
        assert prev.hour == 8

    def test_describe_cron(self):
        """T1.6: Cron 人类可读描述"""
        from src.mlkit.scheduler.cron_parser import describe_cron
        assert "8" in describe_cron("0 8 * * *")
        assert "分钟" in describe_cron("*/30 * * * *")
        assert "每周一" in describe_cron("0 0 * * 1")


# =============================================================================
# T2: 数据模型测试
# =============================================================================

class TestSchedulerModels:
    """Scheduler 数据模型测试"""

    def test_job_model_creation(self):
        """T2.1: Job 模型创建与字段验证"""
        from src.mlkit.scheduler.models import Job, JobType, JobStatus

        job = Job(
            id=str(uuid.uuid4()),
            user_id=1,
            name="Test Job",
            job_type=JobType.TRAINING,
            target_id=42,
            cron_expression="0 8 * * *",
            status=JobStatus.ACTIVE,
            retry_count=2,
            is_enabled=True,
        )
        assert job.name == "Test Job"
        assert job.job_type == JobType.TRAINING
        assert job.status == JobStatus.ACTIVE
        assert job.retry_count == 2

    def test_execution_model_creation(self):
        """T2.2: Execution 模型创建"""
        from src.mlkit.scheduler.models import Execution, ExecutionStatus, TriggerType

        exec_record = Execution(
            id=str(uuid.uuid4()),
            job_id=str(uuid.uuid4()),
            status=ExecutionStatus.RUNNING,
            triggered_by=TriggerType.MANUAL,
            started_at=datetime.now(dt_tz.utc),
        )
        assert exec_record.status == ExecutionStatus.RUNNING
        assert exec_record.triggered_by == TriggerType.MANUAL
        assert exec_record.duration_seconds is None  # 尚未完成

    def test_execution_finished_fields(self):
        """T2.3: Execution 完成后的字段填充"""
        from src.mlkit.scheduler.models import Execution, ExecutionStatus

        now = datetime.now(dt_tz.utc)
        exec_record = Execution(
            id=str(uuid.uuid4()),
            job_id=str(uuid.uuid4()),
            status=ExecutionStatus.SUCCESS,
            started_at=now,
            finished_at=now,
            duration_seconds=120,
            triggered_by="scheduled",
        )
        assert exec_record.status == ExecutionStatus.SUCCESS
        assert exec_record.duration_seconds == 120


# =============================================================================
# T3: API 路由测试
# =============================================================================

class TestSchedulerAPI:
    """调度器 API 路由测试"""

    def test_create_job_success(self, app):
        """T3.1: 创建定时任务成功"""
        response = app.post("/api/scheduler/jobs", json={
            "name": "每日训练任务",
            "job_type": "training",
            "target_id": 10,
            "cron_expression": "0 8 * * *",
            "is_enabled": True,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "每日训练任务"
        assert data["job_type"] == "training"
        assert data["status"] in ("active", "paused")  # is_enabled 控制

    def test_create_job_missing_target_id(self, app):
        """T3.2: training 类型必须指定 target_id"""
        response = app.post("/api/scheduler/jobs", json={
            "name": "无关联训练",
            "job_type": "training",
            "cron_expression": "0 8 * * *",
        })
        assert response.status_code == 422

    def test_create_job_invalid_cron(self, app):
        """T3.3: 无效 Cron 表达式返回 422"""
        response = app.post("/api/scheduler/jobs", json={
            "name": "Bad Cron",
            "job_type": "pipeline",
            "cron_expression": "not valid",
        })
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_create_job_invalid_webhook_url(self, app):
        """T3.4: 非 https WebHook URL 返回 422"""
        response = app.post("/api/scheduler/jobs", json={
            "name": "Bad Webhook",
            "job_type": "pipeline",
            "cron_expression": "0 8 * * *",
            "webhook_url": "http://evil.com/webhook",  # 非 https
        })
        assert response.status_code == 422

    def test_list_jobs_empty(self, app):
        """T3.5: 空列表返回 200"""
        response = app.get("/api/scheduler/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_list_jobs_pagination(self, app):
        """T3.6: 列表分页参数"""
        # 先创建一个任务
        app.post("/api/scheduler/jobs", json={
            "name": "分页测试",
            "job_type": "pipeline",
            "cron_expression": "0 8 * * *",
        })
        response = app.get("/api/scheduler/jobs?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 1
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_get_job_detail(self, app):
        """T3.7: 获取单个任务详情"""
        create_resp = app.post("/api/scheduler/jobs", json={
            "name": "详情测试",
            "job_type": "preprocessing",
            "target_id": 5,
            "cron_expression": "0 9 * * *",
        })
        job_id = create_resp.json()["id"]
        response = app.get(f"/api/scheduler/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["name"] == "详情测试"

    def test_get_job_not_found(self, app):
        """T3.8: 获取不存在的任务返回 404"""
        fake_id = str(uuid.uuid4())
        response = app.get(f"/api/scheduler/jobs/{fake_id}")
        assert response.status_code == 404

    def test_update_job_name(self, app):
        """T3.9: 更新任务名称"""
        create_resp = app.post("/api/scheduler/jobs", json={
            "name": "原名称",
            "job_type": "pipeline",
            "cron_expression": "0 8 * * *",
        })
        job_id = create_resp.json()["id"]

        response = app.patch(f"/api/scheduler/jobs/{job_id}", json={
            "name": "新名称",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新名称"

    def test_update_job_pause(self, app):
        """T3.10: 暂停任务"""
        create_resp = app.post("/api/scheduler/jobs", json={
            "name": "暂停测试",
            "job_type": "training",
            "target_id": 1,
            "cron_expression": "0 8 * * *",
            "is_enabled": True,
        })
        job_id = create_resp.json()["id"]

        response = app.patch(f"/api/scheduler/jobs/{job_id}", json={
            "status": "paused",
        })
        assert response.status_code == 200

    def test_delete_job(self, app):
        """T3.11: 删除任务"""
        create_resp = app.post("/api/scheduler/jobs", json={
            "name": "删除测试",
            "job_type": "pipeline",
            "cron_expression": "0 8 * * *",
        })
        job_id = create_resp.json()["id"]

        response = app.delete(f"/api/scheduler/jobs/{job_id}")
        assert response.status_code == 204

        # 再次获取应该 404
        get_resp = app.get(f"/api/scheduler/jobs/{job_id}")
        assert get_resp.status_code == 404

    def test_cron_validate_valid(self, app):
        """T3.12: Cron 表达式校验（合法）"""
        response = app.post("/api/scheduler/cron/validate", json={
            "cron_expression": "0 8 * * *",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["next_run_time"] is not None

    def test_cron_validate_invalid(self, app):
        """T3.13: Cron 表达式校验（非法）"""
        response = app.post("/api/scheduler/cron/validate", json={
            "cron_expression": "bad_expression",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["error"] is not None

    def test_job_filter_by_status(self, app):
        """T3.14: 按状态筛选任务"""
        # 创建多个任务
        for name, status in [("任务A", "active"), ("任务B", "paused")]:
            app.post("/api/scheduler/jobs", json={
                "name": name,
                "job_type": "pipeline",
                "cron_expression": "0 8 * * *",
                "is_enabled": status == "active",
            })

        response = app.get("/api/scheduler/jobs?status=active")
        assert response.status_code == 200
        data = response.json()
        assert all(j["status"] == "active" for j in data["data"])

    def test_job_filter_by_keyword(self, app):
        """T3.15: 按关键词搜索任务"""
        app.post("/api/scheduler/jobs", json={
            "name": "特别的长名称任务",
            "job_type": "pipeline",
            "cron_expression": "0 8 * * *",
        })
        response = app.get("/api/scheduler/jobs?keyword=长名称")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 1
        assert "长名称" in data["data"][0]["name"]


# =============================================================================
# T4: 告警冷却测试
# =============================================================================

class TestAlertCooldown:
    """告警冷却机制测试"""

    def test_cooldown_blocks_duplicate_alert(self):
        """T4.1: 冷却期内第二次调用 can_alert 返回 False"""
        from src.mlkit.scheduler.alerter import AlertCooldownTracker

        tracker = AlertCooldownTracker(cooldown_seconds=5)
        job_id = str(uuid.uuid4())

        assert tracker.can_alert(job_id) is True  # 第一次
        assert tracker.can_alert(job_id) is False  # 冷却中

    def test_cooldown_allows_after_expiry(self):
        """T4.2: 冷却期满后允许再次告警（使用短冷却时间测试）"""
        from src.mlkit.scheduler.alerter import AlertCooldownTracker
        import time

        tracker = AlertCooldownTracker(cooldown_seconds=1)
        job_id = str(uuid.uuid4())

        assert tracker.can_alert(job_id) is True
        time.sleep(1.1)
        assert tracker.can_alert(job_id) is True  # 冷却已过

    def test_cooldown_independent_jobs(self):
        """T4.3: 不同 Job 独立冷却"""
        from src.mlkit.scheduler.alerter import AlertCooldownTracker

        tracker = AlertCooldownTracker(cooldown_seconds=10)
        job_a = str(uuid.uuid4())
        job_b = str(uuid.uuid4())

        assert tracker.can_alert(job_a) is True
        tracker.can_alert(job_a)  # 进入冷却
        assert tracker.can_alert(job_b) is True  # job_b 不受影响


# =============================================================================
# T5: Runner 并发控制测试
# =============================================================================

class TestRunnerConcurrency:
    """Runner 并发控制测试"""

    def test_mark_job_running_and_done(self):
        """T5.1: Job 运行标记与释放"""
        from src.mlkit.scheduler.runner import _is_job_running, _mark_job_running, _mark_job_done

        job_id = str(uuid.uuid4())

        assert _is_job_running(job_id) is False
        _mark_job_running(job_id)
        assert _is_job_running(job_id) is True
        _mark_job_done(job_id)
        assert _is_job_running(job_id) is False

    def test_concurrent_same_job_blocked(self):
        """T5.2: 同一 Job 重复触发被阻止"""
        from src.mlkit.scheduler.runner import _is_job_running, _mark_job_running, _mark_job_done

        job_id = str(uuid.uuid4())
        _mark_job_running(job_id)
        # 模拟第二次调用（同一 Job 已在运行）
        assert _is_job_running(job_id) is True
        _mark_job_done(job_id)

    def test_multiple_jobs_independent(self):
        """T5.3: 多个 Job 可同时运行"""
        from src.mlkit.scheduler.runner import _is_job_running, _mark_job_running, _mark_job_done

        job_ids = [str(uuid.uuid4()) for _ in range(3)]
        for jid in job_ids:
            _mark_job_running(jid)

        # 所有 Job 都应该在运行
        assert all(_is_job_running(jid) for jid in job_ids)

        # 清理
        for jid in job_ids:
            _mark_job_done(jid)
