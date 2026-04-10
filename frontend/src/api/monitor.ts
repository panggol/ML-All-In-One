/**
 * 系统监控 API
 * 提供前端与后端 /api/monitor/* 的对接
 */
import api from './client'

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
  getOverview: () => api.get<MonitorOverviewResponse>('/api/monitor/overview'),

  /**
   * 获取 CPU 详情
   */
  getCPU: () => api.get<CPUInfo>('/api/monitor/cpu'),

  /**
   * 获取内存详情
   */
  getMemory: () => api.get<MemoryInfo>('/api/monitor/memory'),

  /**
   * 获取 GPU 详情
   */
  getGPU: () => api.get<GPUInfo>('/api/monitor/gpu'),

  /**
   * 获取磁盘详情
   */
  getDisk: () => api.get<DiskInfo>('/api/monitor/disk'),

  /**
   * 获取网络详情
   */
  getNetwork: () => api.get<NetworkInfo>('/api/monitor/network'),

  /**
   * 获取训练任务统计
   */
  getJobs: () => api.get<JobStats>('/api/monitor/jobs'),

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
