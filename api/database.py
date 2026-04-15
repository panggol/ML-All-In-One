"""
数据库配置和模型
"""
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON
from datetime import datetime, timezone
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ml_all_in_one.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 专用
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass

def get_db():
    """依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ 数据模型 ============

class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="user", nullable=False)  # "user" | "admin"
    is_protected = Column(Boolean, default=False, nullable=False)  # 受保护用户不可删除
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 关联
    data_files = relationship("DataFile", back_populates="owner", cascade="all, delete-orphan")
    training_jobs = relationship("TrainingJob", back_populates="owner", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="owner", cascade="all, delete-orphan")


class DataFile(Base):
    """数据文件模型"""
    __tablename__ = "data_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    size = Column(Integer, nullable=False)  # bytes
    rows = Column(Integer, default=0)
    columns = Column(JSON, default=list)  # 列名列表
    dtypes = Column(JSON, default=dict)   # 列类型
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 关联
    owner = relationship("User", back_populates="data_files")


class Experiment(Base):
    """实验模型"""
    __tablename__ = "experiments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    params = Column(JSON, default=dict)
    metrics = Column(JSON, default=dict)
    status = Column(String(20), default="pending")  # pending/running/completed/failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    
    # 关联
    owner = relationship("User", back_populates="experiments")
    training_jobs = relationship("TrainingJob", back_populates="experiment", cascade="all, delete-orphan")


class TrainingJob(Base):
    """训练任务模型"""
    __tablename__ = "training_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True)
    data_file_id = Column(Integer, ForeignKey("data_files.id"), nullable=True)
    
    model_type = Column(String(50), nullable=False)   # sklearn/xgboost/lightgbm/pytorch
    model_name = Column(String(50), nullable=False)    # RandomForestClassifier 等
    task_type = Column(String(20), nullable=False)     # classification/regression
    target_column = Column(String(100), nullable=False)
    
    params = Column(JSON, default=dict)               # 超参数
    status = Column(String(20), default="pending")   # pending/running/completed/failed
    progress = Column(Integer, default=0)            # 0-100
    current_iter = Column(Integer, default=0)
    metrics = Column(JSON, default=dict)               # 最终指标
    metrics_curve = Column(JSON, default=dict)          # 每个epoch的曲线数据
    logs = Column(Text, default="")                   # 训练日志
    
    error_message = Column(Text, nullable=True)
    checkpoint_path = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    
    # 关联
    owner = relationship("User", back_populates="training_jobs")
    experiment = relationship("Experiment", back_populates="training_jobs")


class TrainedModel(Base):
    """训练好的模型"""
    __tablename__ = "trained_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    training_job_id = Column(Integer, ForeignKey("training_jobs.id"), nullable=True)

    name = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)
    model_path = Column(String(500), nullable=False)  # 模型文件路径
    metrics = Column(JSON, default=dict)
    config = Column(JSON, default=dict)  # 模型配置

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关联
    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")


class ModelVersion(Base):
    """
    模型版本表
    为 TrainedModel 提供版本化包装，记录每次训练的元数据和指标。
    """
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("trained_models.id"), nullable=False)
    version = Column(Integer, nullable=False)  # 版本号，整数递增
    tag = Column(String(20), nullable=False, default="staging")  # staging/production/archived

    # 算法元数据
    algorithm_type = Column(String(50), nullable=True)
    model_type = Column(String(50), nullable=True)  # sklearn/xgboost/pytorch
    task_type = Column(String(20), nullable=True)   # classification/regression

    # 数据集指纹
    dataset_name = Column(String(255), nullable=True)
    dataset_hash = Column(String(64), nullable=True)  # SHA256 指纹

    # 训练信息
    training_params = Column(JSON, default=dict)
    training_time = Column(Float, nullable=True)      # 秒
    metrics = Column(JSON, default=dict)             # 评估指标
    training_job_id = Column(Integer, ForeignKey("training_jobs.id"), nullable=True)

    # 文件信息
    model_file_path = Column(String(500), nullable=True)
    model_file_size = Column(Integer, nullable=True)  # bytes

    # 审计字段
    registered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    registered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关联
    model = relationship("TrainedModel", back_populates="versions")

    # 约束：同一模型下版本号唯一
    __table_args__ = (
        # 使用 SQLAlchemy 约束语法（SQLite 兼容）
    )


class ModelVersionHistory(Base):
    """
    模型版本操作历史表
    记录所有版本变更操作（注册/标签变更/回滚/归档），用于审计追溯。
    """
    __tablename__ = "model_version_history"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # register/tag_change/rollback/archive
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(JSON, default=dict)          # 操作详情 JSON
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
