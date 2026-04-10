# training_curves 模块 QA 测试报告

**模块：** Training Curves（训练曲线图）  
**测试日期：** 2026-04-11  
**项目：** ml-all-in-one  
**测试工程师：** QA-Subagent  
**代码文件：** `frontend/src/pages/Training.tsx`（含 `TrainingCurves` + `TrainingCurveCard` 子组件）

---

## 1. 构建测试

| 测试项 | 命令 | 结果 |
|--------|------|------|
| TypeScript 编译 | `npx tsc --noEmit` | ✅ 通过（无输出，无错误） |
| Vite 生产构建 | `npm run build` | ✅ 通过（exit code 0，8.76s） |

> ⚠️ 警告（非阻塞）：dist/assets/index-DJpJFC1Z.js 打包后 777KB，超过 500KB 建议值。属于现有打包策略，非本次功能引入，建议后续通过 code-splitting 优化。

---

## 2. 验收标准（AC）核对

### AC1：训练完成后自动展示 loss 曲线 ✅

**实现证据：**
- 轮询 effect（`useEffect` 监听 `currentJob`）：当 `status.status === 'completed' && status.metrics_curve` 时，调用 `setMetricsCurve(status.metrics_curve)` + `setCurveExpanded(true)`
- `TrainingCurves` 组件默认 `activeMetric` 为 `'loss'`，`buildChartData` 默认构建 loss 数据
- `TrainingCurveCard` 在 `status === 'completed' && metricsCurve` 时渲染 `<TrainingCurves metrics_curve={metricsCurve} />`

**结论：** ✅ 通过

---

### AC2：可切换到 accuracy 曲线视图 ✅

**实现证据：**
- `TrainingCurves` 组件内部有 `activeMetric` state：`useState<'loss' | 'accuracy'>('loss')`
- 两个 Tab 按钮："Loss" 和 "Accuracy"，点击分别 `setActiveMetric('loss')` / `setActiveMetric('accuracy')`
- `buildChartData(metrics_curve, activeMetric)` 接收 metric 参数，构建对应的 chartData
- Tab 样式激活态：选中态 `bg-indigo-600 text-white`，非选中态 `bg-slate-100 text-slate-600`

**结论：** ✅ 通过

---

### AC3：两个指标（train/val）在同一图中叠加显示 ✅

**实现证据：**
- 同一 `LineChart` 内渲染两个 `Line` 组件：
  - `<Line dataKey="train" name="Train {metricLabel}" stroke="#6366F1" />`（蓝）
  - `<Line dataKey="val" name="Val {metricLabel}" stroke="#F59E0B" />`（橙）
- 颜色符合需求文档规定（蓝 `#6366F1`、橙 `#F59E0B`）

**结论：** ✅ 通过

---

### AC4：图例点击可隐藏/显示对应曲线（本次修复重点）✅

**实现证据：**
- `hiddenSeries` state：`useState<Set<string>>(new Set())`，管理被隐藏的 series key
- `toggleSeries` 函数：点击图例时切换 series 的显示/隐藏
- `<Legend onClick={(e: any) => toggleSeries(e.dataKey)} />` 绑定点击事件
- 每个 `Line` 组件：
  - `hide={hiddenSeries.has('train'/'val')}` — 控制曲线渲染
  - `stroke={hiddenSeries.has('key') ? '#cbd5e1' : COLOR}` — 被隐藏时显示灰色占位

**结论：** ✅ 通过（关键修复已实现）

---

### AC5：Tooltip 显示 hover 点的具体数值 ✅

**实现证据：**
- `<Tooltip formatter={formatter} />`，其中 `formatter = (v: any) => typeof v === 'number' ? v.toFixed(4) : v`
- Tooltip 样式配置：`backgroundColor: 'white'`、圆角、阴影
- `labelStyle` 配置：颜色 `#334155`，加粗

**结论：** ✅ 通过

---

### AC6：训练中状态显示「训练中，曲线将在完成后展示」✅

**实现证据：**
- `TrainingCurveCard` 组件中：
  ```tsx
  {(status === 'running') && !curveExpanded && (
    <div className="text-center text-slate-400 py-8 bg-slate-50 rounded-lg">
      训练中，曲线将在完成后展示
    </div>
  )}
  ```
- 训练失败状态另有独立文案「训练失败，无曲线数据」

**结论：** ✅ 通过

---

## 3. 测试汇总

| AC | 标准 | 结果 |
|----|------|------|
| AC1 | 训练完成后自动展示 loss 曲线 | ✅ 通过 |
| AC2 | 可切换到 accuracy 曲线视图 | ✅ 通过 |
| AC3 | 两个指标（train/val）在同一图中叠加显示 | ✅ 通过 |
| AC4 | 图例点击可隐藏/显示对应曲线 | ✅ 通过 |
| AC5 | Tooltip 显示 hover 点的具体数值 | ✅ 通过 |
| AC6 | 训练中状态显示「训练中，曲线将在完成后展示」 | ✅ 通过 |
| AC7 | TypeScript 编译无错误 | ✅ 通过 |
| AC8 | Vite Build 成功 | ✅ 通过 |

**最终判定：8/8 通过 ✅**

---

## 4. 代码质量备注

- **数据流清晰**：训练状态轮询 → `metrics_curve` 存入 state → 子组件渲染，流程无断层
- **图例交互**：使用 Recharts 内置 Legend `onClick` + Line `hide` prop 实现，方案可靠
- **状态隔离**：`hiddenSeries` 和 `activeMetric` 均封装在 `TrainingCurves` 内部，不污染外层状态
- **动态导入 Recharts**：通过 `import('recharts').then(...)` 延迟加载，避免首屏包体积影响
- **连接缺失数据**：`connectNulls={true}` 配置允许曲线跨过空值点，符合需求

---

_报告生成时间：2026-04-11 01:25 GMT+8_
