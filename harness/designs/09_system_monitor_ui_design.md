# ML All In One - 系统监控模块 UI 设计

**项目：** ML All In One
**模块：** 系统监控（System Monitoring）
**日期：** 2026-04-10
**状态：** 设计完成

---

## 一、模块概述

### 1.1 模块定位

系统监控模块是 ML All In One 平台的运维支撑组件，提供服务器资源、GPU 资源、磁盘、网络及训练任务状态的实时可视化监控能力。该模块包含两个交付物：Dashboard 内嵌改造（实时系统状态卡片）和独立监控页面（`/monitor`）。

### 1.2 设计目标

- **实时性**：5 秒高频刷新，满足运维监控需求
- **层次清晰**：用进度条展示资源使用率，用折线图展示趋势
- **优雅降级**：GPU 不可用时显示友好提示而非报错
- **风格统一**：复用现有设计系统的颜色、间距和组件规范

### 1.3 技术选型

| 技术 | 选型 | 说明 |
|------|------|------|
| 图表库 | recharts（已引入） | LineChart 绘制网络流量趋势 |
| 状态管理 | @tanstack/react-query（已引入） | `useQuery` + `refetchInterval` 管理轮询 |
| 环形缓冲区 | 前端内存数组（最多 60 条） | 维护最近 5 分钟网络流量数据 |
| 组件库 | 复用现有组件（Card, StatCard, ProgressBar） | 保证风格一致性 |
| 图标库 | lucide-react（已引入） | Activity, Cpu, HardDrive, Network, Server |

---

## 二、设计规范

### 2.1 色彩系统

```typescript
// 监控模块专用色板
const monitorColors = {
  // 状态色
  status: {
    healthy: '#10b981',    // emerald-500，正常
    warning: '#f59e0b',    // amber-500，警告
    danger: '#ef4444',     // red-500，危险
    unknown: '#94a3b8',     // slate-400，不可获取
  },

  // 指标色（与图表 series 保持一致）
  metric: {
    cpu:      '#0ea5e9',   // sky-500
    memory:   '#8b5cf6',   // violet-500
    gpu:      '#f59e0b',   // amber-500
    disk:     '#10b981',   // emerald-500
    network:  '#06b6d4',   // cyan-500
  },

  // 进度条渐变
  gradient: {
    low:    ['#10b981', '#34d399'],     // 0-60%，绿色
    medium: ['#f59e0b', '#fbbf24'],     // 60-85%，黄色
    high:   ['#ef4444', '#f87171'],     // 85-100%，红色
  },

  // 背景与边框
  bg: {
    card: '#ffffff',
    page: '#f8fafc',      // slate-50
    hover: '#f1f5f9',     // slate-100
  },
}
```

### 2.2 间距系统

```typescript
// 监控模块间距
const monitorSpacing = {
  // 页面级
  pagePadding: 'px-6 py-8',
  pageGap: 'gap-6',

  // 卡片级
  cardPadding: 'p-6',
  cardGap: 'gap-4',

  // 指标卡片内部
  metricCardContentGap: 'gap-3',
  metricCardPadding: 'p-5',

  // 网格
  grid: {
    overview: 'grid-cols-2 lg:grid-cols-4',  // 顶部概览卡片
    gpu: 'grid-cols-1 lg:grid-cols-2 xl:grid-cols-3',  // GPU 卡片
  },
}
```

### 2.3 阈值语义色

进度条颜色根据使用率动态变化：

| 使用率范围 | 颜色 | 含义 |
|-----------|------|------|
| 0% - 60% | emerald-500（绿色） | 正常 |
| 60% - 85% | amber-500（黄色） | 警告 |
| 85% - 100% | red-500（红色） | 危险 |

```typescript
// 颜色计算函数
function getUsageColor(percent: number): string {
  if (percent >= 85) return 'bg-red-500'
  if (percent >= 60) return 'bg-amber-500'
  return 'bg-emerald-500'
}
```

### 2.4 字体规范

与现有设计系统保持一致，监控模块特殊字体使用：

```typescript
const monitorTypography = {
  // 指标数值（醒目大字）
  metricValue: {
    fontSize: 'text-3xl',
    fontWeight: 'font-bold',
    fontFamily: 'Inter, system-ui, sans-serif',
    lineHeight: 'leading-none',
  },
  // 指标标签
  metricLabel: {
    fontSize: 'text-sm',
    fontWeight: 'font-medium',
    color: 'text-slate-500',
  },
  // 卡片标题
  cardTitle: {
    fontSize: 'text-base',
    fontWeight: 'font-semibold',
    color: 'text-slate-800',
  },
  // 表格内容
  tableCell: {
    fontSize: 'text-sm',
    color: 'text-slate-700',
  },
}
```

---

## 三、页面布局

### 3.1 独立监控页面整体布局

```
┌─────────────────────────────────────────────────────────────┐
│ Header（全局导航栏，与其他页面保持一致）                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Page Header                                          │  │
│  │ 系统监控           最后更新: 23:28:00   [🔄 手动刷新]  │  │
│  │ 实时监控服务器资源、GPU 状态、磁盘、网络和训练任务     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Top Metric Cards (4列)                               │  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│  │ │ CPU      │ │ 内存     │ │ GPU 显存 │ │ 磁盘     │ │  │
│  │ │  23.5%   │ │  57.1%   │ │  31.0%   │ │  45.2%   │ │  │
│  │ │ [进度条] │ │ [进度条] │ │ [进度条] │ │ [进度条] │ │  │
│  │ │ 8核      │ │ 18.2/31.9│ │ 12.4/40  │ │ 45.2/100 │ │  │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ GPU Devices                                          │  │
│  │ GPU 设备 (1块)                        [全部展开]     │  │
│  │ ┌────────────────────────────────────────────────┐  │  │
│  │ │ A100-SXM4-40GB  [index: 0]                    │  │  │
│  │ │ 显存: ████████░░░░░░░░░░░ 12.4/40 GB  31%    │  │  │
│  │ │ 利用率: ████████░░░░░░░░░░░░░░░░░░░  45%     │  │  │
│  │ │ 温度:  62°C  🔥 (正常/过热)                   │  │  │
│  │ └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌────────────────────────┐  ┌────────────────────────────┐ │
│  │ 磁盘挂载点             │  │ 训练任务状态                │ │
│  │                       │  │                            │ │
│  │ 挂载点  总容量 已用 剩余│  │ 运行中:  ●●●●●●●●○  2      │ │
│  │ /      100GB  45GB 55GB│  │ 队列中:  ●○○○○○○○○○  1      │ │
│  │ /data  500GB  120GB 380│  │ 已完成:  ████████████ 15   │ │
│  │                       │  │ 失败:     ██░░░░░░░░░  1    │ │
│  └────────────────────────┘  └────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 网络流量（实时）                      [最近 5 分钟]  │  │
│  │ 发送: 2.5 MB/s  接收: 8.3 MB/s                       │  │
│  │ ┌────────────────────────────────────────────────┐  │  │
│  │ │        📈 折线图（发送 / 接收）                 │  │  │
│  │ └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 系统信息                                             │  │
│  │ 主机名: ml-server-01  |  运行时间: 10天  |  OS: Linux│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Dashboard 内嵌改造

现有 Dashboard 的"系统状态"区块（第 145-165 行）改为动态数据：

```
┌──────────────────────────────────────────────────────┐
│ ● 系统状态                                           │
│ ┌──────────────┐ ┌──────────────────┐ ┌────────────┐│
│ │ API 服务     │ │ GPU 内存         │ │ 磁盘使用   ││
│ │ ● 正常运行   │ │ ██████░░░░ 2.1/8 │ │ ███░ 45/  ││
│ │              │ │              26%  │ │      100GB ││
│ │              │ │                   │ │        45% ││
│ └──────────────┘ └──────────────────┘ └────────────┘│
└──────────────────────────────────────────────────────┘
```

- API 服务状态通过 `/api/health` 判断（`status === 'ok'` → 绿色）
- GPU 内存、磁盘使用量使用 `ProgressBar` 组件展示
- Dashboard 刷新间隔：30 秒（使用 `useQuery` 的 `refetchInterval: 30000`）

### 3.3 响应式断点

| 断点 | 布局变化 |
|------|----------|
| ≥1280px | 4 列顶部卡片，GPU 3 列，双栏并排 |
| 768-1279px | 2 列顶部卡片，GPU 单列，单栏堆叠 |
| <768px | 单列全宽，简化标签文字 |

---

## 四、组件清单

### 4.1 页面组件

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `Monitor` | `pages/Monitor.tsx` | 独立监控页面主组件 |
| `Dashboard`（改造） | `pages/Dashboard.tsx` | 改造系统状态区块 |

### 4.2 监控专用组件

| 组件名 | 路径 | 说明 |
|--------|------|------|
| `MetricCard` | `components/monitor/MetricCard.tsx` | 顶部指标大卡片（CPU/内存/GPU/磁盘） |
| `GPUDeviceCard` | `components/monitor/GPUDeviceCard.tsx` | 单块 GPU 详情卡片 |
| `DiskTable` | `components/monitor/DiskTable.tsx` | 磁盘挂载点表格 |
| `NetworkChart` | `components/monitor/NetworkChart.tsx` | 网络流量折线图 |
| `JobStatusBar` | `components/monitor/JobStatusBar.tsx` | 训练任务状态统计条 |
| `SystemInfoBar` | `components/monitor/SystemInfoBar.tsx` | 系统基本信息行 |
| `UsageProgressBar` | `components/monitor/UsageProgressBar.tsx` | 带阈值语义色的进度条 |

### 4.3 组件关系图

```
pages/Monitor.tsx
├── MetricCard (×4)          // CPU / 内存 / GPU 显存 / 磁盘
├── GPUDeviceCard (×N)      // 每块 GPU 一个，N = gpu.count
├── DiskTable                // 所有挂载点
├── NetworkChart             // 折线图（recharts）
├── JobStatusBar             // 任务统计
└── SystemInfoBar            // 系统信息

pages/Dashboard.tsx（改造）
└── SystemStatusPanel        // 嵌入 Dashboard 的监控状态区
    ├── APIHealthBadge        // API 服务状态徽章
    ├── UsageProgressBar (×2) // GPU 显存 / 磁盘
```

---

## 五、Props 定义

### 5.1 MetricCard

```typescript
interface MetricCardProps {
  // 指标名称
  title: string

  // 当前值（百分比）
  value: number

  // 总量（可选，用于显示 "used/total" 格式）
  total?: number
  used?: number

  // 格式化显示
  format?: {
    unit?: string         // 'GB', '%', '核心'
    decimals?: number     // 小数位数，默认 1
    showAbsolute?: boolean // 是否显示绝对值，默认 false
  }

  // 图标
  icon: LucideIcon

  // 颜色（可覆盖自动阈值计算）
  colorScheme?: 'auto' | 'emerald' | 'amber' | 'red' | 'sky' | 'violet'

  // 附加信息
  subInfo?: string

  // 尺寸
  size?: 'sm' | 'md'

  // 加载状态
  loading?: boolean
}

// 使用示例
<MetricCard
  title="GPU 显存"
  value={31.0}
  total={40}
  used={12.4}
  format={{ unit: 'GB', decimals: 1 }}
  icon={HardDrive}
  colorScheme="auto"
  subInfo="A100-SXM4-40GB"
/>
```

### 5.2 GPUDeviceCard

```typescript
interface GPUDeviceCardProps {
  // GPU 设备信息
  device: {
    index: number
    name: string
    memory_total_gb: number
    memory_used_gb: number
    memory_free_gb: number
    memory_usage_percent: number
    utilization_percent: number
    temperature_celsius: number | null
  }

  // 是否可展开更多详情
  expandable?: boolean

  // 尺寸
  size?: 'sm' | 'md'

  // 加载状态
  loading?: boolean
}

// 使用示例
<GPUDeviceCard
  device={{
    index: 0,
    name: 'NVIDIA A100-SXM4-40GB',
    memory_total_gb: 40,
    memory_used_gb: 12.4,
    memory_free_gb: 27.6,
    memory_usage_percent: 31,
    utilization_percent: 45,
    temperature_celsius: 62,
  }}
/>
```

### 5.3 UsageProgressBar

```typescript
interface UsageProgressBarProps {
  // 数值
  value: number       // 当前值
  max?: number        // 最大值，默认 100

  // 标签
  label?: string
  showLabel?: boolean  // 是否显示百分比标签，默认 true

  // 格式化
  format?: {
    unit?: string
    decimals?: number
    showValue?: boolean  // 显示 "value / max" 格式，默认 false
  }

  // 颜色策略
  colorStrategy?: 'auto' | 'fixed'  // 'auto' 根据阈值自动变色

  // 阈值配置
  thresholds?: {
    warning: number   // 触发警告的值，默认 60
    danger: number    // 触发危险的值，默认 85
  }

  // 颜色固定时的颜色
  fixedColor?: string

  // 尺寸
  size?: 'sm' | 'md' | 'lg'

  // 类名
  className?: string
}

// 使用示例
<UsageProgressBar
  value={31}
  max={40}
  label="GPU 显存"
  format={{ unit: 'GB', showValue: true }}
  colorStrategy="auto"
  size="md"
/>
```

### 5.4 DiskTable

```typescript
interface DiskTableProps {
  // 磁盘分区数据
  partitions: Array<{
    mountpoint: string
    total_gb: number
    used_gb: number
    free_gb: number
    usage_percent: number
  }>

  // 加载状态
  loading?: boolean

  // 空状态显示
  emptyText?: string
}

// 使用示例
<DiskTable partitions={disk.partitions} />
```

### 5.5 NetworkChart

```typescript
interface NetworkChartProps {
  // 数据点数组（环形缓冲区，最多 60 条）
  data: Array<{
    timestamp: string   // ISO 8601
    send_mbps: number
    recv_mbps: number
  }>

  // 刷新间隔（秒），用于显示 "每 N 秒刷新"
  refreshInterval?: number

  // 是否显示发送/接收切换
  showToggle?: boolean

  // 默认显示哪个 series
  defaultSeries?: 'both' | 'send' | 'recv'

  // 图表高度
  height?: number

  // 加载状态
  loading?: boolean
}

// 使用示例
<NetworkChart
  data={networkBuffer}
  refreshInterval={5}
  height={200}
/>
```

### 5.6 JobStatusBar

```typescript
interface JobStatusBarProps {
  // 任务统计
  stats: {
    running: number
    pending: number
    completed: number
    failed: number
  }

  // 是否显示详情（展开为多个进度条）
  expandable?: boolean

  // 默认展开状态
  defaultExpanded?: boolean

  // 加载状态
  loading?: boolean
}

// 使用示例
<JobStatusBar
  stats={{ running: 2, pending: 1, completed: 15, failed: 1 }}
  expandable={true}
/>
```

### 5.7 SystemInfoBar

```typescript
interface SystemInfoBarProps {
  // 系统信息
  info: {
    hostname: string
    uptime_seconds: number
    os_type: string
    os_version: string
  }

  // 加载状态
  loading?: boolean
}

// 使用示例
<SystemInfoBar
  info={{
    hostname: 'ml-server-01',
    uptime_seconds: 864000,
    os_type: 'Linux',
    os_version: '6.8.0-100-generic',
  }}
/>
```

---

## 六、API 对接

### 6.1 新增 API 文件

创建 `frontend/src/api/monitor.ts`，使用已有的 `api`（Axios 实例）：

```typescript
// frontend/src/api/monitor.ts
import { api } from './client'

// ============ 类型定义 ============

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

export interface HistoryDataPoint {
  timestamp: string
  value: number
}

export interface MonitorHistoryResponse {
  metric: string
  interval: string
  data: HistoryDataPoint[]
}

// ============ API 方法 ============

export const monitorApi = {
  /**
   * 获取系统监控概览数据
   * 实时数据，每次请求时实时采集
   */
  getOverview: () =>
    api.get<MonitorOverviewResponse>('/api/monitor/overview'),

  /**
   * 获取历史监控数据
   * @param metric 指标名：cpu, memory, gpu_memory, disk, network_send, network_recv
   * @param from 开始时间（ISO 8601）
   * @param to 结束时间（ISO 8601）
   * @param interval 采样间隔：30s, 60s, 5m（默认 60s）
   */
  getHistory: (params: {
    metric: string
    from: string
    to: string
    interval?: string
  }) => api.get<MonitorHistoryResponse>('/api/monitor/history', { params }),
}
```

### 6.2 Dashboard 集成方式

在 `Dashboard.tsx` 中引入监控 API，改造系统状态区块：

```typescript
import { monitorApi } from '../api/monitor'

// 在 Dashboard 组件内
const { data: monitorData, isLoading: monitorLoading } = useQuery({
  queryKey: ['monitor', 'overview'],
  queryFn: () => monitorApi.getOverview(),
  refetchInterval: 30000,  // 30 秒刷新
  // GPU 不可用时 gpu.available === false，queryFn 仍正常返回
  // 所以这里不需要额外的 onError 处理
})

// GPU 内存进度条
<UsageProgressBar
  value={monitorData?.gpu.devices[0]?.memory_used_gb ?? 0}
  max={monitorData?.gpu.devices[0]?.memory_total_gb ?? 1}
  format={{ unit: 'GB', showValue: true }}
  colorStrategy="auto"
/>

// 磁盘进度条
<UsageProgressBar
  value={monitorData?.disk.partitions[0]?.used_gb ?? 0}
  max={monitorData?.disk.partitions[0]?.total_gb ?? 1}
  format={{ unit: 'GB', showValue: true }}
  colorStrategy="auto"
/>
```

### 6.3 独立监控页面集成方式

在 `Monitor.tsx` 中使用高频轮询：

```typescript
import { monitorApi, type MonitorOverviewResponse } from '../api/monitor'
import { useQuery } from '@tanstack/react-query'

// 网络流量环形缓冲区（最多 60 条，5 分钟 × 12 条/分钟）
const MAX_BUFFER_SIZE = 60

export default function Monitor() {
  const [networkBuffer, setNetworkBuffer] = useState<Array<{
    timestamp: string
    send_mbps: number
    recv_mbps: number
  }>>([])

  // 高频轮询概览数据（5 秒刷新）
  const { data, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['monitor', 'overview'],
    queryFn: () => monitorApi.getOverview(),
    refetchInterval: 5000,
  })

  // 维护网络流量环形缓冲区
  useEffect(() => {
    if (!data) return
    const point = {
      timestamp: data.timestamp,
      send_mbps: data.network.send_rate_mbps,
      recv_mbps: data.network.recv_rate_mbps,
    }
    setNetworkBuffer(prev => {
      const next = [...prev, point]
      return next.length > MAX_BUFFER_SIZE ? next.slice(-MAX_BUFFER_SIZE) : next
    })
  }, [data])

  // ... 渲染
}
```

### 6.4 GPU 不可用时的降级处理

在组件层统一处理 `gpu.available === false` 的情况：

```typescript
// GPUDeviceCard 中
function GPUDeviceCard({ device, ... }: GPUDeviceCardProps) {
  if (!device) {
    return (
      <Card className="opacity-60">
        <div className="flex items-center gap-3 text-slate-500">
          <AlertTriangle className="w-5 h-5 text-amber-500" />
          <span>GPU 不可用</span>
        </div>
      </Card>
    )
  }
  // 正常渲染 GPU 卡片
}
```

---

## 七、路由配置

### 7.1 App.tsx 改造

在 `frontend/src/App.tsx` 中新增监控页面路由：

```typescript
import Monitor from './pages/Monitor'

// tabs 数组中新增（放在 dashboard 之后）
const tabs = [
  { id: 'dashboard' as const, label: '仪表盘', icon: Sparkles },
  { id: 'monitor' as const, label: '系统监控', icon: Activity },   // ← 新增
  // ...其他 tab
]

// 路由配置中新增
<Route path="/monitor" element={<Layout />} />

// Layout 中新增渲染逻辑
{activeTab === 'monitor' && <Monitor />}
```

### 7.2 导航栏图标

使用 `lucide-react` 的 `Activity` 图标作为系统监控 Tab 的标识：

```typescript
import { Activity } from 'lucide-react'
```

---

## 八、网络流量折线图详细规格

### 8.1 图表配置

```typescript
// NetworkChart 内部使用 recharts
<ResponsiveContainer width="100%" height={height || 200}>
  <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
    <XAxis
      dataKey="timestamp"
      tickFormatter={(v) => format(new Date(v), 'HH:mm:ss')}
      tick={{ fontSize: 11, fill: '#64748b' }}
      tickLine={false}
      axisLine={{ stroke: '#e2e8f0' }}
    />
    <YAxis
      tick={{ fontSize: 11, fill: '#64748b' }}
      tickLine={false}
      axisLine={false}
      tickFormatter={(v) => `${v} MB/s`}
      width={60}
    />
    <Tooltip
      formatter={(value: number, name: string) => [
        `${value.toFixed(2)} MB/s`,
        name === 'send_mbps' ? '发送' : '接收',
      ]}
      labelFormatter={(label) => format(new Date(label), 'HH:mm:ss')}
      contentStyle={{
        backgroundColor: 'white',
        border: '1px solid #e2e8f0',
        borderRadius: '8px',
        fontSize: 12,
      }}
    />
    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
    <Line
      type="monotone"
      dataKey="send_mbps"
      stroke="#06b6d4"   // cyan-500
      strokeWidth={2}
      dot={false}
      name="发送"
      isAnimationActive={false}  // 高频刷新时禁用动画
    />
    <Line
      type="monotone"
      dataKey="recv_mbps"
      stroke="#8b5cf6"   // violet-500
      strokeWidth={2}
      dot={false}
      name="接收"
      isAnimationActive={false}
    />
    <Legend
      formatter={(value) => value === 'send_mbps' ? '发送' : '接收'}
      iconType="line"
    />
  </LineChart>
</ResponsiveContainer>
```

### 8.2 数据刷新策略

| 场景 | 刷新间隔 | 数据源 |
|------|---------|--------|
| Dashboard 系统状态区 | 30 秒 | `useQuery` + `refetchInterval: 30000` |
| 独立监控页面（概览数据） | 5 秒 | `useQuery` + `refetchInterval: 5000` |
| 网络流量折线图 | 5 秒（跟随概览） | 内存环形缓冲区（最多 60 条） |
| 历史趋势图 | 页面加载时请求 | `/api/monitor/history` |

---

## 九、状态管理

### 9.1 Local State（组件内）

```typescript
// 组件级别的临时状态
interface MonitorLocalState {
  // 网络流量环形缓冲区
  networkBuffer: Array<{ timestamp: string; send_mbps: number; recv_mbps: number }>

  // GPU 卡片展开状态
  gpuCardsExpanded: boolean

  // 任务状态条展开状态
  jobBarExpanded: boolean

  // 最后更新时间
  lastUpdated: Date | null
}
```

### 9.2 URL State（无）

监控页面暂无 URL 参数需求，数据完全由后端 API 驱动。

### 9.3 Global State（React Query Cache）

```typescript
// React Query 缓存键
interface MonitorQueryKeys {
  overview: ['monitor', 'overview']
  history: (metric: string, from: string, to: string, interval?: string)
           => ['monitor', 'history', metric, from, to, interval]
}
```

---

## 十、视觉效果与交互

### 10.1 阈值告警视觉效果

当指标超过阈值时，进度条颜色变化并伴随轻微动画：

```typescript
// 危险状态（≥85%）额外效果
{percent >= 85 && (
  <div className="absolute inset-0 rounded-full animate-pulse bg-red-500/10" />
)}
```

### 10.2 加载状态

所有卡片在加载中时显示骨架屏：

```typescript
{loading && (
  <div className="animate-pulse">
    <div className="h-4 bg-slate-200 rounded w-1/2 mb-2" />
    <div className="h-8 bg-slate-200 rounded w-3/4 mb-2" />
    <div className="h-2 bg-slate-200 rounded w-full" />
  </div>
)}
```

### 10.3 空值处理

所有数值字段显示前做空值保护：

```typescript
// 统一使用此辅助函数
function formatValue(value: number | undefined | null, fallback = 'N/A'): string {
  if (value === undefined || value === null) return fallback
  return value.toFixed(1)
}
```

### 10.4 GPU 不可用状态

```typescript
// GPU 区域当 gpu.available === false 时显示
<Card className="border border-amber-200 bg-amber-50">
  <div className="flex items-center gap-3 py-4">
    <AlertTriangle className="w-5 h-5 text-amber-500" />
    <div>
      <p className="font-medium text-amber-800">GPU 不可用</p>
      <p className="text-sm text-amber-600">{gpu.reason || '未检测到 NVIDIA GPU 或 nvidia-smi 不可用'}</p>
    </div>
  </div>
</Card>
```

---

## 十一、后续优化

### 短期计划
- [ ] 实现 `UsageProgressBar` 阈值语义色组件
- [ ] 实现 `MetricCard` 指标卡片组件
- [ ] 实现 `GPUDeviceCard` GPU 详情卡片
- [ ] 接入 Dashboard 系统状态区改造
- [ ] 接入独立监控页面 `/monitor`

### 中期计划
- [ ] 实现 `NetworkChart` 折线图组件（recharts）
- [ ] 实现 `DiskTable` 磁盘表格组件
- [ ] 实现 `JobStatusBar` 任务状态条
- [ ] 实现 `SystemInfoBar` 系统信息栏
- [ ] 添加历史趋势图查询功能

### 长期计划
- [ ] 支持自定义告警阈值配置
- [ ] 支持告警通知（WebSocket 推送）
- [ ] 支持多服务器集群监控视图
- [ ] 支持导出监控报告（PDF/CSV）

---

*文档版本：v1.0.0 | 最后更新：2026-04-10*
