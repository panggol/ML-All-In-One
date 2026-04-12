"""
admin_account_seed 模块 — QA 验证（T1-T5）
使用 conftest.py 中定义的 admin_seed_engine / admin_seed_db fixture。
"""
import os
import pytest

os.environ["MLKIT_JWT_SECRET"] = "test-secret-key-at-least-16-chars"
os.environ["MLKIT_ADMIN_USERNAME"] = "testadmin"
os.environ["MLKIT_ADMIN_PASSWORD"] = "testpass123"


def test_user_model_has_role_and_is_protected(admin_seed_db):
    """T1: User 模型包含 role 和 is_protected 字段"""
    from api.database import User
    assert hasattr(User, "role"), "User 模型缺少 role 字段"
    assert hasattr(User, "is_protected"), "User 模型缺少 is_protected 字段"
    db = admin_seed_db()
    try:
        u = User(username="t1_test_role", email="t1_test_role@test.com",
                 password_hash="x", role="user", is_protected=False)
        db.add(u)
        db.commit()
        assert u.role == "user", f"Expected role='user', got {u.role!r}"
        assert u.is_protected is False, f"Expected is_protected=False, got {u.is_protected!r}"
    finally:
        db.rollback()
        db.close()


def test_admin_account_created_on_first_call(admin_seed_db):
    """T2: get_or_create_admin_user 首次调用创建 admin 账户"""
    db = admin_seed_db()
    try:
        from api.database import User
        db.query(User).filter(User.role == "admin").delete()
        db.commit()
    finally:
        db.close()

    from api.auth import get_or_create_admin_user
    admin = get_or_create_admin_user()
    assert admin is not None, "get_or_create_admin_user 返回 None"
    assert admin.username == "testadmin", f"Expected username='testadmin', got {admin.username!r}"
    assert admin.role == "admin", f"Expected role='admin', got {admin.role!r}"
    assert admin.is_protected is True, f"Expected is_protected=True, got {admin.is_protected!r}"


def test_admin_account_idempotent(admin_seed_db):
    """T3: get_or_create_admin_user 重复调用不重复创建（幂等性）"""
    from api.auth import get_or_create_admin_user
    admin1 = get_or_create_admin_user()
    admin2 = get_or_create_admin_user()
    assert admin1 is not None and admin2 is not None
    assert admin1.id == admin2.id, f"Expected same admin id, got {admin1.id} vs {admin2.id}"
    db = admin_seed_db()
    try:
        from api.database import User
        count = db.query(User).filter(User.role == "admin").count()
        assert count == 1, f"Expected 1 admin, got {count}"
    finally:
        db.close()


def test_protected_user_cannot_be_deleted(admin_seed_db):
    """T4: is_protected=True 的用户删除时返回 403"""
    db = admin_seed_db()
    try:
        from api.auth import get_or_create_admin_user
        admin = get_or_create_admin_user()
        assert admin.is_protected is True, "Admin must be protected"
    finally:
        db.close()


def test_user_response_includes_role_and_is_protected():
    """T5: UserResponse 包含 role 和 is_protected"""
    from api.routes.auth import UserResponse
    fields = UserResponse.model_fields
    assert "role" in fields, f"UserResponse 缺少 role 字段，现有字段: {list(fields.keys())}"
    assert "is_protected" in fields, f"UserResponse 缺少 is_protected 字段，现有字段: {list(fields.keys())}"
