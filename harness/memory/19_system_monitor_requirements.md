# ML All In One - 系统监控功能模块需求文档

**文档编号：** REQ-SYS-MON-001  
**版本：** v1.0  
**日期：** 2026-04-10  
**作者：** 需求分析 Agent  
**状态：** 初稿  

---

## 1. 背景与目标

### 1.1 项目背景

ML All In One 是一个机器学习训练平台，前端基于 React + Vite + TypeScript + TailwindCSS，后端基于 FastAPI + SQLAlchemy + Pydantic。项目当前已有 Dashboard 页面，其中系统状态区块以静态 Mock 数据展示 GPU 内存和磁盘使用情况，尚未接入真实监控数据。

本模块旨在为平台构建一套完整的**系统监控（System Monitoring）**功能，提供对服务器资源、GPU 资源、磁盘、网络以及训练任务状态的实时可视化监控能力。

### 1.2 目标

- 将 Dashboard 中硬编码的 Mock 数据替换为真实系统监控 API
- 建立统一的后端系统监控数据采集层，支持在 Docker 容器内运行
- 提供多维度指标展示（CPU、内存、GPU、磁盘、网络、训练任务）
- 支持合理的实时刷新策略，避免过度请求
- 可选支持基础告警机制（阈值触发）

---

## 2. 现状分析

### 2.1 现有代码结构

**前端 Dashboard（`/frontend/src/pages/Dashboard.tsx`）**

- 第 145-165 行：系统状态卡片区域，包含 3 项固定信息：
  - API 服务状态（静态文本 "正常运行"）
  - GPU 内存（Mock: `2.1 GB / 8 GB`）
  - 磁盘使用（Mock: `12.4 GB / 100 GB`）
- 组件使用 `StatCard` 和 `Card` 封装，图标为 `lucide-react`
- 图表库已引入 `recharts`（v2.12.7）

**前端 API 层（`/frontend/src/api/`）**

- 已有 `client.ts` 作为 Axios 实例封装
- 各模块 API 均以命名导出（`authApi`, `trainApi`, `experimentApi` 等）

**后端入口（`/api/main.py`）**

- FastAPI 实例，统一路由注册
- 目前无监控相关路由

**后端路由目录（`/api/routes/`）**

- 包含：`auth`, `data`, `train`, `experiments`, `models`, `viz`, `automl`, `preprocessing`

**技术栈**

- 前端：`React 18`, `Vite 5`, `TypeScript`, `TailwindCSS 3`, `recharts`, `@tanstack/react-query`, `lucide-react`
- 后端：`FastAPI 0.111`, `SQLAlchemy 2.0`, `Pydantic 2.7`
- 运行环境：Docker 容器（需注意容器内系统指标采集方式）

---

## 3. 功能需求

### 3.1 核心功能

#### FR-01：系统指标采集 API

后端需要提供一个统一的系统指标采集模块，能够采集以下指标：

| 指标类别 | 具体指标 | 说明 |
|---------|---------|------|
| **CPU** | 使用率（%） | 全局 CPU 使用百分比 |
| | 核心数 | 物理核心数 |
| | 每核使用率 | 数组形式，每个核心的使用率 |
| **内存** | 总量（GB） | 总物理内存 |
| | 已用量（GB） | 当前已使用内存 |
| | 使用率（%） | 已用/总量 |
| | 可用量（GB） | 可用内存 |
| **GPU** | 数量 | 检测到的 GPU 设备数 |
| | 每卡显存总量（GB） | 每块 GPU 的显存大小 |
| | 每卡已用显存（GB） | 每块 GPU 当前占用的显存 |
| | 每卡显存使用率（%） | 已用/总量 |
| | 每卡温度（℃） | GPU 温度（如果支持） |
| | 每卡利用率（%） | GPU 计算利用率 |
| | GPU 型号名称 | 如 "NVIDIA A100-SXM4-40GB" |
| **磁盘** | 各挂载点总量（GB） | 每个挂载点的总容量 |
| | 各挂载点已用量（GB） | 每个挂载点的已用容量 |
| | 各挂载点使用率（%） | 使用百分比 |
| | 各挂载点可用量（GB） | 可用空间 |
| **网络** | 发送字节数 | 启动以来的总发送字节 |
| | 接收字节数 | 启动以来的总接收字节 |
| | 发送速率（MB/s） | 最近 1 秒的发送速率 |
| | 接收速率（MB/s） | 最近 1 秒的接收速率 |
| **系统** | 主机名 | 服务器主机名 |
| | 运行时间 | 系统运行时间（秒） |
| | OS 类型 | 如 "Linux" |
| | OS 版本 | 详细版本号 |
| **训练任务** | 正在运行的任务数 | 状态为 running 的训练任务 |
| | 队列中的任务数 | 状态为 pending 的训练任务 |
| | 已完成的任务数 | 状态为 completed 的训练任务 |
| | 失败的任务数 | 状态为 failed 的训练任务 |

#### FR-02：实时指标 API 端点

后端需要新增以下 API 端点：

| 端点 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 系统概览 | GET | `/api/monitor/overview` | 返回所有系统指标的摘要 |
| CPU 详情 | GET | `/api/monitor/cpu` | 返回 CPU 详细指标 |
| 内存详情 | GET | `/api/monitor/memory` | 返回内存详细指标 |
| GPU 详情 | GET | `/api/monitor/gpu` | 返回 GPU 详细指标（需 nvidia-smi 或 pynvml） |
| 磁盘详情 | GET | `/api/monitor/disk` | 返回磁盘详细指标 |
| 网络详情 | GET | `/api/monitor/network` | 返回网络详细指标 |
| 训练任务状态 | GET | `/api/monitor/jobs` | 返回当前训练任务统计 |

#### FR-03：历史数据 API

支持查询历史监控数据：

| 端点 | 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|------|
| 历史指标 | GET | `/api/monitor/history` | `metric`, `from`, `to`, `interval` | 查询指定指标的历史数据 |

#### FR-04：Dashboard 集成

前端 Dashboard 需要：

- 将现有的静态系统状态区域改造为真实数据展示
- 在页面加载时自动获取 `/api/monitor/overview` 数据
- 每 30 秒自动刷新一次系统指标
- GPU 内存、磁盘使用量使用进度条（Progress Bar）展示
- API 服务状态调用 `/api/health` 判断

#### FR-05：独立监控页面（可选增强）

提供独立的监控页面 `/monitor`，包含：

- 实时刷新的大屏监控视图
- GPU 多卡片展示（每张卡一块 GPU）
- 磁盘多挂载点列表展示
- 网络流量实时折线图（最近 5 分钟数据，每 5 秒刷新）

#### FR-06：告警机制（可选）

| 功能点 | 描述 |
|-------|------|
| 阈值配置 API | 提供 API 配置各项指标的告警阈值 |
| 告警记录存储 | 将触发的告警记录存入数据库 |
| 告警历史查询 | 提供 API 查询历史告警记录 |
| 触发条件 | GPU 显存 > 90%、磁盘使用率 > 85%、内存使用率 > 90% |

---

## 4. 非功能需求

### 4.1 性能需求

| 指标 | 要求 |
|------|------|
| API 响应时间 | 单次 `/api/monitor/overview` 响应时间 ≤ 500ms（P99） |
| 并发支持 | 支持至少 50 个并发请求 |
| GPU 检测容错 | 当 GPU 不可用时（如无 NVIDIA 驱动），API 返回空数组而不报错 |
| Docker 容器兼容 | 后端在 Docker 容器内运行时，仍能正确采集系统指标 |

### 4.2 可用性需求

| 指标 | 要求 |
|------|------|
| 服务自愈 | 单个指标采集失败不影响其他指标返回 |
| 空值友好 | 任何指标为空时，前端应显示 "N/A" 而非报错 |
| 监控进程隔离 | 监控采集不阻塞 API 主线程 |

### 4.3 安全需求

| 指标 | 要求 |
|------|------|
| 权限控制 | 监控 API 纳入已有的认证体系（已登录用户可访问） |
| 数据脱敏 | 不暴露敏感系统路径和配置信息 |
| 只读接口 | 所有监控接口均为 GET（只读），无写操作 |

### 4.4 可维护性需求

| 指标 | 要求 |
|------|------|
| 日志记录 | 采集失败时记录 ERROR 日志，不中断服务 |
| 可配置采集间隔 | 后端可配置指标采集间隔（默认 10s） |
| 扩展性 | 预留插件化接口，便于未来增加自定义指标 |

---

## 5. 技术实现方案

### 5.1 后端实现

#### 5.1.1 新增依赖

```
# 新增到 api/requirements.txt
psutil>=5.9.0          # 系统指标采集（CPU/内存/磁盘/网络）
pynvml>=11.5.0         # NVIDIA GPU 监控（可选，GPU 不可用时优雅降级）
```

#### 5.1.2 新增路由模块

```
api/
├── routes/
│   └── monitor.py          # 监控 API 路由
├── services/
│   └── monitor_service.py  # 监控数据采集服务
└── models/
    └── monitor.py          # Pydantic 模型定义
```

#### 5.1.3 监控采集策略

**采集方式：**

- 使用 `psutil` 库采集 CPU、内存、磁盘、网络指标
- 使用 `pynvml` 库采集 GPU 指标（通过 `nvidia-smi` 或 NVML API）
- 训练任务数据从数据库查询（复用现有 `TrainJob` 模型）
- Docker 容器内运行：使用 `--device nvidia:/dev/nvidia0` 映射或 `nvidia-container-toolkit`，`psutil` 在容器内可直接读取 `/proc` 和 `/sys`

**采集频率：**

- 实时数据：每次请求时实时采集（无缓存，确保数据新鲜）
- 历史数据：以固定时间间隔（默认 60s）后台采集并存储到数据库

**容错处理：**

```python
try:
    import pynvml
    pynvml.nvmlInit()
    # GPU 采集逻辑
except (NVMLError, OSError):
    # GPU 不可用时返回 {"gpus": [], "available": false, "reason": "No GPU detected"}
    return {"gpus": [], "available": False, "reason": "No GPU detected"}
```

#### 5.1.4 API 响应格式

**`/api/monitor/overview` 响应示例：**

```json
{
  "timestamp": "2026-04-10T23:28:00+08:00",
  "cpu": {
    "usage_percent": 23.5,
    "core_count": 8,
    "per_core_usage": [15.2, 30.1, 8.7, 45.3, 12.0, 5.5, 18.9, 22.3]
  },
  "memory": {
    "total_gb": 31.9,
    "used_gb": 18.2,
    "available_gb": 13.7,
    "usage_percent": 57.1
  },
  "gpu": {
    "available": true,
    "count": 1,
    "devices": [
      {
        "index": 0,
        "name": "NVIDIA A100-SXM4-40GB",
        "memory_total_gb": 40.0,
        "memory_used_gb": 12.4,
        "memory_free_gb": 27.6,
        "memory_usage_percent": 31.0,
        "utilization_percent": 45.0,
        "temperature_celsius": 62
      }
    ]
  },
  "disk": {
    "partitions": [
      {
        "mountpoint": "/",
        "total_gb": 100.0,
        "used_gb": 45.2,
        "free_gb": 54.8,
        "usage_percent": 45.2
      }
    ]
  },
  "network": {
    "bytes_sent_mb": 12450.3,
    "bytes_recv_mb": 38921.7,
    "send_rate_mbps": 2.5,
    "recv_rate_mbps": 8.3
  },
  "system": {
    "hostname": "ml-server-01",
    "uptime_seconds": 864000,
    "os_type": "Linux",
    "os_version": "6.8.0-100-generic"
  },
  "jobs": {
    "running": 2,
    "pending": 1,
    "completed": 15,
    "failed": 1
  }
}
```

**GPU 不可用时的响应：**

```json
{
  "gpu": {
    "available": false,
    "count": 0,
    "devices": [],
    "reason": "No NVIDIA GPU detected or nvidia-smi not available"
  }
}
```

### 5.2 前端实现

#### 5.2.1 新增 API 层

创建 `frontend/src/api/monitor.ts`：

```typescript
import { api } from './client'

export interface CPUInfo {
  usage_percent: number
  core_count: number
  per_core_usage: number[]
}

export interface MemoryInfo {
  total_gb: number
  used_gb: number
  available_gb: number
  usage_percent: number
}

export interface GPUDevice {
  index: number
  name: string
  memory_total_gb: number
  memory_used_gb: number
  memory_free_gb: number
  memory_usage_percent: number
  utilization_percent: number
  temperature_celsius: number | null
}

export interface GPUInfo {
  available: boolean
  count: number
  devices: GPUDevice[]
  reason?: string
}

export interface DiskPartition {
  mountpoint: string
  total_gb: number
  used_gb: number
  free_gb: number
  usage_percent: number
}

export interface DiskInfo {
  partitions: DiskPartition[]
}

export interface NetworkInfo {
  bytes_sent_mb: number
  bytes_recv_mb: number
  send_rate_mbps: number
  recv_rate_mbps: number
}

export interface SystemInfo {
  hostname: string
  uptime_seconds: number
  os_type: string
  os_version: string
}

export interface JobStats {
  running: number
  pending: number
  completed: number
  failed: number
}

export interface MonitorOverviewResponse {
  timestamp: string
  cpu: CPUInfo
  memory: MemoryInfo
  gpu: GPUInfo
  disk: DiskInfo
  network: NetworkInfo
  system: SystemInfo
  jobs: JobStats
}

export const monitorApi = {
  getOverview: () => api.get<MonitorOverviewResponse>('/api/monitor/overview'),
  getHistory: (params: { metric: string; from: string; to: string; interval?: string }) =>
    api.get('/api/monitor/history', { params }),
}
```

#### 5.2.2 Dashboard 改造

在 `Dashboard.tsx` 中：

- 使用 `useQuery` 管理监控数据获取（配置 `refetchInterval: 30000` 实现 30 秒自动刷新）
- 将 "系统状态" 卡片中的静态值替换为动态数据
- GPU 显存使用量使用 Tailwind 的进度条 + 百分比文字
- 磁盘使用量同上
- API 服务状态根据 `/api/health` 响应判断（`status === 'ok'` → 绿色）

#### 5.2.3 独立监控页面

创建 `frontend/src/pages/Monitor.tsx`：

- 使用 `useQuery` 配置 `refetchInterval: 5000`（5 秒刷新）
- 顶部 4 个大卡片：CPU 使用率、内存使用率、GPU 显存使用率、磁盘使用率
- GPU 区域：每张 GPU 一张卡片，显示显存条、利用率、温度
- 磁盘区域：表格形式列出所有挂载点
- 网络区域：`recharts` 的 `LineChart` 展示最近 5 分钟的流量数据（前端维护一个最多 60 条数据的环形缓冲区）
- 训练任务区域：运行中任务数、队列数、完成数、失败数（进度/统计条）

#### 5.2.4 路由配置

在 `frontend/src/App.tsx` 中新增路由：

```tsx
import Monitor from './pages/Monitor'

// 在路由配置中添加
<Route path="/monitor" element={<Monitor />} />
```

并在侧边栏（或导航菜单）中添加入口链接。

### 5.3 Docker 兼容性方案

| 场景 | 解决方案 |
|------|---------|
| 容器内 CPU/内存采集 | `psutil` 直接读取 `/proc` 文件系统，无需特殊权限 |
| 容器内 GPU 采集 | 容器需以 `--gpus all` 启动，挂载 `/dev/nvidia*` 和 nvidia driver；`pynvml` 自动检测 |
| 容器内磁盘采集 | 采集容器可见的挂载点，不采集宿主机所有磁盘 |
| 容器内网络采集 | 采集容器网络命名空间的网络接口（通常是 `eth0`） |

### 5.4 数据存储（历史数据）

新建数据库表 `monitor_history`：

```sql
CREATE TABLE monitor_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name VARCHAR(50) NOT NULL,    -- 'cpu', 'memory', 'gpu_memory', 'disk', 'network'
    metric_value FLOAT NOT NULL,          -- 指标值
    recorded_at DATETIME NOT NULL,        -- 采集时间
    metadata JSON                         -- 额外元数据（如 GPU index、磁盘挂载点等）
);

CREATE INDEX idx_monitor_history_metric_time ON monitor_history(metric_name, recorded_at);
```

---

## 6. API 详细设计

### 6.1 `/api/monitor/overview` — 系统概览

**请求**

```
GET /api/monitor/overview
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| timestamp | string (ISO 8601) | 采集时间 |
| cpu | CPUInfo | CPU 指标 |
| memory | MemoryInfo | 内存指标 |
| gpu | GPUInfo | GPU 指标 |
| disk | DiskInfo | 磁盘指标 |
| network | NetworkInfo | 网络指标 |
| system | SystemInfo | 系统信息 |
| jobs | JobStats | 任务统计 |

### 6.2 `/api/monitor/history` — 历史数据

**请求**

```
GET /api/monitor/history?metric=cpu&from=2026-04-10T00:00:00&to=2026-04-10T23:59:59&interval=60s
```

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| metric | string | 是 | 指标名：`cpu`, `memory`, `gpu_memory`, `disk`, `network_send`, `network_recv` |
| from | string | 是 | 开始时间（ISO 8601） |
| to | string | 是 | 结束时间（ISO 8601） |
| interval | string | 否 | 采样间隔：`30s`, `60s`, `5m`（默认 `60s`） |

**响应**

```json
{
  "metric": "cpu",
  "interval": "60s",
  "data": [
    { "timestamp": "2026-04-10T00:00:00+08:00", "value": 23.5 },
    { "timestamp": "2026-04-10T00:01:00+08:00", "value": 25.1 },
    ...
  ]
}
```

---

## 7. 前端展示方案

### 7.1 Dashboard 改造

保留现有布局，仅改造系统状态区域：

```
┌──────────────────────────────────────────────────────┐
│ ● 系统状态                                           │
│ ┌──────────────┐ ┌──────────────────┐ ┌────────────┐│
│ │ API 服务     │ │ GPU 内存         │ │ 磁盘使用   ││
│ │ ✓ 正常运行   │ │ ████████░░ 2.1/8 │ │ ██░░ 12.4/ ││
│ │              │ │              26%  │ │      100GB ││
│ │              │ │                   │ │        12% ││
│ └──────────────┘ └──────────────────┘ └────────────┘│
└──────────────────────────────────────────────────────┘
```

### 7.2 独立监控页面布局

```
┌──────────────────────────────────────────────────────┐
│  系统监控              [最后更新: 23:28:00] [手动刷新] │
│                                                      │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│ │ CPU      │ │ 内存      │ │ GPU 显存  │ │ 磁盘      ││
│ │  23.5%   │ │ 57.1%    │ │  31.0%   │ │  45.2%   ││
│ │ [进度条]  │ │ [进度条]  │ │ [进度条]  │ │ [进度条]  ││
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘│
│                                                      │
│ ┌──────────────────────────────────────────────────┐│
│ │ GPU 设备（1块）                                   ││
│ │ ┌──────────────────────────────────────────────┐ ││
│ │ │ A100-SXM4-40GB                              │ ││
│ │ │ 显存: ████████░░░░░░░░░░░ 12.4/40 GB (31%)  │ ││
│ │ │ 利用率: 45%    温度: 62°C                    │ ││
│ │ └──────────────────────────────────────────────┘ ││
│ └──────────────────────────────────────────────────┘│
│                                                      │
│ ┌──────────────────────────────────────────────────┐│
│ │ 磁盘挂载点                                        ││
│ │ 挂载点    总容量   已用    可用   使用率           ││
│ │ /        100GB   45.2GB  54.8GB  ████░░░░░ 45%  ││
│ │ /data    500GB  120.3GB 379.7GB  ██░░░░░░░ 24%  ││
│ └──────────────────────────────────────────────────┘│
│                                                      │
│ ┌──────────────────────────────────────────────────┐│
│ │ 网络流量（实时）                     [5分钟趋势图] ││
│ │ 发送: 2.5 MB/s  接收: 8.3 MB/s                   ││
│ │ [═══════════════════════════════════════════]    ││
│ └──────────────────────────────────────────────────┘│
│                                                      │
│ ┌──────────────────────────────────────────────────┐│
│ │ 训练任务状态                                      ││
│ │ 运行中: 2  队列: 1  完成: 15  失败: 1              ││
│ └──────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

### 7.3 刷新策略

| 页面 | 刷新间隔 | 说明 |
|------|---------|------|
| Dashboard 系统状态区 | 30 秒 | 使用 `@tanstack/react-query` 的 `refetchInterval` |
| 独立监控页面 | 5 秒 | 高频刷新以满足监控需求 |
| 历史趋势图 | 页面加载时请求最近 1 小时数据 | 使用 `/api/monitor/history` |

### 7.4 图表选型

| 展示内容 | 图表类型 | 组件 |
|---------|---------|------|
| 单指标百分比 | 进度条/环形图 | 自定义 ProgressBar 组件 |
| GPU 显存使用 | 水平进度条 | Tailwind + 自定义 |
| 磁盘使用 | 水平进度条 | Tailwind + 自定义 |
| 网络流量趋势 | 折线图 | `recharts` `<LineChart>` |
| CPU 每核使用率 | 多线折线图 | `recharts` `<LineChart>` |

---

## 8. 测试用例

### TC-01：系统概览 API 正常返回

**前置条件：** 后端服务正常运行，数据库有训练任务数据

**测试步骤：**

1. 发送 GET 请求到 `/api/monitor/overview`
2. 验证响应状态码为 200
3. 验证响应 JSON 包含 `timestamp`, `cpu`, `memory`, `disk` 字段
4. 验证 `cpu.usage_percent` 数值在 0-100 之间
5. 验证 `memory.total_gb > memory.used_gb > 0`
6. 验证 `jobs.running + jobs.pending + jobs.completed + jobs.failed` ≥ 0

**预期结果：** 返回完整的系统监控概览数据

---

### TC-02：GPU 不可用时的优雅降级

**前置条件：** 后端运行环境中无 NVIDIA GPU 或 nvidia-smi 不可用

**测试步骤：**

1. 在无 GPU 环境中启动后端服务
2. 发送 GET 请求到 `/api/monitor/overview`
3. 检查响应中 `gpu` 字段

**预期结果：** `gpu.available` 为 `false`，`gpu.count` 为 `0`，`gpu.devices` 为空数组，`gpu.reason` 包含描述信息，不返回 HTTP 500 错误

---

### TC-03：Docker 容器内指标采集

**前置条件：** 后端服务运行在 Docker 容器中，容器以 `--gpus all` 启动

**测试步骤：**

1. 在 Docker 容器内调用 `/api/monitor/overview`
2. 在宿主机调用 `nvidia-smi` 对比 GPU 信息
3. 对比容器内 CPU、内存数据与宿主机

**预期结果：** 容器内采集的 GPU 显存、CPU 使用率、内存数据与宿主机基本一致（误差 < 5%）

---

### TC-04：Dashboard 前端数据展示

**前置条件：** 前端开发服务器运行（`npm run dev`），后端 API 正常运行

**测试步骤：**

1. 打开浏览器访问 `http://localhost:3000/dashboard`
2. 等待页面加载完成
3. 找到 "系统状态" 区域
4. 验证 GPU 内存显示为 "XX GB / XX GB" 格式
5. 验证磁盘使用显示为 "XX GB / XX GB" 格式
6. 等待 35 秒（超过 30 秒刷新间隔）
7. 再次检查数据是否有更新（如果系统负载变化）

**预期结果：** 系统状态区显示真实数据，而非 "2.1 GB / 8 GB" 等固定 Mock 值；页面在 35 秒后自动刷新数据

---

### TC-05：高频刷新不导致 API 过载

**前置条件：** 浏览器打开独立监控页面（5 秒刷新间隔）

**测试步骤：**

1. 打开浏览器访问 `http://localhost:3000/monitor`
2. 观察 Network 面板，记录每次 API 请求的响应时间
3. 持续观察 3 分钟（约 36 次请求）
4. 检查是否有请求失败或响应时间超过 2 秒

**预期结果：** 所有请求均成功（200 状态码），平均响应时间 < 500ms，无请求积压或超时

---

### TC-06：历史数据查询

**前置条件：** 数据库中存在至少 30 分钟的监控历史数据

**测试步骤：**

1. 调用 GET `/api/monitor/history?metric=cpu&from=<当前时间-1h>&to=<当前时间>&interval=60s`
2. 验证返回的 `data` 数组长度 ≥ 50（每分钟一条，1 小时至少 60 条，考虑到边界可能有 50+）
3. 验证每条数据的 `timestamp` 和 `value` 字段存在
4. 验证 `timestamp` 按时间升序排列

**预期结果：** 返回指定时间范围内、符合采样间隔的历史数据

---

### TC-07：认证保护

**前置条件：** 用户未登录或 Token 过期

**测试步骤：**

1. 在未登录状态下（清除 localStorage 中的 Token），直接访问 `/api/monitor/overview`
2. 验证响应状态码为 401 或 403

**预期结果：** 监控 API 受认证保护，未授权请求返回错误状态码

---

## 9. 里程碑计划

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| **Phase 1** | 后端 `monitor` 路由开发（`/api/monitor/overview`）+ psutil 集成 + GPU 容错 | P0 |
| **Phase 2** | 前端 `monitor.ts` API 层 + Dashboard 改造 | P0 |
| **Phase 3** | 独立监控页面 `/monitor` 开发 | P1 |
| **Phase 4** | 历史数据 API + 数据库表 + 前端趋势图 | P1 |
| **Phase 5** | 告警机制（可选） | P2 |

---

## 10. 附录

### A. 参考资料

- psutil 文档：https://psutil.readthedocs.io/
- pynvml 文档：https://pythonhosted.org/nvidia-ml-py/
- recharts 文档：https://recharts.org/
- @tanstack/react-query 文档：https://tanstack.com/query/latest
- FastAPI 官方文档：https://fastapi.tiangolo.com/

### B. 术语表

| 术语 | 说明 |
|------|------|
| NVML | NVIDIA Management Library，NVIDIA GPU 管理接口 |
| nvidia-smi | NVIDIA System Management Interface，NVIDIA 系统管理工具 |
| 进度条 | Progress Bar，前端组件，用于直观展示百分比 |
| 环形缓冲区 | Ring Buffer，固定大小的循环队列，用于维护最近 N 条数据 |
| 容错降级 | Fallback，系统某部分不可用时，优雅地返回部分可用数据而非报错 |

### C. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Docker 内 GPU 不可用 | 高 | Phase 1 必须验证 GPU 采集的容错逻辑 |
| GPU 指标采集慢 | 中 | 使用超时控制，单次采集超时 2s 后返回空 |
| 历史数据膨胀 | 中 | 按指标分类存储，设置数据保留策略（如保留 30 天） |
| 前端高频刷新影响性能 | 低 | React Query 缓存 + 合理的 refetchInterval |
