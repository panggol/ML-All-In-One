import { clsx } from 'clsx'

interface ProgressBarProps {
  value: number
  max?: number
  showLabel?: boolean
  size?: 'sm' | 'md'
  className?: string
}

export default function ProgressBar({
  value,
  max = 100,
  showLabel = true,
  size = 'md',
  className,
}: ProgressBarProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

  const sizeStyles = {
    sm: 'h-1',
    md: 'h-2',
  }

  return (
    <div className={clsx('w-full', className)}>
      {showLabel && (
        <div className="flex justify-between text-sm mb-2">
          <span className="text-slate-600">训练进度</span>
          <span className="font-medium text-primary-600">{percentage.toFixed(0)}%</span>
        </div>
      )}
      <div className={clsx('h-2 bg-slate-100 rounded-full overflow-hidden', sizeStyles[size])}>
        <div
          className="h-full bg-primary-500 rounded-full transition-all duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}
