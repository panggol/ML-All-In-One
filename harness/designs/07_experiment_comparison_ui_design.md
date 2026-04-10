# Experiment Comparison UI 设计文档

**模块：** Tab 3 实验对比（experiment_comparison）  
**Harness 阶段：** Step 2 设计  
**日期：** 2026-04-10  
**项目：** ml-all-in-one  

---

## 1. 布局结构

### 1.1 实验列表视图（现有 → 扩展 Checkbox 模式）

```
┌─ 顶部操作栏 ──────────────────────────────────────────┐
│ [← 返回]  (仅在对比视图显示)                           │
│                    已选择 3 个实验   [对比] [取消选择] │
└───────────────────────────────────────────────────────┘
┌─ 实验列表 ────────────────────────────────────────────┐
│ [✓] exp_001 | accuracy=0.97 | f1=0.96 | 运行中        │
│ [✓] exp_002 | accuracy=0.95 | f1=0.94 | 已完成        │
│ [ ] exp_003 | accuracy=0.93 | f1=0.92 | 已完成        │
│ [✓] exp_004 | accuracy=0.91 | f1=0.90 | 已完成        │
└───────────────────────────────────────────────────────┘
```

**Checkbox 选择行为：**
- 点击行任意位置或 Checkbox 切换选中状态
- 选中行背景色：`bg-indigo-50/30`（淡紫色）
- 未选中行：默认背景
- 底部栏固定在视口底部，不随列表滚动

### 1.2 对比视图（实验选择后）

```
┌─ 顶部操作栏 ──────────────────────────────────────────┐
│ [← 返回]  已选择 3 个实验对比     [取消选择]            │
└───────────────────────────────────────────────────────┘
┌─ 子 Tab ───────────────────────────────────────────────┐
│ [指标对比表] [曲线对比]                                 │
└───────────────────────────────────────────────────────┘
┌─ 指标对比表 ───────────────────────────────────────────┐
│ 实验名 | 任务 | 模型 | 准确率↑ | F1↑ | 精确率↑ | ...  │
│ exp_001 |分类 | RF  | 0.970   | 0.96 | 0.965   | ...  │
│ exp_004 |分类 | RF  | 0.910   | 0.90 | 0.895   | ...  │
│ exp_002 |分类 | SVM | 0.950   | 0.94 | 0.935   | ...  │
└───────────────────────────────────────────────────────┘
┌─ 曲线对比 ─────────────────────────────────────────────┐
│ 指标: [▼ Accuracy]   (下拉: Accuracy / Loss / F1)     │
│ ┌────────────────────────────────────────────────────┐ │
│ │           📈 曲线叠加图                              │ │
│ │  0.98 ┤    ╱╱                                        │ │
│ │  0.95 ┤ ╱╱  ╲╲  ─ exp_001 (Indigo)                 │ │
│ │  0.92 ┤╱     ╲ ╲ ─ exp_004 (Amber)                 │ │
│ │      1    5   10   Epoch                            │ │
│ └────────────────────────────────────────────────────┘ │
│ 图例: ● exp_001 ● exp_002 ● exp_004                   │
└───────────────────────────────────────────────────────┘
```

---

## 2. 视觉规格

### 2.1 颜色规格
- 选中行背景：`bg-indigo-50`
- 最优指标高亮：`bg-emerald-50` + `text-emerald-700` 字体
- 按钮主色：`bg-indigo-600 hover:bg-indigo-700`
- 按钮次色：`bg-slate-100 hover:bg-slate-200 text-slate-700`
- 危险按钮：`bg-red-500 hover:bg-red-600`

### 2.2 字体规格
- 页面标题：`text-lg font-semibold text-slate-800`
- 表格表头：`text-xs font-medium text-slate-500 uppercase tracking-wider`
- 表格内容：`text-sm text-slate-700`
- 图例：`text-xs`

### 2.3 间距规格
- 页面内边距：`p-6`
- 卡片内边距：`p-4`
- 元素间距：`gap-4`
- 表格单元格padding：`px-3 py-2`

### 2.4 曲线图表规格
- 图表高度：`h-80`（320px）
- 线条粗细：`strokeWidth={2}`
- 点半径：`dot={{ r: 3 }}`
- X轴标签：`fontSize: 12, fill: #64748b`
- Y轴标签：`fontSize: 12, fill: #64748b`
- Tooltip：`bg-white border border-slate-200 rounded-lg text-sm`

---

## 3. 组件规格

### 3.1 CheckboxColumn
- 宽度：40px（固定）
- 居中对齐
- Checkbox 组件：`accent-indigo-600`

### 3.2 CompareBar（底部浮动栏）
- 定位：`sticky bottom-4 mx-6 mb-4`
- 背景：`bg-white border border-slate-200 rounded-xl shadow-lg`
- 高度：`h-14`
- 布局：`flex items-center justify-between px-4`
- 左侧：已选实验数量文字
- 右侧操作：`[取消选择]` `[对比]` 按钮

### 3.3 MetricBadge（指标单元格）
- 数值格式：`0.0000`（4位小数）
- 最优值：`bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded`
- 缺失值：`-` 灰色

### 3.4 ComparisonChart
- 基于 Recharts `LineChart`
- 响应式容器：`ResponsiveContainer width="100%" height={320}`
- 指标切换：原生 `<select>` 组件
- 图例：`layout="horizontal" verticalAlign="bottom"`

### 3.5 ComparisonTable
- 固定表头：`table-fixed`
- 列宽：实验名 140px，任务/模型 各 80px，指标各 70px
- 滚动容器：`max-h-96 overflow-y-auto`
- 表头吸顶：`sticky top-0 bg-white z-10`

---

## 4. 状态规格

### 4.1 组件状态
| 状态 | 表现 |
|------|------|
| 默认（无选中） | Checkbox 全部未选中，CompareBar 隐藏 |
| 部分选中 | CompareBar 显示选中数量，取消选择/对比按钮可用 |
| 对比视图-指标表 | 子 Tab 激活「指标对比表」，表格内容显示 |
| 对比视图-曲线 | 子 Tab 激活「曲线对比」，图表渲染 |
| 无实验数据 | 空状态：「还没有实验数据，请先运行训练」 |

### 4.2 交互状态
| 交互 | 行为 |
|------|------|
| 点击 Checkbox | 切换选中状态，更新 selectedIds |
| 点击「对比」 | 验证 selectedIds.length >= 2，切换到对比视图 |
| 点击「取消选择」 | 清空 selectedIds，CompareBar 消失 |
| 点击图例项 | 切换对应曲线显示/隐藏（Recharts legend onClick） |
| 切换指标下拉 | 重新渲染曲线（不同 metric 的曲线数据） |
| 点击「返回」 | 回到列表视图（保留 selectedIds） |

---

## 5. 技术实现要点

- 在 `Experiments.tsx` 中新增 `viewMode: 'list' | 'compare'` 状态
- `selectedIds: string[]` 存储选中的实验 ID
- `compareTab: 'table' | 'chart'` 切换指标表/曲线
- 复用现有 `Experiment[]` 数据，不需要额外 API 调用
- 颜色分配：维护 `colorPalette` 数组，顺序分配，下标循环
- 图例点击隐藏：通过 Recharts `hide` 属性控制每条线的显示
- 指标最优高亮：遍历 `metrics[]` 找最大值，标记 `isBest=true`
