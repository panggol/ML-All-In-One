/**
 * MetricCard - 顶部指标大卡片（CPU/内存/GPU/磁盘）
 * 阈值定义于 constants/monitor.ts
 */
import { clsx } from 'clsx'
import { LucideIcon } from 'lucide-react'
import UsageProgressBar from './UsageProgressBar'
import { getUsageColorClass } from '../../constants/monitor'

interface MetricCardProps {
  title: string
  value: number
  total?: number
  used?: number
  format?: {
    unit?: string
    decimals?: number
    showAbsolute?: boolean
  }
  icon: LucideIcon
  colorScheme?: 'auto' | 'emerald' | 'amber' | 'red' | 'sky' | 'violet'
  subInfo?: string
  size?: 'sm' | 'md'
  loading?: boolean
  className?: string
}

const COLOR_SCHEME_MAP: Record<string, string> = {
  sky: 'text-sky-500',
  violet: 'text-violet-500',
  emerald: 'text-emerald-500',
  amber: 'text-amber-500',
  red: 'text-red-500',
}

function getColorClass(scheme: MetricCardProps['colorScheme'], percent: number): string {
  if (scheme === 'auto') {
    return getUsageColorClass(percent)
  }
  return COLOR_SCHEME_MAP[scheme ?? ''] || 'text-slate-700'
}

export default function MetricCard({
  title,
  value,
  total,
  used,
  format,
  icon: Icon,
  colorScheme = 'auto',
  subInfo,
  size = 'md',
  loading = false,
  className,
}: MetricCardProps) {
  const percent = total ? Math.min((value / total) * 100, 100) : value
  const decimals = format?.decimals ?? 1

  if (loading) {
    return (
      <div className={clsx('bg-white rounded-xl shadow-card p-5', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-slate-200 rounded w-1/2" />
          <div className="h-8 bg-slate-200 rounded w-3/4" />
          <div className="h-2 bg-slate-200 rounded w-full" />
        </div>
      </div>
    )
  }

  const displayValue = total
    ? `${value.toFixed(decimals)}${format?.unit ? ' ' + format.unit : ''}`
    : `${value.toFixed(decimals)}${format?.unit ?? '%'}`

  const absoluteText = total && used !== undefined
    ? `${used.toFixed(decimals)} / ${total.toFixed(decimals)}${format?.unit ? ' ' + format.unit : ''}`
    : subInfo

  return (
    <div className={clsx('bg-white rounded-xl shadow-card p-5 flex flex-col gap-3', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{title}</span>
        <Icon className={clsx('w-5 h-5', getColorClass(colorScheme, percent))} />
      </div>

      {/* Value */}
      <div className={clsx('font-bold leading-none', size === 'sm' ? 'text-2xl' : 'text-3xl', getColorClass(colorScheme, percent))}>
        {displayValue}
      </div>

      {/* Progress Bar */}
      <UsageProgressBar
        value={value}
        max={total ?? 100}
        format={{ ...format, showValue: false }}
        colorStrategy="auto"
        size="sm"
      />

      {/* Sub Info / Absolute */}
      {absoluteText && (
        <span className="text-xs text-slate-400">{absoluteText}</span>
      )}
    </div>
  )
}
