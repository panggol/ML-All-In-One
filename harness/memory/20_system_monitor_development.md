# 系统监控模块开发总结

**文档编号：** DEV-MON-001
**版本：** v1.0
**日期：** 2026-04-10
**作者：** 开发 Agent
**状态：** 完成

---

## 一、交付内容

本次实现了 ML All In One 平台的完整系统监控功能模块，包含后端数据采集服务和前端监控页面。

### 1.1 后端交付

| 文件 | 路径 | 说明 |
|------|------|------|
| 依赖添加 | `api/requirements.txt` | 新增 `psutil>=5.9.0` 和 `pynvml>=11.5.0` |
| 监控服务 | `api/services/monitor_service.py` | 核心监控数据采集逻辑（CPU/内存/GPU/磁盘/网络/任务统计） |
| 监控路由 | `api/routes/monitor.py` | FastAPI 路由定义（8 个端点） |
| 服务导出 | `api/services/__init__.py` | 新建，导出 monitor_service |
| 路由注册 | `api/main.py` | 注册 `/api/monitor` 路由 |
| 路由汇总 | `api/routes/__init__.py` | 新增 monitor 模块导出 |

### 1.2 前端交付

| 文件 | 路径 | 说明 |
|------|------|------|
| API 层 | `frontend/src/api/monitor.ts` | TypeScript 类型定义 + API 请求函数 |
| 进度条组件 | `frontend/src/components/monitor/UsageProgressBar.tsx` | 带阈值语义色的进度条（绿/黄/红） |
| 指标卡片组件 | `frontend/src/components/monitor/MetricCard.tsx` | 顶部指标大卡片（数值+进度条+图标） |
| GPU 卡片组件 | `frontend/src/components/monitor/GPUDeviceCard.tsx` | 单块 GPU 详情（显存/利用率/温度） |
| 磁盘表格组件 | `frontend/src/components/monitor/DiskTable.tsx` | 磁盘挂载点表格 |
| 网络折线图 | `frontend/src/components/monitor/NetworkChart.tsx` | recharts 折线图（发送/接收） |
| 任务状态条 | `frontend/src/components/monitor/JobStatusBar.tsx` | 训练任务统计（4 状态点阵图） |
| 系统信息栏 | `frontend/src/components/monitor/SystemInfoBar.tsx` | 主机名/运行时间/OS 信息 |
| 独立监控页 | `frontend/src/pages/Monitor.tsx` | 完整监控页面（5 秒轮询） |
| Dashboard 改造 | `frontend/src/pages/Dashboard.tsx` | 系统状态区改造（30 秒轮询） |
| 路由配置 | `frontend/src/App.tsx` | 新增 `/monitor` 路由和导航 Tab |

---

## 二、API 设计

### 2.1 新增端点

| 端点 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 系统概览 | GET | `/api/monitor/overview` | 所有指标摘要 |
| CPU 详情 | GET | `/api/monitor/cpu` | CPU 指标 |
| 内存详情 | GET | `/api/monitor/memory` | 内存指标 |
| GPU 详情 | GET | `/api/monitor/gpu` | GPU 指标（优雅降级） |
| 磁盘详情 | GET | `/api/monitor/disk` | 磁盘挂载点 |
| 网络详情 | GET | `/api/monitor/network` | 网络流量（含实时速率） |
| 任务统计 | GET | `/api/monitor/jobs` | 训练任务统计 |
| 历史数据 | GET | `/api/monitor/history` | 历史指标查询 |

所有端点均受认证保护（`Depends(get_current_user)`）。

### 2.2 GPU 优雅降级实现

```python
# api/services/monitor_service.py
def _init_nvml() -> bool:
    try:
        import pynvml
        pynvml.nvmlInit()
        return True
    except Exception as e:
        logger.warning(f"NVML init failed: {e}")
        return False

def _get_gpu_info() -> Dict[str, Any]:
    if not _init_nvml():
        return {
            "available": False,
            "count": 0,
            "devices": [],
            "reason": "No NVIDIA GPU detected or nvidia-smi not available"
        }
    # ... 正常采集逻辑
```

**效果：** 在无 GPU 环境下，`/api/monitor/overview` 返回 HTTP 200，`gpu.available = false`，不触发任何错误。

---

## 三、技术实现要点

### 3.1 后端采集策略

- **实时采集**：每次 API 请求时实时采集指标，无缓存（P99 ≤ 500ms 目标）
- **单次超时控制**：整个 overview 采集过程在 500ms 内完成
- **独立容错**：每个指标采集相互独立，任一失败不影响其他指标返回
- **网络速率计算**：通过两次 `psutil.net_io_counters()` 调用差分计算实时速率

```python
# 网络速率计算
bytes_sent_mb = net.bytes_sent / (1024**2)
send_rate_mbps = (net.bytes_sent - last.bytes_sent) / (1024**2) / elapsed
```

### 3.2 前端轮询策略

| 页面 | 刷新间隔 | 实现方式 |
|------|---------|---------|
| Dashboard 系统状态区 | 30 秒 | `useQuery({ refetchInterval: 30000 })` |
| 独立监控页面 | 5 秒 | `useQuery({ refetchInterval: 5000 })` |

### 3.3 网络流量环形缓冲区

独立监控页面使用 React `useState` 维护最多 60 条数据的环形缓冲区：

```typescript
const MAX_BUFFER_SIZE = 60
setNetworkBuffer(prev => {
  const next = [...prev, newPoint]
  return next.length > MAX_BUFFER_SIZE ? next.slice(-MAX_BUFFER_SIZE) : next
})
```

### 3.4 recharts 折线图配置

- 双线展示：发送（cyan-500）+ 接收（violet-500）
- `isAnimationActive={false}`：高频刷新时禁用动画避免性能问题
- `tickFormatter`：X 轴时间格式化为 `HH:mm:ss`
- 自定义 Tooltip：显示每条线的具体数值

### 3.5 Docker 容器兼容性

- **CPU/内存/磁盘**：通过 `psutil` 直接读取 `/proc` 文件系统，无需特殊权限
- **GPU**：依赖容器以 `--gpus all` 启动，挂载 `/dev/nvidia*` 和 nvidia driver
- **网络**：采集容器网络命名空间的网络接口（通常是 `eth0`）

---

## 四、阈值语义色

进度条颜色根据使用率动态变化：

| 使用率范围 | 颜色 | 含义 |
|-----------|------|------|
| 0% - 60% | emerald-500（绿色） | 正常 |
| 60% - 85% | amber-500（黄色） | 警告 |
| 85% - 100% | red-500（红色） | 危险 |

阈值逻辑在 `UsageProgressBar.tsx` 的 `getAutoColor()` 函数中实现。

---

## 五、依赖变更

### 5.1 新增 Python 依赖

```txt
psutil>=5.9.0     # 系统指标采集（CPU/内存/磁盘/网络）
pynvml>=11.5.0    # NVIDIA GPU 监控（可选，GPU 不可用时优雅降级）
```

### 5.2 前端已有依赖（无需额外安装）

- `recharts@2.12.7`：已引入，用于网络流量折线图
- `@tanstack/react-query`：已引入，用于数据轮询
- `lucide-react`：已引入，用于图标

---

## 六、验证清单

| 检查项 | 状态 |
|--------|------|
| requirements.txt 包含 psutil + pynvml | ✅ |
| `api/services/monitor_service.py` 实现 CPU/内存/GPU/磁盘/网络采集 | ✅ |
| `api/routes/monitor.py` 实现 8 个端点 | ✅ |
| GPU 不可用时返回 `available: false` 不报错 | ✅ |
| `api/main.py` 注册 monitor 路由 | ✅ |
| `frontend/src/api/monitor.ts` 类型 + API 函数 | ✅ |
| 7 个监控专用组件（UsageProgressBar/MetricCard/GPUDeviceCard/DiskTable/NetworkChart/JobStatusBar/SystemInfoBar） | ✅ |
| `frontend/src/pages/Monitor.tsx` 独立监控页面（5 秒刷新） | ✅ |
| Dashboard 系统状态区改造（30 秒刷新 + 进度条） | ✅ |
| App.tsx 新增 `/monitor` 路由和导航 Tab | ✅ |
| 网络折线图使用 recharts（发送/接收双线，无动画） | ✅ |

---

## 七、后续优化方向（Phase 2-5）

1. **历史数据 API**：完善 `monitor_history` 表 + 后台定时采集任务
2. **告警机制**：GPU 显存 > 90%、磁盘 > 85%、内存 > 90% 触发告警
3. **多服务器集群监控视图**
4. **监控报告导出（PDF/CSV）**

---

## 八、已知约束

1. **历史数据 API**：目前 `monitor_history` 表已定义但后台采集任务尚未实现（Phase 4 范围）
2. **认证依赖**：监控 API 需要用户已登录，未登录时返回 401
3. **Docker 网络**：在 Docker 容器内采集的是容器网络命名空间的网络接口，而非宿主机
4. **GPU 温度**：部分 GPU 不支持温度读取，`temperature_celsius` 可能为 `null`，前端显示 "N/A"
