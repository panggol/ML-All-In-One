"""
平台统一日志聚合服务

提供：
- contextvars：user_id、request_id 跨协程传递
- PlatformJsonHandler：按模块+日期输出 JSON Lines 文件
- ContextFilter：自动注入 user_id、request_id、module
- 各模块预配置 logger：platform.api / platform.auth / platform.preprocessing / platform.error
- 日志清理：保留 30 天，超期文件异步删除
"""
import os
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextvars import ContextVar
from typing import Optional
from logging.handlers import RotatingFileHandler

# ============ 全局 contextvars ============
# 在每个请求的生命周期内，这几个变量会被中间件写入，供各 logger 使用
_current_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_current_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_current_module: ContextVar[str] = ContextVar("module", default="platform")


# ============ 工具函数 ============

def generate_request_id() -> str:
    """生成一个 UUID 作为 request_id"""
    return str(uuid.uuid4())


def get_request_id() -> Optional[str]:
    return _current_request_id.get()


def get_user_id() -> Optional[str]:
    return _current_user_id.get()


def set_request_context(request_id: str, user_id: Optional[str], module: str = "platform") -> None:
    """在当前协程上下文中设置 request_id 和 user_id"""
    _current_request_id.set(request_id)
    _current_user_id.set(user_id)
    _current_module.set(module)


def reset_request_context() -> None:
    """重置上下文（请求结束时调用）"""
    _current_request_id.set(None)
    _current_user_id.set(None)
    _current_module.set("platform")


def _ensure_log_dir(module: str) -> Path:
    """确保日志目录存在，返回日志目录路径"""
    base_dir = Path("./logs")
    module_dir = base_dir / module
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir


def _get_log_file_path(module: str) -> Path:
    """获取当日日志文件路径：logs/{module}/YYYY-MM-DD.log"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    module_dir = _ensure_log_dir(module)
    return module_dir / f"{today}.log"


# ============ JSON Formatter（手动序列化，避免依赖 python-json-logger）============

def _serialize_log_record(record: logging.LogRecord) -> str:
    """
    将 LogRecord 序列化为单行 JSON 字符串。
    字段顺序固定，便于人工阅读和日志分析。
    """
    module_name = record.name.split(".")[-1]  # "platform.api" → "api"
    if module_name.startswith("platform."):
        module_name = module_name[len("platform."):]

    extra = getattr(record, "extra_fields", {})

    entry = {
        "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "level": record.levelname,
        "module": module_name,
        "message": record.getMessage(),
        "request_id": _current_request_id.get() or record.__dict__.get("request_id", ""),
        "user_id": _current_user_id.get() or record.__dict__.get("user_id", ""),
        "extra": extra,
    }
    return json.dumps(entry, ensure_ascii=False, separators=(",", ":"))


# ============ 自定义 Handler ============

class PlatformJsonHandler(RotatingFileHandler):
    """
    输出 JSON Lines 格式的日志文件，按模块+日期分割。
    - 按天：每天一个文件 logs/{module}/YYYY-MM-DD.log
    - 100MB 轮转兜底（父类 RotatingFileHandler 实现）
    """

    def __init__(self, module: str, maxBytes: int = 100 * 1024 * 1024, backupCount: int = 3):
        self._module = module
        # 先用临时路径，emit 时再确定正确路径
        self._init_file_path()
        super().__init__(self._current_file_path, maxBytes=maxBytes, backupCount=backupCount, encoding="utf-8")

    def _init_file_path(self) -> None:
        self._current_file_path = str(_get_log_file_path(self._module))

    def emit(self, record: logging.LogRecord) -> None:
        """
        覆写 emit：每日检查是否需要切换文件（跨天后新建当日文件）。
        """
        today_path = str(_get_log_file_path(self._module))
        if today_path != self._current_file_path:
            # 日期变了，切换文件
            self._current_file_path = today_path
            self.baseFilename = today_path
            self.stream = open(today_path, "a", encoding="utf-8")
        try:
            line = _serialize_log_record(record)
            self.stream.write(line + "\n")
            self.flush()
        except Exception:
            self.handleError(record)


# ============ Context Filter ============

class ContextFilter(logging.Filter):
    """
    日志 Filter：在每条日志记录中注入 extra_fields（包含 request_id、user_id）。
    这样 logger.info(...) 时无需手动传参。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _current_request_id.get() or ""
        record.user_id = _current_user_id.get() or ""
        record.extra_fields = getattr(record, "extra_fields", {})
        return True


# ============ Logger 工厂 ============

_loggers: dict[str, logging.Logger] = {}
_handler_initialized: bool = False


def _ensure_handlers(module: str) -> None:
    """为指定 module 确保 handler 和 filter 已配置"""
    if module in _loggers:
        return

    logger = logging.getLogger(f"platform.{module}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # 不向上传播，避免重复

    handler = PlatformJsonHandler(module)
    handler.setLevel(logging.DEBUG)

    # Formatter 仅用于回退（handler 内部已 JSON 序列化）
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)

    ctx_filter = ContextFilter()
    handler.addFilter(ctx_filter)

    logger.addHandler(handler)
    _loggers[module] = logger


def get_logger(module: str) -> logging.Logger:
    """
    获取指定模块的 logger。
    - module: "api" | "auth" | "preprocessing" | "error" | "system"
    """
    _ensure_handlers(module)
    return _loggers[module]


# ============ 预配置各模块 logger ============

def init_platform_loggers() -> None:
    """初始化所有平台 logger（启动时调用一次）"""
    for m in ("api", "auth", "preprocessing", "error", "system"):
        _ensure_handlers(m)


# ============ 便捷日志方法 ============

def log_api(method: str, path: str, status: int, duration_ms: float, extra: Optional[dict] = None) -> None:
    """快捷写 API 日志"""
    _ensure_handlers("api")
    logger = _loggers["api"]
    msg = f"{method} {path} {status} ({duration_ms:.0f}ms)"
    record = logger.makeRecord(
        logger.name, logging.INFO, "(api)", 0, msg, (), None
    )
    record.extra_fields = extra or {}
    logger.handle(record)


def log_auth(event: str, user_id: Optional[str] = None, detail: Optional[str] = None, success: bool = True) -> None:
    """快捷写 Auth 日志"""
    _ensure_handlers("auth")
    logger = _loggers["auth"]
    msg = f"Auth {event}: {detail or ''}"
    if not success:
        msg = f"Auth {event} FAILED: {detail or ''}"
    record = logger.makeRecord(
        logger.name, logging.INFO if success else logging.WARNING, "(auth)", 0, msg, (), None
    )
    record.extra_fields = {"event": event, "success": success, "detail": detail}
    logger.handle(record)


def log_preprocessing(
    event: str,
    data_file_id: Optional[int] = None,
    user_id: Optional[str] = None,
    detail: Optional[dict] = None,
    level: int = logging.INFO,
) -> None:
    """快捷写 Preprocessing 日志"""
    _ensure_handlers("preprocessing")
    logger = _loggers["preprocessing"]
    msg = f"Preprocessing {event}"
    if data_file_id:
        msg += f" (data_file_id={data_file_id})"
    record = logger.makeRecord(
        logger.name, level, "(preprocessing)", 0, msg, (), None
    )
    record.extra_fields = detail or {}
    if data_file_id:
        record.extra_fields["data_file_id"] = data_file_id
    logger.handle(record)


def log_error(exc: Exception, request_id: Optional[str] = None, user_id: Optional[str] = None, extra: Optional[dict] = None) -> None:
    """快捷写 Error 日志"""
    _ensure_handlers("error")
    logger = _loggers["error"]
    import traceback
    tb = traceback.format_exc()
    msg = f"Unhandled exception: {type(exc).__name__}: {str(exc)}"
    record = logger.makeRecord(
        logger.name, logging.ERROR, "(error)", 0, msg, (), None
    )
    record.extra_fields = {
        "exception": type(exc).__name__,
        "message": str(exc),
        "traceback": tb,
    }
    if extra:
        record.extra_fields.update(extra)
    logger.handle(record)


# ============ 日志清理（30 天）============

LOG_RETENTION_DAYS = 30


async def cleanup_old_logs() -> dict[str, int]:
    """
    异步清理超期日志文件。
    返回清理统计：{module: deleted_count}
    """
    base_dir = Path("./logs")
    if not base_dir.exists():
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOG_RETENTION_DAYS)
    deleted: dict[str, int] = {}
    total_deleted = 0

    for module_dir in base_dir.iterdir():
        if not module_dir.is_dir():
            continue
        module_deleted = 0
        for log_file in module_dir.glob("*.log"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    log_file.unlink(missing_ok=True)
                    module_deleted += 1
                    total_deleted += 1
            except OSError:
                pass
        if module_deleted > 0:
            deleted[module_dir.name] = module_deleted

    # 写清理日志
    if total_deleted > 0:
        _ensure_handlers("system")
        sl = _loggers["system"]
        msg = f"Log cleanup done: {total_deleted} files removed, modules={list(deleted.keys())}"
        r = sl.makeRecord(sl.name, logging.INFO, "(system)", 0, msg, (), None)
        r.extra_fields = {"deleted": deleted, "total": total_deleted}
        sl.handle(r)

    return deleted


def cleanup_old_logs_sync() -> dict[str, int]:
    """同步版本，供 startup 事件同步调用（不怕短暂阻塞）"""
    return asyncio.get_event_loop().run_until_complete(cleanup_old_logs())
