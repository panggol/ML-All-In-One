"""
JWT 认证模块
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from api.database import User, get_db, SessionLocal
from api.middleware.logging_middleware import log_login_event

# 配置
import os

logger = logging.getLogger(__name__)

# 优先使用 MLKIT_JWT_SECRET，兼容旧名 JWT_SECRET_KEY
SECRET_KEY = os.getenv("MLKIT_JWT_SECRET") or os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY / MLKIT_JWT_SECRET environment variable is required. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Bearer Token
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """哈希密码"""
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """解码 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前登录用户（依赖注入）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失败，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    return current_user


def get_or_create_admin_user():
    """
    服务启动时调用，确保存在一个 admin 账户（幂等）。
    - 检查 User.role == "admin" 是否已存在
    - 存在 → DEBUG 日志，不重复创建
    - 不存在 → 创建，INFO 日志
    """
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == "admin").first()
        if existing:
            logger.debug("Admin account already exists, skipping")
            return existing

        username = os.getenv("MLKIT_ADMIN_USERNAME", "admin")
        password = os.getenv("MLKIT_ADMIN_PASSWORD", "admin123")
        if username == "admin" and password == "admin123":
            logger.warning(
                "⚠️  [SECURITY] Default admin password 'admin123' is in use. "
                "Please set MLKIT_ADMIN_PASSWORD env var to change it."
            )
        admin = User(
            username=username,
            email="admin@admin.local",
            password_hash=get_password_hash(password),
            role="admin",
            is_protected=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info(f"Admin account created: {username}")
        return admin
    except Exception as e:
        logger.warning(f"Failed to create admin account: {e}")
        db.rollback()
        return None
    finally:
        db.close()
