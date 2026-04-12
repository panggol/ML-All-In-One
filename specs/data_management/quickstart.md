# 快速验证：Data Management

**模块**：Data Management
**验证目标**：确保全部 6 个 User Stories 可端到端验证
**测试环境**：FastAPI TestClient（内存 SQLite，无需真实数据库）

---

## 验证前准备

### 1. 安装依赖

```bash
cd /home/gem/workspace/agent/workspace/ml-all-in-one
pip install fastapi sqlalchemy pandas pytest
```

### 2. 运行测试套件（推荐）

```bash
cd /home/gem/workspace/agent/workspace/ml-all-in-one
python3 -m pytest tests/test_data_management_api.py -v
```

**预期结果**：16 passed

---

## 验证场景（关键用户路径）

### 场景 1：上传 CSV 文件（US1）

**验证方法**：
1. 准备测试 CSV 文件：
   ```python
   csv_content = "name,age,score\nAlice,25,95.5\nBob,30,88.0\nCharlie,22,92.0"
   ```
2. 使用 TestClient POST 到 `/api/data/upload`：
   ```bash
   curl -X POST http://localhost:8000/api/data/upload \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@test.csv"
   ```
3. **预期结果**：
   - 状态码 200
   - 响应包含 `id`、`filename`、`rows: 3`、`columns: ["name","age","score"]`
   - 文件出现在 `/data/list` 列表中

---

### 场景 2：浏览数据集列表（US2）

**验证方法**：
1. 调用 `GET /api/data/list`
2. **预期结果**：
   - 状态码 200
   - 返回数组，按 `created_at` 倒序（最新在前）
   - 每项包含：`id`、`filename`、`size`、`rows`、`columns`、`created_at`

**空列表验证**：
1. 清空数据库后调用 `GET /api/data/list`
2. **预期结果**：返回空数组 `[]`

---

### 场景 3：预览数据（US3）

**验证方法**：
1. 调用 `GET /api/data/1/preview`
2. **预期结果**：
   - 状态码 200
   - `total_rows: 10`（或实际行数 < 10 时为实际值）
   - `columns` 包含列名
   - `rows` 长度为 10 或更少

---

### 场景 4：查看统计信息（US4）

**验证方法**：
1. 调用 `GET /api/data/1/stats`
2. **预期结果**：
   - 状态码 200
   - `total_rows` 和 `total_columns` 正确
   - 数值列包含：`min`、`max`、`mean`、`std`、`Q1`、`median`、`Q3`
   - 分类列包含：`top_values`（最多 5 项）

---

### 场景 5：导出 CSV（US5）

**验证方法**：
1. 调用 `GET /api/data/1/export`
2. **预期结果**：
   - 状态码 200
   - `Content-Type: text/csv`
   - `Content-Disposition: attachment; filename="xxx.csv"`
   - 文件内容与原始 CSV 完全一致

---

### 场景 6：删除数据集（US6）

**验证方法**：
1. 调用 `DELETE /api/data/1`
2. **预期结果**：
   - 状态码 200，返回 `{"message": "文件已删除"}`
   - 再次调用 `GET /data/list`，文件不再出现

**确认取消验证**：
1. 打开删除确认对话框 → 点击"取消"
2. **预期结果**：对话框关闭，数据集保留

---

## 手动前端验证步骤

### 环境启动

```bash
cd /home/gem/workspace/agent/workspace/ml-all-in-one
# 启动后端
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
# 启动前端
cd frontend && npm run dev &
```

### 功能检查清单

| 功能 | 检查项 | 通过标准 |
|------|--------|---------|
| 上传 | 拖拽 CSV 文件到上传区 | 进度条出现 → 上传成功提示 → 列表刷新 |
| 上传 | 点击上传按钮选择文件 | 同上 |
| 列表 | 查看数据集列表 | 按上传时间倒序，显示文件名/大小/行数/列数/时间 |
| 列表 | 无数据集时 | 显示"暂无数据集"空状态 |
| 预览 | 点击"预览"按钮 | 展开详情面板，显示前 10 行 |
| 统计 | 点击"统计"按钮 | 显示行数/列数，每列显示类型/缺失值/唯一值/分位数 |
| Tab切换 | 在详情面板切换 Preview/Stats | 500ms 内切换完成 |
| 导出 | 点击"导出"按钮 | 浏览器下载 CSV 文件 |
| 删除 | 点击删除按钮 | 弹出确认对话框，显示文件名 |
| 删除 | 确认删除 | 数据集消失，列表刷新，显示成功提示 |

---

## 性能基准（Success Criteria 验证）

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 上传响应 | 上传 + 列表刷新 < 5s（不含网络传输） | 计时器测量 |
| 列表加载 | < 2s（100 个数据集） | 计时器测量 |
| Preview/Stats 切换 | < 500ms（< 1GB 文件） | 计时器测量 |
| 空状态加载 | < 1s | 计时器测量 |
| 进度条 | 每 10% 事件触发更新 | 日志检查 |
