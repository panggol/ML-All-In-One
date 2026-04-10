/**
 * GPUDeviceCard - 单块 GPU 详情卡片
 * 阈值定义于 constants/monitor.ts
 */
import { clsx } from 'clsx'
import { Thermometer, Cpu } from 'lucide-react'
import UsageProgressBar from './UsageProgressBar'
import type { GPUDevice } from '../../api/monitor'
import {
  GPU_TEMP_NORMAL_MAX,
  GPU_TEMP_WARNING_MAX,
  getGpuTempColor,
  getGpuUtilColor,
} from '../../constants/monitor'

interface GPUDeviceCardProps {
  device: GPUDevice
  size?: 'sm' | 'md'
  loading?: boolean
  className?: string
}

function getTempLabel(temp: number | null): string {
  if (temp === null) return 'N/A'
  if (temp >= GPU_TEMP_WARNING_MAX) return '过热'
  if (temp >= GPU_TEMP_NORMAL_MAX) return '偏高'
  return '正常'
}

export default function GPUDeviceCard({
  device,
  className,
}: GPUDeviceCardProps) {
  const memPercent = device.memory_usage_percent ?? 0
  const utilPercent = device.utilization_percent ?? 0
  const temp = device.temperature_celsius

  return (
    <div className={clsx('bg-white rounded-xl shadow-card p-5 flex flex-col gap-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-800">{device.name}</h3>
          <span className="text-xs text-slate-400">GPU {device.index}</span>
        </div>
        <div className="text-right">
          <div className={clsx('text-sm font-medium', getGpuTempColor(temp ?? 0))}>
            {temp !== null ? `${temp}°C` : 'N/A'}
          </div>
          <div className="text-xs text-slate-400">{getTempLabel(temp)}</div>
        </div>
      </div>

      {/* Memory */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-violet-400 inline-block" />
            显存
          </span>
          <span className="font-medium text-slate-700">
            {device.memory_used_gb.toFixed(1)} / {device.memory_total_gb.toFixed(1)} GB
          </span>
        </div>
        <UsageProgressBar
          value={memPercent}
          max={100}
          colorStrategy="auto"
          size="md"
        />
        <div className="flex justify-end">
          <span className="text-xs text-slate-400">{memPercent.toFixed(1)}%</span>
        </div>
      </div>

      {/* Utilization */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600 flex items-center gap-1">
            <Cpu className="w-3 h-3" />
            利用率
          </span>
          <span className="font-medium text-slate-700">{utilPercent}%</span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
          <div
            className={clsx('h-full rounded-full transition-all duration-500', getGpuUtilColor(utilPercent))}
            style={{ width: `${utilPercent}%` }}
          />
        </div>
      </div>

      {/* Temperature */}
      {temp !== null && (
        <div className="flex items-center gap-2 text-sm">
          <Thermometer className={clsx('w-4 h-4', getGpuTempColor(temp))} />
          <span className="text-slate-600">温度</span>
          <span className={clsx('font-medium ml-auto', getGpuTempColor(temp))}>
            {temp}°C <span className="text-xs text-slate-400">({getTempLabel(temp)})</span>
          </span>
        </div>
      )}

      {/* Free memory */}
      <div className="text-xs text-slate-400">
        剩余显存：{device.memory_free_gb.toFixed(1)} GB
      </div>
    </div>
  )
}
