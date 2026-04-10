/**
 * NetworkChart - 网络流量实时折线图（使用 recharts）
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export interface NetworkDataPoint {
  timestamp: string
  send_mbps: number
  recv_mbps: number
}

interface NetworkChartProps {
  data: NetworkDataPoint[]
  refreshInterval?: number
  height?: number
  loading?: boolean
  className?: string
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg shadow-md p-3 text-xs">
        <p className="text-slate-500 mb-1">{label ? formatTime(new Date(label)) : ''}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} style={{ color: entry.color }} className="font-medium">
            {entry.name}：{entry.value.toFixed(3)} MB/s
          </p>
        ))}
      </div>
    )
  }
  return null
}

export default function NetworkChart({
  data,
  refreshInterval = 5,
  height = 200,
  loading = false,
  className,
}: NetworkChartProps) {
  if (loading) {
    return (
      <div
        className={`bg-white rounded-xl shadow-card p-5 flex items-center justify-center ${className ?? ''}`}
        style={{ height }}
      >
        <div className="animate-pulse text-slate-400">加载中...</div>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div
        className={`bg-white rounded-xl shadow-card p-5 flex items-center justify-center ${className ?? ''}`}
        style={{ height }}
      >
        <span className="text-slate-400 text-sm">暂无网络数据</span>
      </div>
    )
  }

  return (
    <div className={`bg-white rounded-xl shadow-card p-5 ${className ?? ''}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-600">网络流量</span>
        <span className="text-xs text-slate-400">每 {refreshInterval}s 刷新</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(v: string) => {
              try {
                return formatTime(new Date(v))
              } catch {
                return ''
              }
            }}
            tick={{ fontSize: 11, fill: '#64748b' }}
            tickLine={false}
            axisLine={{ stroke: '#e2e8f0' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#64748b' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `${v} MB/s`}
            width={65}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            formatter={(value: string) => (value === 'send_mbps' ? '发送' : '接收')}
            iconType="line"
          />
          <Line
            type="monotone"
            dataKey="send_mbps"
            stroke="#06b6d4"
            strokeWidth={2}
            dot={false}
            name="发送"
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="recv_mbps"
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={false}
            name="接收"
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
