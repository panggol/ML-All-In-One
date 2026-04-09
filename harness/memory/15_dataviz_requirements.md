# ML All In One — 数据可视化功能需求文档

_Version: 1.0_
_Date: 2026-04-09_
_Author: 需求分析 Agent_

---

## 1. 概述

### 1.1 项目背景

ML All In One 是一个机器学习训练平台，已具备以下核心功能：

- 数据上传与管理
- 模型训练任务编排
- 实验追踪（Experiment Tracking）

当前缺少统一的数据可视化模块，导致用户无法直观理解训练过程中的数据分布、模型特征重要性及预测结果，制约了模型调优和数据分析效率。

### 1.2 目标

为 ML All In One 平台新增 **数据可视化（Data Visualization）** 功能模块，帮助用户在训练全生命周期内查看、对比和分析可视化图表，提升模型可解释性和调优效率。

### 1.3 范围

本模块覆盖以下可视化场景：

- 训练数据分布可视化
- 特征重要性分析可视化
- 预测结果与真实标签对比可视化
- 训练过程指标曲线（与实验追踪模块联动）

---

## 2. 功能需求

### 2.1 数据分布可视化

**目标**：帮助用户快速了解数据集的结构和统计特性。

#### 2.1.1 数值特征分布图
- 直方图（Histogram）：展示单维数值特征的分布形态（正态、偏态等）
- 箱线图（Box Plot）：展示数值特征的离散程度和异常值检测
- 密度图（Density Plot）：平滑的分布曲线，适合连续变量

#### 2.1.2 类别特征分布图
- 柱状图（Bar Chart）：展示类别型特征各取值的样本数量
- 饼图（Pie Chart）：展示类别占比（仅在类别数 ≤ 7 时使用）

#### 2.1.3 多变量关系图
- 散点图矩阵（Scatter Matrix / Pair Plot）：展示多对特征之间的两两关系
- 相关性热力图（Correlation Heatmap）：展示特征间的皮尔逊相关系数矩阵

#### 2.1.4 数据质量检测可视化
- 缺失值热力图（Missing Value Heatmap）：直观展示各特征列的缺失比例
- 重复行高亮提示

**用户故事**：
> 作为数据科学家，我希望在训练前查看数据的分布情况，以便判断是否需要做特征工程或异常值处理。

### 2.2 特征重要性可视化

**目标**：帮助用户理解模型学到的特征贡献，提升模型可解释性。

#### 2.2.1 全局特征重要性
- 水平柱状图（Horizontal Bar Chart）：按重要性降序展示所有特征重要性得分
- SHAP Summary Plot（蜂群图/条形图）：展示特征对模型输出的平均影响，兼容 TreeSHAP 和 DeepSHAP

#### 2.2.2 单样本特征贡献
- SHAP Force Plot：展示单个样本各特征的正/负贡献，叠加显示预测值
- SHAP Decision Plot：展示单个样本的决策路径

#### 2.2.3 特征对比分析
- 双模型特征重要性对比图：左右并列柱状图，对比两个模型（如 RF vs XGBoost）的特征重要性排序

**用户故事**：
> 作为算法工程师，我需要了解哪些特征对模型预测贡献最大，以便决定是否可以简化模型或收集更多相关数据。

### 2.3 预测结果可视化

**目标**：帮助用户评估模型性能，发现预测偏差。

#### 2.3.1 分类任务
- 混淆矩阵热力图（Confusion Matrix Heatmap）：展示真实标签与预测标签的交叉矩阵
- ROC 曲线（ROC Curve）：展示不同阈值下的 TPR vs FPR 曲线，并标注 AUC 值
- Precision-Recall 曲线（PR Curve）：适合不平衡数据集
- 分类报告可视化：将 Precision/Recall/F1 做成横向条形图

#### 2.3.2 回归任务
- 真实值 vs 预测值散点图（True vs Predicted Scatter Plot）：理想情况下点应落在对角线上
- 残差分布图（Residual Distribution Histogram）：残差应接近正态分布
- 残差 vs 预测值图（Residuals vs Fitted）：检验异方差性

#### 2.3.3 聚类任务
- 降维可视化：使用 t-SNE 或 UMAP 将高维特征/嵌入向量降至 2D 散点图
- 聚类轮廓分析：展示各聚类的轮廓系数

**用户故事**：
> 作为模型评估者，我需要通过可视化快速定位模型的预测错误模式，以便针对性地优化。

### 2.4 训练过程可视化（与实验追踪联动）

**目标**：实时监控训练进度，分析收敛行为。

- 损失曲线（Loss Curve）：训练集和验证集的 loss 随 epoch 变化
- 评估指标曲线（Metrics Curve）：Accuracy、F1、AUC 等随 epoch 变化
- 学习率热力图（Learning Rate Finder Plot）：展示不同学习率对应的 loss
- 梯度分布直方图（Gradient Histogram）：监控梯度爆炸/消失问题

**用户故事**：
> 作为训练工程师，我希望实时查看训练曲线，以便判断是否需要提前停止训练或调整超参数。

### 2.5 可视化仪表盘（Dashboard）

**目标**：提供一站式概览页面。

- 数据集概览卡片：样本数、特征数、缺失率等统计摘要
- 模型性能排行榜：展示所有实验模型的评估指标横向对比
- 可交互图表：支持缩放、悬停提示（Tooltip）、框选放大（Box Zoom）

---

## 3. 非功能需求

### 3.1 性能要求
- 单个图表渲染时间 ≤ 2 秒（数据集 ≤ 100 万行）
- 大数据集（> 100 万行）自动降采样渲染
- 支持异步图表生成，不阻塞主界面

### 3.2 可用性要求
- 所有图表支持悬停提示（显示具体数值）
- 支持图表导出为 PNG / SVG 格式
- 支持图表全屏查看
- 深色模式适配

### 3.3 兼容性要求
- 支持主流浏览器：Chrome、Firefox、Safari、Edge（最新两个版本）
- 响应式布局，支持 1280×720 及以上分辨率

### 3.4 安全要求
- 图表数据仅对有数据访问权限的用户可见
- 不在前端暴露原始训练数据（仅传输聚合/处理后的可视化数据）

---

## 4. 图表类型清单

### 4.1 数据分布类
| 图表名称 | 用途 | 数据类型 |
|----------|------|----------|
| 直方图（Histogram） | 数值特征分布 | 数值型 |
| 箱线图（Box Plot） | 离散程度 / 异常值 | 数值型 |
| 密度图（Density Plot） | 连续分布 | 数值型 |
| 柱状图（Bar Chart） | 类别分布 | 类别型 |
| 饼图（Pie Chart） | 类别占比 | 类别型（≤7类）|
| 散点图（Scatter Plot） | 两特征关系 | 数值型 |
| 散点矩阵（Pair Plot） | 多特征两两关系 | 多数值型 |
| 相关性热力图（Correlation Heatmap） | 特征相关度 | 多特征 |
| 缺失值热力图（Missing Value Heatmap） | 数据质量 | 全特征 |

### 4.2 模型解释类
| 图表名称 | 用途 | 适用模型 |
|----------|------|----------|
| 特征重要性柱状图 | 全局特征贡献 | 树模型、线性模型 |
| SHAP Summary Plot | 全局 / 局部特征贡献 | 所有模型 |
| SHAP Force Plot | 单样本解释 | 所有模型 |
| SHAP Decision Plot | 决策路径 | 所有模型 |
| 双模型对比图 | 特征重要性对比 | 任意两模型 |

### 4.3 模型评估类
| 图表名称 | 用途 | 任务类型 |
|----------|------|----------|
| 混淆矩阵热力图 | 分类错误分析 | 分类 |
| ROC 曲线 | 阈值敏感度分析 | 分类 |
| PR 曲线 | 不平衡分类 | 分类 |
| 分类报告条形图 | 指标概览 | 分类 |
| 真值 vs 预测散点图 | 回归偏差分析 | 回归 |
| 残差直方图 | 残差正态性 | 回归 |
| 残差 vs 预测值图 | 异方差检测 | 回归 |
| t-SNE / UMAP 散点图 | 聚类可视化 | 聚类 |

### 4.4 训练监控类
| 图表名称 | 用途 |
|----------|------|
| 损失曲线（Loss Curve） | 收敛监控 |
| 指标曲线（Metrics Curve） | 性能监控 |
| 学习率曲线（LR Finder Plot） | 学习率调优 |
| 梯度分布直方图 | 梯度健康度 |

---

## 5. 技术实现方案

### 5.1 技术选型

#### 前端可视化库
| 库 | 适用场景 | 选型理由 |
|----|----------|----------|
| **ECharts** | 通用图表（柱状图、折线图、热力图等） | 轻量、配置灵活、社区活跃、国内 CDN 友好 |
| **Plotly.py**（Python）/ **Plotly.js**（前端） | 交互式图表（散点图矩阵、3D 图） | 支持缩放、悬停、导出 PNG |
| **D3.js** | 自定义复杂图表 | 高度可定制，用于特殊定制需求 |
| **SHAP Plots**（Python） | 模型可解释性图表 | 官方 SHAP 库直接生成，需后端渲染后传递 JSON 数据 |

#### 后端数据处理
- **Python**：主要计算语言
  - `pandas`：数据聚合与统计计算
  - `numpy`：数值计算与降采样
  - `scipy`：统计检验与分布拟合
  - `shap`：特征重要性计算
  - `scikit-learn`：metrics、clustering、降维（t-SNE、PCA）
  - `matplotlib` / `seaborn`：服务端图表渲染（生成 PNG 供前端展示）

#### 降维与嵌入
- **t-SNE / UMAP**（通过 `openTSNE` / `umap-learn`）：高维数据可视化
- **PCA**：线性降维预投影

#### 前端框架
- 复用项目现有前端框架（React/Vue），图表组件封装为可复用组件库

### 5.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      前端（Web UI）                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ 数据分布页面  │  │ 特征重要性页 │  │  预测结果页面    │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                │                   │              │
│         └────────────────┼───────────────────┘              │
│                          │                                   │
│                   ┌──────▼──────┐                            │
│                   │  可视化组件库 │  (ECharts + Plotly)       │
│                   └─────────────┘                            │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP REST API
┌──────────────────────────▼──────────────────────────────────┐
│                      后端（Python API）                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ 数据统计服务   │  │ 模型解释服务  │  │  评估指标服务    │   │
│  │ /api/viz/stats│  │ /api/viz/shap │  │  /api/viz/eval   │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                │                   │              │
│  ┌──────▼─────────────────▼───────────────────▼─────────┐   │
│  │              数据处理层（Pandas / NumPy / Scipy）      │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              存储层（数据集、模型输出、图表缓存）          │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

### 5.3 核心 API 设计

#### 5.3.1 数据分布 API
```
GET /api/viz/datasets/{dataset_id}/distributions

Query Params:
  - features: comma-separated feature names (optional, default=all)
  - plot_type: histogram | boxplot | density | heatmap (optional)
  - sample_size: int (default=10000, for auto-downsampling)

Response:
{
  "dataset_info": { "rows": int, "cols": int, "missing_rate": float },
  "plots": [
    {
      "feature": "age",
      "type": "histogram",
      "data": { "bins": [...], "counts": [...] },
      "stats": { "mean": float, "std": float, "min": float, "max": float }
    },
    ...
  ],
  "correlation_matrix": [[...]],  // optional for multi-feature
  "missing_values": { "feature": "income", "missing_rate": 0.05 }
}
```

#### 5.3.2 特征重要性 API
```
GET /api/viz/models/{model_id}/feature-importance

Query Params:
  - method: shap | tree_importance (default=tree_importance)
  - top_k: int (default=20)
  - sample_size: int (default=1000, for SHAP)

Response:
{
  "model_info": { "name": str, "type": str },
  "importance": [
    { "feature": "credit_score", "importance": 0.342, "direction": "positive" },
    ...
  ],
  "shap_values": [  // if method=shap
    { "feature": "age", "shap_value": -0.12, "feature_value": 35 },
    ...
  ]
}
```

#### 5.3.3 预测结果 API
```
GET /api/viz/experiments/{experiment_id}/predictions

Query Params:
  - task_type: classification | regression | clustering

Response:
{
  "experiment_info": { "name": str, "task_type": str },
  "plots": [
    {
      "type": "confusion_matrix",
      "data": [[20, 3], [2, 25]],
      "labels": ["class_0", "class_1"]
    },
    {
      "type": "roc_curve",
      "data": { "fpr": [...], "tpr": [...], "auc": 0.94 }
    },
    ...
  ],
  "summary": { "accuracy": 0.91, "f1": 0.89 }
}
```

#### 5.3.4 训练曲线 API
```
GET /api/viz/experiments/{experiment_id}/training-curves

Response:
{
  "epochs": [1, 2, 3, ..., 100],
  "curves": [
    { "name": "train_loss", "values": [...] },
    { "name": "val_loss", "values": [...] },
    { "name": "train_accuracy", "values": [...] },
    { "name": "val_accuracy", "values": [...] }
  ]
}
```

### 5.4 关键实现细节

#### 降采样策略
- 行数 > 10,000 时：对数值特征使用均匀采样（stratified sampling）；对类别特征按类别比例采样
- 可视化请求携带 `sample_size` 参数，由后端控制采样逻辑

#### SHAP 集成
1. 后端接收 SHAP 计算请求，调度 Python 进程执行 `shap.TreeExplainer()` 或 `shap.DeepExplainer()`
2. 计算完成后，将结果转换为 JSON 格式（feature + shap_value 数组）
3. 前端使用 ECharts 渲染 SHAP Summary Plot（蜂群图 / 条形图）

#### 图表缓存
- 相同数据集 + 相同模型 + 相同参数的可视化请求，优先返回缓存（Redis 或文件系统缓存）
- 缓存 key：`viz:{dataset_id}:{model_id}:{plot_type}:{params_hash}`
- 缓存失效：数据集更新、模型重训后自动失效

#### 安全性
- 所有 API 需携带用户认证 Token
- 后端对原始数据做聚合处理后返回，不直接暴露原始行数据
- 大文件可视化结果（> 10MB）通过预签名 URL 下载

### 5.5 技术栈汇总

| 层级 | 技术选型 |
|------|----------|
| 前端图表 | ECharts 5.x、Plotly.js |
| 前端框架 | 复用项目现有（React/Vue） |
| 后端 API | Python FastAPI |
| 数据处理 | pandas、numpy、scipy |
| ML 可解释性 | shap |
| 降维 | scikit-learn（PCA）、umap-learn（UMAP）、openTSNE |
| 服务端渲染 | matplotlib、seaborn（生成 PNG/SVG） |
| 缓存 | Redis 或文件系统 |
| 部署 | Docker，与现有平台容器化部署统一 |

---

## 6. 里程碑计划

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| Phase 1 | 数据分布可视化（直方图、箱线图、热力图、相关性图） | P0 |
| Phase 2 | 特征重要性可视化（树模型重要性、SHAP Summary Plot） | P0 |
| Phase 3 | 预测结果可视化（混淆矩阵、ROC/PR 曲线、残差图） | P0 |
| Phase 4 | 训练曲线可视化（Loss、Metrics 曲线） | P1 |
| Phase 5 | 可视化仪表盘 + 图表导出功能 | P2 |
| Phase 6 | t-SNE/UMAP 聚类可视化 | P2 |

---

## 7. 附录

### 7.1 术语表
| 术语 | 说明 |
|------|------|
| SHAP | SHapley Additive exPlanations，博弈论驱动的特征贡献解释方法 |
| t-SNE | t-distributed Stochastic Neighbor Embedding，非线性降维算法 |
| UMAP | Uniform Manifold Approximation and Projection，高维数据降维可视化 |
| Confusion Matrix | 混淆矩阵，分类任务预测结果与真实标签的交叉表 |
| ROC Curve | Receiver Operating Characteristic Curve，分类器阈值分析曲线 |

### 7.2 参考资料
- SHAP Python Library: https://github.com/slundberg/shap
- ECharts 官方文档: https://echarts.apache.org/
- Plotly Python: https://plotly.com/python/
- UMAP 官方文档: https://umap-learn.readthedocs.io/
