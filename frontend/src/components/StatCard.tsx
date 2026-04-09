import { clsx } from 'clsx'
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  color?: 'primary' | 'emerald' | 'amber' | 'violet'
}

const colorStyles = {
  primary: { bg: 'bg-primary-50', text: 'text-primary-600' },
  emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600' },
  amber: { bg: 'bg-amber-50', text: 'text-amber-600' },
  violet: { bg: 'bg-violet-50', text: 'text-violet-600' },
}

export default function StatCard({ label, value, icon: Icon, color = 'primary' }: StatCardProps) {
  const styles = colorStyles[color]

  return (
    <div className="bg-white rounded-xl shadow-card p-6 hover:shadow-soft transition-all duration-200">
      <div className="flex items-center gap-4">
        <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center', styles.bg)}>
          <Icon className={clsx('w-6 h-6', styles.text)} />
        </div>
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="text-2xl font-semibold text-slate-900">{value}</p>
        </div>
      </div>
    </div>
  )
}
