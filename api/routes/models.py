"""
模型路由
"""
import joblib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from api.database import TrainedModel, User, get_db
from api.auth import get_current_user

router = APIRouter()

# ============ Pydantic 模型 ============

class ModelResponse(BaseModel):
    id: int
    name: str
    model_type: str
    metrics: dict
    created_at: str
    
    model_config = ConfigDict(from_attributes=True)


class PredictRequest(BaseModel):
    data: List[dict]


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载模型失败: {str(e)}")
    
    # 预测
    import pandas as pd
    df = pd.DataFrame(request.data)
    predictions = clf.predict(df)
    probabilities = None
    
    if hasattr(clf, 'predict_proba'):
        try:
            probabilities = clf.predict_proba(df).tolist()
        except:
            pass
    
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
