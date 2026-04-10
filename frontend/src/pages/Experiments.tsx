import { useState, useEffect, useMemo } from 'react'
import { BarChart3, RotateCcw, CheckCircle2, XCircle, Clock, TrendingUp, ArrowLeft } from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Badge from '../components/Badge'
import { TrainingCurvesChart } from '../components/Charts'
import { experimentApi, vizApi } from '../api'
import type { TrainingCurvesResponse } from '../api'

interface Experiment {
  id: number
  name: string
  description?: string
  params: Record<string, any>
  metrics: Record<string, number>
  status: string
  created_at: string
  finished_at?: string
}

const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-3.5 h-3.5" />
    case 'failed':
      return <XCircle className="w-3.5 h-3.5" />
    case 'running':
    case 'pending':
      return <Clock className="w-3.5 h-3.5" />
    default:
      return null
  }
}

const StatusBadge = ({ status }: { status: string }) => {
  const variant = status === 'completed' ? 'success' : status === 'failed' ? 'error' : status === 'running' ? 'warning' : 'default'
  const label = status === 'completed' ? '完成' : status === 'failed' ? '失败' : status === 'running' ? '运行中' : status === 'pending' ? '等待中' : status
  return (
    <Badge variant={variant} icon={<StatusIcon status={status} />}>
      {label}
    </Badge>
  )
}

// ─── Comparison Curve Data

interface CompareCurvesData {
  experiments: Array<{
    experiment_id: number
    experiment_name: string
    color: string
    epochs: number[]
    curves: Array<{ name: string; values: number[] }>
  }>
}

async function loadCompareCurves(ids: number[]): Promise<CompareCurvesData | null> {
  return await experimentApi.compareCurves(ids)
}

// ─── CompareBar（底部浮动栏）────────────────────────────────────────────────

function CompareBar({
  count,
  onCompare,
  onCancel,
}: {
  count: number
  onCompare: () => void
  onCancel: () => void
}) {
  return (
    <div className="sticky bottom-4 mx-6 mb-4 z-30">
      <div className="bg-white border border-slate-200 rounded-xl shadow-lg h-14 flex items-center justify-between px-4">
        <span className="text-sm font-medium text-slate-700">
          已选择 <span className="text-indigo-600 font-bold">{count}</span> 个实验
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
          >
            取消选择
          </button>
          <button
            onClick={onCompare}
            disabled={count < 2}
            className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors ${
              count >= 2
                ? 'bg-indigo-600 hover:bg-indigo-700 cursor-pointer'
                : 'bg-slate-300 cursor-not-allowed'
            }`}
          >
            对比
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── 指标对比表（子 Tab 1）───────────────────────────────────────────────────

interface ComparisonTableProps {
  experiments: Experiment[]
  getColor: (index: number) => string
}

function ComparisonTable({ experiments, getColor }: ComparisonTableProps) {
  const metricCols = ['accuracy', 'f1', 'precision', 'recall'] as const
  const metricLabels: Record<string, string> = {
    accuracy: 'Accuracy',
    f1: 'F1',
    precision: 'Precision',
    recall: 'Recall',
  }

  // Cache best values per metric to avoid recalculating on every cell render
  const bestMetrics = useMemo(() => {
    const result: Record<string, number | null> = {}
    for (const col of metricCols) {
      const vals = experiments
        .map(e => e.metrics?.[col])
        .filter((v): v is number => typeof v === 'number')
      result[col] = vals.length ? Math.max(...vals) : null
    }
    return result
  }, [experiments])

  const format4 = (v: number | null | undefined) => {
    if (v === null || v === undefined) return <span className="text-slate-400">-</span>
    return v.toFixed(4)
  }

  const formatTrainTime = (exp: Experiment) => {
    if (!exp.finished_at) return <span className="text-slate-400">-</span>
    const diff = new Date(exp.finished_at).getTime() - new Date(exp.created_at).getTime()
    const seconds = Math.floor(diff / 1000)
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    if (mins < 60) return `${mins}m`
    const hours = Math.floor(mins / 60)
    const remainingMins = mins % 60
    return `${hours}h ${remainingMins}m`
  }

  const tableHeaderCols = ['实验名', '任务类型', '模型', '状态', ...metricCols.map(m => metricLabels[m]), '训练时间']

  return (
    <div className="max-h-96 overflow-y-auto border border-slate-200 rounded-lg">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-white z-10">
          <tr className="border-b border-slate-200">
            {tableHeaderCols.map(col => (
              <th
                key={col}
                className="px-3 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider text-left whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {experiments.map((exp, i) => (
            <tr key={exp.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              {/* 实验名 */}
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: getColor(i) }}
                  />
                  <span className="font-medium text-slate-800 text-sm max-w-36 truncate" title={exp.name}>
                    {exp.name}
                  </span>
                </div>
              </td>
              {/* 任务类型 */}
              <td className="px-3 py-2 text-slate-600 text-sm whitespace-nowrap">
                {exp.params?.task_type || '-'}
              </td>
              {/* 模型 */}
              <td className="px-3 py-2 text-slate-600 text-sm whitespace-nowrap">
                {exp.params?.model_name || '-'}
              </td>
              {/* 状态 */}
              <td className="px-3 py-2 whitespace-nowrap">
                <StatusBadge status={exp.status} />
              </td>
              {/* Accuracy */}
              {metricCols.map(col => {
                const val = exp.metrics?.[col] ?? null
                const best = bestMetrics[col]
                const isBest = val !== null && best !== null && val === best
                return (
                  <td key={col} className="px-3 py-2 text-center text-sm whitespace-nowrap">
                    {isBest ? (
                      <span className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-medium">
                        {format4(val)}
                      </span>
                    ) : (
                      <span className="text-slate-700">{format4(val)}</span>
                    )}
                  </td>
                )
              })}
              {/* 训练时间 */}
              <td className="px-3 py-2 text-slate-500 text-sm whitespace-nowrap">
                {formatTrainTime(exp)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── 曲线对比（子 Tab 2）────────────────────────────────────────────────────

interface ComparisonChartProps {
  selectedIds: string[]
}

function ComparisonChart({ selectedIds }: ComparisonChartProps) {
  const [RechartsComps, setRechartsComps] = useState<any>(null)
  const [chartData, setChartData] = useState<CompareCurvesData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chartMetric, setChartMetric] = useState<'accuracy' | 'loss' | 'f1'>('accuracy')
  const [hiddenLines, setHiddenLines] = useState<Set<string>>(new Set())

  useEffect(() => {
    import('recharts').then(mod => setRechartsComps(mod))
  }, [])

  useEffect(() => {
    if (selectedIds.length < 2) return
    setLoading(true)
    setError(null)
    setHiddenLines(new Set())
    loadCompareCurves(selectedIds.map(Number))
      .then(data => {
        setChartData(data)
        setLoading(false)
      })
      .catch(() => {
        setError('加载曲线数据失败，请稍后重试')
        setChartData(null)
        setLoading(false)
      })
  }, [selectedIds])

  if (!RechartsComps) {
    return <div className="h-80 flex items-center justify-center text-slate-400">加载图表...</div>
  }

  if (loading) {
    return <div className="h-80 flex items-center justify-center text-slate-400">加载中...</div>
  }

  if (error) {
    return (
      <div className="h-80 flex items-center justify-center text-red-500 bg-red-50 border border-red-200 rounded-lg">
        {error}
      </div>
    )
  }

  if (!chartData?.experiments?.length) {
    return (
      <div className="h-80 flex items-center justify-center text-slate-400">
        暂无曲线数据
      </div>
    )
  }

  const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = RechartsComps

  // Build chart data for selected metric
  const epochs = chartData.experiments[0]?.epochs ?? []
  const lines: Array<{ key: string; label: string; color: string; values: number[] }> = []

  for (const exp of chartData.experiments) {
    const metricCurves = exp.curves.filter(c => {
      const n = c.name.toLowerCase()
      if (chartMetric === 'accuracy' || chartMetric === 'f1') {
        return n.includes('acc') || n.includes('metric') || n.includes('f1')
      }
      return n.includes('loss')
    })

    for (const curve of metricCurves) {
      const label = `${exp.experiment_name} / ${curve.name}`
      lines.push({
        key: label,
        label,
        color: exp.color,
        values: curve.values,
      })
    }
  }

  if (!lines.length) {
    return (
      <div className="h-80 flex items-center justify-center text-slate-400">
        暂无该指标曲线数据
      </div>
    )
  }

  const data = epochs.map((epoch, i) => {
    const point: Record<string, number | string> = { epoch }
    lines.forEach(l => { point[l.key] = l.values[i] ?? NaN })
    return point
  })

  const handleLegendClick = (dataKey: string) => {
    setHiddenLines(prev => {
      const next = new Set(prev)
      if (next.has(dataKey)) next.delete(dataKey)
      else next.add(dataKey)
      return next
    })
  }

  return (
    <div>
      {/* 指标切换下拉框 */}
      <div className="mb-4 flex items-center gap-3">
        <span className="text-sm text-slate-600 font-medium">指标:</span>
        <select
          value={chartMetric}
          onChange={e => setChartMetric(e.target.value as 'accuracy' | 'loss' | 'f1')}
          className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="accuracy">Accuracy</option>
          <option value="loss">Loss</option>
          <option value="f1">F1</option>
        </select>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 4, right: 24, left: -12, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="epoch"
            tick={{ fontSize: 12, fill: '#64748b' }}
            label={{ value: 'Epoch', position: 'insideBottomRight', offset: -8, fontSize: 12, fill: '#64748b' }}
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
              name,
            ]}
            labelFormatter={(label: unknown) => `Epoch ${label}`}
          />
          <Legend
            wrapperStyle={{ fontSize: 11 }}
            onClick={(e: any) => handleLegendClick(e.dataKey)}
          />
          {lines.map(line => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              stroke={line.color}
              strokeWidth={2}
              dot={{ r: 3 }}
              hide={hiddenLines.has(line.key)}
              name={line.key}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* 曲线颜色说明 */}
      <div className="mt-3 flex flex-wrap gap-3">
        {chartData.experiments.map((exp) => (
          <div key={exp.experiment_id} className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: exp.color }}
            />
            <span className="text-xs text-slate-600 max-w-32 truncate" title={exp.experiment_name}>
              {exp.experiment_name}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Main Experiments Page ─────────────────────────────────────────────────────

export default function Experiments() {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedExp] = useState<number | null>(null)

  // 实验对比状态
  const [viewMode, setViewMode] = useState<'list' | 'compare'>('list')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [compareTab, setCompareTab] = useState<'table' | 'chart'>('table')

  // Training Curves state
  const [curveTab, setCurveTab] = useState<'all' | 'loss' | 'accuracy'>('all')
  const [curvesData, setCurvesData] = useState<TrainingCurvesResponse | null>(null)
  const [curvesLoading, setCurvesLoading] = useState(false)

  // 颜色分配逻辑
  const colorPalette = [
    '#6366F1', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6',
    '#EC4899', '#14B8A6', '#F97316', '#3B82F6', '#84CC16',
  ]
  const getColor = (index: number) => colorPalette[index % colorPalette.length]

  useEffect(() => {
    loadExperiments()
  }, [])

  const loadExperiments = async () => {
    setLoading(true)
    try {
      const data = await experimentApi.list()
      setExperiments(data)
    } catch {
      console.error('Failed to load experiments:')
    } finally {
      setLoading(false)
    }
  }

  // Load curves when single experiment selected
  useEffect(() => {
    if (!selectedExp) return
    setCurvesLoading(true)
    vizApi.getTrainingCurves(selectedExp)
      .then(data => { setCurvesData(data); setCurvesLoading(false) })
      .catch(() => { setCurvesData(null); setCurvesLoading(false) })
  }, [selectedExp])

  const filteredCurves = curvesData?.curves.filter(c => {
    if (curveTab === 'all') return true
    if (curveTab === 'loss') return c.name.toLowerCase().includes('loss')
    if (curveTab === 'accuracy') return c.name.toLowerCase().includes('acc') || c.name.toLowerCase().includes('metric')
    return true
  }) ?? []

  const selectedExperiment = experiments.find(e => e.id === selectedExp)

  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    if (hours < 1) return '刚刚'
    if (hours < 24) return hours + '小时前'
    const days = Math.floor(hours / 24)
    if (days < 7) return days + '天前'
    return date.toLocaleDateString('zh-CN')
  }

  // ── Checkbox 行切换 ──────────────────────────────────────────────────────
  const toggleSelect = (id: number) => {
    setSelectedIds(prev =>
      prev.includes(String(id))
        ? prev.filter(x => x !== String(id))
        : [...prev, String(id)]
    )
  }

  const handleCompare = () => {
    if (selectedIds.length < 2) {
      alert('请至少选择 2 个实验进行对比')
      return
    }
    setViewMode('compare')
  }

  const handleBack = () => {
    setViewMode('list')
  }

  const handleCancelSelect = () => {
    setSelectedIds([])
  }

  const selectedExperiments = experiments
    .filter(e => selectedIds.includes(String(e.id)))
    .sort((a, b) => (b.metrics?.accuracy ?? 0) - (a.metrics?.accuracy ?? 0))
  const showCompareBar = viewMode === 'list' && selectedIds.length > 0

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          {viewMode === 'compare' ? (
            <div className="flex items-center gap-3">
              <button
                onClick={handleBack}
                className="flex items-center gap-1.5 text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                返回
              </button>
              <h1 className="text-2xl font-semibold text-slate-900">实验对比</h1>
              <span className="text-sm text-slate-400 ml-2">
                {selectedExperiments.length} 个实验
              </span>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-semibold text-slate-900">实验记录</h1>
              <p className="text-slate-500 mt-1">追踪和对比所有训练实验</p>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {viewMode === 'list' && (
            <Button variant="secondary" onClick={loadExperiments}>
              <RotateCcw className="w-4 h-4" />
              刷新
            </Button>
          )}
        </div>
      </div>

      {/* ── 实验对比视图 ─────────────────────────────────────────────────── */}
      {viewMode === 'compare' && (
        <>
          {/* 子 Tab 切换 */}
          <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
            {(['table', 'chart'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setCompareTab(tab)}
                className={`px-4 py-2 text-sm rounded-lg transition-colors font-medium ${
                  compareTab === tab
                    ? 'bg-white shadow-sm text-slate-900'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {tab === 'table' ? '指标对比表' : '曲线对比'}
              </button>
            ))}
          </div>

          <Card>
            {compareTab === 'table' ? (
              <ComparisonTable experiments={selectedExperiments} getColor={getColor} />
            ) : (
              <ComparisonChart selectedIds={selectedIds} />
            )}
          </Card>
        </>
      )}

      {/* ── 实验列表视图 ─────────────────────────────────────────────────── */}
      {viewMode === 'list' && (
        <>
          {/* Training Curves Section */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-indigo-600" />
                <h2 className="text-lg font-semibold text-slate-900">训练曲线</h2>
                {selectedExp && (
                  <span className="text-sm text-slate-400 ml-2">
                    — {experiments.find(e => e.id === selectedExp)?.name ?? `实验 #${selectedExp}`}
                  </span>
                )}
              </div>
              <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
                {(['all', 'loss', 'accuracy'] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setCurveTab(tab)}
                    className={`px-3 py-1 text-sm rounded-md transition-colors ${
                      curveTab === tab ? 'bg-white shadow-sm text-slate-900 font-medium' : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {tab === 'all' ? '全部' : tab === 'loss' ? 'Loss' : 'Accuracy'}
                  </button>
                ))}
              </div>
            </div>

            {!selectedExp ? (
              <div className="flex items-center justify-center text-slate-400 py-12">
                <span className="text-sm">← 请先从下方选择一个实验查看训练曲线</span>
              </div>
            ) : (
              <TrainingCurvesChart
                data={{ epochs: curvesData?.epochs ?? [], curves: filteredCurves }}
                loading={curvesLoading}
                height={320}
              />
            )}

            {curvesData && filteredCurves.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-3 gap-4">
                {curvesData.curves.filter(c => c.name.toLowerCase().includes('loss')).map(curve => {
                  const lastVal = curve.values[curve.values.length - 1]
                  const bestVal = Math.min(...curve.values)
                  const label = curve.name.includes('val') ? 'Val Loss' : 'Train Loss'
                  return (
                    <div key={curve.name} className="text-center">
                      <p className="text-xs text-slate-400 mb-1">{label}</p>
                      <p className="text-xl font-semibold text-slate-900">{typeof lastVal === 'number' ? lastVal.toFixed(4) : '-'}</p>
                      <p className="text-xs text-slate-400">最佳: {bestVal.toFixed(4)}</p>
                    </div>
                  )
                })}
                {curvesData.curves.filter(c => !c.name.toLowerCase().includes('loss')).map(curve => {
                  const lastVal = curve.values[curve.values.length - 1]
                  const bestVal = Math.max(...curve.values)
                  const label = curve.name.includes('val') ? 'Val Acc' : 'Train Acc'
                  return (
                    <div key={curve.name} className="text-center">
                      <p className="text-xs text-slate-400 mb-1">{label}</p>
                      <p className="text-xl font-semibold text-slate-900">{typeof lastVal === 'number' ? lastVal.toFixed(4) : '-'}</p>
                      <p className="text-xs text-slate-400">最佳: {bestVal.toFixed(4)}</p>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          {/* Experiments List with Checkbox */}
          <Card className="p-0">
            {loading ? (
              <div className="p-8 text-center text-slate-500">加载中...</div>
            ) : experiments.length === 0 ? (
              <div className="p-8 text-center text-slate-500">暂无实验记录</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50">
                      {/* CheckboxColumn */}
                      <th className="text-left py-3 px-4 w-10">
                        {selectedIds.length > 0 && (
                          <input
                            type="checkbox"
                            checked={selectedIds.length > 0 && selectedIds.length === experiments.length}
                            ref={input => {
                              if (input) input.indeterminate = selectedIds.length > 0 && selectedIds.length < experiments.length
                            }}
                            onChange={() => {
                              if (selectedIds.length === experiments.length) {
                                setSelectedIds([])
                              } else {
                                setSelectedIds(experiments.map(e => String(e.id)))
                              }
                            }}
                            className="w-4 h-4 rounded border-slate-300 text-indigo-600"
                          />
                        )}
                      </th>
                      <th className="text-left py-3 px-4 font-semibold text-slate-900">实验名称</th>
                      <th className="text-left py-3 px-4 font-semibold text-slate-900">状态</th>
                      <th className="text-left py-3 px-4 font-semibold text-slate-900">准确率</th>
                      <th className="text-left py-3 px-4 font-semibold text-slate-900">F1分数</th>
                      <th className="text-left py-3 px-4 font-semibold text-slate-900">创建时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {experiments.map(exp => {
                      const isSelected = selectedIds.includes(String(exp.id))
                      return (
                        <tr
                          key={exp.id}
                          onClick={() => {
                            // 如果点了 checkbox 区域，不重复触发
                            toggleSelect(exp.id)
                          }}
                          className={`border-b border-slate-100 last:border-0 cursor-pointer transition-colors hover:bg-slate-50 ${
                            selectedExp === exp.id ? 'bg-primary-50' : ''
                          } ${isSelected ? 'bg-indigo-50' : ''}`}
                        >
                          {/* CheckboxColumn - 40px */}
                          <td className="py-4 px-4 w-10" onClick={e => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelect(exp.id)}
                              className="w-4 h-4 rounded border-slate-300 text-indigo-600"
                            />
                          </td>
                          <td className="py-4 px-4">
                            <div className="flex items-center gap-3">
                              <BarChart3 className="w-5 h-5 text-slate-400" />
                              <span className="font-medium text-slate-900">{exp.name}</span>
                            </div>
                          </td>
                          <td className="py-4 px-4">
                            <StatusBadge status={exp.status} />
                          </td>
                          <td className="py-4 px-4">
                            {exp.metrics?.accuracy !== undefined ? (
                              <span className="font-medium text-primary-600">{(exp.metrics.accuracy * 100).toFixed(1)}%</span>
                            ) : (
                              <span className="text-slate-400">-</span>
                            )}
                          </td>
                          <td className="py-4 px-4">
                            {exp.metrics?.f1 !== undefined ? (
                              <span className="font-medium text-slate-700">{(exp.metrics.f1 * 100).toFixed(1)}%</span>
                            ) : (
                              <span className="text-slate-400">-</span>
                            )}
                          </td>
                          <td className="py-4 px-4 text-slate-500 text-sm">
                            {formatTime(exp.created_at)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* Detail Panel */}
          {selectedExperiment && (
            <Card>
              <h2 className="text-lg font-semibold text-slate-900 mb-4">实验详情</h2>
              <div className="bg-slate-50 rounded-lg p-4 font-mono text-sm">
                <div>名称: {selectedExperiment.name}</div>
                <div>描述: {selectedExperiment.description || '无'}</div>
                <div>状态: {selectedExperiment.status}</div>
                <div>创建时间: {selectedExperiment.created_at}</div>
                {selectedExperiment.finished_at && (
                  <div>完成时间: {selectedExperiment.finished_at}</div>
                )}
                <div>参数: {JSON.stringify(selectedExperiment.params, null, 2)}</div>
                <div>指标: {JSON.stringify(selectedExperiment.metrics, null, 2)}</div>
              </div>
            </Card>
          )}
        </>
      )}

      {/* CompareBar 底部浮动栏 */}
      {showCompareBar && (
        <CompareBar
          count={selectedIds.length}
          onCompare={handleCompare}
          onCancel={handleCancelSelect}
        />
      )}
    </div>
  )
}
