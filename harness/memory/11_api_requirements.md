# ML All In One - API后端与认证需求补充

**文档版本：** v2.0  
**更新日期：** 2026-04-09  
**基于：** v1.0 需求文档

---

## 1. 概述

本文档补充 ML All In One 平台的 API 后端需求和认证需求，与 React 前端集成，提供完整的机器学习训练服务。

---

## 2. API 后端需求

### 2.1 技术栈
- **框架**：FastAPI
- **数据库**：SQLite（轻量，随项目交付）
- **ORM**：SQLAlchemy
- **认证**：JWT (python-jose + passlib)
- **文件存储**：本地文件系统

### 2.2 核心 API

#### 认证模块 `/api/auth`
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录，返回JWT |
| `/api/auth/me` | GET | 获取当前用户信息 |

#### 数据模块 `/api/data`
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/data/upload` | POST | 上传CSV文件 |
| `/api/data/list` | GET | 获取用户文件列表 |
| `/api/data/{id}` | GET | 获取文件详情 |
| `/api/data/{id}` | DELETE | 删除文件 |
| `/api/data/{id}/preview` | GET | 数据预览（前50行） |
| `/api/data/{id}/stats` | GET | 数据统计（行列数、类型） |

#### 训练模块 `/api/train`
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/train` | POST | 创建训练任务 |
| `/api/train` | GET | 获取训练任务列表 |
| `/api/train/{id}` | GET | 获取任务详情 |
| `/api/train/{id}/status` | GET | 获取实时状态（轮询） |
| `/api/train/{id}/stop` | POST | 停止训练 |
| `/api/train/{id}/logs` | GET | 获取训练日志 |

#### 实验模块 `/api/experiments`
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/experiments` | GET | 获取实验列表 |
| `/api/experiments/{id}` | GET | 获取实验详情 |
| `/api/experiments/{id}/metrics` | GET | 获取指标历史 |
| `/api/experiments/compare` | POST | 对比多个实验 |

#### 模型模块 `/api/models`
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/models` | GET | 获取模型列表 |
| `/api/models/{id}` | GET | 获取模型详情 |
| `/api/models/{id}/predict` | POST | 批量预测 |
| `/api/models/{id}` | DELETE | 删除模型 |

### 2.3 数据模型

#### User（用户）
```python
{
    "id": int,
    "username": str,
    "email": str,
    "password_hash": str,
    "created_at": datetime
}
```

#### DataFile（数据文件）
```python
{
    "id": int,
    "user_id": int,
    "filename": str,
    "filepath": str,
    "size": int,
    "rows": int,
    "columns": list[str],
    "created_at": datetime
}
```

#### TrainingJob（训练任务）
```python
{
    "id": int,
    "user_id": int,
    "experiment_id": int,
    "model_type": str,       # sklearn/xgboost/lightgbm/pytorch
    "model_name": str,
    "task_type": str,        # classification/regression
    "status": str,           # pending/running/completed/failed
    "progress": int,         # 0-100
    "metrics": dict,         # 最终指标
    "created_at": datetime,
    "finished_at": datetime
}
```

#### Experiment（实验）
```python
{
    "id": int,
    "user_id": int,
    "name": str,
    "description": str,
    "params": dict,
    "metrics": dict,
    "status": str,
    "created_at": datetime
}
```

### 2.4 错误处理

| 错误码 | 描述 |
|--------|------|
| 400 | 参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |

错误响应格式：
```json
{
    "detail": "错误描述",
    "code": "ERROR_CODE"
}
```

---

## 3. 认证需求

### 3.1 JWT 配置
- **算法**：HS256
- **过期时间**：7天
- **刷新**：不支持，登录重新获取

### 3.2 注册流程
1. 用户名（3-20字符）+ 邮箱 + 密码（6位以上）
2. 密码 bcrypt 加密存储
3. 返回用户信息（不含密码）

### 3.3 登录流程
1. 用户名/邮箱 + 密码
2. 验证密码
3. 返回 JWT token

### 3.4 受保护路由
所有 `/api/*` 路由（除 `/api/auth/*`）需要 JWT 认证。

前端在请求头中携带：
```
Authorization: Bearer <token>
```

### 3.5 认证中间件
```python
@router.get("/protected")
@login_required
async def protected_route(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "username": user.username}
```

---

## 4. 前端集成需求

### 4.1 API 客户端
```typescript
// src/api/client.ts
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器：添加token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

### 4.2 认证状态管理
```typescript
// 登录后存储token
localStorage.setItem('token', response.data.access_token)

// 请求时自动携带
// 401时跳转登录页
```

### 4.3 页面权限
| 页面 | 权限 |
|------|------|
| 登录/注册 | 公开 |
| Dashboard | 需要登录 |
| Training | 需要登录 |
| Experiments | 需要登录 |

---

## 5. 非功能需求

### 5.1 性能
- API 响应时间 < 500ms
- 文件上传限制：100MB
- 支持并发训练：最多3个

### 5.2 安全
- 密码加密存储
- JWT 短期令牌
- 用户数据隔离（只能访问自己的数据）

### 5.3 可用性
- 友好的错误提示
- 加载状态指示
- 操作成功/失败反馈

---

## 6. 验收标准

### 6.1 API 验收
- [ ] 用户可以注册和登录
- [ ] 登录后获取 JWT token
- [ ] 可以上传 CSV 文件
- [ ] 可以创建训练任务
- [ ] 可以查看训练进度
- [ ] 可以查看实验列表
- [ ] 可以进行模型预测

### 6.2 前端验收
- [ ] 未登录用户访问 /dashboard 自动跳转登录页
- [ ] 登录页可以注册和登录
- [ ] 登录后显示用户信息
- [ ] 可以登出
- [ ] 训练页面对接真实 API
- [ ] 实验页面对接真实 API

---

*本文档为 API 后端和认证的补充需求，与 v1.0 需求文档合并使用*
