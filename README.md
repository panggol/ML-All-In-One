# ML All In One

机器学习全流程一站式平台，支持 sklearn、XGBoost、LightGBM、PyTorch，覆盖数据管理、模型训练、AutoML、推理服务、模型解释、漂移检测、实验对比、时序预测、自动化调度全流程。

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

## 本地开发

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

### 认证系统 ✅
- ✅ 用户注册 / 登录
- ✅ JWT Token 认证
- ✅ 内置管理员账户（seed 机制，幂等初始化）
- ✅ 用户数据隔离

### 数据管理 ✅
- ✅ CSV 文件上传与解析
- ✅ 数据预览（前50行）
- ✅ 数据统计（describe / 缺失值 / 类型）
- ✅ 数据管道编排（Pipeline DSL + DAG 执行引擎）

### 模型训练 ✅
- ✅ 多模型支持：RandomForest、XGBoost、LightGBM、LogisticRegression、MLP（PyTorch）、SVC、SVR、LinearRegression、GradientBoosting
- ✅ 分类 / 回归任务
- ✅ 训练进度实时追踪（WebSocket）
- ✅ 训练日志面板
- ✅ 提前停止与中断恢复

### AutoML ✅
- ✅ 自动化超参搜索（Grid / Random / Bayesian Optimization via Optuna）
- ✅ 最佳模型自动注册

### 实验追踪 ✅
- ✅ 实验列表与对比
- ✅ 训练曲线可视化
- ✅ 指标历史与排序

### 模型推理 ✅
- ✅ JSON / CSV / 数据集三种推理模式
- ✅ 批量预测与结果导出

### 模型可解释性 ✅
- ✅ SHAP 全局解释（特征重要性）
- ✅ SHAP 局部解释（单样本）
- ✅ ICE 曲线

### 模型漂移检测 ✅
- ✅ 特征漂移（PSI / KS 统计）
- ✅ 预测漂移监控
- ✅ 飞书告警集成

### 模型版本注册表 ✅
- ✅ 版本化注册与 staging/proroduction 标签
- ✅ 版本回滚
- ✅ 版本对比

### 时序预测 ✅
- ✅ ARIMA、Prophet、LightGBM 三种引擎
- ✅ 交叉验证
- ✅ 趋势 / 季节 / 残差分解

### 自动化调度 ✅
- ✅ Cron 表达式定时任务
- ✅ 预处理 / 训练 / 管道任务调度
- ✅ APScheduler 内存调度

### 平台统一日志 ✅
- ✅ 请求日志中间件（结构化 JSON）
- ✅ Auth / 预处理 / API 全链路日志汇聚
- ✅ 实时日志 WebSocket

### 数据可视化 ✅
- ✅ 训练曲线（Acc/Loss）
- ✅ 特征重要性图
- ✅ SHAP 解释图

## 项目结构

```
ML-All-In-One/
├── frontend/                    # React + TypeScript + Vite + TailwindCSS
│   ├── src/
│   │   ├── api/                 # API 客户端（axios）
│   │   ├── components/          # 共享 UI 组件
│   │   ├── pages/               # 页面（12个Tab）
│   │   └── App.tsx             # 路由 + 懒加载
│   ├── e2e/                    # Playwright E2E 测试
│   └── vite.config.ts
├── api/                        # FastAPI 后端
│   ├── main.py                  # 应用入口
│   ├── database.py             # SQLAlchemy 模型
│   └── routes/                 # API 路由
│       ├── auth.py             # 认证
│       ├── data.py             # 数据管理
│       ├── train.py            # 模型训练
│       ├── experiments.py      # 实验管理
│       ├── automl.py           # AutoML
│       ├── preprocessing.py    # 数据预处理
│       ├── inference.py        # 推理服务
│       ├── monitor.py          # 系统监控
│       ├── models.py           # 模型列表
│       ├── logs.py             # 训练日志
│       ├── platform_logs.py    # 平台统一日志
│       ├── scheduler.py        # 自动化调度
│       ├── forecast.py         # 时序预测
│       ├── viz.py              # 可视化
│       ├── model_registry.py   # 模型版本注册表
│       ├── explain.py          # SHAP 可解释性
│       ├── drift.py            # 漂移检测
│       └── pipelines.py         # 管道编排
├── src/mlkit/                  # Python 核心库
│   ├── config/                  # 配置管理
│   ├── auth/                   # JWT 认证
│   ├── data/                   # 数据加载
│   ├── model/                  # 模型基类 + sklearn/PyTorch 封装
│   ├── hooks/                  # 训练生命周期钩子
│   ├── experiment/              # 实验记录
│   ├── preprocessing/           # 数据预处理
│   ├── automl/                 # Optuna 搜索
│   ├── scheduler/              # APScheduler 调度
│   ├── forecast/               # 时序预测引擎
│   ├── explainability/         # SHAP 解释
│   ├── drift/                 # 漂移检测
│   ├── model_registry/         # 版本注册
│   ├── pipeline/               # DAG 管道
│   ├── registry/               # 注册机制
│   ├── runner/                # 训练运行器
│   └── utils/                  # 工具函数
├── middleware/
│   └── logging_middleware.py   # 结构化请求日志中间件
├── services/
│   └── log_aggregator.py      # 日志聚合服务
├── tests/                     # pytest 测试套件
├── harness/                   # Harness Engineering 文档
└── docker-compose.yml         # Docker 部署
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

### 预处理接口
- `POST /api/preprocessing/run` - 运行预处理管道

### 训练接口
- `POST /api/train` - 创建训练
- `GET /api/train/{id}/status` - 训练状态
- `POST /api/train/{id}/stop` - 停止训练
- `GET /api/train/{id}/logs` - 训练日志（WebSocket 支持）

### AutoML 接口
- `POST /api/automl/run` - 创建 AutoML 任务
- `GET /api/automl/{id}/result` - 获取最佳模型

### 实验接口
- `GET /api/experiments` - 实验列表
- `POST /api/experiments/compare` - 实验对比

### 推理接口
- `POST /api/inference/predict` - 批量推理
- `POST /api/inference/by_dataset` - 数据集推理

### 模型管理接口
- `GET /api/models` - 模型列表
- `GET /api/models/{id}` - 模型详情

### 模型版本注册表接口
- `POST /api/model-registry/register` - 注册模型版本
- `GET /api/model-registry/list` - 版本列表
- `POST /api/model-registry/{id}/rollback` - 回滚版本

### SHAP 可解释性接口
- `POST /api/explain/global` - 全局特征重要性
- `POST /api/explain/local` - 本地单样本解释

### 漂移检测接口
- `POST /api/drift/run` - 运行漂移检测
- `GET /api/drift/history` - 漂移历史

### 时序预测接口
- `POST /api/forecast/train` - 训练时序模型
- `POST /api/forecast/predict` - 时序预测

### 调度接口
- `POST /api/scheduler/jobs` - 创建定时任务
- `GET /api/scheduler/jobs` - 任务列表
- `DELETE /api/scheduler/jobs/{id}` - 删除任务

### 监控接口
- `GET /api/monitor/system` - 系统资源（CPU / 内存 / 磁盘 / 网络）
- `GET /api/monitor/jobs` - 运行中任务

### 日志接口
- `GET /api/logs/{job_id}` - 训练日志
- `GET /api/platform-logs` - 平台统一日志（支持分页 / 级别过滤）

## 测试

```bash
# Python pytest
pytest tests/ -v

# 前端 E2E（需先启动前后端服务）
cd frontend
npx playwright test
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
- Recharts（可视化）
- Playwright（E2E 测试）

### 后端
- FastAPI
- SQLAlchemy 2.0
- JWT (python-jose)
- Pandas
- Scikit-learn
- XGBoost
- LightGBM
- PyTorch
- Optuna（贝叶斯优化）
- APScheduler（任务调度）
- SHAP（模型解释）
- pmdarima / Prophet（时序预测）

## License

MIT
