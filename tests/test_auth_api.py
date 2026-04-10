"""
Auth API 单元测试 + 集成测试

测试所有 /api/auth 端点：
- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me
- POST /api/auth/logout

覆盖正常流程和错误处理。
使用 FastAPI TestClient + 内存数据库 + dependency_overrides。
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

# 添加 api 到 sys.path（与其他测试保持一致）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import Base, User, get_db
from api.main import app
from api.auth import get_current_user


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """构建 FastAPI 测试客户端，使用内存数据库"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db_session = TestingSession()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app), db_session

    app.dependency_overrides.clear()
    db_session.close()


@pytest.fixture
def registered_user(client):
    """创建一个已注册的用户（供其他测试复用）"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def auth_token(client, registered_user):
    """获取已注册用户的登录 token"""
    c, db = client
    resp = c.post("/api/auth/login", json={
        "username": "alice",
        "password": "password123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

def test_register_success(client):
    """正常注册返回 201"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "securepass123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "created_at" in data
    # 密码不应返回
    assert "password" not in data
    assert "password_hash" not in data


def test_register_username_exists(client, registered_user):
    """用户名已存在返回 409"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "alice",          # 已存在
        "email": "another@example.com",
        "password": "password123",
    })
    assert resp.status_code == 409
    assert resp.json()["detail"] == "用户名已存在"


def test_register_email_exists(client, registered_user):
    """邮箱已存在返回 409"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "bob",
        "email": "alice@example.com",  # 已存在
        "password": "password123",
    })
    assert resp.status_code == 409
    assert resp.json()["detail"] == "邮箱已被注册"


def test_register_invalid_password_too_short(client):
    """密码太短返回 422"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "12345",  # 不足 6 字符
    })
    assert resp.status_code == 422


def test_register_invalid_password_too_short_2(client):
    """密码为空返回 422"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "",
    })
    assert resp.status_code == 422


def test_register_missing_fields(client):
    """缺少必填字段返回 422"""
    c, db = client
    # 缺 username
    resp = c.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert resp.status_code == 422

    # 缺 email
    resp = c.post("/api/auth/register", json={
        "username": "testuser",
        "password": "password123",
    })
    assert resp.status_code == 422

    # 缺 password
    resp = c.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
    })
    assert resp.status_code == 422


def test_register_username_too_short(client):
    """用户名太短返回 422"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "ab",          # 不足 3 字符
        "email": "test@example.com",
        "password": "password123",
    })
    assert resp.status_code == 422


def test_register_invalid_email(client):
    """无效邮箱格式返回 422"""
    c, db = client
    resp = c.post("/api/auth/register", json={
        "username": "testuser",
        "email": "not-an-email",
        "password": "password123",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

def test_login_success(client, registered_user):
    """正确凭据返回 token"""
    c, db = client
    resp = c.post("/api/auth/login", json={
        "username": "alice",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0


def test_login_user_not_found(client):
    """用户不存在返回 401"""
    c, db = client
    resp = c.post("/api/auth/login", json={
        "username": "nobody",
        "password": "password123",
    })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "用户名或密码错误"


def test_login_wrong_password(client, registered_user):
    """密码错误返回 401"""
    c, db = client
    resp = c.post("/api/auth/login", json={
        "username": "alice",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "用户名或密码错误"


def test_login_email_as_username(client, registered_user):
    """使用邮箱作为用户名登录成功"""
    c, db = client
    resp = c.post("/api/auth/login", json={
        "username": "alice@example.com",  # 使用邮箱登录
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_missing_password(client):
    """缺少密码字段返回 422"""
    c, db = client
    resp = c.post("/api/auth/login", json={
        "username": "alice",
    })
    assert resp.status_code == 422


def test_login_inactive_user(client):
    """被禁用的用户登录返回 403"""
    c, db = client
    # 注册用户
    resp = c.post("/api/auth/register", json={
        "username": "inactive_user",
        "email": "inactive@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201

    # 禁用用户
    user = db.query(User).filter(User.username == "inactive_user").first()
    user.is_active = False
    db.commit()

    # 尝试登录
    resp = c.post("/api/auth/login", json={
        "username": "inactive_user",
        "password": "password123",
    })
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

def test_me_success(client, registered_user, auth_token):
    """有效token返回用户信息"""
    c, db = client
    resp = c.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "id" in data
    assert "created_at" in data


def test_me_no_token(client):
    """无token返回401"""
    c, db = client
    resp = c.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_invalid_token(client):
    """无效token返回401"""
    c, db = client
    resp = c.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert resp.status_code == 401


def test_me_malformed_auth_header(client):
    """格式错误的 Authorization header 返回 401"""
    c, db = client
    resp = c.get(
        "/api/auth/me",
        headers={"Authorization": "NotBearer sometoken"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

def test_logout_success(client, auth_token):
    """登出成功（JWT无状态，返回200）"""
    c, db = client
    resp = c.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "已登出"


def test_logout_no_token(client):
    """无token登出返回401"""
    c, db = client
    resp = c.post("/api/auth/logout")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 认证保护验证
# ---------------------------------------------------------------------------

def test_protected_routes_require_auth(client):
    """验证 /api/train, /api/experiments, /api/models 等端点需要认证"""
    c, db = client

    # GET /api/train  (训练任务列表)
    resp = c.get("/api/train")
    assert resp.status_code == 401, f"Expected 401 for /api/train, got {resp.status_code}"

    # GET /api/experiments/  (实验列表)
    resp = c.get("/api/experiments/")
    assert resp.status_code == 401, f"Expected 401 for /api/experiments/, got {resp.status_code}"

    # GET /api/models/  (模型列表)
    resp = c.get("/api/models/")
    assert resp.status_code == 401, f"Expected 401 for /api/models/, got {resp.status_code}"

    # POST /api/train  (提交训练任务，空body)
    resp = c.post("/api/train", json={})
    assert resp.status_code == 401, f"Expected 401 for POST /api/train, got {resp.status_code}"


def test_protected_routes_with_valid_token(client, auth_token):
    """带有效 token 可以访问受保护端点（返回非 401）"""
    c, db = client
    headers = {"Authorization": f"Bearer {auth_token}"}

    resp = c.get("/api/train", headers=headers)
    assert resp.status_code != 401, "Should not return 401 with valid token"

    resp = c.get("/api/experiments/", headers=headers)
    assert resp.status_code != 401, "Should not return 401 with valid token"

    resp = c.get("/api/models/", headers=headers)
    assert resp.status_code != 401, "Should not return 401 with valid token"


# ---------------------------------------------------------------------------
# 集成测试：完整认证流程
# ---------------------------------------------------------------------------

def test_full_auth_flow_register_login_me(client):
    """完整流程：注册 → 登录 → 获取用户信息"""
    c, db = client

    # 1. 注册
    resp = c.post("/api/auth/register", json={
        "username": "bob",
        "email": "bob@example.com",
        "password": "bobpass123",
    })
    assert resp.status_code == 201
    user_data = resp.json()
    assert user_data["username"] == "bob"
    assert user_data["email"] == "bob@example.com"

    # 2. 登录
    resp = c.post("/api/auth/login", json={
        "username": "bob",
        "password": "bobpass123",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert len(token) > 0

    # 3. 获取用户信息
    resp = c.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    me_data = resp.json()
    assert me_data["username"] == "bob"
    assert me_data["email"] == "bob@example.com"
