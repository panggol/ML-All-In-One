"""
admin_account_seed 模块 — T6 API 集成测试
使用 conftest.py 中定义的 admin_seed_engine fixture。
"""
import os
import pytest

os.environ["MLKIT_JWT_SECRET"] = "test-secret-key-at-least-16-chars"
os.environ["MLKIT_ADMIN_USERNAME"] = "testadmin"
os.environ["MLKIT_ADMIN_PASSWORD"] = "testpass123"

from fastapi.testclient import TestClient


def test_admin_can_login_and_access_me(admin_seed_engine):
    """
    T6: admin 账户可以登录并访问 /me
    使用 conftest 提供的 admin_seed_engine fixture，确保 DB 隔离且 SessionLocal 正确 patch。
    """
    # admin_seed_engine fixture 已 patch api.auth.SessionLocal
    from api.auth import get_or_create_admin_user

    # 确保 admin 存在（使用 fixture 的 DB）
    admin = get_or_create_admin_user()
    assert admin is not None
    assert admin.username == "testadmin"
    assert admin.role == "admin"
    assert admin.is_protected is True

    # patch main app 的 get_db
    from sqlalchemy.orm import sessionmaker
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
    client = TestClient(app)

    print("\n--- T6: Admin login + /me ---")
    resp = client.post("/api/auth/login", json={"username": "testadmin", "password": "testpass123"})
    print(f"Login status: {resp.status_code}, body: {resp.text}")
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json()["access_token"]
    print(f"Token received: {token[:20]}...")

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    print(f"/me status: {me.status_code}, body: {me.text}")
    assert me.status_code == 200, f"/me failed: {me.text}"
    body = me.json()
    assert body["role"] == "admin", f"Expected role='admin', got {body.get('role')!r}"
    assert body["is_protected"] is True, f"Expected is_protected=True, got {body.get('is_protected')!r}"
    print("✅ T6 PASSED: Admin login + /me returned correct role and is_protected")
