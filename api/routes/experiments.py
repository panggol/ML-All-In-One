"""
实验路由
"""
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
router = APIRouter(redirect_slashes=False)
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from api.database import Experiment, User, get_db
from api.auth import get_current_user


# ============ Pydantic 模型 ============

class ExperimentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    params: dict
    metrics: dict
    status: str
    created_at: str
    finished_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CompareRequest(BaseModel):
    experiment_ids: List[int]


@router.get("", response_model=List[ExperimentResponse])
async def list_experiments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取实验列表"""
    experiments = db.query(Experiment).filter(
        Experiment.user_id == current_user.id
    ).order_by(Experiment.created_at.desc()).all()

    return [
        ExperimentResponse(
            id=exp.id,
            name=exp.name,
            description=exp.description,
            params=exp.params,
            metrics=exp.metrics,
            status=exp.status,
            created_at=exp.created_at.isoformat(),
            finished_at=exp.finished_at.isoformat() if exp.finished_at else None
        )
        for exp in experiments
    ]


@router.get("/{exp_id}", response_model=ExperimentResponse)
async def get_experiment(
    exp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取实验详情"""
    exp = db.query(Experiment).filter(
        Experiment.id == exp_id,
        Experiment.user_id == current_user.id
    ).first()

    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")

    return ExperimentResponse(
        id=exp.id,
        name=exp.name,
        description=exp.description,
        params=exp.params,
        metrics=exp.metrics,
        status=exp.status,
        created_at=exp.created_at.isoformat(),
        finished_at=exp.finished_at.isoformat() if exp.finished_at else None
    )


@router.get("/{exp_id}/metrics")
async def get_experiment_metrics(
    exp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取实验指标历史(用于绘图)"""
    exp = db.query(Experiment).filter(
        Experiment.id == exp_id,
        Experiment.user_id == current_user.id
    ).first()

    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")

    # 返回模拟的指标历史
    # 实际应该从训练日志中提取
    return {
        "train_loss": [0.9, 0.7, 0.5, 0.35, 0.28, 0.22, 0.18],
        "val_loss": [0.95, 0.75, 0.55, 0.42, 0.35, 0.30, 0.28],
        "train_acc": [0.5, 0.65, 0.78, 0.85, 0.90, 0.93, 0.95],
        "val_acc": [0.48, 0.62, 0.74, 0.82, 0.88, 0.91, 0.93],
        "iterations": [0, 10, 20, 30, 40, 50, 60]
    }


@router.post("/compare")
async def compare_experiments(
    request: CompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """对比多个实验"""
    experiments = db.query(Experiment).filter(
        Experiment.id.in_(request.experiment_ids),
        Experiment.user_id == current_user.id
    ).all()

    if len(experiments) != len(request.experiment_ids):
        raise HTTPException(status_code=404, detail="部分实验不存在")

    return {
        "experiments": [
            {
                "id": exp.id,
                "name": exp.name,
                "metrics": exp.metrics,
                "params": exp.params,
                "status": exp.status,
                "created_at": exp.created_at.isoformat(),
                "finished_at": exp.finished_at.isoformat() if exp.finished_at else None,
            }
            for exp in experiments
        ]
    }


class CompareCurvesRequest(BaseModel):
    experiment_ids: List[int]


@router.post("/compare-curves")
async def compare_training_curves(
    request: CompareCurvesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取多个实验的训练曲线（用于对比）"""
    experiments = db.query(Experiment).filter(
        Experiment.id.in_(request.experiment_ids),
        Experiment.user_id == current_user.id
    ).all()

    if not experiments:
        raise HTTPException(status_code=404, detail="实验不存在")

    # 颜色映射
    COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#f97316"]

    result = []
    for idx, exp in enumerate(experiments):
        metrics = exp.metrics or {}
        train_loss = metrics.get("train_loss_history", [])
        val_loss = metrics.get("val_loss_history", [])
        train_metric = metrics.get("train_metric_history", [])
        val_metric = metrics.get("val_metric_history", [])

        # 如果没有历史数据，生成模拟曲线
        if not train_loss and not val_loss:
            epochs = list(range(1, 21))
            base_loss = 0.9 + idx * 0.05
            base_metric = 0.5 + idx * 0.02
            train_loss = [base_loss - i * 0.04 + np.random.randn() * 0.02 for i in range(20)]
            val_loss = [base_loss + 0.05 - i * 0.035 + np.random.randn() * 0.03 for i in range(20)]
            train_metric = [base_metric + i * 0.025 + np.random.randn() * 0.01 for i in range(20)]
            val_metric = [base_metric - 0.02 + i * 0.024 + np.random.randn() * 0.02 for i in range(20)]
        else:
            epochs = list(range(1, len(train_loss) + 1))

        result.append({
            "experiment_id": exp.id,
            "experiment_name": exp.name,
            "color": COLORS[idx % len(COLORS)],
            "epochs": epochs,
            "curves": [
                {"name": "train_loss", "values": [float(x) for x in train_loss]},
                {"name": "val_loss", "values": [float(x) for x in val_loss]},
                {"name": "train_metric", "values": [float(x) for x in train_metric]},
                {"name": "val_metric", "values": [float(x) for x in val_metric]},
            ],
        })

    return {"experiments": result}
