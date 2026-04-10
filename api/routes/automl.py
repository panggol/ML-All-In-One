"""
AutoML 路由 - 超参数自动搜索 API
"""
import os
import sys
import threading
import uuid
import time
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))

from api.database import User, SessionLocal, get_db
from api.auth import get_current_user

router = APIRouter()

# ─── Pydantic 模型 ────────────────────────────────────────────────────────────


class SearchSpaceItem(BaseModel):
    name: str
    type: str = Field(description="choice | int | float")
    values: Optional[list] = None  # choice 类型
    low: Optional[float] = None  # int/float 类型下限
    high: Optional[float] = None  # int/float 类型上限
    step: Optional[int] = 1  # int 类型步长
    log: Optional[bool] = False  # float 类型是否对数采样


class AutoMLStartRequest(BaseModel):
    data_file_id: int
    target_column: str
    task_type: str = Field(description="classification | regression")
    strategy: str = Field(default="random", description="grid | random | bayesian")
    search_space: list[SearchSpaceItem] = []
    n_trials: int = Field(default=10, ge=1, le=100)
    timeout: int = Field(default=300, ge=10, description="总超时秒数")


class AutoMLJobResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    current_trial: int
    n_trials: int
    logs: str


class AutoMLReportResponse(BaseModel):
    job_id: str
    status: str
    best_params: dict
    best_val_score: float
    best_train_score: float
    strategy: str
    n_trials: int
    total_time: float
    top_models: list[dict]
    report_md: str


# ─── Job 管理器 ───────────────────────────────────────────────────────────────


class AutoMLJobManager:
    """管理所有 AutoML 任务状态"""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}

    def create(self) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "status": "pending",
                "progress": 0,
                "current_trial": 0,
                "n_trials": 0,
                "logs": "",
                "best_params": {},
                "best_val_score": 0.0,
                "best_train_score": 0.0,
                "strategy": "",
                "total_time": 0.0,
                "top_models": [],
                "report_md": "",
                "stop_event": threading.Event(),
            }
        return job_id

    def update(self, job_id: str, **kwargs):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)

    def get_status(self, job_id: str) -> dict:
        with self._lock:
            return dict(self._jobs.get(job_id, {}))

    def is_stopped(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.get(job_id, {}).get("stop_event", threading.Event()).is_set()

    def request_stop(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job["stop_event"].set()

    def delete(self, job_id: str):
        with self._lock:
            self._jobs.pop(job_id, None)


job_mgr = AutoMLJobManager()


# ─── 后台训练函数 ─────────────────────────────────────────────────────────────


def _run_automl(
    job_id: str,
    user_id: int,
    data_file_id: int,
    target_column: str,
    task_type: str,
    strategy: str,
    search_space_raw: list[dict],
    n_trials: int,
    timeout_seconds: int,
):
    """在后台线程中运行 AutoML 搜索"""
    from mlkit.automl import AutoMLEngine, SearchSpace, AutoMLResult

    db = SessionLocal()
    try:
        # 1. 加载数据
        from api.database import DataFile

        data_file = db.query(DataFile).filter(
            DataFile.id == data_file_id,
            DataFile.user_id == user_id,
        ).first()

        if not data_file:
            job_mgr.update(job_id, status="failed", logs=f"数据文件不存在: id={data_file_id}\n")
            return

        df = pd.read_csv(data_file.filepath)

        if target_column not in df.columns:
            job_mgr.update(job_id, status="failed", logs=f"目标列 '{target_column}' 不存在\n")
            return

        # 2. 准备特征和标签
        from sklearn.model_selection import train_test_split

        feature_cols = [c for c in df.columns if c != target_column]
        X = df[feature_cols].values
        y = df[target_column].values

        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

        job_mgr.update(
            job_id,
            status="running",
            n_trials=n_trials,
            logs=f"数据加载完成: {len(df)} 行, 特征 {len(feature_cols)} 列\n"
            f"训练集: {len(X_train)} | 验证集: {len(X_val)}\n"
            f"开始 AutoML 搜索 (strategy={strategy}, trials={n_trials})...\n",
        )

        # 3. 构建搜索空间
        if search_space_raw:
            space = SearchSpace()
            for item in search_space_raw:
                if item["type"] == "choice":
                    space.add(item["name"], item.get("values", []))
                elif item["type"] == "int":
                    space.add_int(item["name"], int(item["low"]), int(item["high"]), item.get("step", 1))
                elif item["type"] == "float":
                    space.add_float(item["name"], float(item["low"]), float(item["high"]), item.get("log", False))
        else:
            space = None  # 使用默认搜索空间

        # 4. 运行 AutoML
        engine = AutoMLEngine(
            task_type=task_type,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            strategy=strategy,
            n_trials=n_trials,
            search_space=space,
            timeout_per_trial=max(timeout_seconds / n_trials, 10.0),
            random_state=42,
        )

        # 进度回调
        def _progress_callback(trial_id: int, val_score: float, best_score: float):
            if job_mgr.is_stopped(job_id):
                raise KeyboardInterrupt("stop requested")
            progress = int((trial_id + 1) / n_trials * 100)
            logs = f"  Trial {trial_id + 1}/{n_trials} | Val: {val_score:.4f} | Best: {best_score:.4f}\n"
            job_mgr.update(job_id, progress=progress, current_trial=trial_id + 1, logs=logs)

        # patch _evaluate for progress
        original_evaluate = engine._evaluate

        def _evaluate_with_progress(params: dict, trial_id: int):
            result = original_evaluate(params, trial_id)
            best = max(t.val_score for t in engine._trials) if engine._trials else 0.0
            _progress_callback(trial_id, result.val_score if hasattr(result, "val_score") else 0.0, best)
            return result

        engine._evaluate = _evaluate_with_progress

        result: AutoMLResult = engine.run()

        if job_mgr.is_stopped(job_id):
            job_mgr.update(job_id, status="stopped", logs="搜索已停止\n")
            return

        # 5. 生成报告
        report_md = engine.generate_report()
        top_models = []
        for i, t in enumerate(engine.get_top_models(3), 1):
            top_models.append({
                "rank": i,
                "model_type": t.params.get("model_type", "?"),
                "val_score": round(t.val_score, 4),
                "train_score": round(t.train_score, 4),
                "train_time": round(t.train_time, 2),
                "params": {k: round(v, 4) if isinstance(v, float) else v for k, v in t.params.items()},
            })

        job_mgr.update(
            job_id,
            status="completed",
            progress=100,
            current_trial=n_trials,
            best_params=result.best_params,
            best_val_score=round(result.best_val_score, 4),
            best_train_score=round(result.best_train_score, 4),
            strategy=strategy,
            n_trials=len(result.trials),
            total_time=round(result.total_time, 2),
            top_models=top_models,
            report_md=report_md,
            logs=f"\n✅ 搜索完成！最佳验证分数: {result.best_val_score:.4f}\n"
            f"最佳参数: {result.best_params}\n",
        )

    except KeyboardInterrupt:
        job_mgr.update(job_id, status="stopped", logs="搜索已停止\n")
    except Exception as e:
        job_mgr.update(
            job_id,
            status="failed",
            logs=f"搜索失败: {str(e)}\n",
        )
        import traceback

        traceback.print_exc()
    finally:
        db.close()


# ─── API 路由 ─────────────────────────────────────────────────────────────────


@router.post("/start", response_model=AutoMLJobResponse)
async def start_automl(
    request: AutoMLStartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建 AutoML 搜索任务，立即返回 job_id"""
    # 验证数据文件
    from api.database import DataFile

    data_file = db.query(DataFile).filter(
        DataFile.id == request.data_file_id,
        DataFile.user_id == current_user.id,
    ).first()

    if not data_file:
        raise HTTPException(status_code=404, detail="数据文件不存在")

    if request.target_column not in data_file.columns:
        raise HTTPException(status_code=400, detail=f"目标列 '{request.target_column}' 不在数据文件中")

    if request.task_type not in ("classification", "regression"):
        raise HTTPException(status_code=400, detail="task_type 必须是 classification 或 regression")

    if request.strategy not in ("grid", "random", "bayesian"):
        raise HTTPException(status_code=400, detail="strategy 必须是 grid / random / bayesian")

    # 创建 job
    job_id = job_mgr.create()
    job_mgr.update(job_id, user_id=current_user.id, n_trials=request.n_trials, strategy=request.strategy)

    # 启动后台搜索
    background_tasks.add_task(
        _run_automl,
        job_id,
        current_user.id,
        request.data_file_id,
        request.target_column,
        request.task_type,
        request.strategy,
        [item.model_dump() for item in request.search_space],
        request.n_trials,
        request.timeout,
    )

    status_data = job_mgr.get_status(job_id)
    return AutoMLJobResponse(
        job_id=job_id,
        status=status_data.get("status", "pending"),
        progress=status_data.get("progress", 0),
        current_trial=status_data.get("current_trial", 0),
        n_trials=request.n_trials,
        logs=status_data.get("logs", ""),
    )


@router.get("/status/{job_id}", response_model=AutoMLJobResponse)
async def get_automl_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """查询 AutoML 任务状态"""
    status_data = job_mgr.get_status(job_id)

    if not status_data:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if status_data.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")

    return AutoMLJobResponse(
        job_id=job_id,
        status=status_data.get("status", "unknown"),
        progress=status_data.get("progress", 0),
        current_trial=status_data.get("current_trial", 0),
        n_trials=status_data.get("n_trials", 0),
        logs=status_data.get("logs", ""),
    )


@router.get("/report/{job_id}", response_model=AutoMLReportResponse)
async def get_automl_report(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取 AutoML 搜索报告"""
    status_data = job_mgr.get_status(job_id)

    if not status_data:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if status_data.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")

    return AutoMLReportResponse(
        job_id=job_id,
        status=status_data.get("status", "unknown"),
        best_params=status_data.get("best_params", {}),
        best_val_score=status_data.get("best_val_score", 0.0),
        best_train_score=status_data.get("best_train_score", 0.0),
        strategy=status_data.get("strategy", ""),
        n_trials=status_data.get("n_trials", 0),
        total_time=status_data.get("total_time", 0.0),
        top_models=status_data.get("top_models", []),
        report_md=status_data.get("report_md", ""),
    )


@router.post("/stop/{job_id}")
async def stop_automl(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """停止 AutoML 搜索"""
    status_data = job_mgr.get_status(job_id)

    if not status_data:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    if status_data.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")

    if status_data.get("status") not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="任务已完成或已停止")

    job_mgr.request_stop(job_id)
    return {"message": "已发送停止信号"}
