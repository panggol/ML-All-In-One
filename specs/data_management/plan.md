# 实施计划：Data Management

**Constitution 遵循**：✅ Principles I（规划先行）、III（接口标准化）、IV（测试不可绕过）、VI（可观测性）、VIII（简洁优先）
**对应需求**：spec.md v1.0（2026-04-11）
**Spec-Kit 版本**：1.0.0

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  DataManagement.tsx — 拖拽上传 / 列表 / 预览 / 统计 / 导出    │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP (JSON / Multipart)
┌─────────────────────▼───────────────────────────────────────┐
│                    FastAPI (api/routes/data.py)              │
│  /data/upload  /data/list  /data/{id}                       │
│  /data/{id}/preview  /data/{id}/stats  /data/{id}/export    │
└─────────────────────┬───────────────────────────────────────┘
                      │ SQLAlchemy ORM
┌─────────────────────▼───────────────────────────────────────┐
│                   SQLite (默认) / PostgreSQL                  │
│  data_files 表 ← DataFile 模型                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│               本地文件系统 (./uploads/{user_id}/)            │
│  CSV 文件存储                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 模块划分

| 模块 | 职责 | 技术选型 | 选型理由 |
|------|------|---------|---------|
| 前端页面 | 上传 UI、列表、详情面板 | React + TypeScript | Constitution 约束；现有组件复用 |
| API 路由 | 6 个 REST 端点 | FastAPI + Pydantic | Constitution 约束；自动 OpenAPI 文档 |
| 数据模型 | DataFile ORM 模型 | SQLAlchemy + SQLite | Constitution 约束；开箱即用 |
| 文件存储 | CSV 文件读写 | 本地文件系统 + pandas | 简单可靠；支持大数据分块读取 |
| 测试套件 | 16 个 API 集成测试 | pytest + TestClient | Constitution IV 强制要求 |

---

## 技术选型理由

### FastAPI vs Django/Flask
- 选择 **FastAPI**：原生 Pydantic 验证、自动 OpenAPI、async 支持；Django 过重，Flask 缺少类型推导
- 理由链接到 Constitution：技术栈约束（Python 3.10+ / FastAPI）

### SQLite vs PostgreSQL
- 选择 **SQLite（默认）**：零配置、文件级数据库，适合单节点 ML 平台原型
- PostgreSQL：生产环境切换路径清晰（改 DATABASE_URL 环境变量即可）
- 理由链接到 Constitution：技术栈约束（SQLite 默认 / PostgreSQL 生产）

### pandas 分块读取
- 选择 **pandas**：成熟稳定，CSV 解析性能好，支持 dtype 推断
- 对于 50GB+ 文件：使用 `pd.read_csv(chunksize=...)` 或 Dask（FR-026）
- 理由链接到 Constitution：大数据处理约束

---

## 实现状态（已验证）

### Phase 1: 基础设施 ✅
- [x] DataFile 数据库模型（SQLAlchemy）
- [x] User 认证依赖（JWT Bearer Token）
- [x] 上传目录管理（`./uploads/{user_id}/`）

### Phase 2: 核心功能 ✅（6 User Stories 全部实现）

| User Story | 端点 | 状态 |
|-----------|------|------|
| US1: CSV 上传 | POST /data/upload | ✅ 已实现 |
| US2: 列表浏览 | GET /data/list | ✅ 已实现 |
| US3: 数据预览 | GET /data/{id}/preview | ✅ 已实现 |
| US4: 统计信息 | GET /data/{id}/stats | ✅ 已实现 |
| US5: 数据导出 | GET /data/{id}/export | ✅ 已实现 |
| US6: 删除确认 | DELETE /data/{id} | ✅ 已实现 |

### Phase 3: 可观测性 ✅
- [x] 结构化 JSON 日志（FR-025）：所有 6 个端点已添加 `structured_log()` 调用
- [x] 日志字段：request_id / user_id / operation / duration_ms / status_code

---

## 缺口列表

| ID | 缺口描述 | 严重度 | 备注 |
|----|---------|--------|------|
| GAP-001 | 前端进度条未实现实时百分比（FR-003） | 中 | 当前仅显示加载状态，XHR 进度事件需前端配合 |
| GAP-002 | 50GB+ 文件未使用分块读取（FR-026） | 高 | 需要 chunksize 实现，pending 团队决策 |
| GAP-003 | 预览空文件 / 仅 header 文件边界情况未测试 | 低 | 建议补充边界测试用例 |

---

## 风险与备选方案

| 风险 | 概率 | 影响 | 备选方案 |
|------|------|------|---------|
| SQLite 并发写入冲突 | 低 | 中 | 切换 PostgreSQL（已有 DATABASE_URL 支持） |
| 超大 CSV 内存溢出 | 低 | 高 | 启用 pandas chunksize 或 Dask（FR-026） |
| 非 UTF-8 编码文件读取失败 | 中 | 低 | 捕获异常返回 400 错误（已实现） |
| 用户隔离绕过（user_id 伪造） | 低 | 高 | JWT 签名验证已在 auth.py 实现 |

---

## 决策可追溯

| 决策 | 日期 | 理由 |
|------|------|------|
| 使用 pandas 读取 CSV | 2026-04-11 | 成熟稳定，dtype 推断；对比：纯标准库（功能不足），Polars（额外依赖） |
| preview 默认返回 10 行 | 2026-04-11 | spec.md 明确要求；修复了最初错误实现的 50 行 |
| stats 端点包含 Q1/median/Q3 | 2026-04-11 | FR-015 明确要求；修复了遗漏 |
| 结构化 JSON 日志 | 2026-04-11 | Constitution Principle VI；使用 Python logging 模块 |
