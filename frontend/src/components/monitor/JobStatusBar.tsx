/**
 * JobStatusBar - 训练任务状态统计条
 */
import { clsx } from 'clsx'
import { Play, Clock, CheckCircle, XCircle } from 'lucide-react'
import type { JobStats } from '../../api/monitor'

interface JobStatusBarProps {
  stats: JobStats
  expandable?: boolean
  defaultExpanded?: boolean
  loading?: boolean
  className?: string
}

interface MiniBarProps {
  value: number
  max?: number
  color: string
  label: string
  icon: React.ElementType
  count: number
}

function MiniBar({ value, max = 10, color, label, icon: Icon, count }: MiniBarProps) {
  const dots = Math.min(Math.ceil((value / Math.max(max, 1)) * 8), 8)
  return (
    <div className="flex items-center gap-3">
      <Icon className={clsx('w-4 h-4', color)} />
      <span className="text-sm text-slate-600 w-12">{label}</span>
      <div className="flex gap-0.5">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className={clsx(
              'w-3 h-3 rounded-sm transition-colors',
              i < dots ? color.replace('text-', 'bg-') : 'bg-slate-100'
            )}
          />
        ))}
      </div>
      <span className="text-sm font-medium text-slate-700 ml-1">{count}</span>
    </div>
  )
}

export default function JobStatusBar({
  stats,
  expandable: _expandable = false,
  defaultExpanded: _defaultExpanded = false,
  loading = false,
  className,
}: JobStatusBarProps) {
  const total = stats.running + stats.pending + stats.completed + stats.failed
  const maxValue = Math.max(stats.running, stats.pending, stats.completed, stats.failed, 1)

  if (loading) {
    return (
      <div className={clsx('bg-white rounded-xl shadow-card p-5', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-slate-200 rounded w-1/3" />
          <div className="h-3 bg-slate-200 rounded w-full" />
        </div>
      </div>
    )
  }

  return (
    <div className={clsx('bg-white rounded-xl shadow-card p-5 flex flex-col gap-4', className)}>
      <div className="flex items-center justify-between">
        <span className="text-base font-semibold text-slate-800">训练任务状态</span>
        <span className="text-sm text-slate-400">共 {total} 个任务</span>
      </div>

      <div className="space-y-3">
        <MiniBar
          value={stats.running}
          max={maxValue}
          color="text-emerald-500"
          label="运行中"
          icon={Play}
          count={stats.running}
        />
        <MiniBar
          value={stats.pending}
          max={maxValue}
          color="text-amber-500"
          label="队列中"
          icon={Clock}
          count={stats.pending}
        />
        <MiniBar
          value={stats.completed}
          max={maxValue}
          color="text-sky-500"
          label="已完成"
          icon={CheckCircle}
          count={stats.completed}
        />
        <MiniBar
          value={stats.failed}
          max={maxValue}
          color="text-red-500"
          label="失败"
          icon={XCircle}
          count={stats.failed}
        />
      </div>

      {/* Summary */}
      {stats.running > 0 && (
        <div className="pt-2 border-t border-slate-100">
          <span className="text-xs text-emerald-600 font-medium">
            ● {stats.running} 个任务正在运行中
          </span>
        </div>
      )}
    </div>
  )
}
