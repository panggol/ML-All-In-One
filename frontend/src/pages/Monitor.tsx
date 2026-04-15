/**
 * Monitor - 独立系统监控页面
 * 实时刷新，5秒轮询，使用环形缓冲区维护网络流量历史
 * 包含系统监控和漂移检测两个子 Tab
 */
import { useState, useEffect } from 'react'
import { Activity, RefreshCw, AlertTriangle, TrendingUp, Bell, BellOff, Upload, FileUp } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { monitorApi, type MonitorOverviewResponse } from '../api/monitor'
import {
  driftApi,
  type DriftCheckResponse,
  type DriftTrendResponse,
  type DriftAlertResponse,
  type DriftReportResponse,
} from '../api/drift'
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
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

// ============ 类型别名 ============
type DriftSubTab = 'dashboard' | 'check' | 'alerts'
type MonitorSubTab = 'system' | 'drift'

// ============ 辅助函数 ============

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

// ============ 子组件：系统监控 ============

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

function SystemMonitorTab() {
  const [networkBuffer, setNetworkBuffer] = useState<NetworkDataPoint[]>([])

  const { data: monitorData, isLoading, refetch } = useQuery({
    queryKey: ['monitor', 'overview'],
    queryFn: () => monitorApi.getOverview(),
    select: (res) => res.data as MonitorOverviewResponse,
    refetchInterval: POLL_INTERVAL_MS,
    retry: 2,
  })

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

  const gpuMemoryPercent = (() => {
    if (!monitorData?.gpu.available || monitorData.gpu.devices.length === 0) return 0
    return monitorData.gpu.devices[0].memory_usage_percent
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

  const diskTotal = monitorData?.disk.partitions?.[0]?.total_gb ?? 0
  const diskUsed = monitorData?.disk.partitions?.[0]?.used_gb ?? 0
  const diskPercent = monitorData?.disk.partitions?.[0]?.usage_percent ?? 0

  return (
    <div className="space-y-6">
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

// ============ 子组件：漂移检测 ============

function DriftDashboardTab() {
  const [subTab, setSubTab] = useState<DriftSubTab>('dashboard')
  return (
    <div className="space-y-6">
      {/* Drift Sub-Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        {([
          { id: 'dashboard', label: '仪表盘', icon: TrendingUp },
          { id: 'check', label: '上传检测', icon: FileUp },
          { id: 'alerts', label: '告警配置', icon: Bell },
        ] as const).map(tab => (
          <button
            key={tab.id}
            onClick={() => setSubTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              subTab === tab.id
                ? 'bg-primary-50 text-primary-700'
                : 'text-slate-500 hover:bg-slate-100'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {subTab === 'dashboard' && <DriftDashboardContent />}
      {subTab === 'check' && <DriftCheckContent />}
      {subTab === 'alerts' && <DriftAlertConfigContent />}
    </div>
  )
}

function DriftLevelBadge({ level }: { level: string }) {
  const config: Record<string, { color: string; label: string }> = {
    none: { color: 'bg-emerald-100 text-emerald-700', label: '无漂移' },
    mild: { color: 'bg-yellow-100 text-yellow-700', label: '轻度漂移' },
    moderate: { color: 'bg-orange-100 text-orange-700', label: '中度漂移' },
    severe: { color: 'bg-red-100 text-red-700', label: '严重漂移' },
    undefined: { color: 'bg-slate-100 text-slate-600', label: '无法判定' },
  }
  const c = config[level] ?? config['undefined']
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${c.color}`}>
      {c.label}
    </span>
  )
}

function DriftDashboardContent() {
  // 默认展示 model_id=1 的趋势（后续可扩展为模型选择器）
  const [selectedModelId, setSelectedModelId] = useState(1)
  const [selectedDays, setSelectedDays] = useState(30)

  const { data: trendData, isLoading: trendLoading } = useQuery({
    queryKey: ['drift', 'trend', selectedModelId, selectedDays],
    queryFn: () =>
      driftApi.getTrend(selectedModelId, { days: selectedDays, metric: 'psi' }),
    select: (res) => res.data as DriftTrendResponse,
    enabled: selectedModelId > 0,
  })

  const { data: alertData } = useQuery({
    queryKey: ['drift', 'alerts'],
    queryFn: () => driftApi.listAlerts({}),
    select: (res) => res.data,
  })

  // 当前 PSI（从趋势数据取最新）
  const latestPsi = trendData?.data.length
    ? trendData.data[trendData.data.length - 1].psi_overall
    : null

  const psiColor = (() => {
    if (latestPsi === null) return 'text-slate-400'
    if (latestPsi < 0.1) return 'text-emerald-600'
    if (latestPsi < 0.2) return 'text-yellow-600'
    if (latestPsi < 0.25) return 'text-orange-600'
    return 'text-red-600'
  })()

  return (
    <div className="space-y-6">
      {/* 顶部概览 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 当前 PSI 大卡片 */}
        <Card className="col-span-1">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-5 h-5 text-slate-500" />
            <span className="text-sm font-medium text-slate-600">当前 PSI</span>
          </div>
          <div className={`text-5xl font-bold ${psiColor}`}>
            {latestPsi !== null ? latestPsi.toFixed(4) : '—'}
          </div>
          <div className="mt-2">
            <DriftLevelBadge
              level={
                latestPsi === null
                  ? 'undefined'
                  : latestPsi < 0.1
                  ? 'none'
                  : latestPsi < 0.2
                  ? 'mild'
                  : latestPsi < 0.25
                  ? 'moderate'
                  : 'severe'
              }
            />
          </div>
        </Card>

        {/* 告警配置卡片 */}
        <Card className="col-span-1">
          <div className="flex items-center gap-2 mb-3">
            <Bell className="w-5 h-5 text-slate-500" />
            <span className="text-sm font-medium text-slate-600">告警规则</span>
          </div>
          <div className="text-3xl font-bold text-slate-800">
            {alertData?.total ?? 0}
          </div>
          <p className="text-sm text-slate-500 mt-1">条已配置规则</p>
          <div className="mt-3 space-y-1">
            {(alertData?.alerts ?? []).slice(0, 2).map(alert => (
              <div key={alert.id} className="flex items-center justify-between text-xs">
                <span className="text-slate-600 truncate max-w-[120px]">{alert.name}</span>
                <span className={alert.enabled ? 'text-emerald-600' : 'text-slate-400'}>
                  {alert.enabled ? '已启用' : '已禁用'}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* 检测次数 */}
        <Card className="col-span-1">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-5 h-5 text-slate-500" />
            <span className="text-sm font-medium text-slate-600">最近 {selectedDays} 天</span>
          </div>
          <div className="text-3xl font-bold text-slate-800">
            {trendData?.data.length ?? 0}
          </div>
          <p className="text-sm text-slate-500 mt-1">次检测记录</p>
        </Card>
      </div>

      {/* 筛选器 */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600">模型 ID</label>
          <input
            type="number"
            min={1}
            value={selectedModelId}
            onChange={e => setSelectedModelId(Number(e.target.value))}
            className="w-24 px-2 py-1 border border-slate-200 rounded-lg text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600">天数</label>
          <select
            value={selectedDays}
            onChange={e => setSelectedDays(Number(e.target.value))}
            className="px-2 py-1 border border-slate-200 rounded-lg text-sm"
          >
            <option value={7}>最近 7 天</option>
            <option value={30}>最近 30 天</option>
            <option value={90}>最近 90 天</option>
          </select>
        </div>
      </div>

      {/* PSI 趋势图 */}
      <Card>
        <h3 className="text-base font-semibold text-slate-800 mb-4">PSI 趋势</h3>
        {trendLoading ? (
          <div className="h-60 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : !trendData?.data.length ? (
          <div className="h-60 flex items-center justify-center text-slate-400">
            暂无趋势数据，请先上传检测数据
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trendData.data.map(d => ({
              time: new Date(d.timestamp).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }),
              psi: d.psi_overall,
            }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" fontSize={12} tickLine={false} />
              <YAxis fontSize={12} tickLine={false} domain={[0, 'auto']} />
              <Tooltip
                formatter={(val: number) => [val.toFixed(4), 'PSI']}
                contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0' }}
              />
              <ReferenceLine y={0.2} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: '阈值 0.2', fontSize: 11, fill: '#f59e0b' }} />
              <ReferenceLine y={0.1} stroke="#10b981" strokeDasharray="4 4" label={{ value: '正常 0.1', fontSize: 11, fill: '#10b981' }} />
              <Line
                type="monotone"
                dataKey="psi"
                stroke="#6366f1"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#6366f1' }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* 告警历史 */}
      <Card>
        <h3 className="text-base font-semibold text-slate-800 mb-4">告警规则列表</h3>
        {!alertData?.alerts.length ? (
          <p className="text-sm text-slate-400 text-center py-6">暂无告警规则，请先配置</p>
        ) : (
          <div className="space-y-3">
            {alertData.alerts.map(alert => (
              <div key={alert.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <div className="flex items-center gap-3">
                  {alert.enabled
                    ? <Bell className="w-4 h-4 text-primary-600" />
                    : <BellOff className="w-4 h-4 text-slate-400" />}
                  <div>
                    <p className="font-medium text-slate-800 text-sm">{alert.name}</p>
                    <p className="text-xs text-slate-500">
                      阈值: {alert.threshold} · 指标: {alert.metric.toUpperCase()}
                    </p>
                  </div>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${alert.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'}`}>
                  {alert.enabled ? '启用' : '禁用'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function DriftCheckContent() {
  const [referenceFile, setReferenceFile] = useState<File | null>(null)
  const [currentFile, setCurrentFile] = useState<File | null>(null)
  const [referenceName, setReferenceName] = useState('')
  const [modelId, setModelId] = useState('')
  const [referenceId, setReferenceId] = useState('')
  const [isUploadingRef, setIsUploadingRef] = useState(false)
  const [isChecking, setIsChecking] = useState(false)
  const [result, setResult] = useState<DriftCheckResponse | null>(null)
  const [error, setError] = useState('')

  const uploadReference = async () => {
    if (!referenceFile) return
    setIsUploadingRef(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('file', referenceFile)
      if (referenceName) fd.append('name', referenceName)
      if (modelId) fd.append('model_id', modelId)
      const res = await driftApi.createReference(fd)
      const data = res.data
      setReferenceId(String(data.id))
      alert(`基准数据集创建成功！ID: ${data.id}，特征数: ${data.feature_names.length}`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '上传失败')
    } finally {
      setIsUploadingRef(false)
    }
  }

  const runCheck = async () => {
    if (!currentFile || !referenceId) return
    setIsChecking(true)
    setError('')
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('file', currentFile)
      fd.append('reference_id', referenceId)
      if (modelId) fd.append('model_id', modelId)
      const res = await driftApi.checkDrift(fd)
      setResult(res.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '检测失败')
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 步骤一：上传基准 */}
      <Card>
        <h3 className="text-base font-semibold text-slate-800 mb-4">步骤 1：上传基准数据集</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">基准 CSV 文件 *</label>
            <input
              type="file"
              accept=".csv"
              onChange={e => setReferenceFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">基准名称（可选）</label>
            <input
              value={referenceName}
              onChange={e => setReferenceName(e.target.value)}
              placeholder="如：train_v1"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">关联模型 ID（可选）</label>
            <input
              type="number"
              value={modelId}
              onChange={e => setModelId(e.target.value)}
              placeholder="如：1"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
            />
          </div>
          <button
            onClick={uploadReference}
            disabled={!referenceFile || isUploadingRef}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload className="w-4 h-4" />
            {isUploadingRef ? '上传中...' : '上传基准数据'}
          </button>
        </div>
      </Card>

      {/* 步骤二：提交检测 */}
      <Card>
        <h3 className="text-base font-semibold text-slate-800 mb-4">步骤 2：提交当前数据检测</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">基准数据集 ID *</label>
            <input
              type="number"
              value={referenceId}
              onChange={e => setReferenceId(e.target.value)}
              placeholder="步骤1返回的ID"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">当前数据 CSV *</label>
            <input
              type="file"
              accept=".csv"
              onChange={e => setCurrentFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm"
            />
          </div>
          <button
            onClick={runCheck}
            disabled={!currentFile || !referenceId || isChecking}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <TrendingUp className="w-4 h-4" />
            {isChecking ? '检测中...' : '运行漂移检测'}
          </button>
        </div>
      </Card>

      {/* 错误提示 */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* 检测结果 */}
      {result && (
        <Card>
          <h3 className="text-base font-semibold text-slate-800 mb-4">检测结果</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div className="p-3 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500">检测 ID</p>
              <p className="text-sm font-mono font-medium text-slate-700 truncate">{result.check_id}</p>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500">整体 PSI</p>
              <p className="text-lg font-bold text-slate-800">{result.psi_overall.toFixed(4)}</p>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500">漂移等级</p>
              <div className="mt-0.5"><DriftLevelBadge level={result.drift_level} /></div>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg">
              <p className="text-xs text-slate-500">告警状态</p>
              <p className={`text-sm font-medium ${result.alerted ? 'text-red-600' : 'text-emerald-600'}`}>
                {result.alerted ? '已触发' : '未触发'}
              </p>
            </div>
          </div>

          {/* 特征 PSI 详情 */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700">各特征 PSI：</p>
            {Object.entries(result.psi_features).map(([feat, psi]) => (
              <div key={feat} className="flex items-center justify-between py-1 border-b border-slate-100 last:border-0">
                <span className="text-sm text-slate-700">{feat}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${
                    psi < 0.1 ? 'text-emerald-600' : psi < 0.2 ? 'text-yellow-600' : psi < 0.25 ? 'text-orange-600' : 'text-red-600'
                  }`}>
                    {psi.toFixed(4)}
                  </span>
                  <DriftLevelBadge level={
                    psi < 0.1 ? 'none' : psi < 0.2 ? 'mild' : psi < 0.25 ? 'moderate' : 'severe'
                  } />
                </div>
              </div>
            ))}
          </div>

          {/* 警告 */}
          {result.warnings.length > 0 && (
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-sm text-amber-700 font-medium">⚠️ 警告</p>
              {result.warnings.map((w, i) => (
                <p key={i} className="text-sm text-amber-600 mt-1">{w}</p>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

function DriftAlertConfigContent() {
  const [name, setName] = useState('')
  const [threshold, setThreshold] = useState('0.2')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [modelId, setModelId] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const { data: alertList, refetch } = useQuery({
    queryKey: ['drift', 'alerts'],
    queryFn: () => driftApi.listAlerts({}),
    select: (res) => res.data,
  })

  const createAlert = async () => {
    if (!name || !webhookUrl) return
    setIsCreating(true)
    setError('')
    setSuccess('')
    try {
      await driftApi.createAlert({
        name,
        threshold: parseFloat(threshold),
        webhook_url: webhookUrl,
        model_id: modelId ? parseInt(modelId) : undefined,
      })
      setSuccess('告警规则创建成功！')
      setName('')
      setThreshold('0.2')
      setWebhookUrl('')
      setModelId('')
      refetch()
    } catch (e: any) {
      setError(e?.response?.data?.detail || '创建失败')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 创建告警规则 */}
      <Card>
        <h3 className="text-base font-semibold text-slate-800 mb-4">创建告警规则</h3>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">规则名称 *</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="如：PSI 0.2 告警" className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">PSI 阈值 *</label>
              <input type="number" step="0.01" value={threshold} onChange={e => setThreshold(e.target.value)} placeholder="0.2" className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">飞书 WebHook URL *</label>
            <input value={webhookUrl} onChange={e => setWebhookUrl(e.target.value)} placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..." className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">关联模型 ID（可选）</label>
            <input type="number" value={modelId} onChange={e => setModelId(e.target.value)} placeholder="留空为全局规则" className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
          </div>
          <button
            onClick={createAlert}
            disabled={!name || !webhookUrl || isCreating}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Bell className="w-4 h-4" />
            {isCreating ? '创建中...' : '创建告警规则'}
          </button>
        </div>
      </Card>

      {error && <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}
      {success && <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-700 text-sm">{success}</div>}

      {/* 告警规则列表 */}
      <Card>
        <h3 className="text-base font-semibold text-slate-800 mb-4">已有告警规则</h3>
        {!alertList?.alerts.length ? (
          <p className="text-sm text-slate-400 text-center py-6">暂无告警规则</p>
        ) : (
          <div className="space-y-3">
            {alertList.alerts.map(alert => (
              <div key={alert.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <div>
                  <p className="font-medium text-slate-800 text-sm">{alert.name}</p>
                  <p className="text-xs text-slate-500">
                    阈值: <span className="font-mono">{alert.threshold}</span> · 模型 ID: {alert.model_id ?? '全局'}
                  </p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${alert.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'}`}>
                  {alert.enabled ? '启用' : '禁用'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

// ============ 主组件 ============

export default function Monitor() {
  const [subTab, setSubTab] = useState<MonitorSubTab>('system')

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
            <Activity className="w-6 h-6" />
            {subTab === 'system' ? '系统监控' : '漂移检测'}
          </h1>
          <p className="text-slate-500 mt-1">
            {subTab === 'system'
              ? '实时监控服务器资源、GPU 状态、磁盘、网络和训练任务'
              : '监控模型推理数据分布偏移，PSI/KS 漂移检测与飞书告警'}
          </p>
        </div>
      </div>

      {/* 主 Tab 切换 */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setSubTab('system')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            subTab === 'system'
              ? 'bg-primary-50 text-primary-700'
              : 'text-slate-500 hover:bg-slate-100'
          }`}
        >
          <Cpu className="w-4 h-4" />
          系统监控
        </button>
        <button
          onClick={() => setSubTab('drift')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            subTab === 'drift'
              ? 'bg-primary-50 text-primary-700'
              : 'text-slate-500 hover:bg-slate-100'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          漂移检测
        </button>
      </div>

      {/* 内容区域 */}
      {subTab === 'system' && <SystemMonitorTab />}
      {subTab === 'drift' && <DriftDashboardTab />}
    </div>
  )
}
