"""
Auth 服务核心

处理用户注册、登录、Token 验证等核心逻辑。
支持内存存储（演示用）和扩展到数据库。
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
import yaml

from mlkit.auth.jwt_handler import JWTHandler, JWTError
from mlkit.auth.models import User, TokenData

# 全局变量用于存储用户（生产环境应替换为数据库）
_USERS: dict[str, User] = {}  # user_id -> User
_USERNAME_INDEX: dict[str, str] = {}  # username -> user_id
_JWT_HANDLER: Optional[JWTHandler] = None
_JWT_SECRET: str = ""


def _get_jwt_handler(secret_key: str | None = None, **kwargs) -> JWTHandler:
    """获取或创建全局 JWT Handler"""
    global _JWT_HANDLER, _JWT_SECRET
    if _JWT_HANDLER is None:
        if secret_key is None:
            secret_key = _JWT_SECRET or os.environ.get("MLKIT_JWT_SECRET", "")
            if not secret_key:
                raise RuntimeError(
                    "JWT secret_key not configured. "
                    "Call set_jwt_secret() first or set MLKIT_JWT_SECRET env var."
                )
        _JWT_SECRET = secret_key
        _JWT_HANDLER = JWTHandler(secret_key, **kwargs)
    return _JWT_HANDLER


def set_jwt_secret(
    secret_key: str,
    expire_hours: int = 24,
) -> None:
    """
    配置全局 JWT 密钥（一次性配置，生产环境必须调用）

    Args:
        secret_key: JWT 签名密钥（至少 16 字符）
        expire_hours: Token 过期小时数
    """
    global _JWT_HANDLER, _JWT_SECRET
    _JWT_SECRET = secret_key
    _JWT_HANDLER = JWTHandler(secret_key, expire_hours=expire_hours)


class AuthService:
    """
    认证服务

    提供用户注册、登录、Token 验证等核心功能。
    默认使用内存存储，可通过 load_users() 从文件加载。

    用法：
        # 配置（只需一次）
        set_jwt_secret("your-secret-key-at-least-16-chars")

        auth = get_auth_service()
        auth.register("alice", "password123")
        token = auth.login("alice", "password123")
        user = auth.verify_token(token)
    """

    def __init__(
        self,
        jwt_secret: str | None = None,
        token_expire_hours: int = 24,
        users_file: str | Path | None = None,
    ):
        # jwt_secret 参数优先，否则用全局 _JWT_SECRET
        effective_secret = jwt_secret or _JWT_SECRET
        self._jwt_handler = _get_jwt_handler(effective_secret, expire_hours=token_expire_hours)
        self._token_expire_hours = token_expire_hours
        self._users: dict[str, User] = _USERS
        self._username_index: dict[str, str] = _USERNAME_INDEX
        self._users_file = users_file

        if users_file and Path(users_file).exists():
            self.load_users(users_file)

    # ========== 用户注册 ==========

    def register(
        self,
        username: str,
        password: str,
        role: str = "user",
    ) -> User:
        """
        注册新用户

        Args:
            username: 用户名（唯一，至少 3 字符）
            password: 明文密码（会被 bcrypt hash，至少 8 字符）
            role: 角色，"user" 或 "admin"

        Returns:
            User 对象
        """
        username = username.strip().lower()
        if len(username) < 3:
            raise ValueError("用户名至少需要 3 个字符")

        self._validate_password(password)

        if username in self._username_index:
            raise ValueError(f"用户名 '{username}' 已存在")

        password_hash = self._hash_password(password)
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
        )

        self._users[user.user_id] = user
        self._username_index[username] = user.user_id
        self._save_users()

        return user

    def _validate_password(self, password: str) -> None:
        if len(password) < 8:
            raise ValueError("密码至少需要 8 个字符")
        if password.lower() in ("password", "12345678", "qwerty123", "abcd1234"):
            raise ValueError("密码强度太弱，请使用更复杂的密码")

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

    # ========== 登录 ==========

    def login(self, username: str, password: str) -> str:
        """
        用户登录

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            JWT token string
        """
        username = username.strip().lower()
        user = self.get_user_by_username(username)

        if user is None:
            # 防止用户名枚举：执行相同耗时操作
            bcrypt.hashpw(b"fake", bcrypt.gensalt())
            raise ValueError("用户名或密码错误")

        if not user.is_active:
            raise ValueError("账号已被禁用")

        if not user.verify_password(password):
            raise ValueError("用户名或密码错误")

        return self._jwt_handler.create_token(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
        )

    def logout(self, token: str) -> bool:
        """登出（JWT 无状态，由客户端删除 token）"""
        return True

    # ========== Token 验证 ==========

    def verify_token(self, token: str) -> TokenData:
        """验证 JWT Token"""
        return self._jwt_handler.verify_token(token)

    def get_current_user(self, token: str) -> Optional[User]:
        """从 Token 获取当前用户"""
        try:
            data = self.verify_token(token)
            return self.get_user(data.user_id)
        except JWTError:
            return None

    # ========== 用户查询 ==========

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        username = username.strip().lower()
        uid = self._username_index.get(username)
        return self._users.get(uid) if uid else None

    def list_users(self) -> list[dict]:
        return [u.to_dict() for u in self._users.values()]

    def delete_user(self, user_id: str) -> bool:
        user = self._users.pop(user_id, None)
        if user:
            self._username_index.pop(user.username, None)
            self._save_users()
            return True
        return False

    # ========== 持久化 ==========

    def _save_users(self) -> None:
        if self._users_file is None:
            return
        path = Path(self._users_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {uid: u.to_dict(include_hash=True) for uid, u in self._users.items()}
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)

    def load_users(self, path: str | Path) -> int:
        path = Path(path)
        if not path.exists():
            return 0
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        count = 0
        for uid, udata in data.items():
            user = User(
                user_id=uid,
                username=udata["username"],
                password_hash=udata["password_hash"],
                role=udata.get("role", "user"),
                is_active=udata.get("is_active", True),
            )
            self._users[uid] = user
            self._username_index[user.username] = uid
            count += 1
        return count


# ========== 全局单例 ==========

_AUTH_SERVICE: Optional[AuthService] = None


def get_auth_service(
    jwt_secret: str | None = None,
    token_expire_hours: int = 24,
    users_file: str | Path | None = None,
) -> AuthService:
    """
    获取全局 AuthService 单例

    第一次调用时创建实例，之后返回同一实例。

    Args:
        jwt_secret: JWT 签名密钥。不传则从环境变量 MLKIT_JWT_SECRET 读取。
        token_expire_hours: Token 过期小时数
        users_file: 用户数据持久化文件路径
    """
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        _AUTH_SERVICE = AuthService(
            jwt_secret=jwt_secret,
            token_expire_hours=token_expire_hours,
            users_file=users_file,
        )
    return _AUTH_SERVICE
