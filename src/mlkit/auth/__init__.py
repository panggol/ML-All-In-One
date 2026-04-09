"""
Auth 系统 - 用户认证与授权

Harness Engineering 核心理念：
- 安全是底线，不妥协
- 简洁的 API，安全的实现

功能：
- 用户注册（密码 bcrypt hash）
- JWT 登录（无状态认证）
- Token 验证（装饰器保护）
- 角色权限（user / admin）
"""

from mlkit.auth.models import User, TokenData
from mlkit.auth.service import AuthService, get_auth_service, set_jwt_secret
from mlkit.auth.decorators import login_required, admin_required, get_current_user

__all__ = [
    "User",
    "TokenData",
    "AuthService",
    "get_auth_service",
    "set_jwt_secret",
    "login_required",
    "admin_required",
    "get_current_user",
]
