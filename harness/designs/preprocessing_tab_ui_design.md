# 预处理 Tab - UI 设计

_模块名称: preprocessing-tab_
_版本: 1.0_
_日期: 2026-04-10_

---

## 1. 布局结构

采用 **左右分栏** 布局（与 Training Tab 一致）：

```
┌──────────────────────────────────────────────────────┐
│  Tab 导航 (预处理 - 高亮)                            │
├─────────────────────┬────────────────────────────────┤
│  左侧：配置面板       │  右侧：预览面板                │
│  (40%)              │  (60%)                        │
│                     │                                │
│  ① 数据选择          │  数据预览表格                  │
│  ② 预处理步骤勾选    │  (处理前 | 处理后 对比)        │
│  ③ 参数配置          │                                │
│  ④ 流水线概览        │  统计信息                      │
│                     │                                │
│  [预览] [保存]       │                                │
└─────────────────────┴────────────────────────────────┘
```

---

## 2. 组件清单

### 2.1 数据选择卡片（左侧顶部）
- 上传区域（虚线边框，拖拽上传）
- 或选择已有文件下拉框
- 文件信息展示：文件名、行数、列数
- 列类型标签（数值/类别）

### 2.2 预处理步骤卡片（左侧中部）
- 3 个可折叠的步骤模块：
  - **缺失值填充**（展开时有 strategy 选择）
  - **归一化/标准化**（单选：None / MinMax / Standard）
  - **特征选择**（展开时有 threshold 滑块 + 列多选）

每个步骤模块：
```
┌─ [✓] 缺失值填充 ──────────────────────┐
│  Strategy: [mean ▼]                   │
└───────────────────────────────────────┘
```

### 2.3 流水线概览（左侧底部）
- 显示已启用步骤的执行顺序（从上到下编号）
- 执行顺序说明：
  1. 缺失值填充 → 2. 归一化/标准化 → 3. 特征选择

### 2.4 操作按钮
- **[预览]**: 调用 preview API，展示处理结果
- **[保存]**: 调用 transform API，保存数据集（预览后可用）

### 2.5 预览表格（右侧）
- Tab 切换：「原始数据 | 处理后数据」
- 前 10 行表格展示
- 分页支持

### 2.6 统计信息面板（右侧底部）
- 每列统计：均值、标准差、最小值、最大值、缺失值数量
- 原始 vs 处理后对比（双列展示）

---

## 3. 交互流程

### 流程 1：正常预处理
1. 用户选择/上传数据 → 右侧加载原始数据预览
2. 用户勾选需要的预处理步骤 + 配置参数
3. 点击「预览」→ 右侧展示处理后数据 + 统计对比
4. 用户确认无误 → 点击「保存」→ 保存成功提示

### 流程 2：无预处理直接保存
1. 用户选择数据
2. 点击「保存」（不预览）→ 跳过预览，直接保存原数据

### 流程 3：错误处理
- 未选择数据时点击预览 → Toast: "请先选择数据集"
- 预览失败 → Toast 展示错误信息

---

## 4. 配色与组件复用

- 复用现有组件：Card, Button, Select, Input, ProgressBar
- 步骤启用状态：绿色勾选框，禁用时灰色
- 预览对比：原始数据蓝色边框，处理后绿色边框
- 流水线顺序：垂直连线 + 数字编号

---

## 5. API 调用设计

### Preview（预览）
```
POST /api/preprocessing/preview
Body: {
  data_file_id: number,
  steps: {
    imputer: { enabled: boolean, strategy: string },
    scaler: { enabled: boolean, type: 'minmax' | 'standard' | null },
    feature_select: { enabled: boolean, threshold: number, selected_columns: string[] }
  }
}
Response: {
  original_preview: any[][],     // 前 10 行
  transformed_preview: any[][], // 前 10 行
  stats: ColumnStats[],         // 每列统计
  shape: [number, number]
}
```

### Transform（保存）
```
POST /api/preprocessing/transform
Body: {
  data_file_id: number,
  steps: PreprocessingSteps,
  output_name: string
}
Response: {
  data_file_id: number,
  filename: string,
  rows: number,
  columns: number
}
```

---

## 6. 路由集成

- URL: `/preprocessing`
- Tab 定义添加到 `App.tsx` tabs 数组
- 引入新页面组件 `Preprocessing.tsx`
