# ML All In One - 项目技能

ML 机器学习全流程训练平台开发技能。

## 项目结构

```
ml-all-in-one/
├── src/mlkit/          # 核心框架
│   ├── config/         # 配置系统（YAML/ENV/dot-path）
│   ├── auth/          # 用户认证（JWT/Bcrypt）
│   ├── data/          # 数据加载
│   ├── hooks/         # 生命周期钩子（8事件 + Priority + One-shot）
│   ├── experiment/    # 实验追踪系统
│   ├── preprocessing/ # 预处理（tabular/text/dimensionality/trainable）
│   │   ├── tabular/   # 表格数据（scaler/encoder/imputer）
│   │   ├── text/      # 文本处理（tokenizer/vectorizer）
│   │   ├── dimensionality/  # 降维（PCA/LDA）
│   │   └── trainable/ # 可训练预处理
│   ├── model/         # 模型定义
│   └── api/           # 在线推理
├── examples/          # 示例代码
└── tests/             # 测试（105个测试）
```

## 开发命令

```bash
# 运行测试
cd ml-all-in-one
python3 -m pytest tests/ -v

# 代码检查
make lint

# 运行示例
PYTHONPATH=src python examples/example_auth.py
PYTHONPATH=src python examples/example_continuous_learning.py
```

## 常用操作

### 安装依赖（清华源）
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 运行训练示例
```bash
cd ml-all-in-one
PYTHONPATH=src python3 examples/example_sklearn.py
```

### 调试模型
```python
from mlkit.config import Config, TrainingConfig
from mlkit.hooks import LoggerHook, CheckpointHook, EarlyStoppingHook
from mlkit.runner import create_runner

config = TrainingConfig(epochs=10, learning_rate=0.01)
runner = create_runner(config)
runner.register_hook(LoggerHook())
runner.train()
```

## 核心模块说明

### Hook System
```python
from mlkit.hooks import LoggerHook, CheckpointHook, EarlyStoppingHook

hook = EarlyStoppingHook(monitor="val_loss", patience=5)
runner.register_hook(hook, priority=10)  # priority 越高越先执行
```

### Config 系统
```python
from mlkit.config import Config

# 从 YAML 加载
config = Config.from_yaml("config.yaml")

# dot-path 访问
lr = config.get("training.learning_rate")

# 环境变量注入
# MLKIT_TRAIN__EPOCHS=100 python train.py
```

### Experiment 系统
```python
from mlkit.experiment import ExperimentManager

manager = ExperimentManager("./experiments")
exp = manager.create_experiment("exp-001", params={"lr": 0.01})
runner = create_runner(config, experiment=exp)
runner.train()
report = exp.generate_report()
```

## 添加新模块

1. 在 `src/mlkit/` 下创建模块目录
2. 在模块 `__init__.py` 中导出接口
3. 更新根 `__init__.py` 导出
4. 添加测试用例到 `tests/`

## Preprocessing 规范

- 顶层 `encoder.py`/`scaler.py`/`imputer.py` 从 `tabular/` 重新导出（向后兼容）
- 新增类应加入 `preprocessing/tabular/` 下对应文件
- 所有预处理器需继承 `BaseTransformer`

## Web UI

```bash
cd ml-all-in-one
python3 app.py
# 访问 http://localhost:7860
```

包含 **6 个 Tab**：
- **📊 Dashboard**：系统概览（实验数/模型数/数据集）、最近实验、快速入口
- **🏋️ 训练**：左侧配置 + 右侧结果，训练日志、Loss/Accuracy 曲线
- **🧪 实验**：历史实验列表、批量对比、指标曲线对比
- **⚙️ 预处理**：数据加载、流水线预处理（归一化/缺失值/特征选择/划分）
- **🔮 推理**：模型选择、批量推理、JSON/CSV 多模式输入
- **📁 数据**：CSV 预览、统计描述

**UI 设计规范**: `research/ml-all-in-one-UI设计.md`
**Gradio 6 兼容**: 暗色主题 Ocean + 自定义颜色集

---

*最后更新: 2026-04-09*
