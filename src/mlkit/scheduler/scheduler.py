"""
APScheduler 主调度器
管理所有定时任务的调度循环（启动、停止、添加、移除任务）。
"""
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone as dt_tz
from typing import Optional, Callable, TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from src.mlkit.scheduler.cron_parser import get_next_run_time, CronParseError
from src.mlkit.scheduler.alerter import cleanup_alert_cooldown

if TYPE_CHECKING:
    from src.mlkit.scheduler.models import Job

logger = logging.getLogger("platform.scheduler")

# 环境变量
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MISFIRE_GRACE_TIME = 60  # 最多容忍 60 秒调度延迟


class Scheduler:
    """
    APScheduler 调度器封装。
    提供 Job 的添加、更新、删除、暂停、恢复、手动触发功能。
    """

    _instance: Optional["Scheduler"] = None
    _lock = threading.RLock()

    def __init__(self, db_session_factory: Callable, jwt_secret: str):
        """
        Args:
            db_session_factory: 数据库会话工厂（每次调用创建新 Session）
            jwt_secret: JWT 签名密钥（用于生成内部 API 调用 Token）
        """
        self._db_factory = db_session_factory
        self._jwt_secret = jwt_secret
        self._scheduler: Optional[BackgroundScheduler] = None
        self._started = False
        self._cleanup_timer: Optional[threading.Timer] = None

        # 生成内部服务 Token（用于调度器调用 API）
        self._internal_token = self._generate_internal_token()

    @classmethod
    def get_instance(cls) -> "Scheduler":
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("Scheduler 未初始化，请先调用 Scheduler.start()")
        return cls._instance

    def _generate_internal_token(self) -> str:
        """生成内部服务 Token（用于调度器调用内部 API）"""
        import jwt
        payload = {
            "sub": "scheduler",
            "role": "service",
            "iat": datetime.now(dt_tz.utc),
            "exp": datetime.now(dt_tz.utc).timestamp() + 86400 * 30,  # 30 天有效期
        }
        return jwt.encode(payload, self._jwt_secret, algorithm="HS256")

    def _get_internal_token(self) -> str:
        """获取内部 Token（自动续期）"""
        return self._internal_token

    # ============ APScheduler 生命周期管理 ============

    def start(self):
        """启动调度器（调用一次，在服务启动时）"""
        with self._lock:
            if self._started:
                logger.warning("[Scheduler] 调度器已启动，忽略重复调用")
                return

            # 构建 JobStore（与主数据库共用）
            jobstores = {
                "default": SQLAlchemyJobStore(
                    url=os.getenv("DATABASE_URL", "sqlite:///./ml_all_in_one.db"),
                    tablename="apscheduler_jobs",
                )
            }

            executors = {
                "default": {
                    "type": "threadpool",
                    "max_workers": 10,
                }
            }

            job_defaults = {
                "coalesce": True,
                "max_instances": 1,  # 同一 Job 同时最多一个实例
                "misfire_grace_time": MISFIRE_GRACE_TIME,
            }

            self._scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone="UTC",
            )

            # 注册事件监听器
            self._scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
            self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)

            # 启动
            self._scheduler.start()
            self._started = True

            logger.info("[Scheduler] 调度器启动成功")

            # 启动告警冷却清理定时器（每 10 分钟）
            self._start_cleanup_timer()

    def stop(self):
        """停止调度器"""
        with self._lock:
            if not self._started:
                return

            if self._cleanup_timer:
                self._cleanup_timer.cancel()

            if self._scheduler:
                self._scheduler.shutdown(wait=True)

            self._started = False
            Scheduler._instance = None
            logger.info("[Scheduler] 调度器已停止")

    def _start_cleanup_timer(self):
        """启动定时清理（每 10 分钟清理过期告警冷却记录）"""
        def _run():
            cleanup_alert_cooldown()
            self._cleanup_timer = threading.Timer(600, _run)
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()

        self._cleanup_timer = threading.Timer(600, _run)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    # ============ APScheduler 事件回调 ============

    def _on_job_executed(self, event):
        """任务执行成功后更新 next_run_time"""
        job_id = event.job_id
        if job_id.startswith("scheduler_job_"):
            actual_id = job_id.replace("scheduler_job_", "")
            logger.debug(f"[Scheduler] Job {actual_id} 执行完成，next_run_time 将自动更新")

    def _on_job_error(self, event):
        """任务执行出错时的日志"""
        job_id = event.job_id
        exception = event.exception
        logger.error(f"[Scheduler] Job {job_id} 执行出错: {exception}")

    # ============ Job 管理 API（供 API 路由调用）============

    def add_job(self, job: "Job"):
        """
        将 Job 添加到 APScheduler JobStore 并立即开始调度。

        Args:
            job: Job SQLAlchemy 模型实例
        """
        if not self._scheduler:
            raise RuntimeError("Scheduler 未启动")

        aps_job_id = f"scheduler_job_{job.id}"

        # 计算下次执行时间
        try:
            next_run = get_next_run_time(job.cron_expression)
        except CronParseError as e:
            logger.error(f"[Scheduler] 添加 Job {job.id} 失败，Cron 解析错误: {e}")
            raise

        # APScheduler job_func 需要可序列化，使用全局入口
        self._scheduler.add_job(
            func=_scheduled_job_wrapper,
            trigger="cron",
            cron=job.cron_expression,
            id=aps_job_id,
            replace_existing=True,
            kwargs={
                "job_id": job.id,
                "db_factory_repr": f"{self._db_factory.__module__}.{self._db_factory.__qualname__}",
                "jwt_secret": self._jwt_secret,
            },
            misfire_grace_time=MISFIRE_GRACE_TIME,
            coalesce=True,
            max_instances=1,
            next_run_time=next_run if job.is_enabled else None,
        )

        logger.info(f"[Scheduler] Job 添加成功，id={job.id}, next_run={next_run}")

    def update_job(self, job: "Job"):
        """
        更新 APScheduler 中的 Job（重新计算调度时间）。
        """
        if not self._scheduler:
            raise RuntimeError("Scheduler 未启动")

        aps_job_id = f"scheduler_job_{job.id}"

        # 移除旧 job
        self.remove_job(job.id)

        if job.is_enabled:
            # 重新添加
            self.add_job(job)
        else:
            logger.info(f"[Scheduler] Job {job.id} 已暂停，不加入调度器")

    def remove_job(self, job_id: str):
        """
        从 APScheduler JobStore 中移除 Job。
        """
        if not self._scheduler:
            raise RuntimeError("Scheduler 未启动")

        aps_job_id = f"scheduler_job_{job_id}"
        try:
            self._scheduler.remove_job(aps_job_id)
            logger.info(f"[Scheduler] Job {job_id} 已从调度器移除")
        except Exception:
            # Job 可能不存在，忽略
            pass

    def pause_job(self, job_id: str):
        """暂停 Job（从调度器移除，下次启用时再添加）"""
        self.remove_job(job_id)

    def resume_job(self, job: "Job"):
        """恢复 Job（重新添加到调度器）"""
        self.add_job(job)

    def trigger_job(self, job_id: str) -> str:
        """
        手动触发 Job（立即执行一次，不影响 Cron 调度）。

        Returns:
            execution_id: 本次执行的 UUID
        """
        if not self._scheduler:
            raise RuntimeError("Scheduler 未启动")

        aps_job_id = f"scheduler_job_{job_id}"

        # APScheduler 的 run_job 会立即在新线程中执行
        self._scheduler.run_job(aps_job_id, wait=False)

        logger.info(f"[Scheduler] 手动触发 Job {job_id}")
        return job_id

    def get_next_run_time(self, job_id: str) -> Optional[datetime]:
        """获取某个 Job 的下次执行时间"""
        if not self._scheduler:
            return None

        aps_job_id = f"scheduler_job_{job_id}"
        job = self._scheduler.get_job(aps_job_id)
        if job:
            return job.next_run_time
        return None

    def reload_from_db(self):
        """
        从数据库加载所有 active 任务并注册到调度器。
        用于服务启动时恢复调度状态。
        """
        db = self._db_factory()
        try:
            from src.mlkit.scheduler.models import Job, JobStatus
            active_jobs = db.query(Job).filter(
                Job.is_enabled == True,
                Job.status == JobStatus.ACTIVE,
            ).all()

            for job in active_jobs:
                try:
                    self.add_job(job)
                except Exception as e:
                    logger.error(f"[Scheduler] 恢复 Job {job.id} 失败: {e}")

            logger.info(f"[Scheduler] 从数据库恢复 {len(active_jobs)} 个活跃 Job")
        finally:
            db.close()


def _scheduled_job_wrapper(job_id: str, db_factory_repr: str, jwt_secret: str):
    """
    APScheduler 调度的全局入口函数。
    该函数必须可被 pickle（在多线程环境下），因此放在模块级别。
    """
    import asyncio
    from src.mlkit.scheduler.models import SessionLocal
    from src.mlkit.scheduler.runner import run_job
    from src.mlkit.scheduler.models import TriggerType

    logger.info(f"[Scheduler] 触发定时任务，job_id={job_id}")

    # 生成内部 Token
    import jwt
    payload = {
        "sub": "scheduler",
        "role": "service",
        "iat": datetime.now(dt_tz.utc),
        "exp": datetime.now(dt_tz.utc).timestamp() + 86400,
    }
    internal_token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    asyncio.run(
        run_job(
            job_id=job_id,
            db_session_factory=SessionLocal,
            triggered_by=TriggerType.SCHEDULED,
            token=internal_token,
        )
    )


# =============================================================================
# 全局调度器启动/停止钩子（供 api/main.py lifespan 调用）
# =============================================================================

_scheduler_instance: Optional[Scheduler] = None


def init_scheduler(db_session_factory, jwt_secret: str):
    """初始化调度器（lifespan startup 时调用）"""
    global _scheduler_instance
    Scheduler._instance = Scheduler(db_session_factory, jwt_secret)
    _scheduler_instance = Scheduler._instance
    _scheduler_instance.start()
    # 从数据库恢复已注册的 Job
    _scheduler_instance.reload_from_db()


def shutdown_scheduler():
    """关闭调度器（lifespan shutdown 时调用）"""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop()
        _scheduler_instance = None
