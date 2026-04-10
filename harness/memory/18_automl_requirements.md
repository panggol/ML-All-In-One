# ML All In One — AutoML 模块需求文档

_Version: 1.0_
_Date: 2026-04-10_
_Author: 需求分析 Agent_

---

## 1. 概述

AutoML 模块自动完成模型选择和超参数调优，降低机器学习使用门槛。用户只需提供数据集和任务类型，系统自动搜索最佳模型和超参数组合。

---

## 2. 功能需求

### 2.1 自动模型选择

- 根据任务类型（分类/回归）自动选择候选模型列表
- 分类候选：RandomForest / XGBoost / LightGBM / LogisticRegression
- 回归候选：RandomForest / XGBoost / LightGBM / LinearRegression
- 对每个候选模型做快速基准训练（低迭代），排序后选取 Top-K

### 2.2 超参数搜索策略

#### 2.2.1 Grid Search（暴力网格搜索）
- 定义参数网格，遍历所有组合
- 适合小规模参数空间

#### 2.2.2 Random Search（随机搜索）
- 每个参数在定义范围内随机采样
- 支持 n_trials 参数控制搜索次数
- 比 Grid Search 更高效

#### 2.2.3 Bayesian Optimization（贝叶斯优化）
- 使用 `optuna` 实现
- 基于历史结果智能选择下一个参数组合
- 适合大规模参数空间，效率最高

### 2.3 搜索空间定义

```python
search_space = {
    "model_type": ["random_forest", "xgboost", "lightgbm"],
    "n_estimators": {"type": "int", "min": 50, "max": 300},
    "max_depth": {"type": "int", "min": 3, "max": 15},
    "learning_rate": {"type": "float", "min": 0.01, "max": 0.3, "log": True},
    "min_samples_split": {"type": "int", "min": 2, "max": 20},
}
```

### 2.4 Early Stopping

- 每轮 trial 验证集指标无提升时提前终止
- 防止单个 trial 训练时间过长
- patience 参数控制无改进容忍轮数

### 2.5 结果汇总

- 返回最佳参数组合
- 返回 Top-3 模型对比
- 生成调优报告（Markdown）

---

## 3. 接口设计

### AutoMLEngine

```python
from mlkit.automl import AutoMLEngine, GridSearch, RandomSearch, BayesianOptimization

# 快速启动（使用默认配置）
engine = AutoMLEngine(
    task_type="classification",
    X_train=X_train, y_train=y_train,
    X_val=X_val, y_val=y_val,
    strategy="random",  # grid | random | bayesian
    n_trials=20,
    timeout=600,  # 秒
)
result = engine.run()
print(result.best_params)
print(result.best_score)
```

### SearchSpace

```python
from mlkit.automl import SearchSpace

space = SearchSpace()
space.add("model_type", ["random_forest", "xgboost"])
space.add_int("n_estimators", 50, 300)
space.add_float("max_depth", 3, 15)
space.add_float("learning_rate", 0.01, 0.3, log=True)
```

---

## 4. 技术选型

- `optuna`（贝叶斯优化，必须安装）
- 复用现有 mlkit.model（create_model）
- 复用现有 mlkit.hooks（EarlyStoppingHook）
- 复用现有 mlkit.experiment（ExperimentManager）

---

## 5. 实现里程碑

| 阶段 | 内容 |
|------|------|
| Phase 1 | AutoMLEngine + Grid Search + Random Search |
| Phase 2 | Bayesian Optimization（optuna） |
| Phase 3 | 与 Experiment 系统集成 |
| Phase 4 | Web UI 集成（AutoML Tab） |

---

*文档版本：v1.0.0 | 最后更新：2026-04-10*
