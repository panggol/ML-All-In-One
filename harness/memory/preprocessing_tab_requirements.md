# 预处理 Tab - 需求分析

_模块名称: preprocessing-tab_
_版本: 1.0_
_日期: 2026-04-10_

---

## 1. 功能概述

Tab 4 预处理模块为用户提供可视化数据预处理能力，支持归一化/标准化/缺失值填充/特征选择等操作流水线，并实时预览处理结果。

**核心价值：** 用户可在训练前对数据集进行零代码预处理，降低 ML 门槛。

---

## 2. 用户故事

- **US-1**: 用户上传 CSV 文件后，能选择性地配置预处理步骤（可多选）
- **US-2**: 用户配置完步骤后，能实时预览处理前/后的数据对比
- **US-3**: 用户确认预览无误后，可保存预处理后的数据集到平台，供训练使用
- **US-4**: 流水线支持拖拽排序（可选，后期增强）

---

## 3. 功能范围

### 3.1 数据加载
- 上传 CSV 文件（drag & drop 或点击上传）
- 选择已有数据集（从 data 文件列表）
- 展示数据集基本信息（行数、列数、列类型）
- 数据预览（前 5 行表格展示）

### 3.2 预处理步骤配置
支持以下 4 种预处理步骤，每步可独立开关：

| 步骤 | 类型 | 参数 |
|------|------|------|
| 缺失值填充 | Imputer | strategy: mean / median / most_frequent / constant |
| 归一化 | MinMaxScaler | feature_range: (0, 1) 或自定义 |
| 标准化 | StandardScaler | with_mean: bool, with_std: bool |
| 特征选择 | VarianceThreshold | threshold: float |

**流水线执行顺序**（固定）：
1. 缺失值填充（order=0）
2. 特征选择（order=0，并行）
3. 归一化/标准化（order=2，互斥，只能选一个）

### 3.3 流水线预览
- 显示流水线执行顺序图示
- 每步的处理前后数据对比（前 5 行）
- 展示各列的统计信息（均值、标准差、最小、最大）
- 缺失值统计

### 3.4 保存结果
- 将预处理后的数据保存为新数据集
- 自动命名：`原始文件名_preprocessed`
- 返回保存后的 data_file_id

---

## 4. 非功能需求

### 4.1 性能
- 预览操作在 3 秒内完成（数据集不超过 10 万行）
- 10 万行以上数据采用采样预览（取前 1000 行）

### 4.2 错误处理
- 文件格式错误：提示"仅支持 CSV 格式"
- 空数据集：提示"数据集为空"
- 缺失值过多：警告提示

### 4.3 UI 约束（继承设计规范）
- 深色主题（Slate 900 背景）
- 6 个 Tab 导航（Dashboard/Training/Experiments/AutoML/预处理/推理/数据）
- 使用现有组件库（Card、Button、Select、Input 等）

---

## 5. 数据模型

### 5.1 前端状态

```typescript
interface PreprocessingState {
  // 数据加载
  selectedFile: DataFile | null;
  fileStats: { rows: number; columns: string[]; dtypes: Record<string, string> } | null;
  originalData: any[][];  // 原始数据
  previewData: any[][];   // 预览数据

  // 流水线配置
  steps: {
    imputer: { enabled: boolean; strategy: string };
    scaler: { enabled: boolean; type: 'minmax' | 'standard' | null };
    featureSelect: { enabled: boolean; threshold: number };
  };

  // 预览状态
  previewResult: {
    original: any[][];
    transformed: any[][];
    stats: ColumnStats[];
  } | null;

  // 保存状态
  saving: boolean;
  savedFileId: number | null;
}
```

### 5.2 后端 API

**POST /api/preprocessing/preview**
- Request: `{ data_file_id: number, steps: PreprocessingSteps }`
- Response: `{ preview_rows: any[][], stats: ColumnStats[], shape: [rows, cols] }`

**POST /api/preprocessing/transform**
- Request: `{ data_file_id: number, steps: PreprocessingSteps, output_name: string }`
- Response: `{ data_file_id: number, filename: string, rows: number, columns: number }`

---

## 6. 验收标准

- [ ] 用户可上传 CSV 并加载列信息
- [ ] 用户可开启/关闭各预处理步骤
- [ ] 用户配置后点击"预览"可看到处理前后对比
- [ ] 流水线按正确顺序执行
- [ ] 用户可保存预处理结果为新数据集
- [ ] UI 风格与现有页面一致
- [ ] 后端 API 通过单元测试
- [ ] 前端无 console.error
