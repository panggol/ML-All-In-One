/**
 * DiskTable - 磁盘挂载点表格
 */
import { clsx } from 'clsx'
import UsageProgressBar from './UsageProgressBar'
import type { DiskPartition } from '../../api/monitor'

interface DiskTableProps {
  partitions: DiskPartition[]
  loading?: boolean
  emptyText?: string
  className?: string
}

export default function DiskTable({
  partitions,
  loading = false,
  emptyText = '暂无磁盘信息',
  className,
}: DiskTableProps) {
  if (loading) {
    return (
      <div className={clsx('bg-white rounded-xl shadow-card p-5', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-slate-200 rounded w-1/3" />
          <div className="h-3 bg-slate-200 rounded w-full" />
          <div className="h-3 bg-slate-200 rounded w-full" />
        </div>
      </div>
    )
  }

  if (!partitions || partitions.length === 0) {
    return (
      <div className={clsx('bg-white rounded-xl shadow-card p-5 text-center text-slate-500', className)}>
        {emptyText}
      </div>
    )
  }

  return (
    <div className={clsx('bg-white rounded-xl shadow-card overflow-hidden', className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-100">
            <th className="text-left px-4 py-3 font-medium text-slate-600">挂载点</th>
            <th className="text-right px-4 py-3 font-medium text-slate-600">总容量</th>
            <th className="text-right px-4 py-3 font-medium text-slate-600">已用</th>
            <th className="text-right px-4 py-3 font-medium text-slate-600">剩余</th>
            <th className="text-center px-4 py-3 font-medium text-slate-600">使用率</th>
          </tr>
        </thead>
        <tbody>
          {partitions.map((part, idx) => (
            <tr
              key={part.mountpoint}
              className={clsx(
                'border-b border-slate-50 last:border-b-0 hover:bg-slate-50 transition-colors',
                idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/30'
              )}
            >
              <td className="px-4 py-3 font-mono text-slate-700 text-xs">{part.mountpoint}</td>
              <td className="px-4 py-3 text-right text-slate-600">{part.total_gb.toFixed(1)} GB</td>
              <td className="px-4 py-3 text-right text-slate-600">{part.used_gb.toFixed(1)} GB</td>
              <td className="px-4 py-3 text-right text-slate-600">{part.free_gb.toFixed(1)} GB</td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <UsageProgressBar
                      value={part.usage_percent}
                      max={100}
                      showLabel={false}
                      colorStrategy="auto"
                      size="sm"
                    />
                  </div>
                  <span className={clsx(
                    'text-xs font-medium w-10 text-right',
                    part.usage_percent >= 85 ? 'text-red-500' :
                    part.usage_percent >= 60 ? 'text-amber-500' : 'text-emerald-600'
                  )}>
                    {part.usage_percent.toFixed(1)}%
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
