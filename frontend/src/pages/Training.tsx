import { useState, useEffect, useMemo, useRef } from 'react'
import { Upload, Play, Pause, FileSpreadsheet, Sparkles, Check, Trash2, Terminal, AlertTriangle, X, ExternalLink, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Select from '../components/Select'
import Input from '../components/Input'
import ProgressBar from '../components/ProgressBar'
import { dataApi, trainApi, TrainJob, TrainStatus, MetricsCurve } from '../api'

// ─── Constants ────────────────────────────────────────────────────────────────

const CLASSIFIER_MODELS = [
  { value: 'RandomForestClassifier', label: 'RandomForest' },
  { value: 'XGBClassifier', label: 'XGBoost' },
  { value: 'LGBMClassifier', label: 'LightGBM' },
  { value: 'LogisticRegression', label: 'LogisticRegression' },
]

const REGRESSOR_MODELS = [
  { value: 'RandomForestRegressor', label: 'RandomForest' },
  { value: 'XGBRegressor', label: 'XGBoost' },
  { value: 'LGBMRegressor', label: 'LightGBM' },
]

const TASK_OPTIONS = [
  { value: 'classification', label: '分类' },
  { value: 'regression', label: '回归' },
]

const AUTO_FEATURE_METHODS = [
  { value: 'variance_threshold', label: '方差阈值' },
  { value: 'correlation', label: '相关系数' },
  { value: 'tree_importance', label: '树模型重要性' },
]

const MAX_LOG_LINES = 500
const FEATURE_GROUP_SIZE = 20

// ─── Types ────────────────────────────────────────────────────────────────────

type TrainingPhase = 'idle' | 'configuring' | 'running' | 'completed' | 'failed' | 'stopped'

interface FeatureGroup {
  label: string
  columns: string[]
}

// ─── Feature Column Grouping ─────────────────────────────────────────────────

function buildFeatureGroups(columns: string[]): FeatureGroup[] {
  if (columns.length === 0) return []
  if (columns.length <= FEATURE_GROUP_SIZE) return [{ label: '全部', columns }]

  const sorted = [...columns].sort()
  const groups: FeatureGroup[] = []
  let i = 0

  while (i < sorted.length) {
    const start = i
    const groupColumns: string[] = []
    for (let j = 0; j < FEATURE_GROUP_SIZE && i < sorted.length; j++, i++) {
      groupColumns.push(sorted[i])
    }
    const firstChar = sorted[start][0].toUpperCase()
    const lastChar = sorted[i - 1] ? sorted[i - 1][0].toUpperCase() : firstChar
    groups.push({
      label: firstChar === lastChar ? firstChar : `${firstChar}-${lastChar}`,
      columns: groupColumns,
    })
  }

  return groups
}

// ─── Custom AlertDialog (no radix-ui dependency) ────────────────────────────

function AlertDialog({
  open,
  title,
  description,
  confirmLabel = '确认',
  cancelLabel = '取消',
  destructive = false,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="alert-title"
      aria-describedby="alert-desc"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onCancel}
      />
      {/* Dialog */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 animate-in zoom-in-95 duration-150">
        <div className="flex items-start gap-4">
          <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${destructive ? 'bg-red-100' : 'bg-indigo-100'}`}>
            <AlertTriangle className={`w-5 h-5 ${destructive ? 'text-red-600' : 'text-indigo-600'}`} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 id="alert-title" className="text-lg font-semibold text-slate-900">{title}</h3>
            <p id="alert-desc" className="mt-2 text-sm text-slate-600 leading-relaxed">{description}</p>
          </div>
          <button
            onClick={onCancel}
            className="flex-shrink-0 p-1 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="关闭"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? 'stop' : 'primary'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── LogPanel ────────────────────────────────────────────────────────────────

interface LogPanelProps {
  logs: string[]
  onClear: () => void
}

function LogPanel({ logs, onClear }: LogPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const isUserScrolling = useRef(false)

  // Determine log level from content
  const getLogClass = (line: string) => {
    const lower = line.toLowerCase()
    if (lower.includes('[error]') || lower.includes('error:') || lower.includes('failed') || lower.includes('exception')) return 'text-red-600'
    if (lower.includes('[warn]') || lower.includes('warning') || lower.includes('warn:')) return 'text-amber-600'
    return 'text-slate-700'
  }

  // Format timestamp for display
  const formatLine = (line: string) => {
    // If line already has a timestamp, show as-is
    if (/^\[\d{2}:\d{2}:\d{2}\]/.test(line)) return line
    return line
  }

  useEffect(() => {
    if (!autoScroll || isUserScrolling.current) return
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs, autoScroll])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32
    isUserScrolling.current = !atBottom
    if (atBottom) setAutoScroll(true)
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-slate-900 border-t border-slate-700 shadow-2xl flex flex-col"
      style={{ maxHeight: '220px' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-300">训练日志</span>
          <span className="text-xs text-slate-500">{logs.length} 行</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(v => !v)}
            className={`text-xs px-2 py-1 rounded transition-colors ${autoScroll ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            title="自动滚动"
          >
            自动滚动
          </button>
          <button
            onClick={onClear}
            className="p-1.5 rounded hover:bg-slate-700 transition-colors"
            title="清空日志"
          >
            <Trash2 className="w-4 h-4 text-slate-400 hover:text-slate-200" />
          </button>
        </div>
      </div>

      {/* Log content */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-2 font-mono text-xs leading-6"
        role="log"
        aria-live="polite"
        aria-label="训练日志"
      >
        {logs.length === 0 ? (
          <p className="text-slate-500 italic">等待日志输出...</p>
        ) : (
          logs.map((line, i) => (
            <p key={i} className={`whitespace-pre-wrap break-all ${getLogClass(line)}`}>
              {formatLine(line)}
            </p>
          ))
        )}
      </div>
    </div>
  )
}

// ─── TrainingCurves (extracted sub-component) ────────────────────────────────

interface TrainingCurvesProps {
  metrics_curve: MetricsCurve
  taskType: 'classification' | 'regression'
  isAnimationActive?: boolean
}

function TrainingCurves({ metrics_curve, taskType, isAnimationActive = false }: TrainingCurvesProps) {
  const [activeMetric, setActiveMetric] = useState<'loss' | 'accuracy'>(
    taskType === 'regression' ? 'loss' : 'accuracy'
  )
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set())

  useEffect(() => {
    setActiveMetric(taskType === 'regression' ? 'loss' : 'accuracy')
  }, [taskType])

  const chartData = useMemo(() => {
    return metrics_curve.epochs.map((epoch, i) => ({
      epoch,
      train: activeMetric === 'loss'
        ? metrics_curve.train_loss[i]
        : metrics_curve.train_accuracy[i],
      val: activeMetric === 'loss'
        ? metrics_curve.val_loss[i]
        : metrics_curve.val_accuracy[i],
    }))
  }, [metrics_curve, activeMetric])

  const toggleSeries = (key: string) => {
    setHiddenSeries(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const [RechartsComps, setRechartsComps] = useState<any>(null)
  useEffect(() => {
    import('recharts').then(mod => setRechartsComps(mod))
  }, [])

  if (!RechartsComps) return null

  const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = RechartsComps
  const metricLabel = activeMetric === 'loss' ? 'Loss' : 'Accuracy'
  const formatter = (v: any) => typeof v === 'number' ? v.toFixed(4) : v

  return (
    <div className="mt-4">
      {/* Tab */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setActiveMetric('loss')}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            activeMetric === 'loss'
              ? 'bg-indigo-600 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
          aria-pressed={activeMetric === 'loss'}
        >
          Loss
        </button>
        <button
          onClick={() => setActiveMetric('accuracy')}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            activeMetric === 'accuracy'
              ? 'bg-indigo-600 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
          aria-pressed={activeMetric === 'accuracy'}
        >
          Accuracy
        </button>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={256}>
        <LineChart data={chartData} margin={{ top: 4, right: 24, left: -12, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="epoch" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={{ stroke: '#e2e8f0' }} tickLine={false} />
          <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={{ stroke: '#e2e8f0' }} tickLine={false} />
          <Tooltip formatter={formatter} contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }} labelStyle={{ color: '#334155', fontWeight: 500 }} />
          <Legend wrapperStyle={{ fontSize: 13, color: '#64748b', paddingTop: 8 }} iconType="plainline" onClick={(e: any) => toggleSeries(e.dataKey)} />
          <Line type="monotone" dataKey="train" name={`Train ${metricLabel}`} stroke={hiddenSeries.has('train') ? '#cbd5e1' : '#6366F1'} strokeWidth={2} dot={{ r: 3 }} connectNulls={true} isAnimationActive={isAnimationActive} hide={hiddenSeries.has('train')} />
          <Line type="monotone" dataKey="val" name={`Val ${metricLabel}`} stroke={hiddenSeries.has('val') ? '#cbd5e1' : '#F59E0B'} strokeWidth={2} dot={{ r: 3 }} connectNulls={true} isAnimationActive={isAnimationActive} hide={hiddenSeries.has('val')} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── TrainingResultBanner ───────────────────────────────────────────────────

interface TrainingResultBannerProps {
  status: 'completed' | 'failed' | 'stopped'
  job: TrainJob
  errorMessage?: string
  onViewReport: () => void
  onRetrain: () => void
}

function TrainingResultBanner({ status, job, errorMessage, onViewReport, onRetrain }: TrainingResultBannerProps) {
  const isSuccess = status === 'completed'
  const isStopped = status === 'stopped'

  const accuracy = job.metrics?.accuracy
  const loss = job.metrics?.loss
  const mse = job.metrics?.mse
  const mae = job.metrics?.mae
  const r2 = job.metrics?.r2

  return (
    <Card
      className={`border-2 ${isSuccess ? 'border-emerald-300 bg-emerald-50' : isStopped ? 'border-amber-300 bg-amber-50' : 'border-red-300 bg-red-50'}`}
    >
      <div className="flex items-start gap-4">
        {/* Badge */}
        <div className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center text-2xl ${
          isSuccess ? 'bg-emerald-100' : isStopped ? 'bg-amber-100' : 'bg-red-100'
        }`}>
          {isSuccess ? '✅' : isStopped ? '⏸' : '❌'}
        </div>

        <div className="flex-1 min-w-0">
          <h3 className={`text-lg font-semibold ${isSuccess ? 'text-emerald-800' : isStopped ? 'text-amber-800' : 'text-red-800'}`}>
            {isSuccess ? '训练完成' : isStopped ? '训练已停止' : '训练失败'}
          </h3>

          {/* Error message for failed status */}
          {status === 'failed' && errorMessage && (
            <p className="mt-1 text-sm text-red-700 bg-red-100 rounded-lg px-3 py-2 inline-block">
              <strong>错误：</strong>{errorMessage}
            </p>
          )}

          {/* Metrics */}
          {isSuccess && (
            <div className="mt-3 flex flex-wrap gap-4">
              {accuracy != null && (
                <div className="text-center">
                  <p className="text-2xl font-bold text-emerald-700">{accuracy >= 1 ? accuracy.toFixed(4) : `${(accuracy * 100).toFixed(1)}%`}</p>
                  <p className="text-xs text-emerald-600">准确率</p>
                </div>
              )}
              {loss != null && (
                <div className="text-center">
                  <p className="text-2xl font-bold text-emerald-700">{loss.toFixed(4)}</p>
                  <p className="text-xs text-emerald-600">Loss</p>
                </div>
              )}
              {mse != null && (
                <div className="text-center">
                  <p className="text-2xl font-bold text-emerald-700">{mse.toFixed(4)}</p>
                  <p className="text-xs text-emerald-600">MSE</p>
                </div>
              )}
              {mae != null && (
                <div className="text-center">
                  <p className="text-2xl font-bold text-emerald-700">{mae.toFixed(4)}</p>
                  <p className="text-xs text-emerald-600">MAE</p>
                </div>
              )}
              {r2 != null && (
                <div className="text-center">
                  <p className="text-2xl font-bold text-emerald-700">{r2.toFixed(4)}</p>
                  <p className="text-xs text-emerald-600">R²</p>
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="mt-4 flex flex-wrap gap-3">
            {isSuccess && (
              <Button variant="primary" onClick={onViewReport} aria-label="查看完整报告">
                <ExternalLink className="w-4 h-4" />
                查看完整报告
              </Button>
            )}
            <Button variant="secondary" onClick={onRetrain} aria-label="重新配置">
              <RefreshCw className="w-4 h-4" />
              重新配置
            </Button>
          </div>
        </div>
      </div>
    </Card>
  )
}

// ─── FeatureSelectCard (inline, grouped) ──────────────────────────────────────

interface FeatureSelectCardProps {
  allColumns: string[]
  targetColumn: string
  selectedFeatures: string[]
  autoSelectedFeatures: string[]
  autoSelectApplied: boolean
  isAutoSelecting: boolean
  autoSelectMethod: string
  isDisabled?: boolean
  onFeatureToggle: (col: string) => void
  onSelectAll: () => void
  onDeselectAll: () => void
  onAutoSelect: () => void
  onApplyAuto: () => void
  onAutoMethodChange: (method: string) => void
}

function FeatureSelectCard({
  allColumns,
  targetColumn,
  selectedFeatures,
  autoSelectedFeatures,
  autoSelectApplied,
  isAutoSelecting,
  autoSelectMethod,
  isDisabled = false,
  onFeatureToggle,
  onSelectAll,
  onDeselectAll,
  onAutoSelect,
  onApplyAuto,
  onAutoMethodChange,
}: FeatureSelectCardProps) {
  const featureColumns = allColumns.filter(c => c !== targetColumn)
  const groups = buildFeatureGroups(featureColumns)
  const useGrouping = groups.length > 1
  const [activeGroupIndex, setActiveGroupIndex] = useState(0)

  const displayFeatures = useGrouping
    ? groups[activeGroupIndex]?.columns ?? []
    : featureColumns

  const displaySelected = autoSelectApplied ? autoSelectedFeatures : selectedFeatures

  const handleToggle = (col: string) => {
    if (autoSelectApplied || isDisabled) return
    onFeatureToggle(col)
  }

  const canApplyAuto = autoSelectedFeatures.length > 0 && !autoSelectApplied

  return (
    <div className="space-y-4">
      {/* Auto-select toolbar */}
      <div className="flex flex-wrap items-center gap-3 pb-4 border-b border-slate-100">
        <Select
          label="自动选择"
          options={AUTO_FEATURE_METHODS}
          value={autoSelectMethod}
          onChange={e => onAutoMethodChange(e.target.value)}
          disabled={isDisabled}
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={onAutoSelect}
          disabled={isAutoSelecting || isDisabled}
          aria-label="开始自动特征选择"
        >
          <Sparkles className="w-4 h-4" />
          {isAutoSelecting ? '选择中...' : '自动选择'}
        </Button>

        {canApplyAuto && (
          <Button variant="primary" size="sm" onClick={onApplyAuto} aria-label={`应用自动选择结果 (${autoSelectedFeatures.length} 列)`}>
            <Check className="w-4 h-4" />
            应用 ({autoSelectedFeatures.length} 列)
          </Button>
        )}

        {autoSelectApplied && (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-emerald-100 text-emerald-700 rounded-full">
            <Sparkles className="w-3 h-3" />
            已应用自动选择 ({autoSelectedFeatures.length} 列)
          </span>
        )}
      </div>

      {/* Manual selection controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <span>手动选择：</span>
          <button
            onClick={onSelectAll}
            disabled={isDisabled}
            className="text-primary-600 hover:text-primary-700 disabled:text-slate-300 disabled:cursor-not-allowed font-medium"
          >
            全选
          </button>
          <span className="text-slate-300">|</span>
          <button
            onClick={onDeselectAll}
            disabled={isDisabled}
            className="text-slate-500 hover:text-slate-700 disabled:text-slate-300 disabled:cursor-not-allowed"
          >
            取消全选
          </button>
        </div>
        <span className="text-sm text-slate-500 font-medium">
          已选 {displaySelected.length}/{featureColumns.length} 列
        </span>
      </div>

      {/* Feature grouping tabs (>20 columns) */}
      {useGrouping && (
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-thin pb-1" role="tablist" aria-label="特征分组">
          {groups.map((group, i) => (
            <button
              key={group.label}
              role="tab"
              aria-selected={i === activeGroupIndex}
              onClick={() => setActiveGroupIndex(i)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                i === activeGroupIndex
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {group.label} <span className="opacity-70">({group.columns.length})</span>
            </button>
          ))}
        </div>
      )}

      {/* Feature grid */}
      {isAutoSelecting ? (
        <div className="flex items-center justify-center py-12 bg-slate-50 rounded-lg">
          <div className="flex items-center gap-2 text-slate-500">
            <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">正在分析特征...</span>
          </div>
        </div>
      ) : (
        <div
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 max-h-56 overflow-y-auto pr-1"
          role="group"
          aria-label="特征列列表"
        >
          {displayFeatures.map(col => {
            const isSelected = displaySelected.includes(col)
            const wasAutoSelected = autoSelectApplied && autoSelectedFeatures.includes(col)

            return (
              <button
                key={col}
                role="checkbox"
                aria-checked={isSelected}
                onClick={() => handleToggle(col)}
                disabled={autoSelectApplied || isDisabled}
                className={`text-left px-3 py-2 rounded-lg text-sm transition-all disabled:cursor-default ${
                  isSelected
                    ? wasAutoSelected
                      ? 'bg-emerald-50 border border-emerald-300 text-emerald-700'
                      : 'bg-primary-50 border border-primary-300 text-primary-700'
                    : 'bg-slate-50 border border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <div className="flex items-center gap-2">
                  <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                    isSelected
                      ? wasAutoSelected
                        ? 'bg-emerald-500 border-emerald-500'
                        : 'bg-primary-500 border-primary-500'
                      : 'border-slate-300'
                  }`}>
                    {isSelected && (
                      <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  <span className="truncate">{col}</span>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {displaySelected.length === 0 && !isAutoSelecting && (
        <p className="text-sm text-amber-600 flex items-center gap-1">
          <AlertTriangle className="w-4 h-4" />
          请至少选择一个特征列
        </p>
      )}
    </div>
  )
}

// ─── Main Training Page ──────────────────────────────────────────────────────

export default function Training() {
  const navigate = useNavigate()

  // ── Core State ──────────────────────────────────────────────────────────
  const [files, setFiles] = useState<any[]>([])
  const [selectedFile, setSelectedFile] = useState<number | null>(null)
  const [taskType, setTaskType] = useState<'classification' | 'regression'>('classification')
  const [targetColumn, setTargetColumn] = useState('')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [currentJob, setCurrentJob] = useState<TrainJob | null>(null)
  const [trainingPhase, setTrainingPhase] = useState<TrainingPhase>('idle')
  const [errorMessage, setErrorMessage] = useState<string>('')
  const [startError, setStartError] = useState<string>('')
  const [uploadError, setUploadError] = useState<string>('')

  // ── Feature State ──────────────────────────────────────────────────────
  const [allColumns, setAllColumns] = useState<string[]>([])
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])
  const [autoSelectMethod, setAutoSelectMethod] = useState('tree_importance')
  const [autoSelectedFeatures, setAutoSelectedFeatures] = useState<string[]>([])
  const [isAutoSelecting, setIsAutoSelecting] = useState(false)
  const [autoSelectApplied, setAutoSelectApplied] = useState(false)

  // ── Training Progress State ────────────────────────────────────────────
  const [progress, setProgress] = useState(0)
  const [currentMetrics, setCurrentMetrics] = useState<{ accuracy?: number; loss?: number; mse?: number; mae?: number; r2?: number }>({})
  const [metricsCurve, setMetricsCurve] = useState<MetricsCurve | null>(null)
  const [showCurves, setShowCurves] = useState(false)
  const [logLines, setLogLines] = useState<string[]>([])

  // ── UI State ───────────────────────────────────────────────────────────
  const [showStopConfirm, setShowStopConfirm] = useState(false)
  const [isStopping, setIsStopping] = useState(false)

  // ── Derived ─────────────────────────────────────────────────────────────
  const isTraining = trainingPhase === 'running'
  const currentModelOptions = taskType === 'regression' ? REGRESSOR_MODELS : CLASSIFIER_MODELS
  const finalFeatures = (autoSelectApplied && autoSelectedFeatures.length > 0)
    ? autoSelectedFeatures
    : selectedFeatures

  const canStartTraining = Boolean(
    selectedFile && targetColumn && selectedModel && finalFeatures.length > 0
  )

  const selectedFileData = files.find(f => f.id === selectedFile)

  // ── Load files on mount ─────────────────────────────────────────────────
  useEffect(() => {
    loadFiles()
    // Restore session
    const savedJobId = sessionStorage.getItem('activeTrainingJobId')
    if (savedJobId) {
      const jobId = parseInt(savedJobId, 10)
      if (!isNaN(jobId)) {
        setCurrentJob({ id: jobId } as TrainJob)
        setTrainingPhase('running')
        sessionStorage.removeItem('activeTrainingJobId')
      }
    }
  }, [])

  // ── Polling ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!currentJob || trainingPhase !== 'running') return

    const interval = setInterval(async () => {
      try {
        const status: TrainStatus = await trainApi.getStatus(currentJob.id)

        // Update progress
        setProgress(status.progress)

        // Update current metrics from status
        setCurrentMetrics({
          accuracy: status.accuracy,
          loss: status.loss,
        })

        // Update logs (append new content)
        if (status.logs) {
          const existingCount = logLines.length
          const newContent = status.logs
          // Simple append: if new content has more than existing, add the delta
          // We use a simple approach: split by newline and take the last MAX_LOG_LINES
          const allLines = newContent.split('\n').filter(Boolean)
          const trimmed = allLines.slice(-MAX_LOG_LINES)
          if (trimmed.length > existingCount || allLines.length <= existingCount) {
            setLogLines(trimmed)
          }
        }

        // Update curves — start showing as soon as we have data
        if (status.metrics_curve && status.metrics_curve.epochs.length > 0) {
          setMetricsCurve(status.metrics_curve)
          setShowCurves(true)
        }

        // Handle terminal states
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'stopped') {
          clearInterval(interval)
          setTrainingPhase(status.status as TrainingPhase)
          sessionStorage.removeItem('activeTrainingJobId')

          if (status.status === 'completed' && status.metrics_curve) {
            setMetricsCurve(status.metrics_curve)
            setShowCurves(true)
          }

          // Pull final metrics from status
          if (status.status === 'completed') {
            setCurrentMetrics(prev => ({
              ...prev,
              accuracy: status.accuracy,
              loss: status.loss,
            }))
          }

          // Pull error from status if failed
          if (status.status === 'failed' && status.logs) {
            const lines = status.logs.split('\n').filter(Boolean)
            const errorLine = lines.filter(l => l.toLowerCase().includes('error') || l.toLowerCase().includes('failed')).pop() || ''
            setErrorMessage(errorLine || '训练过程发生未知错误')
          }

          // Update currentJob status
          setCurrentJob(prev => prev ? { ...prev, status: status.status as TrainJob['status'] } : null)
        }
      } catch (err: any) {
        console.error('Failed to get training status:', err)
        // Log the error in the log panel
        const msg = err?.response?.data?.error?.message || err?.response?.data?.message || err?.message || '网络连接异常，请检查网络后重试'
        setLogLines(prev => {
          const next = [...prev, `[${new Date().toLocaleTimeString()}] [ERROR] ${msg}`]
          return next.slice(-MAX_LOG_LINES)
        })
        // Critical 1: If job no longer exists on server (404), stop polling and mark as failed
        if (err?.response?.status === 404) {
          clearInterval(interval)
          setTrainingPhase('failed')
          setErrorMessage('训练任务不存在或已过期，请重新开始训练')
          sessionStorage.removeItem('activeTrainingJobId')
        }
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [currentJob, trainingPhase])

  // ── Model list reset on task type change ───────────────────────────────
  useEffect(() => {
    if (selectedModel && !currentModelOptions.find(m => m.value === selectedModel)) {
      setSelectedModel(null)
    }
  }, [taskType])

  // ── Feature reset on target column change ───────────────────────────────
  useEffect(() => {
    if (targetColumn && allColumns.length > 0) {
      const features = allColumns.filter(col => col !== targetColumn)
      setSelectedFeatures(features)
      setAutoSelectedFeatures([])
      setAutoSelectApplied(false)
    }
  }, [targetColumn, allColumns])

  // ── File loading ─────────────────────────────────────────────────────────
  const loadFiles = async () => {
    try {
      const fileList = await dataApi.list()
      setFiles(fileList)
    } catch (err) {
      console.error('Failed to load files:', err)
    }
  }

  const loadFileColumns = async (fileId: number) => {
    try {
      const stats = await dataApi.stats(fileId)
      setAllColumns(stats.columns || [])
    } catch (err) {
      console.error('Failed to load file columns:', err)
    }
  }

  useEffect(() => {
    if (selectedFile) loadFileColumns(selectedFile)
  }, [selectedFile])

  // ── File upload ─────────────────────────────────────────────────────────
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError('')

    try {
      const uploadedFile = await dataApi.upload(file)
      setFiles(prev => [uploadedFile, ...prev])
      setSelectedFile(uploadedFile.id)

      const stats = await dataApi.stats(uploadedFile.id)
      if (stats.columns?.length > 0) {
        setAllColumns(stats.columns)
        setTargetColumn(stats.columns[stats.columns.length - 1])
      }
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.message || err?.message || '文件上传失败'
      setUploadError(msg)
    }
  }

  // ── Feature selection ────────────────────────────────────────────────────
  const handleFeatureToggle = (col: string) => {
    if (autoSelectApplied) {
      setAutoSelectApplied(false)
      setAutoSelectedFeatures([])
    }
    setSelectedFeatures(prev =>
      prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
    )
  }

  const handleSelectAll = () => {
    setAutoSelectApplied(false)
    setAutoSelectedFeatures([])
    setSelectedFeatures(allColumns.filter(col => col !== targetColumn))
  }

  const handleDeselectAll = () => {
    setAutoSelectApplied(false)
    setAutoSelectedFeatures([])
    setSelectedFeatures([])
  }

  const handleAutoSelect = async () => {
    if (!selectedFile || !targetColumn) return
    setIsAutoSelecting(true)
    setStartError('')

    try {
      const result = await dataApi.featureSelection(selectedFile, {
        target_column: targetColumn,
        method: autoSelectMethod,
      })
      setAutoSelectedFeatures(result.selected_features || [])
      setAutoSelectApplied(true)
    } catch (err: any) {
      // Fallback: simple variance-based selection
      const features = allColumns.filter(col => col !== targetColumn)
      const selected = features.slice(0, Math.max(1, Math.floor(features.length * 0.7)))
      setAutoSelectedFeatures(selected)
      setAutoSelectApplied(true)
      setLogLines(prev => [...prev, `[INFO] 自动特征选择模拟完成，选择 ${selected.length} 列`].slice(-MAX_LOG_LINES))
    } finally {
      setIsAutoSelecting(false)
    }
  }

  const handleApplyAutoSelection = () => {
    if (autoSelectedFeatures.length > 0) {
      setSelectedFeatures(autoSelectedFeatures)
      setAutoSelectApplied(false)
    }
  }

  // ── Training ─────────────────────────────────────────────────────────────
  const handleStartTraining = async () => {
    if (!canStartTraining) return
    setStartError('')
    setErrorMessage('')

    const featuresToUse = (autoSelectApplied && autoSelectedFeatures.length > 0)
      ? autoSelectedFeatures
      : selectedFeatures

    try {
      const job = await trainApi.create({
        data_file_id: selectedFile!,
        target_column: targetColumn,
        task_type: taskType,
        model_type: 'sklearn',
        model_name: selectedModel!,
        feature_columns: featuresToUse,
      })

      setCurrentJob(job)
      setTrainingPhase('running')
      setProgress(0)
      setMetricsCurve(null)
      setShowCurves(false)
      setLogLines([])
      setCurrentMetrics({})

      sessionStorage.setItem('activeTrainingJobId', String(job.id))
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.message || err?.message || '启动训练失败'
      setStartError(msg)
      setTrainingPhase('failed')
      setErrorMessage(msg)
    }
  }

  const handleStopTrainingConfirm = () => {
    setShowStopConfirm(true)
  }

  const handleStopTrainingExecute = async () => {
    if (!currentJob) return
    setShowStopConfirm(false)
    setIsStopping(true)

    try {
      await trainApi.stop(currentJob.id)
      setTrainingPhase('stopped')
      sessionStorage.removeItem('activeTrainingJobId')
      setLogLines(prev => [...prev, `[INFO] 训练已停止`].slice(-MAX_LOG_LINES))
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.message || err?.message || '停止训练失败'
      setLogLines(prev => [...prev, `[ERROR] ${msg}`].slice(-MAX_LOG_LINES))
      // Warning 3: Only close Dialog on success; on failure keep Dialog open via showStopConfirm
      // Note: we already called setShowStopConfirm(false) above, but want to re-show it on error
      // Since the Dialog auto-closes on confirm click, re-show it with an error state
      setShowStopConfirm(true)
    } finally {
      setIsStopping(false)
    }
  }

  // ── Navigation ───────────────────────────────────────────────────────────
  const handleViewReport = () => {
    if (currentJob) navigate(`/results/${currentJob.id}`)
  }

  const handleRetrain = () => {
    setTrainingPhase('idle')
    setCurrentJob(null)
    setProgress(0)
    setMetricsCurve(null)
    setShowCurves(false)
    setLogLines([])
    setCurrentMetrics({})
    setErrorMessage('')
    setStartError('')
    setAutoSelectApplied(false)
    setAutoSelectedFeatures([])
    setSelectedFeatures([])
    sessionStorage.removeItem('activeTrainingJobId')
  }

  // ── Disable config during training ───────────────────────────────────────
  const configDisabled = isTraining

  // ──────────────────────────────────────────────────────────────────────
  // RENDER
  // ──────────────────────────────────────────────────────────────────────
  return (
    <div className={`space-y-6 ${isTraining || trainingPhase === 'completed' || trainingPhase === 'failed' || trainingPhase === 'stopped' ? 'pb-56' : ''}`}>

      {/* ── Page Header ────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">模型训练</h1>
          <p className="text-sm text-slate-500 mt-1">上传数据，配置模型，开始训练</p>
        </div>
      </div>

      {/* ── Config Section ─────────────────────────────────────────────── */}
      {trainingPhase === 'idle' || trainingPhase === 'configuring' ? (
        <div className="space-y-6">

          {/* Data Source */}
          <Card>
            <h2 className="text-base font-semibold text-slate-900 mb-4">数据来源</h2>

            {/* Upload zone */}
            <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-primary-300 transition-colors">
              <input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="hidden"
                id="file-upload"
                disabled={configDisabled}
              />
              <label htmlFor="file-upload" className="cursor-pointer block">
                <Upload className="w-10 h-10 text-slate-400 mx-auto mb-3" />
                <p className="font-medium text-slate-900">拖拽文件或点击上传</p>
                <p className="text-sm text-slate-500 mt-1">支持 CSV 格式</p>
              </label>
            </div>

            {uploadError && (
              <p className="mt-2 text-sm text-red-600 flex items-center gap-1" role="alert">
                <AlertTriangle className="w-4 h-4" />
                {uploadError}
              </p>
            )}

            {/* Selected file badge */}
            {selectedFileData && (
              <div className="mt-4 flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                <FileSpreadsheet className="w-6 h-6 text-primary-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-900 truncate">{selectedFileData.filename}</p>
                  <p className="text-xs text-slate-500">
                    {selectedFileData.rows} 行 · {allColumns.length} 列
                  </p>
                </div>
                <button
                  onClick={() => {
                    setSelectedFile(null)
                    setAllColumns([])
                    setTargetColumn('')
                    setSelectedFeatures([])
                  }}
                  className="p-1 rounded hover:bg-slate-200 transition-colors"
                  aria-label="取消选择"
                >
                  <X className="w-4 h-4 text-slate-400" />
                </button>
              </div>
            )}

            {/* Existing files */}
            {!selectedFile && files.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-sm text-slate-500 font-medium">或选择已有文件</p>
                {files.map(file => (
                  <div
                    key={file.id}
                    onClick={() => setSelectedFile(file.id)}
                    className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 hover:bg-slate-100 cursor-pointer transition-colors"
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && setSelectedFile(file.id)}
                    aria-label={`选择文件 ${file.filename}`}
                  >
                    <FileSpreadsheet className="w-5 h-5 text-slate-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-900 truncate">{file.filename}</p>
                      <p className="text-xs text-slate-500">{file.rows} 行</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Required params */}
          {selectedFile && (
            <Card>
              <h2 className="text-base font-semibold text-slate-900 mb-4">任务配置</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <Select
                  label="任务类型"
                  options={TASK_OPTIONS}
                  value={taskType}
                  onChange={e => setTaskType(e.target.value as typeof taskType)}
                  disabled={configDisabled}
                />
                <Input
                  label="目标列"
                  value={targetColumn}
                  onChange={e => setTargetColumn(e.target.value)}
                  placeholder="输入目标列名"
                  disabled={configDisabled}
                  list="target-column-suggestions"
                />
                {allColumns.length > 0 && (
                  <datalist id="target-column-suggestions">
                    {allColumns.map(col => <option key={col} value={col} />)}
                  </datalist>
                )}
              </div>

              {/* Feature selection — inline, second group */}
              {allColumns.length > 0 && targetColumn && (
                <div className="mb-6 pt-4 border-t border-slate-100">
                  <div className="flex items-center gap-2 mb-4">
                    <Sparkles className="w-4 h-4 text-primary-600" />
                    <h3 className="text-sm font-semibold text-slate-900">特征选择</h3>
                    {autoSelectApplied && (
                      <span className="px-2 py-0.5 text-xs bg-emerald-100 text-emerald-700 rounded">
                        自动选择
                      </span>
                    )}
                  </div>
                  <FeatureSelectCard
                    allColumns={allColumns}
                    targetColumn={targetColumn}
                    selectedFeatures={selectedFeatures}
                    autoSelectedFeatures={autoSelectedFeatures}
                    autoSelectApplied={autoSelectApplied}
                    isAutoSelecting={isAutoSelecting}
                    autoSelectMethod={autoSelectMethod}
                    isDisabled={configDisabled}
                    onFeatureToggle={handleFeatureToggle}
                    onSelectAll={handleSelectAll}
                    onDeselectAll={handleDeselectAll}
                    onAutoSelect={handleAutoSelect}
                    onApplyAuto={handleApplyAutoSelection}
                    onAutoMethodChange={setAutoSelectMethod}
                  />
                </div>
              )}

              {/* Model selection */}
              <div>
                <p className="block text-sm font-medium text-slate-700 mb-3">选择模型</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {currentModelOptions.map(model => (
                    <button
                      key={model.value}
                      onClick={() => setSelectedModel(model.value)}
                      disabled={configDisabled}
                      className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                        selectedModel === model.value
                          ? 'border-primary-500 bg-primary-50 text-primary-700 ring-2 ring-primary-200'
                          : 'border-slate-200 hover:border-primary-300 hover:bg-slate-50 text-slate-700'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                      aria-pressed={selectedModel === model.value}
                    >
                      {model.label}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      ) : null}

      {/* ── Training Progress Card ────────────────────────────────────── */}
      {(isTraining || trainingPhase === 'completed' || trainingPhase === 'failed' || trainingPhase === 'stopped') && (
        <>
          {/* Progress card (show while running) */}
          {isTraining && (
            <Card>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-slate-900">训练进度</h2>
                <span className="text-sm text-slate-500 font-mono">{progress}%</span>
              </div>

              <div
                className="mb-6"
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`训练进度 ${progress}%`}
              >
                <ProgressBar value={progress} />
              </div>

              {/* Live metrics */}
              <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100">
                <div className="text-center">
                  <p className="text-2xl font-semibold text-slate-900">{selectedModel?.split(/(?=[A-Z])/)[0] ?? '—'}</p>
                  <p className="text-xs text-slate-500">模型</p>
                </div>
                {taskType === 'regression' ? (
                  <>
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-primary-600">
                        {currentMetrics.mse != null ? currentMetrics.mse.toFixed(4) : '—'}
                      </p>
                      <p className="text-xs text-slate-500">MSE</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-primary-600">
                        {currentMetrics.mae != null ? currentMetrics.mae.toFixed(4) : '—'}
                      </p>
                      <p className="text-xs text-slate-500">MAE</p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-primary-600">
                        {currentMetrics.accuracy != null
                          ? `${(currentMetrics.accuracy >= 1 ? currentMetrics.accuracy : currentMetrics.accuracy * 100).toFixed(1)}%`
                          : '—'}
                      </p>
                      <p className="text-xs text-slate-500">准确率</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-slate-600">
                        {currentMetrics.loss != null ? currentMetrics.loss.toFixed(4) : '—'}
                      </p>
                      <p className="text-xs text-slate-500">Loss</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-indigo-600">{progress}%</p>
                      <p className="text-xs text-slate-500">进度</p>
                    </div>
                  </>
                )}
              </div>
            </Card>
          )}

          {/* Training Curves — show when data available (even during training) */}
          {(showCurves && metricsCurve) && (
            <Card>
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-base font-semibold text-slate-900">📈 训练曲线</h2>
                {isTraining && (
                  <span className="text-xs text-primary-600 flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
                    实时更新中
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mb-2">
                Epochs: {metricsCurve.epochs.length} | 状态: {trainingPhase}
              </p>
              <TrainingCurves
                metrics_curve={metricsCurve}
                taskType={taskType}
                isAnimationActive={false}
              />
            </Card>
          )}

          {/* Training Result Banner */}
          {(trainingPhase === 'completed' || trainingPhase === 'failed' || trainingPhase === 'stopped') && currentJob && (
            <TrainingResultBanner
              status={trainingPhase}
              job={{ ...currentJob, metrics: currentMetrics, status: trainingPhase } as TrainJob}
              errorMessage={errorMessage}
              onViewReport={handleViewReport}
              onRetrain={handleRetrain}
            />
          )}
        </>
      )}

      {/* ── Action Bar (always visible, fixed height) ─────────────────── */}
      <div className="flex justify-center py-2">
        {isTraining ? (
          <Button
            variant="stop"
            size="lg"
            onClick={handleStopTrainingConfirm}
            disabled={isStopping}
            aria-label="停止训练"
          >
            {isStopping ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                停止中...
              </>
            ) : (
              <>
                <Pause className="w-5 h-5" />
                停止训练
              </>
            )}
          </Button>
        ) : trainingPhase === 'idle' || trainingPhase === 'configuring' ? (
          <Button
            variant="primary"
            size="lg"
            onClick={handleStartTraining}
            disabled={!canStartTraining}
            aria-label="开始训练"
            title={!canStartTraining ? `缺少：${[
              !selectedFile && '数据文件',
              !targetColumn && '目标列',
              !selectedModel && '模型',
              finalFeatures.length === 0 && '特征列',
            ].filter(Boolean).join('、')}` : ''}
          >
            <Play className="w-5 h-5" />
            开始训练
          </Button>
        ) : null}
      </div>

      {/* ── Inline error for start failure ────────────────────────────── */}
      {startError && (
        <div className="max-w-md mx-auto">
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-start gap-2" role="alert">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            {startError}
          </p>
        </div>
      )}

      {/* ── Stop Confirmation Dialog ──────────────────────────────────── */}
      <AlertDialog
        open={showStopConfirm}
        title="停止训练"
        description="确定要停止当前训练任务吗？此操作不可撤销，训练进度将丢失。"
        confirmLabel="确认停止"
        cancelLabel="取消"
        destructive
        onConfirm={handleStopTrainingExecute}
        onCancel={() => setShowStopConfirm(false)}
      />

      {/* ── Log Panel (fixed bottom) ──────────────────────────────────── */}
      {isTraining && (
        <LogPanel
          logs={logLines}
          onClear={() => setLogLines([])}
        />
      )}
    </div>
  )
}
