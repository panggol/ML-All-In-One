"""
系统监控 API 路由
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import SessionLocal, TrainingJob, User, Base, engine
from api.services import monitor_service

# ============ 历史记录表定义（提前避免引用错误） ============
from sqlalchemy import Table, Column, Float, DateTime, String, JSON, Integer, MetaData

_monitor_metadata = MetaData()

monitor_history = Table(
    "monitor_history",
    _monitor_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("metric_name", String(50), nullable=False, index=True),
    Column("metric_value", Float, nullable=False),
    Column("recorded_at", DateTime, nullable=False, index=True),
    Column("metadata", JSON, nullable=True),
)

# 确保表存在（延迟创建，避免循环导入）
try:
    monitor_history.create(engine, checkfirst=True)
except Exception:
    pass

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ Pydantic 响应模型 ============

class CPUInfo(BaseModel):
    usage_percent: float
    core_count: int
    per_core_usage: list[float]


class MemoryInfo(BaseModel):
    total_gb: float
    used_gb: float
    available_gb: float
    usage_percent: float


class GPUDevice(BaseModel):
    index: int
    name: str
    memory_total_gb: float
    memory_used_gb: float
    memory_free_gb: float
    memory_usage_percent: float
    utilization_percent: float
    temperature_celsius: Optional[float] = None


class GPUInfo(BaseModel):
    available: bool
    count: int
    devices: list[GPUDevice]
    reason: Optional[str] = None


class DiskPartition(BaseModel):
    mountpoint: str
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float


class DiskInfo(BaseModel):
    partitions: list[DiskPartition]


class NetworkInfo(BaseModel):
    bytes_sent_mb: float
    bytes_recv_mb: float
    send_rate_mbps: float
    recv_rate_mbps: float


class SystemInfo(BaseModel):
    hostname: str
    uptime_seconds: int
    os_type: str
    os_version: str


class JobStats(BaseModel):
    running: int
    pending: int
    completed: int
    failed: int


class MonitorOverviewResponse(BaseModel):
    timestamp: str
    cpu: CPUInfo
    memory: MemoryInfo
    gpu: GPUInfo
    disk: DiskInfo
    network: NetworkInfo
    system: SystemInfo
    jobs: JobStats


class HistoryDataPoint(BaseModel):
    timestamp: str
    value: float


class MonitorHistoryResponse(BaseModel):
    metric: str
    interval: str
    data: list[HistoryDataPoint]


# ============ API 端点 ============

@router.get("/overview", response_model=MonitorOverviewResponse)
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    系统监控概览
    返回所有系统指标：CPU、内存、GPU、磁盘、网络、训练任务统计
    """
    start = time.time()
    data = monitor_service.collect_overview(db)
    elapsed_ms = (time.time() - start) * 1000

    # 性能日志（P99 ≤ 500ms）
    if elapsed_ms > 500:
        import logging
        logging.getLogger(__name__).warning(f"Monitor overview took {elapsed_ms:.1f}ms (target ≤500ms)")

    return data


@router.get("/cpu", response_model=CPUInfo)
async def get_cpu(
    current_user: User = Depends(get_current_user),
):
    """CPU 详细信息"""
    return monitor_service.collect_cpu()


@router.get("/memory", response_model=MemoryInfo)
async def get_memory(
    current_user: User = Depends(get_current_user),
):
    """内存详细信息"""
    return monitor_service.collect_memory()


@router.get("/gpu", response_model=GPUInfo)
async def get_gpu(
    current_user: User = Depends(get_current_user),
):
    """GPU 详细信息（GPU 不可用时优雅降级）"""
    return monitor_service.collect_gpu()


@router.get("/disk", response_model=DiskInfo)
async def get_disk(
    current_user: User = Depends(get_current_user),
):
    """磁盘挂载点信息"""
    return monitor_service.collect_disk()


@router.get("/network", response_model=NetworkInfo)
async def get_network(
    current_user: User = Depends(get_current_user),
):
    """网络流量信息（包含实时速率）"""
    return monitor_service.collect_network()


@router.get("/jobs", response_model=JobStats)
async def get_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """训练任务统计"""
    return monitor_service.collect_jobs(db)


# ============ 历史数据 API（依赖 monitor_history，已在顶部定义） ============

METRIC_MAP: dict[str, tuple[str, Optional[str]]] = {
    "cpu": ("cpu_percent", None),
    "memory": ("memory_percent", None),
    "gpu_memory": ("gpu_memory_percent", None),
    "disk": ("disk_percent", None),
    "network_send": ("network_send_mbps", None),
    "network_recv": ("network_recv_mbps", None),
}


def _interval_to_seconds(interval: str) -> int:
    """将 '30s', '60s', '5m' 转换为秒数"""
    if interval.endswith("s"):
        return int(interval[:-1])
    elif interval.endswith("m"):
        return int(interval[:-1]) * 60
    elif interval.endswith("h"):
        return int(interval[:-1]) * 3600
    return 60


@router.get("/history", response_model=MonitorHistoryResponse)
async def get_history(
    metric: str,
    from_time: str,
    to_time: str,
    interval: str = "60s",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    查询历史监控数据
    - metric: cpu, memory, gpu_memory, disk, network_send, network_recv
    - from/to: ISO 8601 时间字符串
    - interval: 采样间隔 30s, 60s, 5m（默认 60s）
    """
    if metric not in METRIC_MAP:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unsupported metric: {metric}")

    try:
        from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
        to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    interval_sec = _interval_to_seconds(interval)

    # 检查 monitor_history 表是否存在，不存在则返回空
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1 FROM monitor_history LIMIT 1"))
    except Exception:
        return MonitorHistoryResponse(metric=metric, interval=interval, data=[])

    # 查询历史数据
    # col_name, gpu_index = METRIC_MAP[metric]  # TODO: 保留用于未来多GPU过滤

    query = db.query(monitor_history).filter(
        monitor_history.c.metric_name == metric,
        monitor_history.c.recorded_at >= from_dt,
        monitor_history.c.recorded_at <= to_dt,
    ).order_by(monitor_history.c.recorded_at.asc())

    rows = query.all()

    # 简单降采样：按 interval 间隔取样
    sampled = []
    if rows:
        sampled = [rows[0]]
        for row in rows[1:]:
            last_time = sampled[-1][2]
            if (row[2] - last_time).total_seconds() >= interval_sec:
                sampled.append(row)

    data = [
        HistoryDataPoint(timestamp=row[2].isoformat(), value=float(row[1]))
        for row in sampled
    ]

    return MonitorHistoryResponse(metric=metric, interval=interval, data=data)
