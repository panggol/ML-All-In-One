"""
模型路由
"""
import joblib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

from api.database import TrainedModel, User, get_db
from api.auth import get_current_user

router = APIRouter()

# ============ Pydantic 模型 ============

def _extract_task_type(model: TrainedModel) -> Optional[str]:
    # task_type 可能存储在 config JSON 中
    cfg = model.config if hasattr(model, 'config') else {}
    return cfg.get("task_type") if isinstance(cfg, dict) else None


class ModelResponse(BaseModel):
    id: int
    name: str
    model_type: str
    task_type: Optional[str] = None
    metrics: dict
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class PredictRequest(BaseModel):
    data: List[dict] = Field(min_length=1, description="输入数据，必须是非空数组")


@router.get("/", response_model=List[ModelResponse])
async def list_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型列表"""
    models = db.query(TrainedModel).filter(
        TrainedModel.user_id == current_user.id
    ).order_by(TrainedModel.created_at.desc()).all()
    
    return [
        ModelResponse(
            id=model.id,
            name=model.name,
            model_type=model.model_type,
            task_type=_extract_task_type(model),
            metrics=model.metrics,
            created_at=model.created_at.isoformat()
        )
        for model in models
    ]


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型详情"""
    model = db.query(TrainedModel).filter(
        TrainedModel.id == model_id,
        TrainedModel.user_id == current_user.id
    ).first()
    
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    return ModelResponse(
        id=model.id,
        name=model.name,
        model_type=model.model_type,
        task_type=_extract_task_type(model),
        metrics=model.metrics,
        created_at=model.created_at.isoformat()
    )


@router.post("/{model_id}/predict")
async def predict(
    model_id: int,
    request: PredictRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量预测"""
    model = db.query(TrainedModel).filter(
        TrainedModel.id == model_id,
        TrainedModel.user_id == current_user.id
    ).first()
    
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    # 加载模型
    try:
        clf = joblib.load(model.model_path)
    except Exception:
        raise HTTPException(status_code=500, detail="模型加载失败，请联系管理员")
    
    # 预测
    import pandas as pd
    df = pd.DataFrame(request.data)
    predictions = clf.predict(df)
    probabilities = None
    
    if hasattr(clf, "predict_proba"):
        try:
            probabilities = clf.predict_proba(df).tolist()
        except Exception:
            # 某些模型 predict_proba 可调用但实际运行时出错，静默降级
            probabilities = None
    
    return {
        "predictions": predictions.tolist(),
        "probabilities": probabilities
    }


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除模型"""
    model = db.query(TrainedModel).filter(
        TrainedModel.id == model_id,
        TrainedModel.user_id == current_user.id
    ).first()
    
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    import os
    if os.path.exists(model.model_path):
        os.remove(model.model_path)
    
    db.delete(model)
    db.commit()
    
    return {"message": "模型已删除"}
