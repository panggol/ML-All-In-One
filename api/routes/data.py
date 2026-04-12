"""
数据路由
"""
import os
import shutil
import time
import logging
import uuid
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from starlette import status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from api.database import DataFile, User, get_db
from api.auth import get_current_user

logger = logging.getLogger("api.data")

router = APIRouter()

# 上传目录
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 文件大小限制（默认 500MB）
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_BYTES", 500 * 1024 * 1024))

# 大文件阈值（超过此大小使用 chunked / 采样策略，避免 OOM）
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB

# ============ Structured JSON Logging Helper (FR-025) ============

def structured_log(
    request_id: str,
    user_id: int,
    operation: str,
    duration_ms: float,
    status_code: int,
    extra: Optional[dict] = None
):
    """
    Emit structured JSON log entry.
    Per Constitution Principle VI — Observability.
    """
    log_entry = {
        "request_id": request_id,
        "user_id": user_id,
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "status_code": status_code,
    }
    if extra:
        log_entry["extra"] = extra
    logger.info(log_entry)


# ============ Pydantic 模型 ============

class DataFileResponse(BaseModel):
    id: int
    filename: str
    size: int
    rows: int
    columns: List[str]
    created_at: str
    
    model_config = ConfigDict(from_attributes=True)


class DataStats(BaseModel):
    rows: int
    columns: int
    dtypes: dict
    missing_values: dict
    numeric_summary: Optional[dict] = None


# ============ 前端期望的响应格式 ============

class TopValue(BaseModel):
    value: str
    count: int


class ColumnStatsDetail(BaseModel):
    """匹配前端 ColumnStats 接口 (FR-014, FR-015, FR-016)"""
    column: str
    dtype: str
    null_count: int
    unique_count: Optional[int] = None
    # 数值列统计 (FR-015)
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    Q1: Optional[float] = None
    median: Optional[float] = None
    Q3: Optional[float] = None
    # 分类列 Top 值 (FR-016)
    top_values: Optional[List[TopValue]] = None


class DataStatsResponse(BaseModel):
    """匹配前端 StatsResponse 接口"""
    total_rows: int
    total_columns: int
    column_stats: List[ColumnStatsDetail]


# ============ 路由 ============

@router.post("/upload", response_model=DataFileResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传数据文件"""
    request_id = str(uuid.uuid4())
    start = time.time()
    try:
        # P1-6: 文件类型校验（Content-Type + 扩展名双重校验）
        ALLOWED_MIME_TYPES = {"text/csv", "text/plain", "application/csv", "application/vnd.ms-excel"}
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只支持 CSV 格式文件"
            )
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {file.content_type}"
            )
        
        # 保存文件（使用 safe_filename 过滤原始文件名，防止路径遍历）
        from api.routes.preprocessing import safe_filename
        safe_original = safe_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename_str = f"{timestamp}_{safe_original}"
        filepath = os.path.join(UPLOAD_DIR, str(current_user.id))
        os.makedirs(filepath, exist_ok=True)
        full_path = os.path.join(filepath, safe_filename_str)

        # 检查文件大小（先读到临时位置再校验）
        file.file.seek(0, 2)  # seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # reset

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件超过大小限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)"
            )

        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # P2-2: CSV 文件头校验，防止上传非 CSV 文件
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()
            csv_delimiters = (',', ';', '\t', '|')
            if not any(d in first_line for d in csv_delimiters):
                os.remove(full_path)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="文件内容不是有效的 CSV 格式"
                )
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
        
        response = DataFileResponse(
            id=data_file.id,
            filename=data_file.filename,
            size=data_file.size,
            rows=data_file.rows,
            columns=data_file.columns,
            created_at=data_file.created_at.isoformat()
        )
        structured_log(request_id, current_user.id, "upload",
                        time.time() - start, 200,
                        {"filename": file.filename, "size": file_size, "rows": rows})
        return response
    except HTTPException as e:
        # P1-4: 传递真实 status_code，避免硬编码 400 掩盖错误
        structured_log(request_id, current_user.id, "upload",
                        time.time() - start, e.status_code, {})
        raise


@router.get("/list", response_model=List[DataFileResponse])
async def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户文件列表"""
    request_id = str(uuid.uuid4())
    start = time.time()
    files = db.query(DataFile).filter(
        DataFile.user_id == current_user.id
    ).order_by(DataFile.created_at.desc()).all()
    
    response = [
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
    structured_log(request_id, current_user.id, "list",
                    time.time() - start, 200,
                    {"count": len(files)})
    return response


@router.get("/{file_id}", response_model=DataFileResponse)
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文件信息"""
    request_id = str(uuid.uuid4())
    start = time.time()
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        structured_log(request_id, current_user.id, "get",
                        time.time() - start, 404, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    structured_log(request_id, current_user.id, "get",
                    time.time() - start, 200, {"file_id": file_id})
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
    request_id = str(uuid.uuid4())
    start = time.time()
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        structured_log(request_id, current_user.id, "delete",
                        time.time() - start, 404, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # P1-5: 删除物理文件，失败时记录 warning 不阻止 DB 删除
    if os.path.exists(data_file.filepath):
        try:
            os.remove(data_file.filepath)
        except OSError as e:
            logger.warning(f"Failed to remove physical file {data_file.filepath}: {e}")
            structured_log(request_id, current_user.id, "delete",
                            time.time() - start, 200,
                            {"file_id": file_id, "os_remove_warning": str(e)})
    
    db.delete(data_file)
    db.commit()
    
    structured_log(request_id, current_user.id, "delete",
                    time.time() - start, 200, {"file_id": file_id})
    return {"message": "文件已删除"}


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    预览文件（前10行）
    FR-010: 返回格式匹配前端 PreviewResponse: { rows, columns, total_rows }
    """
    request_id = str(uuid.uuid4())
    start = time.time()
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        structured_log(request_id, current_user.id, "preview",
                        time.time() - start, 404, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    try:
        # P0-1: 使用数据库中的 rows 作为 total_rows（避免 nrows=10 导致错误）
        df = pd.read_csv(data_file.filepath, nrows=10)
        rows = df.values.tolist()
        response = {
            "columns": list(df.columns),
            "rows": rows,
            "total_rows": data_file.rows,  # 使用 DB 中存储的真实行数
        }
        structured_log(request_id, current_user.id, "preview",
                        time.time() - start, 200,
                        {"file_id": file_id, "preview_rows": len(rows)})
        return response
    except Exception as e:
        structured_log(request_id, current_user.id, "preview",
                        time.time() - start, 500, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取文件失败: {str(e)}"
        )


@router.get("/{file_id}/export")
async def export_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    导出完整 CSV 文件（支持完整数据集下载）
    """
    request_id = str(uuid.uuid4())
    start = time.time()
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()

    if not data_file:
        structured_log(request_id, current_user.id, "export",
                        time.time() - start, 404, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    # 验证文件存在
    if not os.path.exists(data_file.filepath):
        structured_log(request_id, current_user.id, "export",
                        time.time() - start, 404, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    # 文件大小检查（防止 DoS）
    if data_file.size > MAX_FILE_SIZE:
        structured_log(request_id, current_user.id, "export",
                        time.time() - start, 413, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过大小限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)"
        )

    structured_log(request_id, current_user.id, "export",
                    time.time() - start, 200,
                    {"file_id": file_id, "filename": data_file.filename})
    # 返回完整文件作为下载
    return FileResponse(
        path=data_file.filepath,
        filename=data_file.filename,
        media_type="text/csv"
    )


@router.get("/{file_id}/stats", response_model=DataStatsResponse)
async def get_stats(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取文件统计信息
    返回格式匹配前端 StatsResponse: { total_rows, total_columns, column_stats }
    """
    request_id = str(uuid.uuid4())
    start = time.time()
    data_file = db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == current_user.id
    ).first()
    
    if not data_file:
        structured_log(request_id, current_user.id, "stats",
                        time.time() - start, 404, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    try:
        # P0-2: 对大文件使用 chunked 读取（避免 OOM）
        if data_file.size > LARGE_FILE_THRESHOLD:
            # chunked 计数总行数
            total_rows = 0
            for chunk in pd.read_csv(data_file.filepath, chunksize=10000):
                total_rows += len(chunk)
            # 采样 10000 行计算统计量
            sample = pd.read_csv(data_file.filepath, nrows=10000)
            df = sample
        else:
            total_rows = data_file.rows
            df = pd.read_csv(data_file.filepath)

        column_stats = []
        for col in df.columns:
            col_dtype = str(df[col].dtype)
            null_count = int(df[col].isnull().sum())
            unique_count = int(df[col].nunique())

            stat: dict = {
                "column": col,
                "dtype": col_dtype,
                "null_count": null_count,
                "unique_count": unique_count,
            }

            if pd.api.types.is_numeric_dtype(df[col]):
                col_data = df[col]
                has_data = not col_data.isnull().all()
                stat["min"] = float(col_data.min()) if has_data else None
                stat["max"] = float(col_data.max()) if has_data else None
                stat["mean"] = float(col_data.mean()) if has_data else None
                stat["std"] = float(col_data.std()) if has_data else None
                if has_data:
                    stat["Q1"] = float(col_data.quantile(0.25))
                    stat["median"] = float(col_data.median())
                    stat["Q3"] = float(col_data.quantile(0.75))
                else:
                    stat["Q1"] = None
                    stat["median"] = None
                    stat["Q3"] = None
            else:
                value_counts = df[col].value_counts(dropna=False).head(5)
                stat["top_values"] = [
                    {"value": str(v), "count": int(c)}
                    for v, c in value_counts.items()
                    if pd.notna(v)
                ]

            column_stats.append(stat)

        response = DataStatsResponse(
            total_rows=total_rows,
            total_columns=len(df.columns),
            column_stats=column_stats,
        )
        structured_log(request_id, current_user.id, "stats",
                        time.time() - start, 200,
                        {"file_id": file_id, "total_rows": total_rows, "total_columns": len(df.columns)})
        return response
    except Exception as e:
        structured_log(request_id, current_user.id, "stats",
                        time.time() - start, 500, {"file_id": file_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"统计失败: {str(e)}"
        )


# ============ 特征选择 API ============

class FeatureSelectionRequest(BaseModel):
    target_column: str
    method: str = "tree_importance"  # variance_threshold | correlation | tree_importance
    threshold: Optional[float] = None  # 可选的阈值参数


class FeatureSelectionResponse(BaseModel):
    selected_features: List[str]
    all_features: List[str]
    method: str
    removed_features: List[str]
    reason: Optional[dict] = None


@router.post("/{file_id}/feature-selection", response_model=FeatureSelectionResponse)
async def feature_selection(
    file_id: int,
    request: FeatureSelectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    自动特征选择

    支持三种方法:
    - variance_threshold: 基于方差阈值移除低方差特征
    - correlation: 移除与目标变量相关性低的特征
    - tree_importance: 使用随机森林特征重要性选择（默认）
    """
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.feature_selection import VarianceThreshold
    from sklearn.preprocessing import LabelEncoder

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
        # P0-3: 对大文件使用采样策略（避免 OOM）
        MAX_SAMPLE_ROWS = 50000  # 采样上限
        if data_file.size > LARGE_FILE_THRESHOLD:
            df = pd.read_csv(data_file.filepath, nrows=MAX_SAMPLE_ROWS)
            sample_note = {
                "note": f"文件较大，采样 {MAX_SAMPLE_ROWS} 行进行分析",
                "sampled_rows": len(df),
                "total_rows_in_db": data_file.rows
            }
        else:
            df = pd.read_csv(data_file.filepath)
            sample_note = None

        # 验证目标列
        if request.target_column not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"目标列 '{request.target_column}' 不存在"
            )

        # 准备特征和目标
        feature_cols = [c for c in df.columns if c != request.target_column]
        X = df[feature_cols]
        y = df[request.target_column]

        # 处理缺失值（用中位数/众数填充）
        for col in X.columns:
            if X[col].dtype in ['float64', 'int64']:
                X[col] = X[col].fillna(X[col].median())
            else:
                X[col] = X[col].fillna(X[col].mode().iloc[0] if len(X[col].mode()) > 0 else 'missing')

        # 对目标变量编码
        if y.dtype == 'object':
            le = LabelEncoder()
            y = le.fit_transform(y.astype(str))

        selected_features = []
        removed_features = []
        reason = {}

        if request.method == "variance_threshold":
            # 方法1: 方差阈值
            numeric_X = X.select_dtypes(include=['number'])
            if numeric_X.shape[1] == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="方差阈值方法需要至少一个数值特征"
                )

            threshold = request.threshold if request.threshold else 0.0
            selector = VarianceThreshold(threshold=threshold)
            selector.fit(numeric_X)

            selected_features = list(numeric_X.columns[selector.get_support()])
            removed_features = list(numeric_X.columns[~selector.get_support()])

            # 保留非数值列（简单处理：保留）
            non_numeric_cols = [c for c in feature_cols if c not in numeric_X.columns]
            selected_features.extend(non_numeric_cols)
            removed_features = [c for c in removed_features if c in feature_cols]

            reason = {"threshold": threshold, "method": "移除方差低于阈值的特征"}

        elif request.method == "correlation":
            # 方法2: 相关系数（与目标变量的相关性）
            numeric_X = X.select_dtypes(include=['number'])
            if numeric_X.shape[1] == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="相关性方法需要至少一个数值特征"
                )

            # 计算与目标的相关性
            threshold = abs(request.threshold) if request.threshold else 0.05

            selected_features = []
            removed_features = []

            for col in numeric_X.columns:
                try:
                    corr = np.corrcoef(numeric_X[col].values, y)[0, 1]
                    if not np.isnan(corr) and abs(corr) >= threshold:
                        selected_features.append(col)
                    else:
                        removed_features.append(col)
                except Exception:
                    removed_features.append(col)

            reason = {"threshold": threshold, "method": "保留与目标相关性 >= 阈值的特征"}

        elif request.method == "tree_importance":
            # 方法3: 树模型特征重要性（默认）
            numeric_X = X.select_dtypes(include=['number'])
            if numeric_X.shape[1] == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="树重要性方法需要至少一个数值特征"
                )

            # 判断是分类还是回归
            is_classification = len(np.unique(y)) <= 20 and len(np.unique(y)) < len(y) / 2

            if is_classification:
                model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            else:
                model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)

            model.fit(numeric_X, y)
            importances = model.feature_importances_

            # 选择重要性 > 中位数的特征，或 top N
            median_imp = np.median(importances)
            threshold_val = max(median_imp, request.threshold if request.threshold else 0)

            selected_indices = importances > threshold_val
            selected_features = list(numeric_X.columns[selected_indices])
            removed_features = list(numeric_X.columns[~selected_indices])

            reason = {
                "threshold": float(threshold_val),
                "importances": dict(zip(numeric_X.columns.tolist(), importances.tolist())),
                "method": "保留重要性 > 阈值的特征（默认阈值 = max(中位数, 指定阈值))"
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知方法: {request.method}，支持: variance_threshold, correlation, tree_importance"
            )

        # 如果没有选中任何特征，至少返回前几个
        if len(selected_features) == 0:
            selected_features = feature_cols[:max(1, min(5, len(feature_cols)))]
            removed_features = [f for f in feature_cols if f not in selected_features]
            reason["fallback"] = "未选中任何特征，使用默认策略"

        if sample_note:
            reason["sample_note"] = sample_note

        return FeatureSelectionResponse(
            selected_features=selected_features,
            all_features=feature_cols,
            method=request.method,
            removed_features=removed_features,
            reason=reason
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"特征选择失败: {str(e)}"
        )
