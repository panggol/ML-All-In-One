"""
SQLAlchemy 数据模型：Pipeline Orchestration 模块

表结构：
- pipelines          — Pipeline 定义
- pipeline_versions   — Pipeline 版本快照
- pipeline_runs       — Pipeline 执行记录
- pipeline_step_runs  — 步骤执行记录

使用 api.database 的 Base（确保所有表使用同一个 engine）。
"""
from __future__ import annotations
import enum
from datetime import datetime, timezone as dt_tz
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey,
    Boolean, Text, JSON, UniqueConstraint, Index,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from api.database import Base


class PipelineStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class TriggerType(str, enum.Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    API = "api"


class Pipeline(Base):
    """Pipeline 定义表"""
    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    dsl_format = Column(String(10), nullable=False, default="json")   # json | yaml
    dsl_content = Column(Text, nullable=False)                         # DSL 定义内容
    schedule_cron = Column(String(100), nullable=True)                  # Cron 表达式，NULL=不调度
    schedule_enabled = Column(Boolean, default=True)
    schedule_job_id = Column(String(100), nullable=True)                # 关联 scheduled_jobs 的 job id
    status = Column(SAEnum(PipelineStatus), default=PipelineStatus.DRAFT, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(dt_tz.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(dt_tz.utc),
                        onupdate=lambda: datetime.now(dt_tz.utc))
    is_deleted = Column(Boolean, default=False)

    # 关联
    owner = relationship("User")
    versions = relationship("PipelineVersion", back_populates="pipeline",
                            cascade="all, delete-orphan", order_by="PipelineVersion.version.desc()")
    runs = relationship("PipelineRun", back_populates="pipeline",
                        cascade="all, delete-orphan", order_by="PipelineRun.run_number.desc()")


class PipelineVersion(Base):
    """Pipeline 版本快照表"""
    __tablename__ = "pipeline_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    dsl_format = Column(String(10), nullable=False)
    dsl_content = Column(Text, nullable=False)
    changelog = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(dt_tz.utc))

    # 关联
    pipeline = relationship("Pipeline", back_populates="versions")
    creator = relationship("User")

    __table_args__ = (
        UniqueConstraint("pipeline_id", "version", name="uq_pipeline_version"),
        Index("ix_pipeline_version_pipeline_version", "pipeline_id", "version"),
    )


class PipelineRun(Base):
    """Pipeline 执行记录表"""
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id", ondelete="SET NULL"), nullable=True, index=True)
    pipeline_version = Column(Integer, nullable=False)                  # 执行时使用的版本号
    run_number = Column(Integer, nullable=False)                         # Pipeline 内递增序号
    status = Column(SAEnum(RunStatus), default=RunStatus.PENDING, nullable=False)
    triggered_by = Column(SAEnum(TriggerType), default=TriggerType.MANUAL, nullable=False)
    run_params = Column(JSON, nullable=True)                              # 执行参数（数据集路径等）
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)                     # 总耗时（秒）
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)                          # 软删除（审计保留）

    # 关联
    pipeline = relationship("Pipeline", back_populates="runs")
    triggerer = relationship("User")
    step_runs = relationship("PipelineStepRun", back_populates="run",
                              cascade="all, delete-orphan", order_by="PipelineStepRun.order_index")

    __table_args__ = (
        UniqueConstraint("pipeline_id", "run_number", name="uq_pipeline_run_number"),
        Index("ix_pipeline_runs_pipeline_status", "pipeline_id", "status"),
    )


class PipelineStepRun(Base):
    """Pipeline 步骤执行记录表"""
    __tablename__ = "pipeline_step_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_name = Column(String(100), nullable=False)
    step_type = Column(String(30), nullable=False)                        # preprocessing | feature_engineering | training | automl | evaluation | model_registration
    status = Column(SAEnum(StepStatus), default=StepStatus.PENDING, nullable=False)
    order_index = Column(Integer, nullable=False)                          # DAG 拓扑序位置
    retry_count = Column(Integer, default=0)                              # 已重试次数
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)                              # metrics / 模型路径
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)                     # 步骤耗时（秒）

    # 关联
    run = relationship("PipelineRun", back_populates="step_runs")

    __table_args__ = (
        Index("ix_pipeline_step_runs_run_status", "run_id", "status"),
    )
