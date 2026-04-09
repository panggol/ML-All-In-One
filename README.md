# ML All In One

机器学习全流程训练平台，支持 sklearn、XGBoost、LightGBM、PyTorch。

## 安装

```bash
git clone https://github.com/panggol/ML-All-In-One.git
cd ML-All-In-One
pip install -e .
```

## Web UI

```bash
python app.py
```

打开 http://localhost:7860 ，有四个页面：训练、实验、推理、数据。

## 训练

上传 CSV，选择模型和参数，点击开始训练。训练过程会自动记录指标，生成可视化曲线。

支持 RandomForest、GradientBoosting、LogisticRegression 等 sklearn 模型，也支持 XGBoost、LightGBM、PyTorch。

## 实验追踪

每次训练会生成实验记录，自动保存参数和指标。可以对比不同实验的结果，生成对比报告。

```python
from mlkit.experiment import ExperimentManager
manager = ExperimentManager("./experiments")
exp = manager.create_experiment("exp-001", params={"lr": 0.01})
```

## Hook 机制

在训练循环中插入扩展点，记录日志、保存模型、早停等。

```python
from mlkit.hooks import LoggerHook, CheckpointHook
runner.register_hook(LoggerHook())
runner.register_hook(CheckpointHook(save_best=True))
```

## Docker 部署

```bash
docker build -t mlkit .
docker compose run --rm mlkit python run_example.py
```

## 测试

```bash
pytest tests/ -v
```

## 项目结构

```
src/mlkit/
├── config/          # 配置管理
├── auth/            # 用户认证
├── data/            # 数据加载
├── hooks/           # 训练生命周期钩子
├── experiment/       # 实验记录
├── preprocessing/    # 数据预处理
├── model/           # 模型封装
└── api/             # 推理服务
```
