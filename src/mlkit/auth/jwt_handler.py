"""
JWT Token 处理

提供 JWT Token 的创建和验证功能。
Harness Engineering 核心理念：安全第一，token 有过期时间。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import jwt

from mlkit.auth.models import TokenData


class JWTError(Exception):
    """JWT 相关错误"""
    pass


class JWTHandler:
    """
    JWT Token 处理器

    使用 HS256 算法，支持设置过期时间。
    """

    DEFAULT_EXPIRE_HOURS = 24  # 默认 24 小时过期

    def __init__(self, secret_key: str, expire_hours: int | None = None):
        """
        Args:
            secret_key: JWT 签名密钥（生产环境必须足够长且随机）
            expire_hours: Token 过期小时数，None 则永不超时（不推荐）
        """
        if not secret_key or len(secret_key) < 16:
            raise ValueError("secret_key must be at least 16 characters")
        self.secret_key = secret_key
        self.expire_hours = expire_hours or self.DEFAULT_EXPIRE_HOURS
        self.algorithm = "HS256"

    def create_token(
        self,
        user_id: str,
        username: str,
        role: str,
        expires_hours: int | None = None,
    ) -> str:
        """
        创建 JWT Token

        Args:
            user_id: 用户 ID
            username: 用户名
            role: 角色
            expires_hours: 手动指定过期小时数

        Returns:
            JWT token string
        """
        exp_hours = expires_hours or self.expire_hours
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=exp_hours)

        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "iat": now,  # issued at
            "exp": exp,  # expiration
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verify_token(self, token: str) -> TokenData:
        """
        验证 JWT Token

        Args:
            token: JWT token string

        Returns:
            TokenData 对象，包含用户信息

        Raises:
            JWTError: token 无效或已过期
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"require": ["exp", "user_id", "username", "role"]},
            )
            return TokenData(
                user_id=payload["user_id"],
                username=payload["username"],
                role=payload["role"],
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                token=token,
            )
        except jwt.ExpiredSignatureError:
            raise JWTError("Token 已过期，请重新登录")
        except jwt.InvalidTokenError as e:
            raise JWTError(f"Token 无效：{e}")

    def refresh_token(self, token: str) -> str:
        """
        刷新 Token（验证通过后颁发新的）

        Args:
            token: 旧 token

        Returns:
            新的 JWT token
        """
        data = self.verify_token(token)
        return self.create_token(
            user_id=data.user_id,
            username=data.username,
            role=data.role,
        )
