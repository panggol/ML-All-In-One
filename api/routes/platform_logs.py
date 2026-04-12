"""
平台日志查询 API - GET /api/platform-logs

功能：
- 按 module / level / start_time / end_time / keyword 过滤
- user_id 隔离（JWT sub 字段）
- 分页返回（page + page_size，默认 100，最大 500）
- 超过 5000 条时返回 next_token（追加加载）
- JSON Lines 文件读取，支持跨天聚合

Constitution C5/C8/C9 约束实现。
"""
import json
import base64
import re
from datetime import datetime, timezone as dt_tz
from pathlib import Path
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from api.database import User
from api.services.log_aggregator import get_request_id, get_user_id

router = APIRouter(redirect_slashes=False)

# ============ 常量 ============
LOGS_BASE_DIR = Path("./logs")
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 100
MAX_SINGLE_QUERY = 5000  # 超过此条数返回 next_token

# 允许的模块列表
VALID_MODULES = frozenset({"api", "auth", "preprocessing", "error", "system"})
VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


# ============ Pydantic 模型 ============

class PlatformLogEntry(BaseModel):
    """单条平台日志条目"""
    timestamp: str = Field(description="ISO8601 时间戳")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(description="日志级别")
    module: str = Field(description="来源模块")
    message: str = Field(description="日志消息")
    request_id: str = Field(default="")
    user_id: Optional[str] = Field(default=None)
    extra: dict = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class PlatformLogsResponse(BaseModel):
    """分页日志列表响应"""
    data: list[PlatformLogEntry] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    next_token: Optional[str] = Field(default=None, description="分页 token，超过 5000 条时返回")


# ============ 工具函数 ============

def _get_log_dir(module: Optional[str]) -> Optional[Path]:
    """获取日志目录路径，不存在返回 None"""
    if module:
        d = LOGS_BASE_DIR / module
    else:
        d = LOGS_BASE_DIR
    return d if d.exists() else None


def _parse_iso_timestamp(ts_str: str) -> Optional[datetime]:
    """解析 ISO8601 时间字符串，返回 datetime（无时区信息）"""
    if not ts_str:
        return None
    try:
        # 容忍 Z 后缀
        ts_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _line_to_entry(line: str) -> Optional[PlatformLogEntry]:
    """解析单行 JSON Line，返回 PlatformLogEntry 或 None（跳过损坏行）"""
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
        return PlatformLogEntry(
            timestamp=obj.get("timestamp", ""),
            level=obj.get("level", "INFO"),
            module=obj.get("module", ""),
            message=obj.get("message", ""),
            request_id=obj.get("request_id", ""),
            user_id=obj.get("user_id"),
            extra=obj.get("extra", {}),
        )
    except (json.JSONDecodeError, ValueError):
        return None


def _matches_filters(
    entry: PlatformLogEntry,
    module: Optional[str],
    level: Optional[str],
    keyword: Optional[str],
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> bool:
    """判断单条日志是否满足所有筛选条件"""
    # module 过滤
    if module and entry.module != module:
        return False

    # level 过滤
    if level and entry.level != level:
        return False

    # keyword 模糊匹配（message 字段 substring）
    if keyword:
        kw = keyword.lower()
        if kw not in entry.message.lower() and kw not in json.dumps(entry.extra).lower():
            return False

    # 时间范围
    if start_dt or end_dt:
        ts = _parse_iso_timestamp(entry.timestamp)
        if ts:
            if start_dt and ts < start_dt:
                return False
            if end_dt and ts > end_dt:
                return False
        else:
            # 无法解析时间，跳过（不匹配）
            return False

    return True


def _collect_log_files(
    module: Optional[str],
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> list[Path]:
    """
    收集所有需要扫描的日志文件路径。
    按日期过滤，优先扫描目标日期的文件。
    """
    if not LOGS_BASE_DIR.exists():
        return []

    files: list[Path] = []

    if module:
        modules = [module]
    else:
        modules = [d.name for d in LOGS_BASE_DIR.iterdir() if d.is_dir() and d.name in VALID_MODULES]

    today = datetime.now(dt_tz.utc).date()

    for mod in modules:
        mod_dir = LOGS_BASE_DIR / mod
        if not mod_dir.exists():
            continue

        for log_file in sorted(mod_dir.glob("*.log")):
            # 从文件名提取日期：YYYY-MM-DD.log
            try:
                date_str = log_file.stem  # "2026-04-12"
                file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                # 跳过无法解析日期的文件
                continue

            # 日期过滤
            if start_dt:
                start_date = start_dt.date()
                if file_date < start_date:
                    continue
            if end_dt:
                end_date = end_dt.date()
                if file_date > end_date:
                    continue

            files.append(log_file)

    return files


def _scan_and_filter_logs(
    files: list[Path],
    module: Optional[str],
    level: Optional[str],
    keyword: Optional[str],
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    target_user_id: Optional[str],
    skip_token: Optional[str],
    max_results: int,
) -> tuple[list[PlatformLogEntry], int, Optional[str]]:
    """
    扫描日志文件，应用过滤条件，返回匹配的日志条目。

    返回：(matched_entries, total_matched, next_token)
    - matched_entries: 最多 max_results 条
    - total_matched: 满足条件的总条数（不含 user_id 过滤，用于 total 计数）
    - next_token: 超过 max_results 时返回 base64 token
    """
    all_matched: list[PlatformLogEntry] = []
    total_count = 0
    started = skip_token is None  # 是否已开始收集
    overflow = False  # 是否已超过 max_results

    # 如果有 skip_token，解析起点
    start_file_index = 0
    start_line_pos = 0
    if skip_token:
        try:
            decoded = json.loads(base64.b64decode(skip_token).decode("utf-8"))
            start_file_index = decoded.get("file_index", 0)
            start_line_pos = decoded.get("line_pos", 0)
            started = True
        except Exception:
            started = True

    for fi, file_path in enumerate(files):
        if fi < start_file_index:
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for li, line in enumerate(f):
                    if fi == start_file_index and li < start_line_pos:
                        continue

                    entry = _line_to_entry(line)
                    if entry is None:
                        continue

                    # user_id 隔离（非 admin）
                    if target_user_id and entry.user_id != target_user_id:
                        continue

                    # 应用其他筛选
                    if not _matches_filters(entry, module, level, keyword, start_dt, end_dt):
                        continue

                    total_count += 1

                    if started and not overflow:
                        all_matched.append(entry)
                        if len(all_matched) >= max_results:
                            overflow = True
                            # 生成 next_token
                            next_t = base64.b64encode(
                                json.dumps({"file_index": fi, "line_pos": li + 1}).encode("utf-8")
                            ).decode("ascii")
                            return all_matched, total_count, next_t
        except (IOError, OSError):
            continue

    return all_matched, total_count, None


def _encode_next_token(file_index: int, line_pos: int) -> str:
    return base64.b64encode(
        json.dumps({"file_index": file_index, "line_pos": line_pos}).encode("utf-8")
    ).decode("ascii")


# ============ 路由 ============

@router.get("", response_model=PlatformLogsResponse)
async def list_platform_logs(
    module: Optional[str] = Query(default=None, description="筛选模块：api | auth | preprocessing | error"),
    level: Optional[str] = Query(default=None, description="筛选级别：DEBUG | INFO | WARNING | ERROR"),
    start_time: Optional[str] = Query(default=None, description="起始时间 ISO8601"),
    end_time: Optional[str] = Query(default=None, description="截止时间 ISO8601"),
    keyword: Optional[str] = Query(default=None, description="关键词模糊匹配（message 字段）"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="每页条数"),
    next_token: Optional[str] = Query(default=None, description="追加加载 token（覆盖 page 参数）"),
    current_user: User = Depends(get_current_user),
) -> PlatformLogsResponse:
    """
    分页列出平台日志，支持多种筛选条件。
    自动按当前用户的 user_id 进行隔离（管理员除外）。
    """

    # 参数校验
    if module and module not in VALID_MODULES:
        raise HTTPException(status_code=400, detail=f"无效的 module：{module}，可选值：{list(VALID_MODULES)}")

    if level and level not in VALID_LEVELS:
        raise HTTPException(status_code=400, detail=f"无效的 level：{level}，可选值：{list(VALID_LEVELS)}")

    start_dt = _parse_iso_timestamp(start_time) if start_time else None
    end_dt = _parse_iso_timestamp(end_time) if end_time else None

    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")

    # user_id 隔离
    target_user_id: Optional[str] = str(current_user.id)
    if current_user.role == "admin":
        # admin 不做 user_id 隔离（全量查看）
        target_user_id = None

    # 收集日志文件
    files = _collect_log_files(module, start_dt, end_dt)

    # 确定最大查询量（超过 MAX_SINGLE_QUERY 用 next_token）
    max_query = MAX_SINGLE_QUERY

    # 计算 offset
    offset = 0
    if next_token:
        # next_token 模式下忽略 page，直接追加
        offset = 0
        page = 1
    else:
        offset = (page - 1) * page_size

    # 扫描日志文件
    matched, total, _ = _scan_and_filter_logs(
        files, module, level, keyword, start_dt, end_dt, target_user_id,
        None, max_query + 1,  # 多读一条判断 overflow
    )

    # 分页切片
    page_entries = matched[offset: offset + page_size]
    has_more = len(matched) > page_size

    # 构造 next_token（超过 MAX_SINGLE_QUERY 时）
    response_next_token: Optional[str] = None
    if total > MAX_SINGLE_QUERY and not next_token:
        # 第一页返回 next_token 用于加载更多
        response_next_token = _encode_next_token(0, page_size)
    elif next_token:
        # 追加模式：已经在 _scan_and_filter_logs 中处理
        response_next_token = None

    # 简化：next_token 追加加载模式（覆盖 page）
    if next_token and len(matched) >= page_size:
        # 继续扫描后续文件
        more_entries, more_total, more_token = _scan_and_filter_logs(
            files, module, level, keyword, start_dt, end_dt, target_user_id,
            next_token, page_size,  # 每次追加 page_size 条
        )
        page_entries = more_entries
        response_next_token = more_token
        total = total  # 保持原值

    return PlatformLogsResponse(
        data=page_entries,
        total=total,
        page=page,
        page_size=page_size,
        next_token=response_next_token,
    )
