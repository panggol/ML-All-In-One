/**
 * UsageProgressBar - 带阈值语义色的进度条
 * 阈值定义于 constants/monitor.ts
 */
import { clsx } from 'clsx'
import {
  THRESHOLD_YELLOW_MAX,
  getUsageBarColor,
  getUsageGradient,
} from '../../constants/monitor'

interface UsageProgressBarProps {
  value: number
  max?: number
  label?: string
  showLabel?: boolean
  format?: {
    unit?: string
    decimals?: number
    showValue?: boolean // 显示 "used / total" 格式
  }
  colorStrategy?: 'auto' | 'fixed'
  fixedColor?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export default function UsageProgressBar({
  value = 0,
  max = 100,
  label,
  showLabel = true,
  format,
  colorStrategy = 'auto',
  fixedColor,
  size = 'md',
  className,
}: UsageProgressBarProps) {
  const percent = Math.min(Math.max((value / max) * 100, 0), 100)
  const decimals = format?.decimals ?? 1

  const sizeStyles = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  }

  const barColor = fixedColor
    ? fixedColor
    : colorStrategy === 'auto'
    ? getUsageBarColor(percent)
    : 'bg-primary-500'

  const gradientClass = colorStrategy === 'auto' ? getUsageGradient(percent) : ''

  // 显示绝对值
  const valueText = format?.showValue
    ? `${value.toFixed(decimals)} / ${max.toFixed(decimals)}${format.unit ? ' ' + format.unit : ''}`
    : `${percent.toFixed(decimals)}%`

  return (
    <div className={clsx('w-full', className)}>
      {(showLabel || label) && (
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-slate-600">{label}</span>
          <span className="text-sm font-medium text-slate-700">{valueText}</span>
        </div>
      )}
      <div className={clsx('w-full bg-slate-100 rounded-full overflow-hidden', sizeStyles[size])}>
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-500',
            barColor,
            gradientClass && `bg-gradient-to-r ${gradientClass}`
          )}
          style={{ width: `${percent}%` }}
        />
      </div>
      {/* 危险状态脉冲效果 */}
      {percent >= THRESHOLD_YELLOW_MAX && (
        <div className="absolute inset-0 rounded-full animate-pulse bg-red-500/5 pointer-events-none" />
      )}
    </div>
  )
}
