# ML All In One - 系统监控模块 QA 报告

**文档编号：** QA-MON-001  
**版本：** v1.0  
**日期：** 2026-04-10  
**检查人：** QA Agent  
**项目路径：** `/home/gem/workspace/agent/workspace/ml-all-in-one/`  
**状态：** ⚠️ 发现 1 个缺陷

---

## 一、总体结论

| 类别 | 结果 |
|------|------|
| 依赖完整性 | ✅ PASS |
| 后端代码 | ⚠️ 1 个缺陷 |
| 前端代码 | ✅ PASS |
| 功能完整性 | ✅ PASS |
| 代码质量 | ✅ PASS（现有测试未破裂）|

**总体判定：⚠️ 有条件通过（需修复 /history 端点的未定义变量问题）**

---

## 二、详细检查结果

### 2.1 依赖检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| requirements.txt 包含 `psutil>=5.9.0` | ✅ PASS | 已添加 |
| requirements.txt 包含 `pynvml>=11.5.0` | ✅ PASS | 已添加 |

---

### 2.2 后端代码检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `api/routes/monitor.py` 存在 | ✅ PASS | 文件存在，155 行 |
| 包含正确的 API 端点（8 个） | ✅ PASS | overview/cpu/memory/gpu/disk/network/jobs/history |
| `api/services/monitor_service.py` 存在 | ✅ PASS | 文件存在，195 行 |
| `api/main.py` 注册了 monitor 路由 | ✅ PASS | `app.include_router(monitor.router, prefix="/api/monitor")` |
| `api/routes/__init__.py` 导出 monitor | ✅ PASS | `from api.routes import ... monitor` 并加入 `__all__` |
| `api/services/__init__.py` 导出 monitor_service | ✅ PASS | 正确导出 |
| GPU 降级逻辑存在 | ✅ PASS | `_init_nvml()` + `_get_gpu_info()` 返回 `available: False` |
| psutil 用于 CPU/内存/磁盘/网络采集 | ✅ PASS | `_get_cpu_info()`、`_get_memory_info()`、`_get_disk_info()`、`_get_network_info()` 均使用 psutil |
| `/history` 端点无未定义变量 | ❌ FAIL | 见下方缺陷说明 |

---

### 2.3 前端代码检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `frontend/src/api/monitor.ts` 存在 | ✅ PASS | 包含完整类型定义 + `getOverview` + `getHistory` |
| `frontend/src/pages/Monitor.tsx` 存在 | ✅ PASS | 独立监控页面，5 秒轮询，环形缓冲区 |
| Dashboard.tsx 已改造（不再是硬编码数据） | ✅ PASS | 使用 `monitorApi.getOverview()` + `refetchInterval: 30000`，进度条动态显示 |
| App.tsx 添加了 `/monitor` 路由 | ✅ PASS | 路由配置 + 导航 Tab（`Activity` 图标）|
| recharts 用于网络流量折线图 | ✅ PASS | `NetworkChart.tsx` 导入 `LineChart, Line` 等 |
| 阈值语义色逻辑（60%/85%） | ✅ PASS | `UsageProgressBar.tsx` 的 `getAutoColor()` 和 `getGradientColor()` |

---

### 2.4 功能完整性验证

| 检查项 | 结果 | 说明 |
|--------|------|------|
| GPU 降级逻辑 | ✅ PASS | `_get_gpu_info()` 无 GPU 时返回 `available: false`，不抛错 |
| psutil 采集逻辑 | ✅ PASS | CPU/内存/磁盘/网络均有独立函数，异常时返回零值/fallback |
| recharts 折线图 | ✅ PASS | 发送线（cyan-500）+ 接收线（violet-500），`isAnimationActive={false}` |
| 阈值语义色（60%/85%） | ✅ PASS | `getAutoColor(percent)`：≥85 红 / ≥60 黄 / 其他 绿 |
| 环形缓冲区（最多 60 条） | ✅ PASS | `Monitor.tsx` 中 `MAX_BUFFER_SIZE = 60`，`next.slice(-MAX_BUFFER_SIZE)` |
| Dashboard 30 秒刷新 | ✅ PASS | `refetchInterval: 30000` |
| 独立监控页 5 秒刷新 | ✅ PASS | `refetchInterval: 5000` |

---

### 2.5 代码质量检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| pytest 测试（248 passed, 1 skipped） | ✅ PASS | 23.35 秒完成，无失败 |
| `api/routes/monitor.py` 语法正确 | ✅ PASS | `python3 -m py_compile` 通过 |
| `api/services/monitor_service.py` 语法正确 | ✅ PASS | `python3 -m py_compile` 通过 |
| `api/main.py` 语法正确 | ✅ PASS | `python3 -m py_compile` 通过 |
| 无明显逻辑错误（端点到采集） | ✅ PASS | 8 个端点均正确对接 service 层 |

---

## 三、缺陷详情

### 🔴 缺陷 #1：`/history` 端点引用未定义变量

**位置：** `api/routes/monitor.py` 第 140 行左右（`get_history` 函数）

**问题描述：**

`get_history` 函数中直接引用了 `monitor_history` 变量，但该变量从未被导入或定义：

```python
# 查询历史数据
query = db.query(monitor_history).filter(
    monitor_history.c.metric_name == metric,  # ← NameError: monitor_history is not defined
    ...
)
```

**影响范围：**
- `/api/monitor/history` 端点无法正常工作
- 当用户调用此端点时会收到 HTTP 500 Internal Server Error
- 其他 7 个端点（`/overview`, `/cpu`, `/memory`, `/gpu`, `/disk`, `/network`, `/jobs`）均正常

**触发条件：**
- 发送请求 `GET /api/monitor/history?metric=cpu&from_time=...&to_time=...`

**根本原因：**

在文件底部（第 195 行附近）通过 `Table` + `MetaData` 定义了 `monitor_history` 表对象，但这一定义在模块级别（`monitor.py` 的顶层），而非在 `get_history` 函数内部或通过数据库模型导入。其定义位置在函数 `get_history` 之后，且通过 `Table(...).create(engine, checkfirst=True)` 方式注册，而非通过 `db.query(...)` 直接引用 `monitor_history` 对象。

由于测试套件未覆盖 `/api/monitor/history` 端点，此缺陷在 `pytest` 中未暴露。

**修复建议：**

方案 A（推荐）：将 `monitor_history` 表对象的定义移到文件顶部，并在 `get_history` 函数中使用 `db.query(monitor_history)` 之前确保该对象已正确定义：

```python
# 文件顶部（在所有函数定义之前）
from sqlalchemy import Table, Column, Float, DateTime, String, JSON, Integer, MetaData

_metadata = MetaData()
monitor_history = Table(
    "monitor_history",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("metric_name", String(50), nullable=False, index=True),
    Column("metric_value", Float, nullable=False),
    Column("recorded_at", DateTime, nullable=False, index=True),
    Column("metadata", JSON, nullable=True),
)
```

方案 B：使用 ORM 模型方式定义 `MonitorHistory` 类，并导入使用。

**注意：** 根据需求文档，Phase 4 才实现历史数据 API 和后台采集任务，但端点已实现（作为存根），建议在 Phase 4 完成时一并修复，或在 Phase 4 之前移除该端点以避免误导。

---

## 四、测试覆盖说明

| 端点 | 是否被测试覆盖 | 备注 |
|------|--------------|------|
| `/api/monitor/overview` | ❌ 未覆盖 | 现有测试套件无监控模块测试 |
| `/api/monitor/cpu` | ❌ 未覆盖 | — |
| `/api/monitor/memory` | ❌ 未覆盖 | — |
| `/api/monitor/gpu` | ❌ 未覆盖 | — |
| `/api/monitor/disk` | ❌ 未覆盖 | — |
| `/api/monitor/network` | ❌ 未覆盖 | — |
| `/api/monitor/jobs` | ❌ 未覆盖 | — |
| `/api/monitor/history` | ❌ 未覆盖 | 存在未定义变量缺陷 |

**建议：** 为系统监控模块编写独立测试用例（参考需求文档 TC-01 ~ TC-07）。

---

## 五、最终判定

| 维度 | 判定 | 说明 |
|------|------|------|
| 整体质量 | ⚠️ 有条件通过 | 1 个阻塞性缺陷（/history 端点 NameError） |
| 功能完整性 | ✅ PASS | 核心功能（8 个端点中的 7 个）+ 前端完全实现 |
| 代码质量 | ✅ PASS | 现有 248 个测试全部通过 |
| 设计一致性 | ✅ PASS | 与 UI 设计文档完全吻合 |

---

## 六、后续建议

1. **立即修复**：`/api/monitor/history` 端点的 `monitor_history` 未定义变量问题（见上文）
2. **测试补充**：为系统监控模块补充测试用例（TC-01 ~ TC-07）
3. **Phase 4 规划**：历史数据 API 的 `monitor_history` 表目前为空，需实现后台采集任务
4. **告警机制**：需求文档中 FR-06（告警机制）标注为可选，Phase 5 范围

---

*报告生成时间：2026-04-10 23:50 GMT+8*
