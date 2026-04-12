# API 合约：Data Management

**版本**：v1.0.0
**对应 Spec**：spec.md（2026-04-11）
**Base URL**：`/api/data`

> 所有端点均需要认证：`Authorization: Bearer <token>`（JWT Bearer Token）

---

## 共同响应头

```http
Content-Type: application/json
```

## 共同错误响应格式

```json
{
  "detail": "错误描述字符串"
}
```

| HTTP 状态码 | 含义 |
|------------|------|
| 200 | 成功 |
| 400 | 请求格式错误（如非 CSV 文件） |
| 401 | 未认证（缺少或无效 Token） |
| 404 | 资源不存在 |
| 413 | 文件超过大小限制（默认 500MB） |
| 500 | 服务器内部错误 |

---

## 1. 上传数据文件

**路径**：`POST /api/data/upload`
**Content-Type**：`multipart/form-data`
**描述**：上传 CSV 文件，系统自动解析基本信息并存入数据库

### 请求参数

| 参数 | 类型 | 位置 | 必填 | 说明 |
|------|------|------|------|------|
| file | UploadFile | body | ✅ | CSV 文件（form-data 字段名） |

### 成功响应（200）

```json
{
  "id": 1,
  "filename": "iris.csv",
  "size": 4321,
  "rows": 150,
  "columns": ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"],
  "created_at": "2026-04-11T08:30:00.000000"
}
```

### 错误响应（400 - 非 CSV）

```json
{
  "detail": "只支持 CSV 格式文件"
}
```

### 错误响应（413 - 文件过大）

```json
{
  "detail": "文件超过大小限制 (500MB)"
}
```

---

## 2. 列出数据集

**路径**：`GET /api/data/list`
**描述**：返回当前用户的所有数据集，按上传时间倒序排列

### 查询参数

无

### 成功响应（200）

```json
[
  {
    "id": 2,
    "filename": "titanic.csv",
    "size": 61194,
    "rows": 891,
    "columns": ["PassengerId", "Survived", "Pclass", "Name", "Sex", "Age", "SibSp", "Parch", "Ticket", "Fare", "Cabin", "Embarked"],
    "created_at": "2026-04-11T09:00:00.000000"
  },
  {
    "id": 1,
    "filename": "iris.csv",
    "size": 4321,
    "rows": 150,
    "columns": ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"],
    "created_at": "2026-04-11T08:30:00.000000"
  }
]
```

### 空列表响应（200）

```json
[]
```

---

## 3. 获取文件信息

**路径**：`GET /api/data/{file_id}`
**描述**：获取单个数据集的基本信息

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| file_id | int | 文件 ID |

### 成功响应（200）

```json
{
  "id": 1,
  "filename": "iris.csv",
  "size": 4321,
  "rows": 150,
  "columns": ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"],
  "created_at": "2026-04-11T08:30:00.000000"
}
```

### 错误响应（404）

```json
{
  "detail": "文件不存在"
}
```

---

## 4. 预览数据（前 10 行）

**路径**：`GET /api/data/{file_id}/preview`
**描述**：返回数据集的前 10 行，用于快速检查数据结构和内容

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| file_id | int | 文件 ID |

### 成功响应（200）

```json
{
  "columns": ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"],
  "rows": [
    [5.1, 3.5, 1.4, 0.2, "setosa"],
    [4.9, 3.0, 1.4, 0.2, "setosa"],
    [4.7, 3.2, 1.3, 0.2, "setosa"],
    [4.6, 3.1, 1.5, 0.2, "setosa"],
    [5.0, 3.6, 1.4, 0.2, "setosa"],
    [5.4, 3.9, 1.7, 0.4, "setosa"],
    [4.6, 3.4, 1.4, 0.3, "setosa"],
    [5.0, 3.4, 1.5, 0.2, "setosa"],
    [4.4, 2.9, 1.4, 0.2, "setosa"],
    [4.9, 3.1, 1.5, 0.1, "setosa"]
  ],
  "total_rows": 10
}
```

### 错误响应（404）

```json
{
  "detail": "文件不存在"
}
```

---

## 5. 统计数据

**路径**：`GET /api/data/{file_id}/stats`
**描述**：返回数据集的统计摘要，包括每列的类型、缺失值、唯一值，以及数值列的分位数

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| file_id | int | 文件 ID |

### 成功响应（200）

```json
{
  "total_rows": 150,
  "total_columns": 5,
  "column_stats": [
    {
      "column": "sepal_length",
      "dtype": "float64",
      "null_count": 0,
      "unique_count": 35,
      "min": 4.3,
      "max": 7.9,
      "mean": 5.84,
      "std": 0.8281,
      "Q1": 5.1,
      "median": 5.8,
      "Q3": 6.4
    },
    {
      "column": "species",
      "dtype": "object",
      "null_count": 0,
      "unique_count": 3,
      "top_values": [
        { "value": "setosa", "count": 50 },
        { "value": "versicolor", "count": 50 },
        { "value": "virginica", "count": 50 }
      ]
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| total_rows | int | 数据集总行数 |
| total_columns | int | 数据集总列数 |
| column_stats[].column | str | 列名 |
| column_stats[].dtype | str | pandas dtype 字符串 |
| column_stats[].null_count | int | 缺失值数量 |
| column_stats[].unique_count | int | 唯一值数量 |
| column_stats[].min/max/mean/std | float | 数值列统计量（仅数值列） |
| column_stats[].Q1/median/Q3 | float | 分位数（仅数值列，FR-015） |
| column_stats[].top_values | array | Top 5 频次值（非数值列，FR-016/FR-017） |

### 错误响应（404）

```json
{
  "detail": "文件不存在"
}
```

---

## 6. 导出数据

**路径**：`GET /api/data/{file_id}/export`
**描述**：触发完整 CSV 文件下载（流式响应），返回原始文件内容

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| file_id | int | 文件 ID |

### 响应头

```http
HTTP/1.1 200 OK
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="iris.csv"
```

### 响应体

原始 CSV 文件内容（完整文件，非截断预览）

```
sepal_length,sepal_width,petal_length,petal_width,species
5.1,3.5,1.4,0.2,setosa
4.9,3.0,1.4,0.2,setosa
...
```

### 错误响应（404）

```json
{
  "detail": "文件不存在"
}
```

### 错误响应（413 - 文件过大）

```json
{
  "detail": "文件超过大小限制 (500MB)"
}
```

---

## 7. 删除数据集

**路径**：`DELETE /api/data/{file_id}`
**描述**：删除指定数据集，同时删除数据库记录和磁盘文件

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| file_id | int | 文件 ID |

### 成功响应（200）

```json
{
  "message": "文件已删除"
}
```

### 错误响应（404）

```json
{
  "detail": "文件不存在"
}
```

---

## 结构化日志格式（FR-025）

每个 API 调用都会输出 JSON 格式日志到 `api.data` logger：

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 1,
  "operation": "upload|list|get|delete|preview|stats|export",
  "duration_ms": 234.5,
  "status_code": 200,
  "extra": {
    "filename": "iris.csv",
    "size": 4321,
    "rows": 150
  }
}
```

---

## 端点与 FR 对照表

| 端点 | 覆盖的 FR |
|------|----------|
| POST /upload | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-025 |
| GET /list | FR-007, FR-008, FR-009, FR-025 |
| GET /{id} | FR-025 |
| GET /{id}/preview | FR-010, FR-011, FR-012, FR-025 |
| GET /{id}/stats | FR-013, FR-014, FR-015, FR-016, FR-017, FR-025 |
| GET /{id}/export | FR-018, FR-025 |
| DELETE /{id} | FR-019, FR-020, FR-021, FR-022, FR-025 |
