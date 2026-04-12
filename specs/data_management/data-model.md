# 数据模型：Data Management

## 实体定义

### DataFile（数据文件）

| 属性 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | Integer | 主键 | 自动递增 |
| user_id | Integer | 所有者用户 ID | 外键 → users.id，非空 |
| filename | String(255) | 原始文件名 | 非空 |
| filepath | String(500) | 磁盘存储路径 | 非空 |
| size | Integer | 文件大小（字节） | 非空 |
| rows | Integer | 数据行数 | 默认 0 |
| columns | JSON | 列名列表 | 默认 [] |
| dtypes | JSON | 列类型字典 | 默认 {} |
| created_at | DateTime | 上传时间 | 自动生成（UTC） |

**关系**：
- `DataFile.user_id → User.id`（多对一）
- `DataFile.id → TrainingJob.data_file_id`（一对多）

---

### User（用户，关联实体）

| 属性 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | Integer | 主键 | 自动递增 |
| username | String(50) | 用户名 | 唯一，非空 |
| email | String(100) | 邮箱 | 唯一，非空 |
| password_hash | String(255) | 密码哈希 | 非空 |
| is_active | Boolean | 是否激活 | 默认 True |
| created_at | DateTime | 注册时间 | 自动生成 |

---

### DataFileResponse（Pydantic，API 响应模型）

| 属性 | 类型 | 说明 |
|------|------|------|
| id | int | 文件 ID |
| filename | str | 文件名 |
| size | int | 文件大小（字节） |
| rows | int | 数据行数 |
| columns | List[str] | 列名列表 |
| created_at | str | ISO 8601 时间字符串 |

---

### PreviewResponse（Pydantic，API 响应模型）

| 属性 | 类型 | 说明 |
|------|------|------|
| rows | List[List[unknown]] | 前 10 行数据 |
| columns | List[str] | 列名列表 |
| total_rows | int | 预览行数（= len(rows)） |

---

### ColumnStats（Pydantic，API 响应模型）

| 属性 | 类型 | 说明 | 适用条件 |
|------|------|------|---------|
| column | str | 列名 | 所有列 |
| dtype | str | pandas dtype | 所有列 |
| null_count | int | 缺失值数量 | 所有列 |
| unique_count | int | 唯一值数量 | 所有列 |
| min | float | 最小值 | 仅数值列 |
| max | float | 最大值 | 仅数值列 |
| mean | float | 均值 | 仅数值列 |
| std | float | 标准差 | 仅数值列 |
| Q1 | float | 第 25 百分位数 | 仅数值列 |
| median | float | 中位数 | 仅数值列 |
| Q3 | float | 第 75 百分位数 | 仅数值列 |
| top_values | List[TopValue] | Top 5 频次值 | 非数值列 |

### TopValue（Pydantic，内嵌模型）

| 属性 | 类型 | 说明 |
|------|------|------|
| value | str | 枚举值 |
| count | int | 出现次数 |

---

### StatsResponse（Pydantic，API 响应模型）

| 属性 | 类型 | 说明 |
|------|------|------|
| total_rows | int | 总行数 |
| total_columns | int | 总列数 |
| column_stats | List[ColumnStats] | 每列统计信息 |

---

## 数据库 Schema（SQLite）

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE data_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    filepath VARCHAR(500) NOT NULL,
    size INTEGER NOT NULL,
    rows INTEGER DEFAULT 0,
    columns TEXT DEFAULT '[]',     -- SQLite: JSON stored as TEXT
    dtypes TEXT DEFAULT '{}',      -- SQLite: JSON stored as TEXT
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_data_files_user_id ON data_files(user_id);
CREATE INDEX idx_data_files_created_at ON data_files(created_at DESC);
```

---

## 关系图

```
User (1) ──────< DataFile (N)
  │                 │
  │ id              │ user_id
  └─────────────────┘
  
DataFile (1) ────< TrainingJob (N)
  │ id                 data_file_id
  └──────────────────┘
```

---

## 数据流

```
用户上传 CSV
    ↓
FastAPI /data/upload（验证格式、大小）
    ↓
保存到 ./uploads/{user_id}/{timestamp}_{filename}
    ↓
pandas 读取基本信息（rows, columns, dtypes）
    ↓
存入 DataFile 表（filepath 指向磁盘文件）
    ↓
前端轮询 /data/list → 展示数据集列表

用户点击"预览"
    ↓
FastAPI /data/{id}/preview（pandas nrows=10）
    ↓
返回 { columns, rows, total_rows }

用户点击"统计"
    ↓
FastAPI /data/{id}/stats（pandas describe + 分位数）
    ↓
返回 { total_rows, total_columns, column_stats[] }

用户点击"导出"
    ↓
FastAPI /data/{id}/export（FileResponse 流式下载）
    ↓
浏览器触发 CSV 下载

用户确认删除
    ↓
FastAPI /data/{id}/delete（删除 DB 记录 + 磁盘文件）
    ↓
前端刷新列表
```
