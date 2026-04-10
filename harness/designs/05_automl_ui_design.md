# ML All In One — AutoML Web UI 设计

**项目：** ML All In One  
**模块：** AutoML Tab（Phase 4）  
**日期：** 2026-04-10  
**状态：** 设计完成

---

## 一、模块概述

在 Web UI 中新增 AutoML Tab，提供超参数搜索的图形化配置、启动和结果展示界面。

---

## 二、页面布局

```
┌─────────────────────────────────────────────────────────────┐
│ Header: AutoML                                              │
├─────────────────────────────────────────────────────────────┤
│ 数据选择                                                      │
│ [数据集下拉] [目标列下拉] [任务类型: 分类|回归]                  │
├─────────────────────────────────────────────────────────────┤
│ 搜索策略                                                      │
│ ○ Grid Search  ○ Random Search  ● Bayesian Optimization     │
├─────────────────────────────────────────────────────────────┤
│ 搜索空间配置（可折叠）                                         │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ model_type: [✓rf] [✓xgb] [✓lgbm]                     │ │
│ │ n_estimators: [50] — [300]                           │ │
│ │ max_depth:   [3]   — [15]                            │ │
│ │ learning_rate:[0.01] — [0.3] log□                   │ │
│ └────────────────────────────────────────────────────────┘ │
│ n_trials: [20]    timeout(s): [30]                        │
├─────────────────────────────────────────────────────────────┤
│ [🚀 开始 AutoML 搜索]                                         │
├─────────────────────────────────────────────────────────────┤
│ 搜索进度（实时）                                               │
│ Trial 5/20 ████████░░░░░░░░ 25%  Best: 0.9234              │
│ [AutoML] Trial 5/20 | Val: 0.8912 | Best: 0.9234 | Time: 12s │
├─────────────────────────────────────────────────────────────┤
│ 调优报告（完成后展示）                                         │
│ ## Top-3 模型                                                │
│ | 排名 | 模型 | Val F1 | 训练 F1 | 用时 |                    │
│ | 1 | lightgbm | 0.9234 | 0.9512 | 28s |                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、API 接口

```
POST /api/automl/start
Body: {
  data_file_id: number,
  target_column: string,
  task_type: "classification" | "regression",
  strategy: "grid" | "random" | "bayesian",
  search_space: {
    model_type: string[],
    n_estimators: { min: number, max: number },
    max_depth: { min: number, max: number },
    learning_rate: { min: number, max: number, log: boolean }
  },
  n_trials: number,
  timeout: number
}

GET /api/automl/status/{job_id}
Response: { status: "running" | "completed", current_trial: number, n_trials: number, best_score: number }

GET /api/automl/report/{job_id}
Response: { best_params: {}, best_score: number, top_models: [...], report_md: string }
```

---

## 四、组件清单

| 组件 | 说明 |
|------|------|
| `AutoMLPage` | 页面容器 |
| `DataSelector` | 数据集+目标列选择 |
| `StrategySelector` | 搜索策略切换 |
| `SearchSpaceForm` | 搜索空间可视化配置 |
| `SearchProgress` | 实时进度条 + 日志流 |
| `AutoMLReport` | 调优报告展示 |

---

## 五、颜色与样式

- 主色调：#6366f1（indigo）
- 进度条：渐变 indigo → violet
- 报告卡片：白底 + 阴影，与 Dashboard 风格一致

---

*文档版本：v1.0.0 | 最后更新：2026-04-10*
