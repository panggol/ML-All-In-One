"""
数据路由
"""
import os
import shutil
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from api.database import DataFile, User, get_db
from api.auth import get_current_user

router = APIRouter()

# 上传目录
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============ Pydantic 模型 ============

class DataFileResponse(BaseModel):
    id: int
    filename: str
    size: int
    rows: int
    columns: List[str]
    created_at: str
    
    class Config:
        from_attributes = True


class DataStats(BaseModel):
    rows: int
    columns: int
    dtypes: dict
    missing_values: dict
    numeric_summary: Optional[dict] = None


# ============ 路由 ============

@router.post("/upload", response_model=DataFileResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传数据文件"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 CSV 格式文件"
        )
    
    # 保存文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(filepath, exist_ok=True)
    full_path = os.path.join(filepath, safe_filename)
    
    with open(full_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 读取基本信息
    try:
        df = pd.read_csv(full_path)
        rows = len(df)
        columns = list(df.columns)
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
    except Exception as e:
        os.remove(full_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无法读取文件: {str(e)}"
        )
    
    # 保存到数据库
    data_file = DataFile(
        user_id=current_user.id,
        filename=file.filename,
        filepath=full_path,
        size=os.path.getsize(full_path),
        rows=rows,
        columns=columns,
        dtypes=dtypes
    )
    db.add(data_file)
    db.commit()
    db.refresh(data_file)
    
    return DataFileResponse(
        id=data_file.id,
        filename=data_file.filename,
        size=data_file.size,
        rows=data_file.rows,
        columns=data_file.columns,
        created_at=data_file.created_at.isoformat()
    )


@router.get("/list", response_model=List[DataFileResponse])
async def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户文件列表"""
    files = db.query(DataFile).filter(
        DataFile.user_id == current_user.id
    ).order_by(DataFile.created_at.desc()).all()
    
    return [
        DataFileResponse(
            id=f.id,
            filename=f.filename,
            size=f.size,
            rows=f.rows,
            columns=f.columns,
            created_at=f.created_at.isoformat()
        )
        for f in files
    ]


@router.get("/{file_id}", response_model=DataFileResponse)
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文件信息"""
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    return DataFileResponse(
        id=data_file.id,
        filename=data_file.filename,
        size=data_file.size,
        rows=data_file.rows,
        columns=data_file.columns,
        created_at=data_file.created_at.isoformat()
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除文件"""
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 删除物理文件
    if os.path.exists(data_file.filepath):
        os.remove(data_file.filepath)
    
    db.delete(data_file)
    db.commit()
    
    return {"message": "文件已删除"}


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """预览文件（前50行）"""
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    try:
        df = pd.read_csv(data_file.filepath, nrows=50)
        return {
            "columns": list(df.columns),
            "data": df.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取文件失败: {str(e)}"
        )


@router.get("/{file_id}/stats", response_model=DataStats)
async def get_stats(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文件统计信息"""
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    try:
        df = pd.read_csv(data_file.filepath)
        
        # 缺失值统计
        missing = df.isnull().sum().to_dict()
        missing = {k: int(v) for k, v in missing.items()}
        
        # 数值列统计
        numeric_cols = df.select_dtypes(include=['number']).columns
        numeric_summary = {}
        if len(numeric_cols) > 0:
            numeric_summary = df[numeric_cols].describe().to_dict()
        
        return DataStats(
            rows=len(df),
            columns=len(df.columns),
            dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
            missing_values=missing,
            numeric_summary=numeric_summary
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"统计失败: {str(e)}"
        )
