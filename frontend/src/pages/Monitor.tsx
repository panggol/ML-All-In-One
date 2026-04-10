/**
 * Monitor - 独立系统监控页面
 * 实时刷新，5秒轮询，使用环形缓冲区维护网络流量历史
 */
import { useState, useEffect } from 'react'
import { Activity, RefreshCw, AlertTriangle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { monitorApi, type MonitorOverviewResponse } from '../api/monitor'
import MetricCard from '../components/monitor/MetricCard'
import GPUDeviceCard from '../components/monitor/GPUDeviceCard'
import DiskTable from '../components/monitor/DiskTable'
import NetworkChart, { type NetworkDataPoint } from '../components/monitor/NetworkChart'
import JobStatusBar from '../components/monitor/JobStatusBar'
import SystemInfoBar from '../components/monitor/SystemInfoBar'
import Card from '../components/Card'
import { Cpu, HardDrive, HardDriveDownload, Gauge } from 'lucide-react'
import {
  MAX_BUFFER_SIZE,
  POLL_INTERVAL_MS,
} from '../constants/monitor'

function formatLastUpdated(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('zh-CN', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return 'N/A'
  }
}

// GPU 不可用时显示的降级卡片
function GPUUnavailableCard({ reason }: { reason?: string }) {
  return (
    <Card className="border border-amber-200 bg-amber-50">
      <div className="flex items-center gap-3 py-2">
        <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
        <div>
          <p className="font-medium text-amber-800">GPU 不可用</p>
          <p className="text-sm text-amber-600">
            {reason || '未检测到 NVIDIA GPU 或 nvidia-smi 不可用'}
          </p>
        </div>
      </div>
    </Card>
  )
}

export default function Monitor() {
  const [networkBuffer, setNetworkBuffer] = useState<NetworkDataPoint[]>([])

  // 高频轮询概览数据（5 秒刷新）
  const {
    data: monitorData,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['monitor', 'overview'],
    queryFn: () => monitorApi.getOverview(),
    select: (res) => res.data as MonitorOverviewResponse,
    refetchInterval: POLL_INTERVAL_MS,
    retry: 2,
  })

  // 维护网络流量环形缓冲区
  useEffect(() => {
    if (!monitorData) return
    const point: NetworkDataPoint = {
      timestamp: monitorData.timestamp,
      send_mbps: monitorData.network.send_rate_mbps,
      recv_mbps: monitorData.network.recv_rate_mbps,
    }
    setNetworkBuffer(prev => {
      const next = [...prev, point]
      return next.length > MAX_BUFFER_SIZE ? next.slice(-MAX_BUFFER_SIZE) : next
    })
  }, [monitorData])

  const lastUpdated = monitorData?.timestamp ? formatLastUpdated(monitorData.timestamp) : 'N/A'

  // 计算 GPU 显存总量和已用量（如果有 GPU）
  const gpuMemoryPercent = (() => {
    if (!monitorData?.gpu.available || monitorData.gpu.devices.length === 0) return 0
    const first = monitorData.gpu.devices[0]
    return first.memory_usage_percent
  })()

  const gpuMemoryUsed = (() => {
    if (!monitorData?.gpu.available || monitorData.gpu.devices.length === 0) return 0
    return monitorData.gpu.devices[0].memory_used_gb
  })()

  const gpuMemoryTotal = (() => {
    if (!monitorData?.gpu.available || monitorData.gpu.devices.length === 0) return 0
    return monitorData.gpu.devices[0].memory_total_gb
  })()

  const gpuName = (() => {
    if (!monitorData?.gpu.available || monitorData.gpu.devices.length === 0) return ''
    return monitorData.gpu.devices[0].name
  })()

  // 磁盘总量（第一个挂载点）
  const diskTotal = monitorData?.disk.partitions[0]?.total_gb ?? 0
  const diskUsed = monitorData?.disk.partitions[0]?.used_gb ?? 0
  const diskPercent = monitorData?.disk.partitions[0]?.usage_percent ?? 0

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
            <Activity className="w-6 h-6" />
            系统监控
          </h1>
          <p className="text-slate-500 mt-1">实时监控服务器资源、GPU 状态、磁盘、网络和训练任务</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">
            最后更新：<span className="font-medium text-slate-600">{lastUpdated}</span>
          </span>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="CPU 使用率"
          value={monitorData?.cpu.usage_percent ?? 0}
          format={{ unit: '%', decimals: 1 }}
          icon={Cpu}
          colorScheme="auto"
          subInfo={`${monitorData?.cpu.core_count ?? '?'} 核心`}
          loading={isLoading}
        />
        <MetricCard
          title="内存使用率"
          value={monitorData?.memory.usage_percent ?? 0}
          total={monitorData?.memory.total_gb}
          used={monitorData?.memory.used_gb}
          format={{ unit: 'GB', decimals: 1 }}
          icon={Gauge}
          colorScheme="auto"
          subInfo={monitorData ? `${monitorData.memory.used_gb.toFixed(1)} / ${monitorData.memory.total_gb.toFixed(1)} GB` : 'N/A'}
          loading={isLoading}
        />
        <MetricCard
          title="GPU 显存"
          value={gpuMemoryPercent}
          total={gpuMemoryTotal}
          used={gpuMemoryUsed}
          format={{ unit: '%', decimals: 1 }}
          icon={HardDriveDownload}
          colorScheme="auto"
          subInfo={gpuName || 'N/A'}
          loading={isLoading}
        />
        <MetricCard
          title="磁盘使用"
          value={diskPercent}
          total={diskTotal}
          used={diskUsed}
          format={{ unit: 'GB', decimals: 1 }}
          icon={HardDrive}
          colorScheme="auto"
          subInfo={diskTotal > 0 ? `${diskUsed.toFixed(1)} / ${diskTotal.toFixed(1)} GB` : 'N/A'}
          loading={isLoading}
        />
      </div>

      {/* GPU Devices */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">
            GPU 设备
            {monitorData?.gpu.available && (
              <span className="ml-2 text-sm font-normal text-slate-500">
                ({monitorData.gpu.count} 块)
              </span>
            )}
          </h2>
        </div>
        {isLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1].map(i => (
              <div key={i} className="animate-pulse">
                <div className="h-40 bg-slate-100 rounded-xl" />
              </div>
            ))}
          </div>
        ) : !monitorData?.gpu.available ? (
          <GPUUnavailableCard reason={monitorData?.gpu.reason} />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {monitorData.gpu.devices.map(device => (
              <GPUDeviceCard key={device.index} device={device} />
            ))}
          </div>
        )}
      </Card>

      {/* Disk & Job Status (two columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DiskTable
          partitions={monitorData?.disk.partitions ?? []}
          loading={isLoading}
          emptyText="暂无磁盘信息"
        />
        <JobStatusBar
          stats={monitorData?.jobs ?? { running: 0, pending: 0, completed: 0, failed: 0 }}
          loading={isLoading}
        />
      </div>

      {/* Network Traffic Chart */}
      <NetworkChart
        data={networkBuffer}
        refreshInterval={5}
        height={220}
        loading={isLoading}
      />

      {/* System Info */}
      <SystemInfoBar
        info={monitorData?.system ?? { hostname: 'N/A', uptime_seconds: 0, os_type: 'N/A', os_version: 'N/A' }}
        loading={isLoading}
      />
    </div>
  )
}
