"""
系统监控数据采集服务
使用 psutil 采集 CPU/内存/磁盘/网络指标，pynvml 采集 GPU 指标
"""
import logging
import os
import platform
import time
from typing import Any, Dict, List, Optional

import psutil
from sqlalchemy.orm import Session

from api.database import TrainingJob

logger = logging.getLogger(__name__)

# ============ Docker / cgroup v2 检测（全局一次） ============

def _detect_container_env() -> tuple[bool, bool]:
    """
    检测运行环境：
    - 是否在 Docker 容器中
    - 是否使用 cgroup v2
    返回 (is_docker, is_cgroupv2)
    """
    is_docker = False
    is_cgroupv2 = False

    # 检测 Docker 方法 1：/proc/1/cgroup 包含 docker/containerd
    try:
        with open("/proc/1/cgroup", "rt") as f:
            cgroup_content = f.read()
            if "docker" in cgroup_content.lower() or "containerd" in cgroup_content.lower():
                is_docker = True
    except Exception:
        pass

    # 检测 Docker 方法 2：存在 /.dockerenv（Docker 特有文件）
    if not is_docker:
        try:
            os.stat("/.dockerenv")
            is_docker = True
        except Exception:
            pass

    # 检测 Docker 方法 3：cgroup 内容只有 /init.scope（常见于轻量级容器/云VM）
    # 如果是 /init.scope 且有 cgroup v2，认为是容器环境
    if not is_docker:
        try:
            with open("/proc/1/cgroup", "rt") as f:
                content = f.read().strip()
                # 格式：0::/init.scope 或 0::/system.slice/docker-xxx.service
                if content.startswith("0::") and "/init.scope" in content:
                    # 进一步检查：/proc/20/cgroup（容器内常见 PID>1 也属于同一 cgroup）
                    for pid in ["20", "self"]:
                        try:
                            with open(f"/proc/{pid}/cgroup", "rt") as pf:
                                pc = pf.read()
                                if "docker" in pc.lower() or "containerd" in pc.lower():
                                    is_docker = True
                                    break
                        except Exception:
                            pass
        except Exception:
            pass

    # 检测 cgroup v2：检查 /sys/fs/cgroup/cgroup.controllers 是否存在
    try:
        os.stat("/sys/fs/cgroup/cgroup.controllers")
        is_cgroupv2 = True
    except Exception:
        # 也检查 /sys/fs/cgroup/cgroup.subtree_control (cgroup v2 特有)
        try:
            os.stat("/sys/fs/cgroup/cgroup.subtree_control")
            is_cgroupv2 = True
        except Exception:
            pass

    return is_docker, is_cgroupv2


_is_docker, _is_cgroupv2 = _detect_container_env()

if _is_docker:
    _container_info = []
    if _is_cgroupv2:
        _container_info.append("cgroup v2")
    _container_info.append("Docker")
    logger.info(f"Container environment detected: {', '.join(_container_info)}")
else:
    logger.info("Running on bare metal / VM (no container detected)")

# ============ GPU 采集（pynvml，可选） ============

_nvml_handle = None
_nvml_init_error: Optional[str] = None


def _init_nvml() -> bool:
    """初始化 NVML（延迟初始化，失败时记录原因）"""
    global _nvml_handle, _nvml_init_error
    if _nvml_handle is not None or _nvml_init_error is not None:
        return _nvml_handle is not None

    try:
        import pynvml

        pynvml.nvmlInit()
        _nvml_handle = pynvml
        return True
    except Exception as e:
        _nvml_init_error = str(e)
        logger.warning(f"NVML init failed (GPU monitoring disabled): {e}")
        return False


def _get_gpu_info() -> Dict[str, Any]:
    """采集 GPU 指标（优雅降级：GPU 不可用时返回空）"""
    if not _init_nvml():
        return {
            "available": False,
            "count": 0,
            "devices": [],
            "reason": _nvml_init_error or "No NVIDIA GPU detected or nvidia-smi not available",
        }

    try:
        nvml = _nvml_handle
        device_count = nvml.nvmlDeviceGetCount()

        devices = []
        for i in range(device_count):
            try:
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                name = nvml.nvmlDeviceGetName(handle)
                if name is None:
                    name = "Unknown GPU"

                memory_info = nvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = nvml.nvmlDeviceGetUtilizationRates(handle)

                try:
                    temperature = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                except Exception:
                    temperature = None

                total_gb = round(memory_info.total / (1024**3), 2)
                used_gb = round(memory_info.used / (1024**3), 2)
                free_gb = round(memory_info.free / (1024**3), 2)
                usage_percent = round((memory_info.used / memory_info.total) * 100, 1) if memory_info.total > 0 else 0

                devices.append({
                    "index": i,
                    "name": name,
                    "memory_total_gb": total_gb,
                    "memory_used_gb": used_gb,
                    "memory_free_gb": free_gb,
                    "memory_usage_percent": usage_percent,
                    "utilization_percent": utilization.gpu,
                    "temperature_celsius": temperature,
                })
            except Exception as e:
                logger.warning(f"Failed to read GPU {i}: {e}")
                continue

        return {
            "available": True,
            "count": device_count,
            "devices": devices,
        }

    except Exception as e:
        logger.error(f"GPU monitoring error: {e}")
        return {
            "available": False,
            "count": 0,
            "devices": [],
            "reason": str(e),
        }


# ============ CPU 采集 ============

def _get_cpu_info() -> Dict[str, Any]:
    """
    采集 CPU 指标

    关键：在 Docker + cgroup v2 环境下，psutil.cpu_percent(interval=None)
    可能返回 0（无基准数据）。强制使用 interval=0.5 强制采样获取真实值。
    """
    try:
        # Docker/cgroup v2 环境：需要 interval 参数才能获取真实数据
        # 原因：interval=None 只返回自上次调用的变化，无上次调用时返回 0
        _interval = 0.5 if (_is_docker and _is_cgroupv2) else None
        per_core = psutil.cpu_percent(interval=_interval, percpu=True)

        # Docker 下 interval=None 可能返回全 0，做一次保护性重试
        if _is_docker and all(u == 0 for u in per_core) and _interval is None:
            logger.debug("CPU percent all-zero in Docker, retrying with interval=0.5")
            per_core = psutil.cpu_percent(interval=0.5, percpu=True)

        usage_percent = round(sum(per_core) / len(per_core), 1) if per_core else 0
        return {
            "usage_percent": usage_percent,
            "core_count": psutil.cpu_count(logical=False) or 1,
            "per_core_usage": [round(u, 1) for u in per_core],
            "interval_used": 0.5 if (_is_docker and _is_cgroupv2) else None,
        }
    except Exception as e:
        logger.error(f"CPU monitoring error: {e}")
        return {
            "usage_percent": 0,
            "core_count": 1,
            "per_core_usage": [],
        }


# ============ 内存采集 ============

def _get_memory_info() -> Dict[str, Any]:
    """采集内存指标"""
    try:
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 2)
        used_gb = round(mem.used / (1024**3), 2)
        available_gb = round(mem.available / (1024**3), 2)
        usage_percent = round(mem.percent, 1)

        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "available_gb": available_gb,
            "usage_percent": usage_percent,
        }
    except Exception as e:
        logger.error(f"Memory monitoring error: {e}")
        return {
            "total_gb": 0,
            "used_gb": 0,
            "available_gb": 0,
            "usage_percent": 0,
        }


# ============ 磁盘采集 ============

def _get_disk_info() -> Dict[str, Any]:
    """采集磁盘挂载点指标"""
    try:
        partitions = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb = round(usage.total / (1024**3), 2)
                used_gb = round(usage.used / (1024**3), 2)
                free_gb = round(usage.free / (1024**3), 2)
                usage_percent = round(usage.percent, 1)

                partitions.append({
                    "mountpoint": part.mountpoint,
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "usage_percent": usage_percent,
                })
            except PermissionError:
                continue
            except Exception as e:
                logger.warning(f"Failed to read disk {part.mountpoint}: {e}")
                continue

        return {"partitions": partitions}
    except Exception as e:
        logger.error(f"Disk monitoring error: {e}")
        return {"partitions": []}


# ============ 网络采集 ============

# 上一次网络采集的时间戳和字节数（用于计算速率）
_last_net: Optional[Dict[str, int]] = None
_last_net_time: float = 0


def _get_network_info() -> Dict[str, Any]:
    """采集网络指标（包含实时速率）"""
    global _last_net, _last_net_time

    try:
        net = psutil.net_io_counters()
        now = time.time()

        bytes_sent_mb = round(net.bytes_sent / (1024**2), 2)
        bytes_recv_mb = round(net.bytes_recv / (1024**2), 2)

        send_rate_mbps = 0.0
        recv_rate_mbps = 0.0

        if _last_net is not None and _last_net_time > 0:
            elapsed = now - _last_net_time
            if elapsed > 0:
                send_rate_mbps = round((net.bytes_sent - _last_net["bytes_sent"]) / (1024**2) / elapsed, 3)
                recv_rate_mbps = round((net.bytes_recv - _last_net["bytes_recv"]) / (1024**2) / elapsed, 3)

        _last_net = {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv}
        _last_net_time = now

        # 速率不能为负
        send_rate_mbps = max(0, send_rate_mbps)
        recv_rate_mbps = max(0, recv_rate_mbps)

        return {
            "bytes_sent_mb": bytes_sent_mb,
            "bytes_recv_mb": bytes_recv_mb,
            "send_rate_mbps": send_rate_mbps,
            "recv_rate_mbps": recv_rate_mbps,
        }
    except Exception as e:
        logger.error(f"Network monitoring error: {e}")
        return {
            "bytes_sent_mb": 0,
            "bytes_recv_mb": 0,
            "send_rate_mbps": 0,
            "recv_rate_mbps": 0,
        }


# ============ 系统信息 ============

def _get_system_info() -> Dict[str, Any]:
    """采集系统基本信息"""
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_time)

        uname = platform.uname()
        return {
            "hostname": uname.node,
            "uptime_seconds": uptime_seconds,
            "os_type": uname.system,
            "os_version": uname.version,
        }
    except Exception as e:
        logger.error(f"System info error: {e}")
        return {
            "hostname": "unknown",
            "uptime_seconds": 0,
            "os_type": platform.system(),
            "os_version": platform.version(),
        }


# ============ 训练任务统计 ============

def _get_job_stats(db: Session) -> Dict[str, int]:
    """从数据库统计训练任务"""
    try:
        running = db.query(TrainingJob).filter(TrainingJob.status == "running").count()
        pending = db.query(TrainingJob).filter(TrainingJob.status == "pending").count()
        completed = db.query(TrainingJob).filter(TrainingJob.status == "completed").count()
        failed = db.query(TrainingJob).filter(TrainingJob.status == "failed").count()

        return {
            "running": running,
            "pending": pending,
            "completed": completed,
            "failed": failed,
        }
    except Exception as e:
        logger.error(f"Job stats error: {e}")
        return {
            "running": 0,
            "pending": 0,
            "completed": 0,
            "failed": 0,
        }


# ============ 统一采集入口 ============

def collect_overview(db: Session) -> Dict[str, Any]:
    """
    采集完整系统监控概览
    所有指标独立采集，任一失败不影响其他
    """
    from datetime import datetime, timezone

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "gpu": _get_gpu_info(),
        "disk": _get_disk_info(),
        "network": _get_network_info(),
        "system": _get_system_info(),
        "jobs": _get_job_stats(db),
    }


def collect_cpu() -> Dict[str, Any]:
    return _get_cpu_info()


def collect_memory() -> Dict[str, Any]:
    return _get_memory_info()


def collect_gpu() -> Dict[str, Any]:
    return _get_gpu_info()


def collect_disk() -> Dict[str, Any]:
    return _get_disk_info()


def collect_network() -> Dict[str, Any]:
    return _get_network_info()


def collect_jobs(db: Session) -> Dict[str, int]:
    return _get_job_stats(db)
