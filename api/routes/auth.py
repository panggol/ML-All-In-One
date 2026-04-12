"""
认证路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional

from api.database import User, get_db
from api.auth import get_password_hash, verify_password, create_access_token, get_current_user
from api.middleware.logging_middleware import log_login_event

router = APIRouter()

# ============ Pydantic 模型 ============

class UserCreate(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    """登录请求"""
    username: str
    password: str

class Token(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: str
    created_at: str
    role: str = "user"
    is_protected: bool = False

    model_config = ConfigDict(from_attributes=True)


# ============ 路由 ============

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否存在
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否存在
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被注册"
        )
    
    # 创建用户（role 强制为 "user"，不接受外部传入）
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password)
        # role 默认为 "user"，is_protected 默认为 False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at.isoformat(),
        role=user.role,
        is_protected=user.is_protected,
    )


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    # 查找用户（按用户名或邮箱）
    user = db.query(User).filter(
        (User.username == login_data.username) | (User.email == login_data.username)
    ).first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        log_login_event(
            user_id=str(user.id) if user else None,
            username=login_data.username,
            success=False,
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    if not user.is_active:
        log_login_event(
            user_id=str(user.id),
            username=user.username,
            success=False,
            reason="user_inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    # 创建 token (sub必须是string)
    access_token = create_access_token(data={"sub": str(user.id)})

    log_login_event(
        user_id=str(user.id),
        username=user.username,
        success=True,
        reason=None,
    )

    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at.isoformat(),
        role=current_user.role,
        is_protected=current_user.is_protected,
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """登出（前端删除 token 即可）"""
    return {"message": "已登出"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除指定用户。

    - **user_id**: 目标用户 ID
    - 受保护用户（is_protected=True 或 role='admin'）不可删除，返回 403
    - 不存在的用户返回 404
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if user.is_protected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="系统管理员账户不可删除")
    if current_user.role == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="管理员账户不可删除")

    db.delete(user)
    db.commit()
    return None
