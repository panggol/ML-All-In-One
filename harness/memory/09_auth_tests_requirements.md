# Auth 路由测试需求文档

**模块：** 后端 Auth API 单元测试 + 集成测试  
**Harness 阶段：** Step 1 需求分析  
**日期：** 2026-04-10  
**项目：** ml-all-in-one  

---

## 1. 背景

当前 `tests/` 目录下 auth 路由完全无单元测试。auth 是系统安全核心，必须有完整覆盖。

---

## 2. 需测试的 API 端点

### 2.1 POST /api/auth/register
| 用例 | 输入 | 预期 |
|------|------|------|
| 正常注册 | 合法 username/email/password | 201，返回用户信息 |
| 用户名已存在 | 已注册的用户名 | 400，`{"detail": "用户名已存在"}` |
| email 已存在 | 已注册的 email | 400，`{"detail": "邮箱已被注册"}` |
| 无效密码格式 | 短密码 | 422，Pydantic 验证错误 |
| 缺少必填字段 | 缺 email | 422，Pydantic 验证错误 |

### 2.2 POST /api/auth/login
| 用例 | 输入 | 预期 |
|------|------|------|
| 正常登录 | 正确的用户名+密码 | 200，返回 access_token |
| 用户不存在 | 未注册的用户名 | 401，`{"detail": "用户名或密码错误"}` |
| 密码错误 | 正确用户名+错误密码 | 401，`{"detail": "用户名或密码错误"}` |
| 缺少字段 | 缺 password | 422 |

### 2.3 GET /api/auth/me
| 用例 | 头部 | 预期 |
|------|------|------|
| 正常 Token | 有效 Bearer Token | 200，返回用户信息 |
| 无 Token | 未带 Authorization | 401，`{"detail": "Not authenticated"}` |
| 无效 Token | 格式错误/过期 | 401 |

### 2.4 @login_required 依赖保护
验证以下端点需要认证：
- `GET /api/train`
- `GET /api/experiments/`
- `GET /api/models/`

---

## 3. 测试实现方式

### 3.1 单元测试（FastAPI TestClient）
- 使用 `from fastapi.testclient import TestClient`
- 绕过认证，直接测路由逻辑
- 使用 `app.dependency_overrides` 覆盖认证依赖

### 3.2 集成测试（pytest + 真实数据库）
- 使用临时数据库 session
- 测试完整的认证流程（注册→登录→访问受保护资源）

---

## 4. 验收标准

| # | 标准 |
|---|------|
| AC1 | `POST /api/auth/register` 正常注册返回 201 |
| AC2 | `POST /api/auth/register` 用户名已存在返回 400 |
| AC3 | `POST /api/auth/login` 正确凭据返回 token |
| AC4 | `POST /api/auth/login` 错误密码返回 401 |
| AC5 | `GET /api/auth/me` 带有效 token 返回用户信息 |
| AC6 | `GET /api/auth/me` 无 token 返回 401 |
| AC7 | 所有 207 原有用例仍然通过 |
| AC8 | pytest 运行时新增 auth 测试全部通过 |
