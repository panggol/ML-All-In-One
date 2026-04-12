"""
平台日志中间件 - PlatformLoggingMiddleware

功能：
1. 请求进入时生成 request_id（UUID），提取 user_id（从 JWT），写入 contextvars
2. 请求结束后写入 API 日志（method, path, status_code, duration_ms）
3. 未捕获异常自动写入 Error 日志
4. 登录成功/失败事件写入 Auth 日志（通过 login 事件触发）

约束（C11/C12/C13）：
- 使用 run_in_executor 异步写文件，避免阻塞 FastAPI 事件循环
- 不引入 aiofiles 等新依赖（constitution 禁止）
"""
import sys
import time
import traceback
import uuid
import asyncio
from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from jose import jwt, JWTError

from api.services.log_aggregator import (
    set_request_context,
    reset_request_context,
    generate_request_id,
    get_request_id,
    get_user_id,
    log_api,
    log_error,
    get_logger,
)

import logging


# ============ JWT 解码工具（独立，不依赖 api.auth 以避免循环导入）============

SECRET_KEY: Optional[str] = None
ALGORITHM = "HS256"


def _init_jwt_config() -> None:
    global SECRET_KEY
    if SECRET_KEY is None:
        import os
        SECRET_KEY = os.getenv("MLKIT_JWT_SECRET") or os.getenv("JWT_SECRET_KEY")


def _decode_user_id_from_token(token: str) -> Optional[str]:
    """从 JWT token 解码出 user_id（sub 字段）"""
    _init_jwt_config()
    if not SECRET_KEY:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def _extract_bearer_token(request: Request) -> Optional[str]:
    """从请求头提取 Bearer token"""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


# ============ PlatformLoggingMiddleware ============

class PlatformLoggingMiddleware(BaseHTTPMiddleware):
    """
    中间件拦截所有 /api/* 请求：
    - on_request：生成 request_id，提取 user_id，写入 contextvars
    - on_response：写入 API 日志
    - on_exception：写入 Error 日志
    """

    # 排除的路径（不记录日志）
    EXCLUDED_PATHS = frozenset({
        "/api/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    })

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过排除路径
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # 生成 request_id 并尝试提取 user_id
        request_id = generate_request_id()
        token = _extract_bearer_token(request)
        user_id: Optional[str] = None
        if token:
            user_id = _decode_user_id_from_token(token)

        # 写入 contextvars（供各 logger 复用）
        set_request_context(request_id, user_id, module="api")

        # 记录开始时间
        start_time = time.perf_counter()

        exc_info: Optional[BaseException] = None
        response: Optional[Response] = None

        try:
            response = await call_next(request)
            return response
        except BaseException as e:
            exc_info = e
            raise
        finally:
            # 计算耗时
            duration_ms = (time.perf_counter() - start_time) * 1000

            # 获取响应状态码
            status_code = response.status_code if response else 500

            # 异步写日志（run_in_executor 避免阻塞事件循环）
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(
                    None,
                    _write_api_log_sync,
                    request.method,
                    str(request.url.path),
                    status_code,
                    duration_ms,
                    {
                        "method": request.method,
                        "path": str(request.url.path),
                        "status": status_code,
                        "duration_ms": round(duration_ms, 2),
                        "user_id": user_id,
                        "query": str(request.url.query) or None,
                    },
                )
            except Exception:
                pass  # 日志写入失败不阻塞请求

            # 如果有异常，写入 Error 日志
            if exc_info:
                try:
                    await loop.run_in_executor(
                        None,
                        _write_error_log_sync,
                        exc_info,
                        request_id,
                        user_id,
                        {
                            "method": request.method,
                            "path": str(request.url.path),
                            "query": str(request.url.query) or None,
                        },
                    )
                except Exception:
                    pass

            # 重置 contextvars
            reset_request_context()


def _write_api_log_sync(
    method: str,
    path: str,
    status: int,
    duration_ms: float,
    extra: dict,
) -> None:
    """同步写 API 日志（供 run_in_executor 调用）"""
    log_api(method, path, status, duration_ms, extra)


def _write_error_log_sync(
    exc: BaseException,
    request_id: str,
    user_id: Optional[str],
    extra: dict,
) -> None:
    """同步写 Error 日志（供 run_in_executor 调用）"""
    import traceback as tb_module
    tb = tb_module.format_exc()
    logger = get_logger("error")
    msg = f"Unhandled exception: {type(exc).__name__}: {str(exc)}"
    record = logger.makeRecord(
        logger.name, logging.ERROR, "(error)", 0, msg, (), sys.exc_info()
    )
    record.extra_fields = {
        "exception": type(exc).__name__,
        "message": str(exc),
        "traceback": tb,
        "request_id": request_id,
        "user_id": user_id,
    }
    record.request_id = request_id
    record.user_id = user_id or ""
    logger.handle(record)


# ============ 公开函数：记录 Auth 事件 ============

def log_login_event(
    user_id: Optional[str],
    username: Optional[str],
    success: bool,
    reason: Optional[str] = None,
) -> None:
    """
    在认证模块中调用，记录登录事件。
    由 api.auth 模块在登录成功/失败时调用。
    """
    event = "login_success" if success else "login_failed"
    detail = f"user={username or ''}"
    if reason:
        detail += f", reason={reason}"

    # 写入 contextvars（如果当前有请求上下文）
    current_request_id = get_request_id()
    if current_request_id:
        set_request_context(current_request_id, user_id, module="auth")

    logger = get_logger("auth")
    level = logging.INFO if success else logging.WARNING
    record = logger.makeRecord(
        logger.name, level, "(auth)", 0, f"Auth {event}: {detail}", (), None
    )
    record.extra_fields = {
        "event": event,
        "success": success,
        "user_id": user_id,
        "username": username,
        "reason": reason,
    }
    record.request_id = current_request_id or ""
    record.user_id = user_id or ""
    logger.handle(record)
