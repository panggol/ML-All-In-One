"""
admin_users API — Constitution 要求的 9 个测试用例
测试 /api/admin/users 的完整 CRUD 行为与权限控制。
"""
import os
import pytest

os.environ["MLKIT_JWT_SECRET"] = "test-secret-key-at-least-16-chars"
os.environ["MLKIT_ADMIN_USERNAME"] = "testadmin"
os.environ["MLKIT_ADMIN_PASSWORD"] = "testpass123"

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


def _get_client(admin_seed_engine):
    """构建 TestClient，并 patch get_db 使用测试引擎。"""
    from api.main import app
    import api.database

    Session = sessionmaker(bind=admin_seed_engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[api.database.get_db] = override_get_db
    return TestClient(app), Session


def _login(client: TestClient, username: str, password: str) -> str:
    """Helper: 登录并返回 access_token。"""
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


# ============ Fixtures ============


@pytest.fixture
def setup_users(admin_seed_engine):
    """
    在测试数据库中准备 admin 和普通用户。
    admin: id=1, username=testadmin, role=admin, is_protected=True
    regular: id=2, username=regularuser, role=user, is_protected=False
    """
    from api.auth import get_or_create_admin_user, get_password_hash
    from api.database import User

    Session = sessionmaker(bind=admin_seed_engine)
    db = Session()

    # 确保 admin 存在
    admin = get_or_create_admin_user()
    assert admin.role == "admin"
    assert admin.is_protected is True

    # 确保 regular user 存在
    regular = db.query(User).filter(User.username == "regularuser").first()
    if not regular:
        regular = User(
            username="regularuser",
            email="regular@test.com",
            password_hash=get_password_hash("password123"),
            role="user",
            is_protected=False,
            is_active=True,
        )
        db.add(regular)
        db.commit()
        db.refresh(regular)

    db.close()
    return {"admin_id": admin.id, "regular_id": regular.id}


# ============ 测试用例 ============


def test_admin_get_users(admin_seed_engine, setup_users):
    """
    T1: admin 获取用户列表 → 200
    验证返回 total + users 数组，users 包含所有字段。
    """
    client, _ = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    resp = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    print(f"\n--- T1: GET /api/admin/users (admin) → {resp.status_code} ---")
    print(f"Body: {resp.text[:500]}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "total" in body, "Response must include 'total'"
    assert "users" in body, "Response must include 'users'"
    assert isinstance(body["users"], list), "users must be a list"

    # 验证用户字段完整
    if body["users"]:
        u = body["users"][0]
        for field in ("id", "username", "email", "role", "is_protected", "is_active", "created_at"):
            assert field in u, f"User object missing field: {field}"

    print("✅ T1 PASSED: admin 获取用户列表 200")


def test_admin_get_users_non_admin(admin_seed_engine, setup_users):
    """
    T2: 非 admin 用户访问 /api/admin/users → 403
    验证 Constitution S6：仅 admin 可访问管理 API。
    """
    client, _ = _get_client(admin_seed_engine)
    token = _login(client, "regularuser", "password123")

    resp = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    print(f"\n--- T2: GET /api/admin/users (non-admin) → {resp.status_code} ---")
    print(f"Body: {resp.text[:200]}")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "detail" in body, "403 response must include 'detail'"
    print("✅ T2 PASSED: 非 admin 用户访问返回 403")


def test_admin_create_user(admin_seed_engine, setup_users):
    """
    T3: admin 创建新用户 → 201
    验证返回用户信息（无 password_hash），包含所有字段。
    """
    client, _ = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    payload = {
        "username": "newtestuser",
        "email": "newtest@test.com",
        "password": "pass123456",
        "role": "user",
    }

    resp = client.post("/api/admin/users", json=payload, headers={"Authorization": f"Bearer {token}"})
    print(f"\n--- T3: POST /api/admin/users (create) → {resp.status_code} ---")
    print(f"Body: {resp.text[:500]}")
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body["username"] == "newtestuser"
    assert body["email"] == "newtest@test.com"
    assert body["role"] == "user"
    assert body["is_protected"] is False, "Newly created user should not be protected"
    assert body["is_active"] is True, "Newly created user should be active"
    assert "password_hash" not in body, "Response must NOT include password_hash"

    print("✅ T3 PASSED: admin 创建用户 201")


def test_admin_create_user_duplicate_username(admin_seed_engine, setup_users):
    """
    T4: admin 创建重复用户名 → 409
    验证 Constitution 要求：username 唯一性约束。
    """
    client, _ = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    payload = {
        "username": "regularuser",  # 已在 setup_users 中创建
        "email": "another@test.com",
        "password": "pass123456",
        "role": "user",
    }

    resp = client.post("/api/admin/users", json=payload, headers={"Authorization": f"Bearer {token}"})
    print(f"\n--- T4: POST /api/admin/users (duplicate username) → {resp.status_code} ---")
    print(f"Body: {resp.text[:200]}")
    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "detail" in body, "409 response must include 'detail'"
    print("✅ T4 PASSED: 重复用户名返回 409")


def test_admin_update_user(admin_seed_engine, setup_users):
    """
    T5: admin 更新普通用户信息 → 200
    验证 email 和 is_active 可被更新。
    """
    client, Session = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    # 获取 regular user id
    from api.database import User
    db = Session()
    regular = db.query(User).filter(User.username == "regularuser").first()
    regular_id = regular.id
    db.close()

    payload = {
        "email": "updated@test.com",
        "is_active": False,
    }

    resp = client.put(
        f"/api/admin/users/{regular_id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"\n--- T5: PUT /api/admin/users/{regular_id} (update) → {resp.status_code} ---")
    print(f"Body: {resp.text[:500]}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body["email"] == "updated@test.com"
    assert body["is_active"] is False
    print("✅ T5 PASSED: admin 更新用户 200")


def test_admin_update_protected_role(admin_seed_engine, setup_users):
    """
    T6: 尝试修改受保护用户角色 → 400
    验证 Constitution S3 + F2：受保护用户不可修改角色。
    """
    client, Session = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    # 获取受保护用户（admin）id
    from api.database import User
    db = Session()
    admin = db.query(User).filter(User.role == "admin").first()
    admin_id = admin.id
    db.close()

    payload = {"role": "user"}

    resp = client.put(
        f"/api/admin/users/{admin_id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"\n--- T6: PUT /api/admin/users/{admin_id} (protected role) → {resp.status_code} ---")
    print(f"Body: {resp.text[:200]}")
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "detail" in body
    assert "受保护" in body["detail"] or "protected" in body["detail"].lower()
    print("✅ T6 PASSED: 修改受保护用户角色返回 400")


def test_admin_delete_user(admin_seed_engine, setup_users):
    """
    T7: admin 删除普通用户 → 204
    验证 Constitution F5：普通用户可删除。
    """
    client, Session = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    # 先创建一个可删除的用户
    from api.database import User
    from api.auth import get_password_hash
    db = Session()
    deletable = User(
        username="deleteme",
        email="deleteme@test.com",
        password_hash=get_password_hash("password123"),
        role="user",
        is_protected=False,
        is_active=True,
    )
    db.add(deletable)
    db.commit()
    db.refresh(deletable)
    deletable_id = deletable.id
    db.close()

    resp = client.delete(
        f"/api/admin/users/{deletable_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"\n--- T7: DELETE /api/admin/users/{deletable_id} (normal user) → {resp.status_code} ---")
    assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
    print("✅ T7 PASSED: admin 删除普通用户 204")


def test_admin_delete_protected(admin_seed_engine, setup_users):
    """
    T8: 尝试删除受保护用户 → 403
    验证 Constitution S3 + F5：受保护用户不可删除。
    """
    client, Session = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    from api.database import User
    db = Session()
    admin = db.query(User).filter(User.role == "admin").first()
    admin_id = admin.id
    db.close()

    resp = client.delete(
        f"/api/admin/users/{admin_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"\n--- T8: DELETE /api/admin/users/{admin_id} (protected) → {resp.status_code} ---")
    print(f"Body: {resp.text[:200]}")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "detail" in body
    print("✅ T8 PASSED: 删除受保护用户返回 403")


def test_admin_delete_self(admin_seed_engine, setup_users):
    """
    T9: 尝试删除自己 → 403
    验证 Constitution S2：admin 不能删除自己的账户。
    """
    client, Session = _get_client(admin_seed_engine)
    token = _login(client, "testadmin", "testpass123")

    from api.database import User
    db = Session()
    admin = db.query(User).filter(User.role == "admin").first()
    admin_id = admin.id
    db.close()

    resp = client.delete(
        f"/api/admin/users/{admin_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"\n--- T9: DELETE /api/admin/users/{admin_id} (self) → {resp.status_code} ---")
    print(f"Body: {resp.text[:200]}")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert "detail" in body
    print("✅ T9 PASSED: 删除自己返回 403")
