"""
任务执行器（Runner）
根据 job_type 分发到对应的 mlkit 模块执行任务（preprocessing / training / pipeline）。
处理重试逻辑，失败时调用告警模块。
"""
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone as dt_tz
from typing import Optional, TYPE_CHECKING

import httpx
from sqlalchemy.orm import Session

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from src.mlkit.scheduler.models import Job, Execution, ExecutionStatus, TriggerType, JobStatus

logger = logging.getLogger("platform.scheduler")

# 环境变量
MAX_HISTORY = int(os.getenv("MLKIT_SCHEDULER_MAX_HISTORY", "100"))
RETRY_COUNT = int(os.getenv("MLKIT_SCHEDULER_RETRY_COUNT", "2"))
RETRY_DELAY = int(os.getenv("MLKIT_SCHEDULER_RETRY_DELAY", "30"))
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# 线程安全的重入保护（同一 Job 同时只跑一个实例）
_running_jobs: dict[str, threading.Event] = {}
_running_lock = threading.Lock()


def _is_job_running(job_id: str) -> bool:
    """检查某个 Job 当前是否正在运行"""
    with _running_lock:
        return job_id in _running_jobs


def _mark_job_running(job_id: str):
    """标记 Job 为运行中"""
    with _running_lock:
        _running_jobs[job_id] = threading.Event()


def _mark_job_done(job_id: str):
    """标记 Job 为已完成"""
    with _running_lock:
        _running_jobs.pop(job_id, None)


def _cleanup_old_executions(db: Session, job_id: str):
    """
    清理超过 MAX_HISTORY 条的执行历史（最老优先删除）。
    在写入新记录后异步调用，不阻塞主流程。
    """
    try:
        # 统计当前历史条数
        count = db.query(Execution).filter(Execution.job_id == job_id).count()
        if count <= MAX_HISTORY:
            return

        # 删除最老的记录
        over_count = count - MAX_HISTORY
        oldest_records = (
            db.query(Execution)
            .filter(Execution.job_id == job_id)
            .order_by(Execution.started_at.asc())
            .limit(over_count)
            .all()
        )
        for rec in oldest_records:
            db.delete(rec)
        db.commit()
        logger.info(f"[Runner] 清理 Job {job_id} 的 {over_count} 条旧执行记录")
    except Exception as e:
        logger.error(f"[Runner] 清理执行历史失败，job_id={job_id}: {e}")


async def _execute_preprocessing(job: Job, execution: Execution, db: Session, token: str) -> bool:
    """
    执行预处理任务。
    通过内部 HTTP 调用 preprocessing API。
    """
    from src.mlkit.scheduler.alerter import send_feishu_alert

    try:
        execution.status = ExecutionStatus.RUNNING
        db.commit()

        params = json.loads(job.params or "{}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/preprocessing/tasks",
                json={
                    "data_file_id": job.target_id,
                    "pipeline": params.get("pipeline", "standard"),
                    "params": params.get("params", {}),
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code in (200, 201):
                execution.status = ExecutionStatus.SUCCESS
                execution.finished_at = datetime.now(dt_tz.utc)
                execution.duration_seconds = int(
                    (execution.finished_at - execution.started_at).total_seconds()
                )
                db.commit()
                logger.info(f"[Runner] Preprocessing 任务执行成功，job={job.id}, execution={execution.id}")
                return True
            else:
                error_msg = f"预处理 API 返回错误: {response.status_code} - {response.text[:200]}"
                execution.status = ExecutionStatus.FAILED
                execution.error_message = error_msg
                execution.finished_at = datetime.now(dt_tz.utc)
                execution.duration_seconds = int(
                    (execution.finished_at - execution.started_at).total_seconds()
                )
                db.commit()
                await send_feishu_alert(job, execution, error_msg)
                return False

    except httpx.RequestError as e:
        error_msg = f"预处理任务执行失败（网络错误）: {str(e)}"
        execution.status = ExecutionStatus.FAILED
        execution.error_message = error_msg
        execution.finished_at = datetime.now(dt_tz.utc)
        execution.duration_seconds = int(
            (execution.finished_at - execution.started_at).total_seconds()
        )
        db.commit()
        await send_feishu_alert(job, execution, error_msg)
        return False
    except Exception as e:
        error_msg = f"预处理任务执行失败: {str(e)}"
        execution.status = ExecutionStatus.FAILED
        execution.error_message = error_msg
        execution.finished_at = datetime.now(dt_tz.utc)
        execution.duration_seconds = int(
            (execution.finished_at - execution.started_at).total_seconds()
        )
        db.commit()
        await send_feishu_alert(job, execution, error_msg)
        return False


async def _execute_training(job: Job, execution: Execution, db: Session, token: str) -> bool:
    """
    执行训练任务。
    通过内部 HTTP 调用 train API。
    """
    from src.mlkit.scheduler.alerter import send_feishu_alert

    try:
        execution.status = ExecutionStatus.RUNNING
        db.commit()

        params = json.loads(job.params or "{}")

        async with httpx.AsyncClient(timeout=3600.0) as client:  # 训练最多 1 小时超时
            response = await client.post(
                f"{API_BASE_URL}/api/train",
                json={
                    "data_file_id": job.target_id,
                    "target_column": params.get("target_column", "target"),
                    "task_type": params.get("task_type", "classification"),
                    "model_type": params.get("model_type", "sklearn"),
                    "model_name": params.get("model_name", "RandomForestClassifier"),
                    "feature_columns": params.get("feature_columns", []),
                    "params": params.get("model_params", {}),
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code in (200, 201):
                execution.status = ExecutionStatus.SUCCESS
                execution.finished_at = datetime.now(dt_tz.utc)
                execution.duration_seconds = int(
                    (execution.finished_at - execution.started_at).total_seconds()
                )
                db.commit()
                logger.info(f"[Runner] Training 任务执行成功，job={job.id}, execution={execution.id}")
                return True
            else:
                error_msg = f"训练 API 返回错误: {response.status_code} - {response.text[:200]}"
                execution.status = ExecutionStatus.FAILED
                execution.error_message = error_msg
                execution.finished_at = datetime.now(dt_tz.utc)
                execution.duration_seconds = int(
                    (execution.finished_at - execution.started_at).total_seconds()
                )
                db.commit()
                await send_feishu_alert(job, execution, error_msg)
                return False

    except httpx.RequestError as e:
        error_msg = f"训练任务执行失败（网络错误）: {str(e)}"
        execution.status = ExecutionStatus.FAILED
        execution.error_message = error_msg
        execution.finished_at = datetime.now(dt_tz.utc)
        execution.duration_seconds = int(
            (execution.finished_at - execution.started_at).total_seconds()
        )
        db.commit()
        await send_feishu_alert(job, execution, error_msg)
        return False
    except Exception as e:
        error_msg = f"训练任务执行失败: {str(e)}"
        execution.status = ExecutionStatus.FAILED
        execution.error_message = error_msg
        execution.finished_at = datetime.now(dt_tz.utc)
        execution.duration_seconds = int(
            (execution.finished_at - execution.started_at).total_seconds()
        )
        db.commit()
        await send_feishu_alert(job, execution, error_msg)
        return False


async def _execute_pipeline(job: Job, execution: Execution, db: Session, token: str) -> bool:
    """
    执行管道任务（预处理 + 训练组合）。
    目前简化为先预处理再训练。
    """
    from src.mlkit.scheduler.alerter import send_feishu_alert

    try:
        execution.status = ExecutionStatus.RUNNING
        db.commit()

        params = json.loads(job.params or "{}")
        pipeline_config = params.get("pipeline_config", {})

        # 模拟管道执行（实际可扩展为多步流水线）
        async with httpx.AsyncClient(timeout=3600.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/preprocessing/tasks",
                json=pipeline_config.get("preprocessing", {}),
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code not in (200, 201):
                error_msg = f"管道预处理步骤失败: {response.status_code}"
                execution.status = ExecutionStatus.FAILED
                execution.error_message = error_msg
                execution.finished_at = datetime.now(dt_tz.utc)
                execution.duration_seconds = int(
                    (execution.finished_at - execution.started_at).total_seconds()
                )
                db.commit()
                await send_feishu_alert(job, execution, error_msg)
                return False

        execution.status = ExecutionStatus.SUCCESS
        execution.finished_at = datetime.now(dt_tz.utc)
        execution.duration_seconds = int(
            (execution.finished_at - execution.started_at).total_seconds()
        )
        db.commit()
        logger.info(f"[Runner] Pipeline 任务执行成功，job={job.id}")
        return True

    except Exception as e:
        error_msg = f"管道任务执行失败: {str(e)}"
        execution.status = ExecutionStatus.FAILED
        execution.error_message = error_msg
        execution.finished_at = datetime.now(dt_tz.utc)
        execution.duration_seconds = int(
            (execution.finished_at - execution.started_at).total_seconds()
        )
        db.commit()
        await send_feishu_alert(job, execution, error_msg)
        return False


async def run_job(
    job_id: str,
    db_session_factory,  # callable -> Session（避免跨线程 session 问题）
    triggered_by: TriggerType = TriggerType.SCHEDULED,
    token: Optional[str] = None,
):
    """
    执行定时任务的主入口（统一分发到各 Job Type 处理器）。

    Args:
        job_id: Job UUID
        db_session_factory: 数据库会话工厂（每次调用创建新 session）
        triggered_by: 触发方式（SCHEDULED / MANUAL）
        token: 当前用户的 Bearer Token（用于内部 API 调用）
    """
    from src.mlkit.scheduler.alerter import send_feishu_alert

    db = db_session_factory()
    try:
        # 加载 Job
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[Runner] Job 不存在，job_id={job_id}")
            return

        # === 并发控制：skip if running ===
        if _is_job_running(job_id):
            logger.warning(f"[Runner] Job {job_id} 正在执行中，跳过本次触发")
            return

        _mark_job_running(job_id)

        # 创建执行记录
        execution = Execution(
            job_id=job_id,
            status=ExecutionStatus.RUNNING,
            triggered_by=triggered_by,
            started_at=datetime.now(dt_tz.utc),
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        execution_id = execution.id

        # 更新 Job 状态为 active（如果之前是 failed）
        if job.status == JobStatus.FAILED:
            job.status = JobStatus.ACTIVE
            db.commit()

        # 执行任务
        job_type = job.job_type.value if hasattr(job.job_type, 'value') else str(job.job_type)
        success = False

        if job_type == "preprocessing":
            success = await _execute_preprocessing(job, execution, db, token or "")
        elif job_type == "training":
            success = await _execute_training(job, execution, db, token or "")
        elif job_type == "pipeline":
            success = await _execute_pipeline(job, execution, db, token or "")
        else:
            error_msg = f"未知的任务类型: {job_type}"
            execution.status = ExecutionStatus.FAILED
            execution.error_message = error_msg
            execution.finished_at = datetime.now(dt_tz.utc)
            db.commit()
            await send_feishu_alert(job, execution, error_msg)
            job.status = JobStatus.FAILED
            db.commit()

        # 失败重试（最多 RETRY_COUNT 次，间隔 RETRY_DELAY 秒）
        if not success and job.retry_count > 0:
            for retry_index in range(1, job.retry_count + 1):
                # 等间隔
                logger.info(f"[Runner] Job {job_id} 等待 {RETRY_DELAY}s 后进行第 {retry_index} 次重试")
                await _async_sleep(RETRY_DELAY)

                # 再次检查并发锁
                if _is_job_running(job_id):
                    logger.warning(f"[Runner] Job {job_id} 重试时发现其他实例在运行，跳过")
                    break

                # 创建重试记录
                retry_exec = Execution(
                    job_id=job_id,
                    status=ExecutionStatus.RUNNING,
                    triggered_by=triggered_by,
                    started_at=datetime.now(dt_tz.utc),
                    retry_index=retry_index,
                )
                db.add(retry_exec)
                db.commit()
                db.refresh(retry_exec)

                # 再次执行
                if job_type == "preprocessing":
                    retry_success = await _execute_preprocessing(job, retry_exec, db, token or "")
                elif job_type == "training":
                    retry_success = await _execute_training(job, retry_exec, db, token or "")
                elif job_type == "pipeline":
                    retry_success = await _execute_pipeline(job, retry_exec, db, token or "")
                else:
                    retry_success = False

                if retry_success:
                    success = True
                    break

        # 最终状态更新
        job.updated_at = datetime.now(dt_tz.utc)
        if not success:
            job.status = JobStatus.FAILED
        db.commit()

        # 清理超量历史（异步，不阻塞）
        threading.Thread(target=_cleanup_old_executions, args=(db_session_factory(), job_id), daemon=True).start()

    except Exception as e:
        logger.exception(f"[Runner] 任务执行异常，job_id={job_id}: {e}")
    finally:
        _mark_job_done(job_id)
        db.close()


async def _async_sleep(seconds: int):
    """异步睡眠（用于重试间隔）"""
    import asyncio
    await asyncio.sleep(seconds)
