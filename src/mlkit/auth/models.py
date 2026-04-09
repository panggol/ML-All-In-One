"""
Auth 数据模型
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """
    用户模型

    密码以 bcrypt hash 形式存储，永不明文。
    """

    username: str
    password_hash: str  # bcrypt hash，永不存储明文密码
    role: str = "user"  # "user" | "admin"
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

    # 认证相关（不持久化）
    token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

    def __post_init__(self):
        if self.role not in ("user", "admin"):
            raise ValueError(f"Invalid role: {self.role}")

    def verify_password(self, password: str) -> bool:
        """验证密码，返回 True/False"""
        import bcrypt

        return bcrypt.checkpw(
            password.encode("utf-8"),
            self.password_hash.encode("utf-8")
        )

    def to_dict(self, include_hash: bool = False) -> dict:
        """序列化为字典"""
        result = {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
        }
        if include_hash:
            result["password_hash"] = self.password_hash
        return result


@dataclass
class TokenData:
    """JWT Token 解析结果"""

    user_id: str
    username: str
    role: str
    exp: datetime
    token: str
