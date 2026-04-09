# ML All In One - 登录页面UI设计方案

**基于：** v2.0 API需求  
**设计日期：** 2026-04-09

---

## 1. 登录页面设计

### 1.1 页面布局

```
┌─────────────────────────────────────────────────┐
│                                                 │
│              ┌───────────────────┐               │
│              │                   │               │
│              │    Logo + 标题    │               │
│              │                   │               │
│              ├───────────────────┤               │
│              │   [Tab] 登录|注册 │               │
│              │                   │               │
│              │   用户名/邮箱     │               │
│              │   ───────────    │               │
│              │                   │               │
│              │   密码            │               │
│              │   ───────────    │               │
│              │                   │               │
│              │   [登录按钮]      │               │
│              │                   │               │
│              │   忘记密码？      │               │
│              │                   │               │
│              └───────────────────┘               │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 1.2 设计规范

**页面背景：** 渐变背景
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)
min-height: 100vh
```

**登录卡片：**
```css
bg-white
rounded-2xl (24px)
shadow-2xl (强阴影)
p-8
max-width: 400px
居中显示
```

**Tab 切换：**
- 登录 / 注册 两个选项
- 激活态：primary 颜色 + 底部边框
- 非激活态：slate-500 文字

**输入框：**
- 全宽
- 高度：py-3
- 圆角：rounded-xl
- Focus：primary 边框 + ring

**按钮：**
- 全宽登录按钮
- variant: primary
- size: lg
- 圆角：rounded-xl

### 1.3 组件状态

#### Tab 切换
```tsx
const [activeTab, setActiveTab] = useState<'login' | 'register'>('login')

// Login tab 激活
activeTab === 'login' ? 'border-b-2 border-primary-500 text-primary-600' : 'text-slate-500'

// Register tab 激活
activeTab === 'register' ? 'border-b-2 border-primary-500 text-primary-600' : 'text-slate-500'
```

#### 表单验证
| 字段 | 验证规则 | 错误提示 |
|------|----------|----------|
| 用户名 | 3-20字符 | 用户名需3-20字符 |
| 邮箱 | 有效邮箱格式 | 请输入有效邮箱 |
| 密码 | 6位以上 | 密码至少6位 |
| 确认密码 | 与密码相同 | 两次密码不一致 |

#### 按钮状态
| 状态 | 显示 |
|------|------|
| 正常 | "登录" / "注册" |
| 加载中 | Spinner + "登录中..." |
| 禁用 | opacity-50 |

---

## 2. 登录页组件 AuthPage

### 2.1 文件位置
```
frontend/src/pages/AuthPage.tsx
```

### 2.2 功能列表

#### 登录表单
- [ ] 用户名/邮箱 输入框
- [ ] 密码 输入框（可切换显示/隐藏）
- [ ] 登录按钮
- [ ] 错误提示

#### 注册表单
- [ ] 用户名 输入框
- [ ] 邮箱 输入框
- [ ] 密码 输入框
- [ ] 确认密码 输入框
- [ ] 注册按钮
- [ ] 错误提示

#### 交互
- [ ] Tab 切换动画
- [ ] 密码可见切换
- [ ] 表单提交 loading
- [ ] 错误信息展示
- [ ] 登录成功后跳转

---

## 3. 路由设计

### 3.1 路由配置
```tsx
<Routes>
  <Route path="/login" element={<AuthPage />} />
  <Route path="/register" element={<AuthPage />} />
  <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
  <Route path="/training" element={<PrivateRoute><Training /></PrivateRoute>} />
  <Route path="/experiments" element={<PrivateRoute><Experiments /></PrivateRoute>} />
</Routes>
```

### 3.2 PrivateRoute 组件
```tsx
const PrivateRoute = ({ children }) => {
  const isAuthenticated = localStorage.getItem('token')
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return children
}
```

---

## 4. API 对接

### 4.1 登录 API
```typescript
// POST /api/auth/login
const login = async (username: string, password: string) => {
  const response = await api.post('/auth/login', { username, password })
  return response.data  // { access_token, token_type, user: {...} }
}
```

### 4.2 注册 API
```typescript
// POST /api/auth/register
const register = async (username: string, email: string, password: string) => {
  const response = await api.post('/auth/register', { username, email, password })
  return response.data
}
```

### 4.3 Token 存储
```typescript
// 登录成功后
localStorage.setItem('token', data.access_token)
localStorage.setItem('user', JSON.stringify(data.user))
```

---

## 5. Header 用户信息

### 5.1 登录后 Header
```
┌─────────────────────────────────────────────────┐
│  Logo    │   Tabs   │   用户名 ▼  │  登出     │
└─────────────────────────────────────────────────┘
```

### 5.2 用户下拉菜单
- 显示用户名
- 显示邮箱
- 分隔线
- 登出按钮

---

## 6. 错误处理

### 6.1 API 错误映射
| 错误码 | 用户提示 |
|--------|----------|
| 400 | 参数错误 |
| 401 | 用户名或密码错误 |
| 409 | 用户名已存在 |
| 500 | 服务器错误，请稍后重试 |

### 6.2 前端验证错误
- 实时验证：blur 时触发
- 提交验证：阻止提交并显示错误
- 必填字段：红色星号标记

---

## 7. 安全性设计

### 7.1 密码安全
- 密码不在 URL 或日志中暴露
- 使用 HTTPS 传输
- 错误提示不区分"用户名不存在"和"密码错误"

### 7.2 XSS 防护
- React 默认转义
- 不使用 dangerouslySetInnerHTML

### 7.3 路由保护
- 所有数据页面需要登录
- Token 过期后自动跳转登录页

---

*本设计方案补充 v2.0 API 需求的登录/注册 UI 部分*
