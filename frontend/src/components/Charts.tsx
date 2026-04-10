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
  LineChart,
  Line,
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

// ─── Training Curves Line Chart ───────────────────────────────────────────────

interface TrainingCurvesChartProps {
  data: {
    epochs: number[];
    curves: Array<{ name: string; values: number[] }>;
  };
  loading?: boolean;
  height?: number;
  showGrid?: boolean;
}

const CURVE_COLORS: Record<string, string> = {
  train_loss: '#6366f1',
  val_loss: '#f59e0b',
  train_accuracy: '#10b981',
  val_accuracy: '#ec4899',
  train_metric: '#6366f1',
  val_metric: '#f59e0b',
  loss: '#6366f1',
  accuracy: '#10b981',
}

const CURVE_STYLES: Record<string, { dash?: string; name: string }> = {
  train_loss: { name: 'Train Loss' },
  val_loss: { name: 'Val Loss', dash: '4 4' },
  train_accuracy: { name: 'Train Accuracy' },
  val_accuracy: { name: 'Val Accuracy', dash: '4 4' },
  train_metric: { name: 'Train Metric' },
  val_metric: { name: 'Val Metric', dash: '4 4' },
  loss: { name: 'Loss' },
  accuracy: { name: 'Accuracy' },
}

const METRIC_LABELS: Record<string, string> = {
  train_loss: 'Train Loss', val_loss: 'Val Loss',
  train_accuracy: 'Train Acc', val_accuracy: 'Val Acc',
  train_metric: 'Train Metric', val_metric: 'Val Metric',
  loss: 'Loss', accuracy: 'Accuracy',
}

export function TrainingCurvesChart({
  data,
  loading = false,
  height = 320,
  showGrid = true,
}: TrainingCurvesChartProps) {
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

  if (!data?.curves || data.curves.length === 0) {
    return (
      <div className="w-full flex items-center justify-center text-slate-400" style={{ height }}>
        <span className="text-sm">暂无训练曲线数据</span>
      </div>
    )
  }

  // 转换数据格式为 Recharts LineChart
  const chartData = data.epochs.map((epoch, i) => {
    const point: Record<string, number> = { epoch }
    data.curves.forEach((curve) => {
      point[curve.name] = curve.values[i] ?? NaN
    })
    return point
  })

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 4, right: 24, left: -12, bottom: 0 }}>
        {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />}
        <XAxis
          dataKey="epoch"
          tick={{ fontSize: 12, fill: '#64748b' }}
          label={{ value: 'Epoch', position: 'insideBottomRight', offset: -4, fontSize: 12, fill: '#64748b' }}
        />
        <YAxis tick={{ fontSize: 12, fill: '#64748b' }} />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            fontSize: 12,
          }}
          formatter={(value: number, name: string) => [
            typeof value === 'number' && !isNaN(value) ? value.toFixed(4) : value,
            METRIC_LABELS[name] ?? name,
          ]}
          labelFormatter={(label) => `Epoch ${label}`}
        />
        <Legend
          formatter={(value) => METRIC_LABELS[value] ?? value}
          wrapperStyle={{ fontSize: 12 }}
        />
        {data.curves.map((curve) => {
          const style = CURVE_STYLES[curve.name] ?? { name: curve.name }
          const color = CURVE_COLORS[curve.name] ?? '#6366f1'
          return (
            <Line
              key={curve.name}
              type="monotone"
              dataKey={curve.name}
              stroke={color}
              strokeWidth={2}
              strokeDasharray={style.dash ?? '0'}
              dot={false}
              name={curve.name}
              connectNulls
            />
          )
        })}
      </LineChart>
    </ResponsiveContainer>
  )
}
