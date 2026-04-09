# ML All In One

机器学习全流程训练平台，支持 sklearn、XGBoost、LightGBM、PyTorch。

## 技术架构

```
┌─────────────┐     ┌─────────────┐
│  React UI   │ ──► │  FastAPI    │
│ (localhost  │     │ (localhost  │
│   :3000)    │     │   :8000)    │
└─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   mlkit     │
                    │   核心库     │
                    └─────────────┘
```

## 快速开始

```bash
# 启动后端 API 和前端 UI
make dev
```

访问 http://localhost:3000 查看前端界面。

# 本地开发

如果需要分别启动服务：

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

## 功能特性

### 认证系统
- ✅ 用户注册/登录
- ✅ JWT Token 认证
- ✅ 用户数据隔离

### 数据管理
- ✅ CSV 文件上传
- ✅ 数据预览（前50行）
- ✅ 数据统计

### 模型训练
- ✅ 多模型支持（RandomForest、XGBoost、LightGBM）
- ✅ 分类/回归任务
- ✅ 训练进度追踪
- ✅ 训练日志

### 实验追踪
- ✅ 实验列表和对比
- ✅ 训练曲线可视化
- ✅ 指标历史

### 模型推理
- ✅ 批量预测
- ✅ 结果导出

## 项目结构

```
ML-All-In-One/
├── frontend/           # React + TailwindCSS 前端
│   ├── src/
│   │   ├── api/         # API 客户端
│   │   ├── components/  # UI 组件
│   │   └── pages/       # 页面
│   └── ...
├── api/                # FastAPI 后端
│   ├── main.py          # 应用入口
│   ├── database.py      # 数据库模型
│   ├── auth.py          # JWT 认证
│   └── routes/          # API 路由
│       ├── auth.py
│       ├── data.py
│       ├── train.py
│       ├── experiments.py
│       └── models.py
├── src/mlkit/          # Python 核心库
│   ├── config/          # 配置管理
│   ├── auth/            # 用户认证
│   ├── data/            # 数据加载
│   ├── hooks/           # 训练生命周期钩子
│   ├── experiment/       # 实验记录
│   ├── preprocessing/    # 数据预处理
│   └── model/           # 模型封装
├── tests/              # 测试
└── harness/            # Harness Engineering 文档
```

## API 文档

启动后端后访问：http://localhost:8000/docs

### 认证接口
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户

### 数据接口
- `POST /api/data/upload` - 上传文件
- `GET /api/data/list` - 文件列表
- `GET /api/data/{id}/preview` - 数据预览
- `GET /api/data/{id}/stats` - 数据统计

### 训练接口
- `POST /api/train` - 创建训练
- `GET /api/train/{id}/status` - 训练状态
- `POST /api/train/{id}/stop` - 停止训练

### 实验接口
- `GET /api/experiments` - 实验列表
- `POST /api/experiments/compare` - 实验对比

## 开发

### 安装依赖
```bash
# 后端
cd api && pip install -r requirements.txt

# 前端
cd frontend && npm install
```

### 运行测试
```bash
# Python
pytest tests/ -v

# 前端 (需在本地浏览器测试)
cd frontend && npm run dev
```

## 技术栈

### 前端
- React 18 + TypeScript
- Vite
- TailwindCSS
- React Router
- TanStack Query
- Axios
- Lucide Icons

### 后端
- FastAPI
- SQLAlchemy
- JWT (python-jose)
- Pandas
- Scikit-learn

## License

MIT
