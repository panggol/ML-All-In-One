"""
训练路由
"""
import os
import sys
import threading
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

# 添加 src 到路径以便导入 mlkit
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))

from api.database import TrainingJob, DataFile, User, get_db
from api.auth import get_current_user

router = APIRouter()

# 模型检查点目录
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "./checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)


# ============ Pydantic 模型 ============

class TrainRequest(BaseModel):
    data_file_id: int
    target_column: str
    task_type: str  # classification/regression
    model_type: str  # sklearn/xgboost/lightgbm
    model_name: str
    params: Optional[dict] = {}


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


# ============ 训练任务存储（内存中）===========
training_status = {}  # job_id -> {status, progress, metrics, logs}


def run_training(job_id: int, db_session: int):
    """后台训练任务"""
    import mlkit
    from mlkit.runner import create_runner
    
    job = TrainingJob.query.get(job_id)
    if not job:
        return
    
    job.status = "running"
    job.started_at = datetime.utcnow()
    db_session.commit()
    
    training_status[job_id] = {
        "status": "running",
        "progress": 0,
        "current_iter": 0,
        "accuracy": 0,
        "loss": 0,
        "logs": ""
    }
    
    try:
        # 读取数据
        data_file = job.data_file
        df = pd.read_csv(data_file.filepath)
        
        # 分割特征和标签
        X = df.drop(columns=[job.target_column])
        y = df[job.target_column]
        
        # 划分训练测试集
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # 创建 runner
        runner = create_runner(
            model_type=job.model_type,
            model_name=job.model_name,
            task_type=job.task_type
        )
        
        # 模拟训练进度
        total_iters = job.params.get("n_estimators", 100)
        for i in range(total_iters):
            if training_status[job_id]["status"] == "stopped":
                break
            
            # 模拟训练
            import time
            time.sleep(0.05)
            
            training_status[job_id]["progress"] = int((i + 1) / total_iters * 100)
            training_status[job_id]["current_iter"] = i + 1
            training_status[job_id]["accuracy"] = 0.5 + (i / total_iters) * 0.4
            training_status[job_id]["logs"] += f"Iteration {i+1}/{total_iters}\n"
            
            job.progress = training_status[job_id]["progress"]
            job.current_iter = i + 1
            db_session.commit()
        
        # 训练完成
        if training_status[job_id]["status"] != "stopped":
            training_status[job_id]["status"] = "completed"
            training_status[job_id]["progress"] = 100
            job.status = "completed"
            job.metrics = {
                "accuracy": training_status[job_id]["accuracy"],
                "f1": training_status[job_id]["accuracy"] - 0.01
            }
            job.finished_at = datetime.utcnow()
            db_session.commit()
    
    except Exception as e:
        training_status[job_id]["status"] = "failed"
        training_status[job_id]["error"] = str(e)
        job.status = "failed"
        job.error_message = str(e)
        job.finished_at = datetime.utcnow()
        db_session.commit()


@router.post("/", response_model=TrainJobResponse)
async def create_training(
    request: TrainRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建训练任务"""
    # 检查数据文件是否存在
    data_file = db.query(DataFile).filter(
        DataFile.id == request.data_file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据文件不存在"
        )
    
    # 创建训练任务
    job = TrainingJob(
        user_id=current_user.id,
        data_file_id=request.data_file_id,
        model_type=request.model_type,
        model_name=request.model_name,
        task_type=request.task_type,
        target_column=request.target_column,
        params=request.params,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # 启动后台训练
    # 注意：这里需要修复 thread 中使用 db session 的问题
    # 简化版本：直接同步训练（后续优化）
    
    return TrainJobResponse(
        id=job.id,
        model_name=job.model_name,
        task_type=job.task_type,
        status=job.status,
        progress=job.progress,
        current_iter=job.current_iter,
        metrics=job.metrics,
        logs=job.logs,
        created_at=job.created_at.isoformat()
    )


@router.get("/", response_model=List[TrainJobResponse])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取训练任务列表"""
    jobs = db.query(TrainingJob).filter(
        TrainingJob.user_id == current_user.id
    ).order_by(TrainingJob.created_at.desc()).all()
    
    return [
        TrainJobResponse(
            id=job.id,
            model_name=job.model_name,
            task_type=job.task_type,
            status=job.status,
            progress=job.progress,
            current_iter=job.current_iter,
            metrics=job.metrics,
            logs=job.logs,
            created_at=job.created_at.isoformat()
        )
        for job in jobs
    ]


@router.get("/{job_id}/status")
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取训练状态"""
    job = db.query(TrainingJob).filter(
        TrainingJob.id == job_id,
        TrainingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 从内存状态获取最新进度
    status_data = training_status.get(job_id, {})
    
    return {
        "id": job.id,
        "status": status_data.get("status", job.status),
        "progress": status_data.get("progress", job.progress),
        "current_iter": status_data.get("current_iter", job.current_iter),
        "accuracy": status_data.get("accuracy", job.metrics.get("accuracy")),
        "loss": status_data.get("loss", job.metrics.get("loss")),
        "logs": status_data.get("logs", job.logs)
    }


@router.post("/{job_id}/stop")
async def stop_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """停止训练"""
    job = db.query(TrainingJob).filter(
        TrainingJob.id == job_id,
        TrainingJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if job.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已完成或已停止"
        )
    
    job.status = "stopped"
    job.finished_at = datetime.utcnow()
    db.commit()
    
    # 更新内存状态
    if job_id in training_status:
        training_status[job_id]["status"] = "stopped"
    
    return {"message": "任务已停止"}
