# ML All In One - 数据可视化模块 UI 设计

**项目：** ML All In One  
**模块：** 数据可视化 (Data Visualization)  
**日期：** 2026-04-09  
**状态：** 设计完成

---

## 一、模块概述

### 1.1 模块定位

数据可视化模块是 ML All In One 平台的核心分析组件，提供训练数据分布、特征重要性评估和预测结果展示三大功能。该模块遵循简约现代的设计语言，与整体平台风格保持一致。

### 1.2 设计目标

- **清晰直观**：让用户快速理解数据特征和模型表现
- **交互友好**：支持数据筛选、缩放、导出等操作
- **性能优先**：大数据集渲染优化，支持懒加载
- **响应式适配**：桌面端和移动端均可良好使用

### 1.3 技术选型

| 技术 | 选型 | 说明 |
|------|------|------|
| 图表库 | Recharts | React 原生，支持 TypeScript，社区活跃 |
| 坐标系统 | D3-scale | 精确的数据映射 |
| 颜色方案 | TailwindCSS + 自定义渐变 | 与设计系统一致 |
| 动效 | Framer Motion | 平滑过渡动画 |

---

## 二、设计规范

### 2.1 色彩系统（扩展）

```typescript
// 图表专用色板
const chartColors = {
  // 系列颜色
  series: [
    '#0ea5e9', // sky-500
    '#10b981', // emerald-500
    '#8b5cf6', // violet-500
    '#f59e0b', // amber-500
    '#ef4444', // red-500
    '#06b6d4', // cyan-500
    '#ec4899', // pink-500
  ],
  
  // 功能色
  gradient: {
    positive: ['#10b981', '#34d399'], // 正向
    negative: ['#ef4444', '#f87171'], // 负向
    neutral:  ['#0ea5e9', '#38bdf8'], // 中性
  },
  
  // 背景
  chartBg: '#ffffff',
  gridLine: '#e2e8f0', // slate-200
}
```

### 2.2 间距系统

```typescript
// 图表区域间距
const chartSpacing = {
  padding: {
    top: 24,
    right: 24,
    bottom: 40,
    left: 48,
  },
  legendGap: 16,
  tooltipGap: 8,
}
```

### 2.3 字体规范

```typescript
const chartTypography = {
  axisLabel: {
    fontSize: 12,
    fill: '#64748b', // slate-500
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  tooltipTitle: {
    fontSize: 13,
    fontWeight: 600,
    fill: '#0f172a', // slate-900
  },
  tooltipValue: {
    fontSize: 12,
    fill: '#475569', // slate-600
  },
}
```

### 2.4 圆角与阴影

```typescript
const chartStyle = {
  // 图表容器
  container: {
    borderRadius: '12px', // rounded-xl
    boxShadow: '0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)',
  },
  // Tooltip
  tooltip: {
    borderRadius: '8px',  // rounded-lg
    boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
  },
  // Legend
  legend: {
    borderRadius: '6px',   // rounded-md
  },
}
```

---

## 三、页面布局

### 3.1 整体布局结构

```
┌─────────────────────────────────────────────────────────────┐
│ Header (全局导航栏，与其他页面保持一致)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Page Title: 数据可视化                               │   │
│  │ Description: 分析训练数据分布与模型预测结果            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Filter Bar                                           │   │
│  │ [实验选择 ▼] [特征选择 ▼] [时间范围 ▼] [导出 ▼]       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Summary Cards (统计概览)                             │   │
│  │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │   │
│  │ │样本数量│ │特征数量│ │准确率  │ │F1分数  │        │   │
│  │ └────────┘ └────────┘ └────────┘ └────────┘        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────┐ ┌──────────────────────┐        │
│  │                      │ │                      │        │
│  │   数据分布图          │ │   特征重要性图        │        │
│  │   (Distribution)      │ │   (Feature Importance)│        │
│  │                      │ │                      │        │
│  │                      │ │                      │        │
│  └──────────────────────┘ └──────────────────────┘        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │              预测结果散点图                           │   │
│  │              (Prediction Scatter)                    │   │
│  │                                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 响应式断点

| 断点 | 布局变化 |
|------|----------|
| ≥1280px | 双列图表布局（2列） |
| 768-1279px | 单列堆叠布局（1列） |
| <768px | 全宽单列，简化图例 |

### 3.3 图表卡片设计

```
┌─────────────────────────────────────────┐
│ Card Header                             │
│ ┌─────────────────────────────────────┐ │
│ │ Title          [操作按钮] [折叠 ▼]  │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ Chart Area                              │
│                                         │
│    ┌───────────────────────────────┐    │
│    │                               │    │
│    │         图表内容               │    │
│    │                               │    │
│    │                               │    │
│    └───────────────────────────────┘    │
│                                         │
├─────────────────────────────────────────┤
│ Optional Footer                         │
│ ┌─────────────────────────────────────┐ │
│ │ 📊 图例 / 分页信息 / 详细数据链接    │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## 四、功能模块设计

### 4.1 数据分布图 (Distribution Chart)

**功能说明**：展示训练数据中各特征的数值分布情况，支持直方图和箱线图两种展示形式。

#### 交互功能
- 切换图表类型（直方图 / 箱线图）
- 选择特征进行展示
- 调整分组数量（bins: 10-100）
- 悬停显示详细统计信息
- 缩放和平移

#### 视觉设计
```
直方图样式：
- 柱形宽度：自适应，根据数据密度计算
- 柱形间距：2px
- 填充色：series[0]（sky-500）
- 悬停色：series[0] 深色版本
- 透明度：0.85（悬停时 1.0）

箱线图样式：
- 箱体填充：series[0] 透明度 0.3
- 中位线：series[0] 实色
- 须线：slate-400
- 异常点：series[0] + 红色标记
```

### 4.2 特征重要性图 (Feature Importance Chart)

**功能说明**：展示模型中各特征对预测结果的影响程度，帮助用户理解模型行为。

#### 交互功能
- 排序切换（升序 / 降序）
- 选择 Top N 显示（5 / 10 / 20 / All）
- 悬停显示贡献百分比
- 点击跳转特征详情

#### 视觉设计
```
水平条形图样式：
- 条形颜色：从 series[0] 到 series[5] 渐变
- 左侧标签：特征名称，可截断
- 条形宽度：最大 80% 容器宽度
- 数值标签：显示在条形末端
- 排序：按重要性降序排列
```

### 4.3 预测结果散点图 (Prediction Scatter Plot)

**功能说明**：展示模型预测值与真实值的对比，直观呈现预测效果。

#### 交互功能
- 选择 X/Y 轴字段
- 颜色编码（按真实标签 / 按预测正确性）
- 缩放和框选
- 显示趋势线
- 显示回归指标（R², RMSE, MAE）

#### 视觉设计
```
散点样式：
- 点半径：5px（可配置 3-10px）
- 透明度：0.6（密集区域加深）
- 正确预测：emerald-500
- 错误预测：red-500
- 趋势线：虚线，slate-400

参考线：
- 对角线（完美预测线）：slate-300，虚线
- 标注：y=x 文字说明
```

---

## 五、组件清单

### 5.1 图表组件

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `DistributionChart` | `components/charts/DistributionChart.tsx` | 数据分布直方图/箱线图 |
| `FeatureImportanceChart` | `components/charts/FeatureImportanceChart.tsx` | 特征重要性水平条形图 |
| `ScatterPlot` | `components/charts/ScatterPlot.tsx` | 预测结果散点图 |
| `ChartCard` | `components/charts/ChartCard.tsx` | 图表卡片包装器 |
| `ChartTooltip` | `components/charts/ChartTooltip.tsx` | 自定义图表 Tooltip |
| `ChartLegend` | `components/charts/ChartLegend.tsx` | 图例组件 |
| `ChartControls` | `components/charts/ChartControls.tsx` | 图表控制栏 |

### 5.2 筛选组件

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `ExperimentSelect` | `components/filter/ExperimentSelect.tsx` | 实验选择器 |
| `FeatureSelect` | `components/filter/FeatureSelect.tsx` | 特征选择器 |
| `DateRangePicker` | `components/filter/DateRangePicker.tsx` | 日期范围选择器 |
| `FilterBar` | `components/filter/FilterBar.tsx` | 筛选工具栏 |

### 5.3 统计组件

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `StatCard` | `components/StatCard.tsx` | 统计卡片（已有） |
| `MetricBadge` | `components/MetricBadge.tsx` | 指标徽章 |
| `ConfusionMatrix` | `components/charts/ConfusionMatrix.tsx` | 混淆矩阵（可选） |

### 5.4 页面组件

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `VisualizationPage` | `pages/Visualization.tsx` | 数据可视化主页面 |
| `DistributionView` | `pages/DistributionView.tsx` | 分布图全屏视图 |
| `ImportanceView` | `pages/ImportanceView.tsx` | 特征重要性全屏视图 |
| `ScatterView` | `pages/ScatterView.tsx` | 散点图全屏视图 |

---

## 六、Props 定义

### 6.1 DistributionChart Props

```typescript
interface DistributionChartProps {
  // 数据
  data: Array<{
    feature: string;
    value: number;
    label?: string;
  }>;
  
  // 配置
  config: {
    /** 图表类型 */
    chartType: 'histogram' | 'boxplot';
    /** 分组数量（直方图用） */
    bins?: number;
    /** 是否显示rug plot */
    showRug?: boolean;
    /** 是否显示密度曲线 */
    showDensity?: boolean;
  };
  
  // 样式
  style?: {
    fillColor?: string;
    strokeColor?: string;
    opacity?: number;
  };
  
  // 交互
  interactions?: {
    /** 是否可缩放 */
    zoomable?: boolean;
    /** 是否可框选 */
    brushable?: boolean;
    /** 点击回调 */
    onClick?: (data: DataPoint) => void;
    /** 悬停回调 */
    onHover?: (data: DataPoint | null) => void;
  };
  
  // 尺寸
  width?: number | string;
  height?: number;
}
```

### 6.2 FeatureImportanceChart Props

```typescript
interface FeatureImportanceChartProps {
  // 数据
  data: Array<{
    feature: string;
    importance: number;
    /** 可选：置信区间 */
    confidenceInterval?: [number, number];
  }>;
  
  // 配置
  config: {
    /** 排序方式 */
    sortBy: 'value' | 'alphabetical';
    /** 升序/降序 */
    ascending?: boolean;
    /** 显示数量限制 */
    topN?: number;
    /** 是否显示数值标签 */
    showValueLabels?: boolean;
    /** 是否显示误差线 */
    showErrorBars?: boolean;
  };
  
  // 样式
  style?: {
    /** 颜色方案 */
    colorScheme?: string[];
    /** 条形最大宽度百分比 */
    maxBarWidth?: number;
    /** 标签颜色 */
    labelColor?: string;
  };
  
  // 交互
  interactions?: {
    /** 点击回调 */
    onClick?: (feature: string) => void;
    /** 悬停高亮 */
    highlightOnHover?: boolean;
  };
  
  // 尺寸
  width?: number | string;
  height?: number;
}
```

### 6.3 ScatterPlot Props

```typescript
interface ScatterPlotProps {
  // 数据
  data: Array<{
    id: string | number;
    actual: number;
    predicted: number;
    /** 可选：分组标签 */
    group?: string;
    /** 可选：点大小 */
    size?: number;
    /** 可选：其他属性 */
    [key: string]: unknown;
  }>;
  
  // 配置
  config: {
    /** X轴字段 */
    xField: 'actual' | 'predicted' | string;
    /** Y轴字段 */
    yField: 'actual' | 'predicted' | string;
    /** 颜色编码方式 */
    colorBy: 'group' | 'correctness' | 'none';
    /** 是否显示趋势线 */
    showTrendline?: boolean;
    /** 是否显示参考线 */
    showReferenceLine?: boolean;
    /** 参考线类型 */
    referenceLineType?: 'diagonal' | 'horizontal' | 'vertical' | 'mean';
  };
  
  // 样式
  style?: {
    /** 点颜色 */
    pointColor?: string;
    /** 正确预测颜色 */
    correctColor?: string;
    /** 错误预测颜色 */
    incorrectColor?: string;
    /** 点半径 */
    pointRadius?: number;
    /** 点透明度 */
    pointOpacity?: number;
    /** 趋势线颜色 */
    trendlineColor?: string;
  };
  
  // 指标显示
  metrics?: {
    /** 是否显示R² */
    showRSquared?: boolean;
    /** 是否显示RMSE */
    showRMSE?: boolean;
    /** 是否显示MAE */
    showMAE?: boolean;
    /** 自定义指标 */
    customMetrics?: Array<{ label: string; value: number }>;
  };
  
  // 交互
  interactions?: {
    /** 是否可缩放 */
    zoomable?: boolean;
    /** 是否可框选 */
    brushable?: boolean;
    /** 点击回调 */
    onClick?: (point: DataPoint) => void;
    /** 悬停回调 */
    onHover?: (point: DataPoint | null) => void;
    /** 点选回调 */
    onSelect?: (points: DataPoint[]) => void;
  };
  
  // 尺寸
  width?: number | string;
  height?: number;
}
```

### 6.4 ChartCard Props

```typescript
interface ChartCardProps {
  // 内容
  title: string;
  description?: string;
  children: React.ReactNode;
  
  // 头部操作
  actions?: React.ReactNode;
  
  // 配置
  config?: {
    /** 是否可折叠 */
    collapsible?: boolean;
    /** 是否默认折叠 */
    defaultCollapsed?: boolean;
    /** 是否可全屏 */
    fullscreenable?: boolean;
  };
  
  // 样式
  style?: {
    /** 自定义类名 */
    className?: string;
    /** 自定义高度 */
    height?: number | string;
  };
  
  // 回调
  onCollapse?: (collapsed: boolean) => void;
}
```

### 6.5 ChartTooltip Props

```typescript
interface ChartTooltipProps {
  // 内容
  title?: string;
  items: Array<{
    label: string;
    value: string | number;
    color?: string;
    /** 值格式化函数 */
    formatter?: (value: number) => string;
  }>;
  
  // 位置
  position: {
    x: number;
    y: number;
  };
  
  // 配置
  config?: {
    /** 是否跟随鼠标 */
    followCursor?: boolean;
    /** 是否显示箭头 */
    showArrow?: boolean;
    /** 偏移量 */
    offset?: number;
  };
}
```

### 6.6 FilterBar Props

```typescript
interface FilterBarProps {
  // 筛选值
  filters: {
    experimentId?: string;
    featureIds?: string[];
    dateRange?: [Date, Date];
  };
  
  // 可选项
  options: {
    experiments: Array<{ id: string; name: string }>;
    features: Array<{ id: string; name: string }>;
  };
  
  // 回调
  onChange: (filters: Filters) => void;
  
  // 配置
  config?: {
    /** 显示的筛选器 */
    visibleFilters?: Array<'experiment' | 'feature' | 'dateRange' | 'export'>;
    /** 是否显示重置按钮 */
    showReset?: boolean;
  };
}
```

---

## 七、页面路由

```typescript
// App.tsx 中的路由配置

const visualizationTabs = [
  { id: 'distribution', label: '数据分布', icon: BarChart3 },
  { id: 'importance', label: '特征重要性', icon: TrendingUp },
  { id: 'scatter', label: '预测散点', icon: ScatterChart },
]

// 路由结构
<Route path="/visualization">
  <Route index element={<Navigate to="/visualization/distribution" replace />} />
  <Route path="distribution" element={<VisualizationPage tab="distribution" />} />
  <Route path="importance" element={<VisualizationPage tab="importance" />} />
  <Route path="scatter" element={<VisualizationPage tab="scatter" />} />
  <Route path=":experimentId" element={<VisualizationPage />}>
    <Route path="distribution" element={<DistributionView />} />
    <Route path="importance" element={<ImportanceView />} />
    <Route path="scatter" element={<ScatterView />} />
  </Route>
</Route>
```

---

## 八、状态管理

### 8.1 Local State（组件内）

```typescript
// 组件级别的临时状态
interface ChartLocalState {
  tooltip: { visible: boolean; position: Point; data: unknown };
  selection: { active: boolean; range?: [number, number] };
  zoom: { level: number; offset: Point };
  collapsed: boolean;
}
```

### 8.2 URL State（路由参数）

```typescript
// 通过 URL 同步状态
interface VisualizationURLState {
  experimentId?: string;
  featureIds?: string[];
  tab?: 'distribution' | 'importance' | 'scatter';
  chartType?: 'histogram' | 'boxplot';
  topN?: number;
}
```

### 8.3 Global State（Zustand）

```typescript
// 跨页面共享状态
interface VisualizationGlobalState {
  selectedExperiment: Experiment | null;
  cache: Map<string, ChartData>;
  preferences: {
    defaultChartType: 'histogram' | 'boxplot';
    defaultTopN: number;
    showGridLines: boolean;
  };
}
```

---

## 九、API 接口

### 9.1 获取分布数据

```typescript
// GET /api/experiments/:id/distribution
interface DistributionResponse {
  experimentId: string;
  features: Array<{
    name: string;
    type: 'numerical' | 'categorical';
    statistics: {
      min: number;
      max: number;
      mean: number;
      median: number;
      std: number;
      q1: number;
      q3: number;
    };
    histogram?: Array<{ bin: number; count: number }>;
  }>;
}
```

### 9.2 获取特征重要性

```typescript
// GET /api/experiments/:id/importance
interface ImportanceResponse {
  experimentId: string;
  modelType: string;
  features: Array<{
    name: string;
    importance: number;
    std?: number;
  }>;
}
```

### 9.3 获取预测结果

```typescript
// GET /api/experiments/:id/predictions
interface PredictionsResponse {
  experimentId: string;
  total: number;
  metrics: {
    r2: number;
    rmse: number;
    mae: number;
    accuracy?: number;
    f1?: number;
  };
  samples: Array<{
    id: string;
    actual: number;
    predicted: number;
    correct: boolean;
  }>;
}
```

---

## 十、后续优化

### 短期计划
- [ ] 实现基础图表组件
- [ ] 接入真实 API 数据
- [ ] 添加导出功能（PNG / CSV）
- [ ] 实现图表全屏查看

### 中期计划
- [ ] 添加数据对比功能
- [ ] 实现图表联动
- [ ] 添加动画过渡效果
- [ ] 支持暗色主题

### 长期计划
- [ ] 添加自定义图表配置
- [ ] 支持自定义图表类型
- [ ] 添加图表收藏功能
- [ ] 支持图表模板

---

*文档版本：v1.0.0 | 最后更新：2026-04-09*
