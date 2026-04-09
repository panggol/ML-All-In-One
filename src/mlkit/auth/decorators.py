"""
Auth 装饰器

提供 @login_required 和 @admin_required 装饰器，
保护 API 端点或函数调用。

用法：
    from mlkit.auth import login_required, admin_required, get_current_user

    @login_required
    def train_model(token: str, config: dict):
        user = get_current_user(token)
        print(f"训练由 {user.username} 发起")

    @admin_required
    def delete_all_experiments(token: str):
        ...
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional

from mlkit.auth.jwt_handler import JWTError
from mlkit.auth.models import User
from mlkit.auth.service import get_auth_service


def get_current_user(token: str) -> Optional[User]:
    """从 token 获取当前用户（供被保护函数使用）"""
    auth = get_auth_service()
    return auth.get_current_user(token)


class AuthError(Exception):
    """认证/授权错误"""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


def login_required(func: Callable) -> Callable:
    """
    装饰器：要求用户已登录

    被装饰的函数必须接受 token 参数（位置或关键字）。

    用法：
        @login_required
        def train(token: str, config: dict):
            user = get_current_user(token)
            ...
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        # 从 args/kwargs 中找 token
        token = _extract_token(args, kwargs)
        if token is None:
            raise AuthError("未提供认证 token", 401)

        auth = get_auth_service()
        user = auth.get_current_user(token)
        if user is None:
            raise AuthError("Token 无效或已过期", 401)

        if not user.is_active:
            raise AuthError("账号已被禁用", 403)

        # 把 user 注入到 kwargs，方便被装饰函数使用
        # user 已通过 get_current_user(token) 提供
        # kwargs["_auth_user"] = user
        return func(*args, **kwargs)

    return wrapper


def admin_required(func: Callable) -> Callable:
    """
    装饰器：要求用户是 admin 角色

    用法：
        @admin_required
        def delete_all_data(token: str):
            ...
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        token = _extract_token(args, kwargs)
        if token is None:
            raise AuthError("未提供认证 token", 401)

        auth = get_auth_service()
        user = auth.get_current_user(token)
        if user is None:
            raise AuthError("Token 无效或已过期", 401)

        if not user.is_active:
            raise AuthError("账号已被禁用", 403)

        if user.role != "admin":
            raise AuthError("需要管理员权限", 403)

        # user 已通过 get_current_user(token) 提供
        # kwargs["_auth_user"] = user
        return func(*args, **kwargs)

    return wrapper


def _extract_token(args: tuple, kwargs: dict) -> Optional[str]:
    """从 args/kwargs 中提取 token"""
    # kwargs["token"]
    token = kwargs.get("token")
    if token:
        return token

    # positional: token 是第一个参数
    if args:
        token = args[0]
        if isinstance(token, str):
            return token

    return None
