# 训练曲线图功能需求文档

**模块：** 训练曲线图（Training Curves）  
**Harness 阶段：** Step 1 需求分析  
**日期：** 2026-04-10  
**项目：** ml-all-in-one  

---

## 1. 背景与目标

当前 Training Tab 只有进度条和实时日志，没有训练过程中指标变化的可视化。用户无法直观看到模型在训练过程中的收敛情况（loss 下降、accuracy 上升）。

**目标：** 在 Training Tab 的训练完成后（或训练进行中），展示 loss 和 accuracy 随 epoch变化的曲线图。

---

## 2. 用户故事

| # | 故事 |
|---|------|
| U1 | 用户运行训练后，训练完成时自动展示 loss 曲线和 accuracy 曲线 |
| U2 | 用户可以切换查看 loss 或 accuracy 曲线 |
| U3 | 曲线展示时有动画过渡效果 |
| U4 | 用户可以点击「查看完整报告」跳转到对应实验的详情页 |

---

## 3. 功能需求

### 3.1 训练曲线展示区域
- 位置：训练 Tab 右侧或下方区域（独立卡片）
- 训练完成前：显示「训练中，曲线将在完成后展示」
- 训练完成后：展示 loss 曲线和 accuracy 曲线
- 使用 Recharts `LineChart` 渲染

### 3.2 双曲线展示
- 两个 Line 在同一张图上叠加显示
- 线条 1：Training Loss（蓝色 `#6366F1`）
- 线条 2：Validation Loss（橙色 `#F59E0B`）
- 或 Training Accuracy（蓝色）+ Validation Accuracy（橙色）
- 图例可点击隐藏/显示对应曲线

### 3.3 指标切换
- Tab 切换：「Loss」/「Accuracy」
- 切换后图表刷新，显示对应指标的曲线

### 3.4 曲线样式
- X 轴：Epoch（1, 2, 3, ...）
- Y 轴：指标值
- 鼠标悬停 Tooltip 显示具体数值
- 曲线平滑（`connectNulls={true}`）

### 3.5 训练完成触发
- 监听训练状态，当 `status === 'completed'` 时触发曲线展示
- 曲线数据来源：`/api/train/{id}/status` 返回的 `metrics_curve` 数据

---

## 4. 数据结构

### 4.1 后端 API 响应
从 `GET /api/train/{id}/status` 获取：
```typescript
interface TrainStatusResponse {
  id: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  metrics_curve?: {
    train_loss: number[]
    val_loss: number[]
    train_accuracy: number[]
    val_accuracy: number[]
    epochs: number[]
  }
  // ... 其他字段
}
```

### 4.2 前端曲线数据格式
```typescript
interface ChartDataPoint {
  epoch: number
  train: number
  val: number
}
```

---

## 5. 非功能需求

- **性能**：曲线数据 ≤1000 个点时渲染流畅
- **响应式**：图表宽度自适应容器
- **加载状态**：数据加载中显示骨架屏或加载动画

---

## 6. 验收标准

| # | 标准 |
|---|------|
| AC1 | 训练完成后自动展示 loss 曲线 |
| AC2 | 可切换到 accuracy 曲线视图 |
| AC3 | 两个指标（train/val）在同一图中叠加显示 |
| AC4 | 图例点击可隐藏/显示对应曲线 |
| AC5 | Tooltip 显示 hover 点的具体数值 |
| AC6 | 训练中状态显示「训练中，曲线将在完成后展示」 |
| AC7 | TypeScript 编译无错误 |
| AC8 | Vite Build 成功 |

---

## 7. 技术约束

- 前端框架：React + TypeScript + TailwindCSS + Recharts
- 数据来源：`/api/train/{id}/status` 的 `metrics_curve` 字段
- 复用 Training Tab 现有状态（`currentJob`, `progress`）
- 不修改后端，只扩展前端展示
- 文件路径：`frontend/src/pages/Training.tsx`（在现有文件上扩展）

---

## 8. 与现有功能的关系

- Training Tab 已有训练状态管理，曲线模块作为子组件嵌入
- 复用 `trainApi.status()` 获取训练状态
- 训练完成后数据保存在 `currentJob.metrics_curve` 中
- 独立于 Experiments Tab 的曲线对比功能（那是多实验对比，这是单次训练曲线）

---

## 9. 里程碑

- **M1：** 曲线卡片基础布局 + 训练中/完成状态区分
- **M2：** Loss 曲线渲染（train_loss + val_loss）
- **M3：** Accuracy 曲线渲染 + Tab 切换
- **M4：** 图例点击隐藏/显示
- **M5：** TypeScript + Build 验证
