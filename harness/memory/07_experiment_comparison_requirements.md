# Experiment Comparison 功能需求文档

**模块：** Tab 3 实验对比（experiment_comparison）  
**Harness 阶段：** Step 1 需求分析  
**日期：** 2026-04-10  
**项目：** ml-all-in-one  

---

## 1. 背景与目标

当前 `Experiments.tsx` 已有实验列表和训练曲线展示，但缺少多实验横向对比能力。用户无法方便地比较多个实验的指标差异、选择要对比的实验、查看汇总对比表格。

**目标：** 在 Tab 3 实验页面中增加独立的「实验对比」子视图，支持多选实验 → 指标对比 → 曲线叠加 → 汇总报告。

---

## 2. 用户故事

| # | 故事 |
|---|------|
| U1 | 用户在实验列表中勾选多个实验，点击「对比」按钮，进入对比视图 |
| U2 | 对比视图中显示所有选中实验的指标汇总表格（accuracy/f1/precision/recall/loss） |
| U3 | 对比视图中将多个实验的训练曲线叠加绘制在同一张图上（不同颜色/线型） |
| U4 | 用户可以点击曲线中的某条线来隐藏/显示对应的实验曲线（legend toggle） |
| U5 | 用户可以切换「指标对比表」和「曲线对比」两个子 Tab |
| U6 | 用户点击「返回」可取消选择，回到普通实验列表视图 |

---

## 3. 功能需求

### 3.1 实验选择机制
- 实验列表左侧增加复选框（Checkbox）
- 底部出现「已选择 N 个实验 / 对比」按钮
- 点击「对比」进入对比视图（不清除选择）
- 选择 2 个及以上实验才能进入对比视图

### 3.2 指标对比表（子 Tab 1）
- 表格列：实验名 / 任务类型 / 模型 / 状态 / Accuracy / F1 / Precision / Recall / 训练时间
- 按 accuracy 降序排列
- 最优值高亮（绿色背景）
- 表格支持滚动

### 3.3 曲线对比（子 Tab 2）
- Recharts `LineChart`，多个 experiment 的曲线叠加
- 每个实验一条线，颜色自动分配（图例含实验名）
- X 轴：Epoch，Y 轴：指标值（loss 或 accuracy，切换时重新绘制）
- 支持 loss / accuracy 指标切换下拉框
- 曲线粗细 2px，dot 点大小 3px
- 图例可点击隐藏/显示对应曲线

### 3.4 状态流转
```
实验列表（Checkbox模式）
    ↓ [点击「对比」且选中≥2个实验]
实验对比视图
    ↓ [点击「返回」]
实验列表（Checkbox模式）
```

---

## 4. 数据结构

### 4.1 Experiment 对比数据结构
```typescript
interface ExperimentComparison {
  experiments: Experiment[]      // 选中的实验列表
  metrics: {
    experiment_name: string
    task_type: string
    model_name: string
    status: string
    accuracy: number | null
    f1: number | null
    precision: number | null
    recall: number | null
    train_time: number | null   // 秒
  }[]
  curves: {
    experiment_name: string
    color: string
    metrics_curve: MetricsCurve  // 来自 Experiment
  }[]
}
```

### 4.2 颜色分配策略
固定调色盘（10色循环）：
```
#6366F1, #F59E0B, #10B981, #EF4444, #8B5CF6,
#EC4899, #14B8A6, #F97316, #3B82F6, #84CC16
```

---

## 5. 非功能需求

- **性能：** 选中 ≤10 个实验时，曲线渲染不超过 500ms
- **响应式：** 对比视图宽度自适应，保持良好可读性
- **兼容性：** 复用现有 `Experiment` 接口，不修改后端 API

---

## 6. 验收标准

| # | 标准 |
|---|------|
| AC1 | 勾选 2+ 实验后「对比」按钮可点击 |
| AC2 | 点击「对比」后正确展示指标对比表 |
| AC3 | 曲线叠加图正确显示所有选中实验的曲线 |
| AC4 | 图例点击可隐藏/显示对应曲线 |
| AC5 | loss/accuracy 切换后曲线正确刷新 |
| AC6 | 点击「返回」正确回到实验列表，选择状态保留 |
| AC7 | TypeScript 编译无错误 |
| AC8 | 前端构建 `vite build` 成功 |

---

## 7. 技术约束

- 前端框架：React + TypeScript + TailwindCSS + Recharts
- 状态管理：React useState（无需 Redux）
- 数据来源：复用现有 `experimentsApi.list()` 和 `experiments` 数据
- 不修改后端 API，只扩展前端功能
- 路径：`frontend/src/pages/Experiments.tsx`（在现有文件上扩展，不新建文件）

---

## 8. 里程碑

- **M1：** 实验选择 Checkbox + 对比入口（AC1）
- **M2：** 指标对比表（AC2）
- **M3：** 曲线叠加对比 + legend toggle（AC3/AC4/AC5）
- **M4：** 状态流转 + 返回（AC6）
- **M5：** TypeScript + Build 验证（AC7/AC8）
