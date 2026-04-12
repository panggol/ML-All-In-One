"""
管理员用户管理 API
仅 role="admin" 可访问，支持用户 CRUD 操作
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List, Literal
from enum import Enum

from api.database import User, get_db
from api.auth import get_password_hash, get_current_user

router = APIRouter()
security = HTTPBearer()

# ============ Pydantic 模型 ============


class RoleEnum(str, Enum):
    """角色枚举"""
    user = "user"
    admin = "admin"


class AdminUserResponse(BaseModel):
    """用户信息响应（管理员视角，不含 password_hash）"""
    id: int
    username: str
    email: str
    role: str
    is_protected: bool
    is_active: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """用户列表响应（含分页）"""
    total: int
    page: int
    page_size: int
    users: List[AdminUserResponse]


class CreateUserRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: RoleEnum = RoleEnum.user


class UpdateUserRequest(BaseModel):
    """更新用户请求（所有字段可选）"""
    email: Optional[EmailStr] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None


# ============ 依赖：Admin 权限校验 ============


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Admin 权限依赖：非 admin 用户抛出 403"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员权限不足"
        )
    return current_user


# ============ 辅助函数 ============


def _user_to_response(user: User) -> AdminUserResponse:
    """将 User ORM 模型转换为 AdminUserResponse"""
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_protected=user.is_protected,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


# ============ 路由 ============


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserListResponse:
    """
    获取用户列表（分页）

    - **权限**：仅 admin 可访问
    - **返回**：total + 分页用户列表
    """
    total = db.query(User).count()
    offset = (page - 1) * page_size
    users = (
        db.query(User)
        .order_by(User.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return UserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        users=[_user_to_response(u) for u in users],
    )


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: CreateUserRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    """
    创建新用户

    - **权限**：仅 admin 可访问
    - **约束**：username/email 唯一
    - **返回**：新用户信息（无 password_hash）
    """
    # 检查用户名唯一性
    existing_username = db.query(User).filter(User.username == req.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在"
        )

    # 检查邮箱唯一性
    existing_email = db.query(User).filter(User.email == req.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被注册"
        )

    # 创建用户
    user = User(
        username=req.username,
        email=req.email,
        password_hash=get_password_hash(req.password),
        role=req.role.value,  # RoleEnum → str
        is_protected=False,   # 新建用户默认非受保护
        is_active=True,       # 新建用户默认启用
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _user_to_response(user)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    req: UpdateUserRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    """
    更新用户信息（role/email/is_active）

    - **权限**：仅 admin 可访问
    - **业务规则**：
      - 受保护用户不可修改 role
      - 不可降级自己的角色
      - 仅更新传入的字段
    """
    # 查找目标用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 业务规则：受保护用户不可修改 role
    if req.role is not None and user.is_protected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="受保护用户不可修改角色"
        )

    # 业务规则：不可降级自己的管理员角色
    if req.role is not None and admin_user.id == user.id and req.role == RoleEnum.user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能修改自己的管理员角色"
        )

    # 业务规则：不可修改自己的 role 为非 admin（但可以修改自己邮箱）
    # 即：普通管理员无法把自己的 role 改为 user

    # 检查新 email 是否与其他用户冲突（如果 email 有变化）
    if req.email is not None and req.email != user.email:
        conflict = db.query(User).filter(User.email == req.email, User.id != user_id).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已被注册"
            )

    # 部分更新：仅修改传入的字段
    if req.email is not None:
        user.email = req.email
    if req.role is not None:
        user.role = req.role.value
    if req.is_active is not None:
        user.is_active = req.is_active

    db.commit()
    db.refresh(user)

    return _user_to_response(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """
    删除指定用户

    - **权限**：仅 admin 可访问
    - **业务规则**：
      - 受保护用户不可删除
      - 不可删除自己
      - 不存在的用户返回 404
    """
    # 查找目标用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 业务规则：不可删除自己（优先级最高）
    if admin_user.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能删除自己的账户"
        )

    # 业务规则：受保护用户不可删除
    if user.is_protected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="受保护用户不可删除"
        )

    db.delete(user)
    db.commit()
