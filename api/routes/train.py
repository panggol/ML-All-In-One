"""
训练路由 - 使用真实 mlkit.runner 进行训练
"""
import os
import sys
import threading
import pandas as pd
import joblib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

# 添加 src 到路径以便导入 mlkit
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))

from api.database import TrainingJob, DataFile, TrainedModel, User, SessionLocal, get_db
from api.auth import get_current_user

router = APIRouter()

# 模型保存目录
MODELS_DIR = os.getenv("MODELS_DIR", "./models")
os.makedirs(MODELS_DIR, exist_ok=True)


# ============ Pydantic 模型 ============

class TrainRequest(BaseModel):
    data_file_id: int
    target_column: str
    task_type: str  # classification/regression
    model_type: str  # sklearn/xgboost/lightgbm
    model_name: str
    params: Optional[dict] = {}
    feature_columns: Optional[List[str]] = None  # 手动选择的特征列


class TrainJobResponse(BaseModel):
    id: int
    model_name: str
    task_type: str
    status: str
    progress: int
    current_iter: int
    metrics: dict
    logs: str
    created_at: str

    class Config:
        from_attributes = True


class PredictRequest(BaseModel):
    data: List[dict]


# ============ 训练任务管理器（线程安全） ============

class TrainingManager:
    """管理所有训练任务的状态和生命周期"""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[int, dict] = {}       # job_id -> status dict
        self._stop_events: dict[int, threading.Event] = {}  # job_id -> stop event
        self._runners: dict[int, object] = {}  # job_id -> runner instance (for stop)

    def register(self, job_id: int):
        with self._lock:
            self._jobs[job_id] = {
                "status": "pending",
                "progress": 0,
                "current_iter": 0,
                "logs": "",
            }
            self._stop_events[job_id] = threading.Event()

    def unregister(self, job_id: int):
        with self._lock:
            self._jobs.pop(job_id, None)
            self._stop_events.pop(job_id, None)
            self._runners.pop(job_id, None)

    def update(self, job_id: int, **kwargs):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)

    def get_status(self, job_id: int) -> dict:
        with self._lock:
            return dict(self._jobs.get(job_id, {}))

    def request_stop(self, job_id: int):
        with self._lock:
            if job_id in self._stop_events:
                self._stop_events[job_id].set()
            if job_id in self._runners:
                self._runners[job_id].stop_training = True

    def register_runner(self, job_id: int, runner):
        with self._lock:
            self._runners[job_id] = runner

    def is_stopped(self, job_id: int) -> bool:
        with self._lock:
            return self._stop_events.get(job_id, threading.Event()).is_set()


training_mgr = TrainingManager()


# ============ 后台训练函数 ============

def _run_training(job_id: int, db_url: str):
    """
    后台训练任务（在线程中运行）

    使用 mlkit.runner 进行真实训练：
    1. 加载数据
    2. 创建 runner 并构建环境
    3. 划分训练/测试集
    4. 在训练集上训练模型
    5. 在测试集上评估
    6. 保存模型文件 (.joblib)
    """
    from mlkit.config import Config
    from mlkit.data import DataLoader
    from mlkit.model import create_model

    db = SessionLocal()
    try:
        job = db.query(TrainingJob).get(job_id)
        if not job:
            return

        # 更新状态
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        training_mgr.update(job_id, status="running", progress=0, logs="开始训练...\n")

        # 1. 加载数据
        data_file = db.query(DataFile).get(job.data_file_id)
        if not data_file:
            raise FileNotFoundError(f"数据文件不存在: id={job.data_file_id}")

        df = pd.read_csv(data_file.filepath)
        if job.target_column not in df.columns:
            raise ValueError(f"目标列 '{job.target_column}' 不存在于数据中")

        # 如果指定了 feature_columns，只保留目标列和指定的特征列
        feature_columns = job.params.get('feature_columns') if job.params else None
        if feature_columns:
            # 验证指定的特征列都存在
            missing_cols = [c for c in feature_columns if c not in df.columns]
            if missing_cols:
                raise ValueError(f"特征列不存在: {missing_cols}")
            # 只保留目标列和指定的特征列
            df = df[[c for c in feature_columns if c != job.target_column] + [job.target_column]]
            training_mgr.update(job_id, logs=f"特征选择: 使用 {len(feature_columns)} 列\n")

        training_mgr.update(job_id, logs=f"数据加载完成: {len(df)} 行, {len(df.columns)} 列\n")

        # 2. 创建 runner 配置并构建环境
        config_dict = {
            "data": {
                "train_path": data_file.filepath,
                "target_column": job.target_column,
            },
            "model": {
                "type": job.model_type,
                "task": job.task_type,
                "model_class": job.model_name,
                **job.params,
            },
            "hooks": {
                "logger": False,
                "checkpoint": False,
                "early_stopping": False,
            },
        }

        config = Config.from_dict(config_dict)
        runner = type("Runner", (), {
            "config": config,
            "model": None,
            "train_dataset": None,
            "stop_training": False,
            "train_history": [],
            "val_history": [],
            "current_epoch": 0,
            "global_iter": 0,
            "hooks": [],
        })()

        # 构建数据集
        loader = DataLoader(data_file.filepath)
        dataset = loader.load(target_column=job.target_column)
        runner.train_dataset = dataset

        # 构建模型
        model_kwargs = {**job.params, "task": job.task_type, "model_class": job.model_name}
        runner.model = create_model(job.model_type, **model_kwargs)

        training_mgr.register_runner(job_id, runner)
        training_mgr.update(job_id, logs="模型构建完成\n")

        # 3. 划分训练/测试集 (80/20)
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            dataset.X, dataset.y, test_size=0.2, random_state=42
        )

        training_mgr.update(job_id, logs=f"训练集: {len(X_train)} 样本, 测试集: {len(X_test)} 样本\n")

        # 4. 训练模型（支持增量学习的模型使用 partial_fit 模拟进度）
        if hasattr(runner.model.model, "partial_fit"):
            # 增量学习模型：分批训练，可查询进度
            from sklearn.utils import shuffle
            import numpy as np

            epochs = job.params.get("epochs", 10)
            batch_size = job.params.get("batch_size", 32)
            total_steps = epochs * max(1, len(X_train) // batch_size)
            step = 0

            classes = np.unique(y_train) if job.task_type == "classification" else None

            for epoch in range(epochs):
                if training_mgr.is_stopped(job_id):
                    training_mgr.update(job_id, status="stopped", logs="训练已停止\n")
                    job.status = "stopped"
                    job.finished_at = datetime.utcnow()
                    db.commit()
                    return

                X_shuffled, y_shuffled = shuffle(X_train, y_train, random_state=epoch)
                n_samples = len(X_shuffled)

                for i in range(0, n_samples, batch_size):
                    if training_mgr.is_stopped(job_id):
                        training_mgr.update(job_id, status="stopped", logs="训练已停止\n")
                        job.status = "stopped"
                        job.finished_at = datetime.utcnow()
                        db.commit()
                        return

                    X_batch = X_shuffled[i:i + batch_size]
                    y_batch = y_shuffled[i:i + batch_size]

                    if classes is not None:
                        runner.model.model.partial_fit(X_batch, y_batch, classes=classes)
                    else:
                        runner.model.model.partial_fit(X_batch, y_batch)

                    step += 1
                    progress = int(step / total_steps * 100)

                    training_mgr.update(
                        job_id,
                        progress=progress,
                        current_iter=step,
                        logs=f"Epoch {epoch+1}/{epochs}, Step {step}/{total_steps}\n",
                    )
                    job.progress = progress
                    job.current_iter = step
                    db.commit()
        else:
            # 非增量学习模型：直接 fit，用进度条模拟
            import time

            training_mgr.update(job_id, progress=10, logs="开始训练...\n")

            # 启动训练线程
            train_result = {"done": False, "error": None}

            def _fit():
                try:
                    runner.model.fit(X_train, y_train)
                    train_result["done"] = True
                except Exception as e:
                    train_result["error"] = str(e)

            fit_thread = threading.Thread(target=_fit, daemon=True)
            fit_thread.start()

            # 监控训练进度
            elapsed = 0
            while fit_thread.is_alive():
                if training_mgr.is_stopped(job_id):
                    training_mgr.update(job_id, status="stopped", logs="训练已停止\n")
                    job.status = "stopped"
                    job.finished_at = datetime.utcnow()
                    db.commit()
                    return

                elapsed += 0.1
                progress = min(int(elapsed * 10), 90)  # 最多到 90%
                training_mgr.update(
                    job_id,
                    progress=progress,
                    logs=f"训练中... {elapsed:.1f}s\n",
                )
                job.progress = progress
                db.commit()
                time.sleep(0.1)

            fit_thread.join(timeout=5)

            if train_result["error"]:
                raise RuntimeError(train_result["error"])

            training_mgr.update(job_id, progress=95, logs="训练完成，评估中...\n")

        # 5. 在测试集上评估
        y_pred = runner.model.predict(X_test)

        metrics = {}
        if job.task_type == "classification":
            from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
            metrics["accuracy"] = float(accuracy_score(y_test, y_pred))
            metrics["f1"] = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
            metrics["precision"] = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
            metrics["recall"] = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        else:
            from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
            metrics["mse"] = float(mean_squared_error(y_test, y_pred))
            metrics["mae"] = float(mean_absolute_error(y_test, y_pred))
            metrics["r2"] = float(r2_score(y_test, y_pred))

        training_mgr.update(
            job_id,
            status="completed",
            progress=100,
            logs="训练完成！\n",
        )

        # 6. 保存模型
        model_path = os.path.join(MODELS_DIR, f"job_{job_id}.joblib")
        runner.model.save(model_path)

        # 7. 更新数据库
        job.status = "completed"
        job.progress = 100
        job.metrics = metrics
        job.checkpoint_path = model_path
        job.finished_at = datetime.utcnow()
        db.commit()

        # 8. 同时在 TrainedModel 表中注册
        trained = TrainedModel(
            user_id=job.user_id,
            training_job_id=job.id,
            name=f"{job.model_name}_job_{job_id}",
            model_type=job.model_type,
            model_path=model_path,
            metrics=metrics,
            config={"model_name": job.model_name, "task_type": job.task_type, **job.params},
        )
        db.add(trained)
        db.commit()

    except Exception as e:
        training_mgr.update(
            job_id,
            status="failed",
            logs=f"训练失败: {str(e)}\n",
        )
        job = db.query(TrainingJob).get(job_id)
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            db.commit()
    finally:
        training_mgr.unregister(job_id)
        db.close()


# ============ API 路由 ============

@router.post("/", response_model=TrainJobResponse)
async def create_training(
    request: TrainRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建训练任务，使用真实 mlkit.runner 进行训练"""
    # 检查数据文件是否存在
    data_file = db.query(DataFile).filter(
        DataFile.id == request.data_file_id,
        DataFile.user_id == current_user.id,
    ).first()

    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据文件不存在",
        )

    # 将 feature_columns 存入 params
    job_params = dict(request.params) if request.params else {}
    if request.feature_columns:
        job_params['feature_columns'] = request.feature_columns

    # 创建训练任务
    job = TrainingJob(
        user_id=current_user.id,
        data_file_id=request.data_file_id,
        model_type=request.model_type,
        model_name=request.model_name,
        task_type=request.task_type,
        target_column=request.target_column,
        params=job_params,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 注册训练状态
    training_mgr.register(job.id)

    # 使用 BackgroundTasks 启动异步训练
    # 传入 db_url 而非 session，因为 BackgroundTasks 在线程池中运行
    from api.database import DATABASE_URL
    background_tasks.add_task(_run_training, job.id, DATABASE_URL)

    return TrainJobResponse(
        id=job.id,
        model_name=job.model_name,
        task_type=job.task_type,
        status=job.status,
        progress=job.progress,
        current_iter=job.current_iter,
        metrics=job.metrics or {},
        logs=job.logs or "",
        created_at=job.created_at.isoformat(),
    )


@router.get("/", response_model=List[TrainJobResponse])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取训练任务列表"""
    jobs = db.query(TrainingJob).filter(
        TrainingJob.user_id == current_user.id,
    ).order_by(TrainingJob.created_at.desc()).all()

    return [
        TrainJobResponse(
            id=job.id,
            model_name=job.model_name,
            task_type=job.task_type,
            status=job.status,
            progress=job.progress,
            current_iter=job.current_iter,
            metrics=job.metrics or {},
            logs=job.logs or "",
            created_at=job.created_at.isoformat(),
        )
        for job in jobs
    ]


@router.get("/{job_id}/status")
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取训练状态（含实时进度）"""
    job = db.query(TrainingJob).filter(
        TrainingJob.id == job_id,
        TrainingJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    # 从内存状态获取最新进度
    status_data = training_mgr.get_status(job_id)

    return {
        "id": job.id,
        "status": status_data.get("status", job.status),
        "progress": status_data.get("progress", job.progress),
        "current_iter": status_data.get("current_iter", job.current_iter),
        "metrics": job.metrics or {},
        "logs": status_data.get("logs", job.logs or ""),
    }


@router.post("/{job_id}/stop")
async def stop_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """停止训练"""
    job = db.query(TrainingJob).filter(
        TrainingJob.id == job_id,
        TrainingJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    if job.status not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已完成或已停止",
        )

    # 请求停止
    training_mgr.request_stop(job_id)

    return {"message": "已发送停止信号"}


@router.post("/{job_id}/predict")
async def predict(
    job_id: int,
    request: PredictRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """使用训练好的模型进行预测"""
    job = db.query(TrainingJob).filter(
        TrainingJob.id == job_id,
        TrainingJob.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="训练任务尚未完成",
        )

    if not job.checkpoint_path or not os.path.exists(job.checkpoint_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型文件不存在",
        )

    # 加载模型
    try:
        model = joblib.load(job.checkpoint_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"加载模型失败: {str(e)}",
        )

    # 预测
    df = pd.DataFrame(request.data)
    predictions = model.predict(df)

    result = {"predictions": predictions.tolist()}

    # 如果有概率输出
    if hasattr(model, "predict_proba"):
        try:
            result["probabilities"] = model.predict_proba(df).tolist()
        except Exception:
            pass

    return result
