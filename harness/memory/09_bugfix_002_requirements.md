# BUG-002 修复需求分析

## Bug 信息
- **Bug ID:** BUG-002
- **名称:** 训练接口不支持含字符串列的 CSV 文件
- **严重度:** 🔴 中等
- **涉及文件:** `api/routes/train.py`

## 问题描述
上传包含非数值列（如 `species` 字符串列）的 CSV 文件进行训练时，训练任务状态变为 `failed`，错误信息：`could not convert string to float`。

## 根因分析
`_run_training` 函数中，`pd.read_csv()` 加载的 DataFrame 直接传给 mlkit 的 DataLoader 和 sklearn 模型，DataLoader 未对非数值列做过滤，导致 sklearn 模型收到字符串数据后抛出异常。

## 修复方案
在 `_run_training` 中，`DataLoader` 加载数据集前，过滤掉非数值列，保留目标列：

```python
# df 加载后、创建 runner 前加入：
target_col = job.target_column
numeric_df = df.select_dtypes(include=['number'])
# 如果目标列本身是字符串类型，需要确保它在 df 中（因为 select_dtypes 会过滤掉）
if target_col not in numeric_df.columns and target_col in df.columns:
    numeric_df[target_col] = df[target_col]
df = numeric_df

# 过滤后检查特征数量
if len(df.columns) == 0:
    raise ValueError("过滤后无有效列，请确保 CSV 包含至少一个数值特征列和目标列")
```

同时，更新 DataLoader 的数据源为过滤后的 CSV 临时文件。

## 关键约束
1. 目标列如果是字符串类型，需特殊处理（保留）
2. 过滤后若只剩目标列（无特征），需报错
3. 不破坏现有正常训练流程

## 验证要求
1. 集成测试：用含字符串列的 CSV 上传训练，验证 status 不为 `failed`
2. pytest 全量测试通过
3. TypeScript + Build 通过
