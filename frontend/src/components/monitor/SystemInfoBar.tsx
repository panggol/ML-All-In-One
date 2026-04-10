/**
 * SystemInfoBar - 系统基本信息栏
 */
import { clsx } from 'clsx'
import { Server, Clock, Monitor } from 'lucide-react'
import type { SystemInfo } from '../../api/monitor'

interface SystemInfoBarProps {
  info: SystemInfo
  loading?: boolean
  className?: string
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  return `${days}天 ${hours}h`
}

export default function SystemInfoBar({
  info,
  loading = false,
  className,
}: SystemInfoBarProps) {
  if (loading) {
    return (
      <div className={clsx('bg-white rounded-xl shadow-card p-5', className)}>
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-slate-200 rounded w-2/3" />
          <div className="h-3 bg-slate-200 rounded w-1/2" />
        </div>
      </div>
    )
  }

  return (
    <div className={clsx('bg-white rounded-xl shadow-card p-5', className)}>
      <div className="flex items-center justify-between">
        <span className="text-base font-semibold text-slate-800">系统信息</span>
        <Monitor className="w-5 h-5 text-slate-400" />
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-slate-400" />
          <span className="text-slate-500">主机名：</span>
          <span className="font-medium text-slate-700">{info.hostname || 'N/A'}</span>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-slate-400" />
          <span className="text-slate-500">运行时间：</span>
          <span className="font-medium text-slate-700">{formatUptime(info.uptime_seconds)}</span>
        </div>
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-slate-400" />
          <span className="text-slate-500">系统：</span>
          <span className="font-medium text-slate-700">
            {info.os_type || 'N/A'}
            {info.os_version ? ` · ${info.os_version}` : ''}
          </span>
        </div>
      </div>
    </div>
  )
}
