import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ZAxis,
  Legend,
  Cell,
} from 'recharts'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface HistogramDatum {
  range: string
  count: number
  density?: number
}

export interface ScatterDatum {
  x: number
  y: number
  name?: string
  size?: number
  color?: string
}

export interface FeatureImportanceDatum {
  feature: string
  importance: number
  color?: string
}

// ─── Histogram ────────────────────────────────────────────────────────────────

interface HistogramChartProps {
  data: HistogramDatum[]
  loading?: boolean
  emptyText?: string
  color?: string
  height?: number
  showDensity?: boolean
}

export function HistogramChart({
  data,
  loading = false,
  emptyText = '暂无数据分布',
  color = '#6366f1',
  height = 300,
  showDensity = false,
}: HistogramChartProps) {
  if (loading) {
    return (
      <div className="w-full flex items-center justify-center" style={{ height }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-3 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
          <span className="text-sm text-slate-400">加载中…</span>
        </div>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="w-full flex items-center justify-center text-slate-400" style={{ height }}>
        <span className="text-sm">{emptyText}</span>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="range" tick={{ fontSize: 12, fill: '#64748b' }} />
        <YAxis tick={{ fontSize: 12, fill: '#64748b' }} />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            fontSize: 12,
          }}
        />
        <Bar
          dataKey={showDensity ? 'density' : 'count'}
          fill={color}
          opacity={0.85}
          radius={[4, 4, 0, 0]}
          name={showDensity ? '密度' : '频数'}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

// ─── Scatter Chart ────────────────────────────────────────────────────────────

interface ScatterChartComponentProps {
  data: ScatterDatum[]
  loading?: boolean
  emptyText?: string
  xLabel?: string
  yLabel?: string
  height?: number
  color?: string
}

export function ScatterChartComponent({
  data,
  loading = false,
  emptyText = '暂无散点数据',
  xLabel = 'X',
  yLabel = 'Y',
  height = 300,
  color = '#6366f1',
}: ScatterChartComponentProps) {
  if (loading) {
    return (
      <div className="w-full flex items-center justify-center" style={{ height }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-3 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
          <span className="text-sm text-slate-400">加载中…</span>
        </div>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="w-full flex items-center justify-center text-slate-400" style={{ height }}>
        <span className="text-sm">{emptyText}</span>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="x"
          name={xLabel}
          tick={{ fontSize: 12, fill: '#64748b' }}
          type="number"
        />
        <YAxis
          dataKey="y"
          name={yLabel}
          tick={{ fontSize: 12, fill: '#64748b' }}
          type="number"
        />
        <ZAxis dataKey="size" range={[30, 300]} />
        <Tooltip
          cursor={{ strokeDasharray: '3 3' }}
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            fontSize: 12,
          }}
          formatter={(value: number, name: string) => [value.toFixed(3), name]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Scatter
          name={`${xLabel} vs ${yLabel}`}
          data={data}
          fill={color}
          fillOpacity={0.7}
        />
      </ScatterChart>
    </ResponsiveContainer>
  )
}

// ─── Feature Importance Bar ───────────────────────────────────────────────────

interface FeatureImportanceChartProps {
  data: FeatureImportanceDatum[]
  loading?: boolean
  emptyText?: string
  color?: string
  height?: number
  topN?: number
}

const DEFAULT_COLORS = [
  '#6366f1', '#8b5cf6', '#a855f7', '#d946ef',
  '#ec4899', '#f43f5e', '#f97316', '#eab308',
]

export function FeatureImportanceChart({
  data,
  loading = false,
  emptyText = '暂无特征重要性数据',
  color,
  height = 300,
  topN,
}: FeatureImportanceChartProps) {
  if (loading) {
    return (
      <div className="w-full flex items-center justify-center" style={{ height }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-3 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
          <span className="text-sm text-slate-400">加载中…</span>
        </div>
      </div>
    )
  }

  const displayData = topN ? data.slice(0, topN) : data

  if (!displayData || displayData.length === 0) {
    return (
      <div className="w-full flex items-center justify-center text-slate-400" style={{ height }}>
        <span className="text-sm">{emptyText}</span>
      </div>
    )
  }

  const barColor = (index: number) =>
    color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length]

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={displayData}
        layout="vertical"
        margin={{ top: 4, right: 24, left: 80, bottom: 4 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} />
        <YAxis
          type="category"
          dataKey="feature"
          tick={{ fontSize: 12, fill: '#64748b' }}
          width={72}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            fontSize: 12,
          }}
          formatter={(value: number) => [value.toFixed(4), '重要性']}
        />
        <Bar
          dataKey="importance"
          radius={[0, 4, 4, 0]}
          name="重要性"
        >
          {displayData.map((_, index) => (
            <Cell key={index} fill={barColor(index)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
