# 🤖 ML All In One

基于 **Harness Engineering** 理念构建的机器学习全流程训练平台。支持 sklearn、XGBoost、LightGBM、PyTorch 多种模型，提供 Hook 生命周期扩展、实验追踪、Gradio Web UI 和 Docker 部署。

---

## ✨ 核心特性

| 分类 | 功能 |
|------|------|
| **多模型支持** | sklearn / XGBoost / LightGBM / PyTorch |
| **预处理** | Encoder / Scaler / Imputer / PCA / LDA / 文本向量化 |
| **训练编排** | Hook 生命周期（8 事件 + Priority + One-shot） |
| **实验追踪** | Experiment 系统（指标记录、横向对比、Markdown 报告） |
| **用户认证** | JWT + Bcrypt 用户注册/登录 |
| **Web UI** | Gradio 可视化界面（训练/实验/推理/数据 4 Tab） |
| **部署** | Docker / docker-compose 一键部署 |
| **测试** | 105 个单元测试，100% 通过率 |

---

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/panggol/ML-All-In-One.git
cd ML-All-In-One
pip install -e .      # 安装为可编辑包
```

### 运行 Web UI

```bash
python app.py
# 访问 http://localhost:7860
```

### 运行训练示例

```bash
python run_example.py
```

### 运行单个示例

```bash
PYTHONPATH=src python examples/train_sklearn.py
PYTHONPATH=src python examples/example_auth.py
PYTHONPATH=src python examples/example_continuous_learning.py
```

---

## 📁 项目结构

```
ml-all-in-one/
├── src/mlkit/              # 核心框架
│   ├── config/             # 配置系统（dot-path / YAML / ENV）
│   ├── auth/               # 用户认证（JWT / Bcrypt）
│   ├── data/               # 数据加载（CSV / Parquet / JSON）
│   ├── hooks/              # 生命周期钩子（8 事件）
│   │   ├── LoggerHook      # 日志记录
│   │   ├── CheckpointHook  # 模型保存
│   │   ├── EarlyStoppingHook  # 早停
│   │   └── ExperimentTrackHook # 实验追踪
│   ├── experiment/         # 实验追踪系统
│   ├── preprocessing/      # 预处理模块
│   │   ├── tabular/        # 表格（encoder/scaler/imputer）
│   │   ├── text/           # 文本（tokenizer/vectorizer）
│   │   └── dimensionality/ # 降维（PCA / LDA）
│   ├── model/              # 模型基类
│   └── api/                # FastAPI 推理服务
├── examples/                # 示例代码
├── tests/                  # 单元测试（105 个）
├── app.py                  # Gradio Web UI
├── Dockerfile              # Docker 镜像
├── docker-compose.yml       # Docker Compose
└── run_example.py          # 一键运行示例
```

---

## 🔧 核心模块

### Hook System

```python
from mlkit.hooks import LoggerHook, CheckpointHook, EarlyStoppingHook

runner = create_runner(config)
runner.register_hook(LoggerHook(), priority=10)
runner.register_hook(CheckpointHook(save_best=True, monitor="val_acc"))
runner.register_hook(EarlyStoppingHook(patience=10, monitor="val_loss"))
runner.train()
```

### Experiment 追踪

```python
from mlkit.experiment import ExperimentManager

manager = ExperimentManager("./experiments")
exp = manager.create_experiment("lr-sweep-v1", params={"lr": 0.01})
runner = create_runner(config, experiment=exp)
runner.train()
report = manager.generate_report([exp.id])
```

### Config 系统

```python
from mlkit.config import Config

config = Config.from_yaml("config.yaml")
lr = config.get("model.learning_rate")  # dot-path 访问

# 环境变量注入
# MLKIT_TRAIN__EPOCHS=100 python train.py
```

---

## 🐳 Docker 部署

```bash
# 构建镜像
docker build -t mlkit .

# 运行训练
docker compose run --rm mlkit python run_example.py

# 启动 API 服务
docker compose up api
```

---

## 📊 测试

```bash
pytest tests/ -v
# 结果：105 passed, 0 failed
```

---

## 🛠️ 开发

```bash
# 安装开发依赖
pip install -r requirements.txt

# 代码检查
ruff check src/mlkit/

# 格式化
ruff format src/mlkit/
black src/mlkit/
```

---

## 📄 License

MIT License

---

*基于 Harness Engineering 理念构建 | Powered by OpenClaw*
