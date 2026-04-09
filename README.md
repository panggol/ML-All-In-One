# ML All In One

机器学习全流程训练平台，支持 sklearn、XGBoost、LightGBM、PyTorch。

## 快速开始

```bash
git clone https://github.com/panggol/ML-All-In-One.git
cd ML-All-In-One

# 后端 API
cd api && pip install fastapi uvicorn && uvicorn main:app --reload

# 前端 UI (新窗口)
cd frontend && npm install && npm run dev
```

访问 http://localhost:3000 查看前端界面。

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

## 功能模块

### 仪表盘
- 系统统计（训练次数、活跃实验、运行时长）
- 快速入口（上传数据、自动ML、模型预测）
- 最近模型列表

### 模型训练
- CSV 数据上传
- 任务配置（分类/回归）
- 模型选择（RandomForest、XGBoost、LightGBM）
- 实时训练进度

### 实验追踪
- 实验列表和状态监控
- 参数对比
- 训练曲线可视化

## 原有功能

### Python API

```python
from mlkit.runner import create_runner

runner = create_runner(
    experiment="my-exp",
    model_type="sklearn",
    model_name="RandomForestClassifier"
)
runner.fit(X_train, y_train)
```

### 实验追踪

```python
from mlkit.experiment import ExperimentManager
manager = ExperimentManager("./experiments")
exp = manager.create_experiment("exp-001", params={"lr": 0.01})
```

### Hook 机制

```python
from mlkit.hooks import LoggerHook, CheckpointHook
runner.register_hook(LoggerHook())
runner.register_hook(CheckpointHook(save_best=True))
```

## 开发

### 安装依赖

```bash
pip install -e .
pytest tests/ -v
```

### 前端开发

```bash
cd frontend
npm install
npm run dev      # 开发模式
npm run build    # 生产构建
```

### Docker 部署

```bash
docker build -t mlkit .
docker compose up
```

## 项目结构

```
ML-All-In-One/
├── frontend/           # React + TailwindCSS 前端
│   ├── src/
│   │   ├── components/  # UI 组件
│   │   └── pages/       # 页面
│   └── ...
├── api/                # FastAPI 后端
│   └── main.py
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

## 更新日志

### 2026-04-09
- 新增 React + TailwindCSS 现代 UI
- 新增 FastAPI 后端
- 采用 Harness Engineering 开发流程
- 简约现代风格，支持 Dashboard、Training、Experiments 三页面
