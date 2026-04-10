# 训练曲线图 UI 设计文档

**模块：** 训练曲线图（Training Curves）  
**Harness 阶段：** Step 2 设计  
**日期：** 2026-04-10  
**项目：** ml-all-in-one  

---

## 1. 布局结构

### 1.1 训练 Tab 整体布局（两栏）

```
┌─ 左侧：训练配置 ──────────┐  ┌─ 右侧：训练结果 ───────────────┐
│                            │  │                               │
│  数据选择 / 特征选择        │  │  进度条（训练中）              │
│  模型选择 / 训练按钮        │  │  实时日志（训练中）            │
│                            │  │                               │
│                            │  │  ┌─ 训练曲线图 ──────────────┐ │
│                            │  │  │ Loss / Accuracy [Tab]     │ │
│                            │  │  │ ┌───────────────────────┐ │ │
│                            │  │  │ │   📈 曲线图             │ │ │
│                            │  │  │ └───────────────────────┘ │ │
│                            │  │  │ ● Train Loss  ● Val Loss   │ │
│                            │  │  └───────────────────────────┘ │
│                            │  └───────────────────────────────┘ │
└────────────────────────────┘
```

### 1.2 曲线卡片展开/收起
- 默认收起（只显示标题栏）
- 训练完成后自动展开，或用户点击展开按钮
- 标题栏：「📈 训练曲线」+ 展开/收起箭头

---

## 2. 视觉规格

### 2.1 颜色规格
- Train Loss：`#6366F1`（Indigo-500）
- Val Loss：`#F59E0B`（Amber-500）
- Train Accuracy：`#6366F1`（Indigo-500）
- Val Accuracy：`#F59E0B`（Amber-500）
- 背景色：`bg-slate-50`
- 卡片背景：`bg-white`

### 2.2 曲线图表规格
- 图表高度：`h-64`（256px）
- 线条粗细：`strokeWidth={2}`
- 点半径：`dot={{ r: 3 }}`（仅 hover 时显示）
- Tooltip：白色背景 + 边框 + 数值 4 位小数
- X轴：`fontSize: 12`，颜色 `#64748b`
- Y轴：`fontSize: 12`，颜色 `#64748b`
- 网格线：水平网格 `stroke="#e2e8f0"`，垂直网格不显示

### 2.3 Tab 切换按钮
- 两个按钮：「Loss」「Accuracy」
- 激活态：`bg-indigo-600 text-white`
- 非激活态：`bg-slate-100 text-slate-600 hover:bg-slate-200`

### 2.4 空状态（训练中）
- 灰色提示文字：「训练中，曲线将在完成后展示」
- 浅灰色背景卡片：`bg-slate-50`
- 文字：`text-slate-400 text-sm`

---

## 3. 组件规格

### 3.1 TrainingCurveCard（曲线卡片）
```tsx
// 位置：Training.tsx 右侧区域底部
<Card>
  <div className="flex items-center justify-between mb-4">
    <h3 className="text-base font-semibold text-slate-700">📈 训练曲线</h3>
    <button onClick={toggleExpand}>展开/收起</button>
  </div>
  
  {status === 'running' && (
    <div className="text-center text-slate-400 py-8">训练中，曲线将在完成后展示</div>
  )}
  
  {status === 'completed' && expanded && (
    <TrainingCurves metrics_curve={currentJob.metrics_curve} />
  )}
</Card>
```

### 3.2 TrainingCurves（曲线渲染组件）
```tsx
// Props: { metrics_curve: MetricsCurve }
// 内部状态: activeMetric: 'loss' | 'accuracy'

// Tab 切换
<div className="flex gap-2 mb-4">
  <button className={activeMetric === 'loss' ? 'bg-indigo-600 text-white' : 'bg-slate-100'}
    onClick={() => setActiveMetric('loss')}>Loss</button>
  <button className={activeMetric === 'accuracy' ? 'bg-indigo-600 text-white' : 'bg-slate-100'}
    onClick={() => setActiveMetric('accuracy')}>Accuracy</button>
</div>

// 图表
<ResponsiveContainer width="100%" height={256}>
  <LineChart>
    <XAxis dataKey="epoch" />
    <YAxis />
    <Tooltip formatter={(v) => toFixed(4)} />
    <Line type="monotone" dataKey="train" stroke="#6366F1" />
    <Line type="monotone" dataKey="val" stroke="#F59E0B" />
  </LineChart>
</ResponsiveContainer>

// 图例
<div className="flex gap-4 mt-2">
  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-indigo-500 inline-block"></span> Train</span>
  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-500 inline-block"></span> Val</span>
</div>
```

### 3.3 动画规格
- 图表首次加载：从左到右绘制动画（`isAnimationActive={true}`，duration 1000ms）
- 展开动画：`transition-all duration-300`

---

## 4. 状态规格

| 训练状态 | 曲线卡片显示 |
|---------|------------|
| `pending` | 收起，不显示曲线区域 |
| `running` | 展开，显示「训练中」空状态 |
| `completed` | 自动展开，显示曲线 |
| `failed` | 展开，显示「训练失败，无曲线数据」|

---

## 5. 技术实现要点

- `currentJob.metrics_curve` 来自训练完成后的 `/api/train/{id}/status` 响应
- `metrics_curve` 结构：
  ```typescript
  {
    epochs: number[],
    train_loss: number[],
    val_loss: number[],
    train_accuracy: number[],
    val_accuracy: number[]
  }
  ```
- 转换函数 `buildChartData(metrics_curve, metric)`：
  ```typescript
  return epochs.map((e, i) => ({
    epoch: e,
    train: metrics_curve[`train_${metric}`][i],
    val: metrics_curve[`val_${metric}`][i]
  }))
  ```
- 图表数据使用 `useMemo` 缓存，避免重复计算
- Recharts 动态 import（与 Experiments.tsx 保持一致）
