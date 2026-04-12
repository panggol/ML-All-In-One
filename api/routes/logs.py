"""
日志路由 - logs_tab 模块
提供训练日志的查询、过滤、查看和删除功能。

日志格式：LoggerHook 写入 JSON 数组文件（每个文件对应一次 Run）
存储路径：./logs/（相对于项目根目录）
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone as dt_tz
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any

from api.auth import get_current_user
from api.database import User

router = APIRouter(redirect_slashes=False)

# ============ 常量 ============
LOGS_DIR = Path("./logs")
PREVIEW_ENTRIES = 5  # 大文件预览时读取的最大条目数

# ============ Pydantic 模型 ============

class LogEntry(BaseModel):
    """单条日志条目（列表页摘要）"""
    file_id: str          # 文件名，如 "run_1_1712000000.json"
    run: int              # Run 编号
    iter: int             # 末次迭代编号
    timestamp: str        # ISO8601 格式时间
    experiment_id: Optional[str] = None
    metrics: dict[str, Any] = {}   # 动态指标字典

    model_config = ConfigDict(extra="allow")


class LogListResponse(BaseModel):
    """分页日志列表响应"""
    data: list[LogEntry]
    total: int
    page: int
    page_size: int


class DeleteResponse(BaseModel):
    """删除响应"""
    message: str


# ============ 工具函数 ============

def _get_logs_dir() -> Path:
    """获取日志目录，不存在则创建"""
    logs_dir = LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _read_log_entries(file_path: Path) -> list[dict]:
    """读取 JSON 数组格式的日志文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, IOError):
        # 损坏的文件跳过
        return []


def _entries_to_log_entry(filename: str, entries: list[dict]) -> Optional[LogEntry]:
    """从文件条目列表转换为 LogEntry（取最后一条作为摘要）"""
    if not entries:
        return None

    last = entries[-1]  # 取最新条目作为摘要

    # 提取字段
    run = int(last.get("run", 0))
    iter_num = int(last.get("iter", 0))
    ts_raw = last.get("timestamp", 0)

    # timestamp 可能是 Unix 时间戳（秒）或 ISO8601 字符串
    if isinstance(ts_raw, (int, float)):
        ts_str = datetime.fromtimestamp(ts_raw).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ts_str = str(ts_raw)

    # metrics = 除 iter/run/timestamp 外的其余字段
    metrics_keys = {"iter", "run", "timestamp"}
    metrics = {k: v for k, v in last.items() if k not in metrics_keys}

    return LogEntry(
        file_id=filename,
        run=run,
        iter=iter_num,
        timestamp=ts_str,
        experiment_id=last.get("experiment_id"),
        metrics=metrics,
    )


def _build_log_entries(
    logs_dir: Path,
    experiment_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list[LogEntry]:
    """
    扫描日志目录，构建 LogEntry 列表（已按时间降序排列）。
    支持 experiment_id 和时间范围过滤。
    """
    entries: list[LogEntry] = []

    if not logs_dir.exists():
        return entries

    for file_path in logs_dir.glob("*.json"):
        json_entries = _read_log_entries(file_path)
        if not json_entries:
            continue

        # 过滤 experiment_id
        if experiment_id is not None:
            matched = any(
                str(e.get("experiment_id", "")) == experiment_id
                for e in json_entries
            )
            if not matched:
                continue

        # 过滤时间范围（使用最后一条的时间）
        last = json_entries[-1]
        ts_raw = last.get("timestamp")
        if ts_raw is not None:
            if isinstance(ts_raw, (int, float)):
                entry_dt = datetime.fromtimestamp(ts_raw, tz=dt_tz.utc).replace(tzinfo=None)
            else:
                ts_str = str(ts_raw).replace("Z", "+00:00")
                try:
                    entry_dt = datetime.fromisoformat(ts_str)
                    if entry_dt.tzinfo is not None:
                        entry_dt = entry_dt.replace(tzinfo=None)
                except ValueError:
                    entry_dt = datetime.min
        else:
            entry_dt = datetime.min

        if start_time and entry_dt < start_time:
            continue
        if end_time and entry_dt > end_time:
            continue

        log_entry = _entries_to_log_entry(file_path.name, json_entries)
        if log_entry:
            entries.append(log_entry)

    # 按 timestamp 降序（最新的在前）
    entries.sort(
        key=lambda e: e.timestamp,
        reverse=True,
    )
    return entries


# ============ 路由 ============

@router.get("", response_model=LogListResponse)
async def list_logs(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    experiment_id: Optional[str] = Query(default=None, description="按实验 ID 筛选"),
    start_time: Optional[str] = Query(default=None, description="起始时间（ISO8601）"),
    end_time: Optional[str] = Query(default=None, description="截止时间（ISO8601）"),
    current_user: User = Depends(get_current_user),
) -> LogListResponse:
    """
    分页列出日志条目，支持 experiment_id 和时间范围筛选。

    日志按 timestamp 降序排列（最新在前）。
    每个文件（对应一次 Run）仅展示最新一条条目作为摘要。
    """

    # 解析时间范围
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if start_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_time 格式错误，请使用 ISO8601 格式")

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            if end_dt.tzinfo is not None:
                end_dt = end_dt.replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_time 格式错误，请使用 ISO8601 格式")

    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")

    logs_dir = _get_logs_dir()
    all_entries = _build_log_entries(logs_dir, experiment_id, start_dt, end_dt)

    total = len(all_entries)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_entries = all_entries[start_idx:end_idx]

    return LogListResponse(
        data=page_entries,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{file_id}")
async def get_log_detail(
    file_id: str,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """
    获取单个日志文件的完整内容（JSON 数组，不分页）。
    file_id 为日志文件名，如 "run_1_1712000000.json"。
    """
    logs_dir = _get_logs_dir()

    # 安全校验：禁止路径遍历
    if ".." in file_id or "/" in file_id or "\\" in file_id:
        raise HTTPException(status_code=400, detail="无效的文件名")

    file_path = logs_dir / file_id
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")

    entries = _read_log_entries(file_path)
    return JSONResponse(content=entries)


@router.delete("/{file_id}", response_model=DeleteResponse)
async def delete_log(
    file_id: str,
    current_user: User = Depends(get_current_user),
) -> DeleteResponse:
    """
    删除指定的日志文件。
    需要 Bearer Token 认证。
    """
    logs_dir = _get_logs_dir()

    # 安全校验：禁止路径遍历
    if ".." in file_id or "/" in file_id or "\\" in file_id:
        raise HTTPException(status_code=400, detail="无效的文件名")

    file_path = logs_dir / file_id
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")

    file_path.unlink()
    return DeleteResponse(message="删除成功")
