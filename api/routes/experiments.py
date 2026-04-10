"""
实验路由
"""
from fastapi import APIRouter, Depends, HTTPException
router = APIRouter(redirect_slashes=False)
from sqlalchemy.orm import Session
from pydantic import BaseModel
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
    
    class Config:
        from_attributes = True


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
    """获取实验指标历史（用于绘图）"""
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
                "status": exp.status
            }
            for exp in experiments
        ]
    }
