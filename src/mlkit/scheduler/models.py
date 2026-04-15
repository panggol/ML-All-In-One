"""
SQLAlchemy 数据模型：Scheduler 模块
Job 表 — 定时任务定义
Execution 表 — 任务执行历史记录

使用 api.database 的 Base（确保所有表使用同一个 Base，create_all 可一次性创建所有表）。
"""
import uuid
from datetime import datetime, timezone as dt_tz
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

# 复用 api.database 的 Base（避免跨 Base 外键引用问题）
from api.database import Base


class JobType(str, enum.Enum):
    """任务类型"""
    PREPROCESSING = "preprocessing"
    TRAINING = "training"
    PIPELINE = "pipeline"


class JobStatus(str, enum.Enum):
    """任务状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"


class ExecutionStatus(str, enum.Enum):
    """执行状态"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"


class TriggerType(str, enum.Enum):
    """触发方式"""
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class Job(Base):
    """定时任务模型"""
    __tablename__ = "scheduler_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(128), nullable=False)
    job_type = Column(SAEnum(JobType), nullable=False)
    target_id = Column(Integer, nullable=True)
    cron_expression = Column(String(64), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.ACTIVE, nullable=False)
    webhook_url = Column(String(512), nullable=True)
    retry_count = Column(Integer, default=0)
    params = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True)
    next_run_time = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(dt_tz.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(dt_tz.utc), onupdate=lambda: datetime.now(dt_tz.utc))

    # 关联执行记录（级联删除）
    executions = relationship("Execution", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job(id={self.id}, name={self.name}, status={self.status})>"


class Execution(Base):
    """任务执行历史记录"""
    __tablename__ = "scheduler_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("scheduler_jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(SAEnum(ExecutionStatus), default=ExecutionStatus.RUNNING, nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(dt_tz.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    triggered_by = Column(SAEnum(TriggerType), default=TriggerType.SCHEDULED, nullable=False)
    retry_index = Column(Integer, default=0)

    job = relationship("Job", back_populates="executions")

    def __repr__(self):
        return f"<Execution(id={self.id}, job_id={self.job_id}, status={self.status})>"
