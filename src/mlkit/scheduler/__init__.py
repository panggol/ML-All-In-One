"""
mlkit.scheduler — 自动化任务调度模块

提供基于 APScheduler 的 Cron 定时任务调度能力：
- Cron 表达式解析与验证（croniter）
- Job / Execution 数据模型
- 任务执行器（支持 preprocessing / training / pipeline）
- 飞书 WebHook 告警（带冷却机制）
- APScheduler 主调度器（启动、停止、CRUD）

使用示例：
    from src.mlkit.scheduler.models import Job, Execution
    from src.mlkit.scheduler.scheduler import init_scheduler, shutdown_scheduler
    from api.database import SessionLocal
    import os

    # 启动时
    init_scheduler(SessionLocal, os.getenv("SECRET_KEY"))

    # 关闭时
    shutdown_scheduler()
"""

from src.mlkit.scheduler.models import (
    Job,
    Execution,
    JobType,
    JobStatus,
    ExecutionStatus,
    TriggerType,
)
from src.mlkit.scheduler.cron_parser import (
    validate_cron,
    get_next_run_time,
    get_prev_run_time,
    describe_cron,
    CronParseError,
    CRON_PRESETS,
)
from src.mlkit.scheduler.alerter import send_feishu_alert
from src.mlkit.scheduler.runner import run_job
from src.mlkit.scheduler.scheduler import (
    Scheduler,
    init_scheduler,
    shutdown_scheduler,
)

__all__ = [
    # Models
    "Job",
    "Execution",
    "JobType",
    "JobStatus",
    "ExecutionStatus",
    "TriggerType",
    # Cron
    "validate_cron",
    "get_next_run_time",
    "get_prev_run_time",
    "describe_cron",
    "CronParseError",
    "CRON_PRESETS",
    # Alerter
    "send_feishu_alert",
    # Runner
    "run_job",
    # Scheduler
    "Scheduler",
    "init_scheduler",
    "shutdown_scheduler",
]
