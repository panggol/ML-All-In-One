import { clsx } from 'clsx'
import type { ReactNode } from 'react'

type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'default'

interface BadgeProps {
  variant?: BadgeVariant
  children: ReactNode
  icon?: ReactNode
  className?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  success: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-700',
  error: 'bg-red-50 text-red-700',
  info: 'bg-primary-50 text-primary-700',
  default: 'bg-slate-100 text-slate-700',
}

export default function Badge({ variant = 'default', children, icon, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium',
        variantStyles[variant],
        className
      )}
    >
      {icon}
      {children}
    </span>
  )
}
