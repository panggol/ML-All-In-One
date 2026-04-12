# 技术调研：Data Management

## 调研问题

1. **前端上传进度**：如何在 FastAPI + React 中实现带百分比的上传进度条？
2. **大数据文件**：如何支持 50GB+ CSV 文件而不内存溢出（FR-026）？
3. **统计计算**：如何处理 nullable 列和全 null 列的统计量（NaN 处理）？

---

## 问题 1：前端上传进度条

### 方案 A：XMLHttpRequest with progress 事件

```typescript
const xhr = new XMLHttpRequest()
xhr.upload.addEventListener('progress', (e) => {
  const percent = (e.loaded / e.total) * 100
  setProgress(percent)
})
xhr.send(formData)
```

**优点**：支持实时进度百分比
**缺点**：需要绕过 axios/fetch；需单独实现错误处理

### 方案 B：FastAPI StreamingResponse + 前端轮询

后端分段写入，前端轮询进度状态。

**优点**：无需 XHR，改动小
**缺点**：进度不精确（依赖轮询频率）

### 方案 C：Starlette StreamingResponse（分块上传）

```python
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 流式写入，每写入 1MB 更新一次内存中的进度
    ...
```

**优点**：后端可控，内存占用低
**缺点**：前端仍需 XHR 获取进度

### 最终推荐：方案 A（XHR）

> 当前前端使用 axios，`axios` 支持 `onUploadProgress` 配置项，可直接实现：
> ```typescript
> await api.post('/data/upload', formData, {
>   onUploadProgress: (e) => setProgress(Math.round((e.loaded * 100) / e.total))
> })
> ```
> **优先级**：中（当前实现有加载状态，进度条为增强功能）

---

## 问题 2：大数据文件（50GB+ CSV）

### 方案 A：pandas chunksize

```python
for chunk in pd.read_csv(filepath, chunksize=100_000):
    process(chunk)  # 增量处理
```

**优点**：无需额外依赖，内存可控
**缺点**：无法做全局统计（需两遍扫描）

### 方案 B：Dask DataFrame

```python
import dask.dataframe as dd
df = dd.read_csv('large_file.csv')
result = df.describe().compute()  # 自动分块
```

**优点**：API 与 pandas 相似，自动并行
**缺点**：引入 Dask 依赖；某些 pandas 操作不兼容

### 方案 C：polars with streaming

```python
import polars as pl
q = pl.scan_csv('large_file.csv')
result = q.collect()
```

**优点**：性能最优，内存效率高
**缺点**：新增依赖；与现有 pandas 代码不兼容

### 最终推荐：方案 A（pandas chunksize）+ 标志位

> Constitution FR-026 明确要求 `chunksize` 或 Dask。当前 `pd.read_csv` 在大文件时会一次性加载到内存。
>
> **近期行动项**：在 `api/routes/data.py` 中添加文件大小检测：
> ```python
> # 文件 > 5GB 时使用 chunksize
> if data_file.size > 5 * 1024**3:
>     for chunk in pd.read_csv(data_file.filepath, chunksize=100_000):
>         ...
> ```
> **优先级**：高（FR-026 合规性缺口）

---

## 问题 3：NaN 处理（all-null 列）

### 当前实现（已修复）

```python
has_data = not col_data.isnull().all()
stat["min"] = float(col_data.min()) if has_data else None
stat["Q1"] = float(col_data.quantile(0.25)) if has_data else None
```

### 验证方式

```python
import pandas as pd
import numpy as np

df = pd.DataFrame({'col': [np.nan, np.nan, np.nan]})
assert df['col'].isnull().all() == True
assert pd.isna(df['col'].quantile(0.5))  # 全 null 返回 NaN，不报错
```

### 结论

- `df[col].isnull().all()` 检测全 null 列
- `quantile()` 对全 null 列返回 `NaN`（不抛异常）
- 当前实现已正确处理：`has_data` 标志位 + `None` 兜底

---

## 已验证的技术决策

| 决策 | 结论 | 日期 |
|------|------|------|
| pandas 用于 CSV 解析 | ✅ 继续使用，无需替换 | 2026-04-11 |
| SQLite 用于原型 | ✅ 默认使用，PostgreSQL 切换路径清晰 | 2026-04-11 |
| FastAPI Pydantic 验证 | ✅ 继续使用，自动 OpenAPI 文档 | 2026-04-11 |
| JWT Bearer Token 认证 | ✅ 继续使用，auth.py 已有实现 | 2026-04-11 |
| 本地文件系统存储 | ✅ 继续使用，适合单节点 | 2026-04-11 |
| Q1/median/Q3 分位数 | ✅ 已在 stats 端点实现（修复了遗漏） | 2026-04-11 |

---

## 踩坑记录

### 2026-04-11 — stats 端点缺少 Q1/median/Q3

- **现象**：`ColumnStatsDetail` Pydantic 模型中缺少 `Q1`、`median`、`Q3` 字段
- **根因**：实现时只添加了 min/max/mean/std，遗漏了 FR-015 要求的三个分位数
- **解决方案**：在 `ColumnStatsDetail` 模型和 `get_stats` 路由中补充了三个字段
- **验证**：`pytest tests/test_data_management_api.py -v` 全部通过（16 passed）

### 2026-04-11 — preview 端点返回 50 行而非 10 行

- **现象**：`pd.read_csv(filepath, nrows=50)` 硬编码为 50 行
- **根因**：实现时写错了默认值（可能是参考了其他系统的默认值）
- **解决方案**：改为 `nrows=10`，并更新 docstring
- **验证**：`pytest tests/test_data_management_api.py -v` 全部通过（test_preview_success 验证 ≥ 3 行）

### 2026-04-11 — 所有端点缺少结构化日志

- **现象**：6 个数据 API 端点没有任何日志输出
- **根因**：实现时跳过了可观测性实现
- **解决方案**：添加 `structured_log()` 辅助函数，在每个端点注入 request_id + duration + status_code
- **Constitution**：Principle VI — Observability（强制）
