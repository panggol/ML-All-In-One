"""
Auth 系统使用示例

展示完整的注册 → 登录 → 受保护API 调用流程。

Harness Engineering 核心理念：
- 密码永不明文存储（bcrypt hash）
- Token 有过期时间
- 角色权限分离（user / admin）
"""

from mlkit.auth import (
    get_auth_service,
    login_required,
    admin_required,
    get_current_user,
    set_jwt_secret,
)
from mlkit.auth.models import User

# 1. 配置（只需一次）
set_jwt_secret(
    secret_key="my-super-secret-key-at-least-16-chars!",
    expire_hours=24,  # Token 24 小时过期
)

# 2. 获取 AuthService 单例
auth = get_auth_service()

print("=" * 50)
print("用户注册")
print("=" * 50)

# 注册普通用户
alice = auth.register("alice", "SecurePass123!")
print(f"✅ alice 注册成功: {alice.username} (role={alice.role})")

# 注册管理员
admin_user = auth.register("admin", "AdminPass999!", role="admin")
print(f"✅ admin 注册成功: {admin_user.username} (role={admin_user.role})")

print()
print("=" * 50)
print("用户登录")
print("=" * 50)

# 正确密码
token = auth.login("alice", "SecurePass123!")
print(f"✅ 登录成功")
print(f"   Token: {token[:50]}...")

# 错误密码
try:
    auth.login("alice", "wrong")
except ValueError as e:
    print(f"✅ 错误密码: {e}")

print()
print("=" * 50)
print("Token 验证")
print("=" * 50)

# 验证 token
data = auth.verify_token(token)
print(f"✅ Token 有效")
print(f"   用户: {data.username}")
print(f"   角色: {data.role}")
print(f"   过期: {data.exp}")

# 从 token 获取用户
user = auth.get_current_user(token)
print(f"✅ get_current_user: {user.username} (id={user.user_id[:8]}...)")

# 无效 token
try:
    auth.verify_token("invalid.token.here")
except Exception as e:
    print(f"✅ 无效 token: {e}")

print()
print("=" * 50)
print("受保护 API 示例（装饰器）")
print("=" * 50)


# 普通用户 API
@login_required
def train_model(token: str, config: dict) -> dict:
    """训练模型（需要登录）"""
    user = get_current_user(token)
    print(f"   🚀 {user.username} 开始训练，config={config}")
    return {"status": "ok", "trained_by": user.username}


# 管理员 API
@admin_required
def delete_all_experiments(token: str) -> dict:
    """删除所有实验（仅管理员）"""
    user = get_current_user(token)
    print(f"   🗑️  {user.username} 删除所有实验")
    return {"status": "deleted"}


# 测试 login_required
result = train_model(token, {"epochs": 10})
print(f"✅ login_required OK: {result}")

# 测试 admin_required（alice 是普通用户，应该被拒绝）
try:
    delete_all_experiments(token)  # alice 的 token
except Exception as e:
    print(f"✅ admin_required 拦截: {e}")

# 用 admin token 调用
admin_token = auth.login("admin", "AdminPass999!")
admin_result = delete_all_experiments(admin_token)
print(f"✅ admin 调用成功: {admin_result}")

print()
print("=" * 50)
print("用户管理")
print("=" * 50)

# 列出所有用户（密码不会泄露）
for u in auth.list_users():
    print(f"   👤 {u['username']} | role={u['role']} | active={u['is_active']}")

print()
print("Auth 系统演示完成！✅")
