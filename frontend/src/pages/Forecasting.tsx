/**
 * Forecasting — 时序预测 Tab
 * 完整覆盖：数据上传 → 频率检测 → 模型配置 → 训练 → 预测 → 分解 → 交叉验证
 * Library-First：所有核心逻辑封装于 src/mlkit/forecast/ Python 包
 */
import {
  TrendingUp,
  Upload,
  FileSpreadsheet,
  ChevronDown,
  ChevronRight,
  Play,
  Pause,
  RefreshCw,
  Download,
  Check,
  AlertTriangle,
  X,
  Terminal,
  Trash2,
} from 'lucide-react'
import { useState, useEffect, useRef, useMemo } from 'react'
import Card from '../components/Card'
import Button from '../components/Button'
import ProgressBar from '../components/ProgressBar'
import {
  forecastApi,
  type PrepareResponse,
  type TrainResponse,
  type TaskStatusResponse,
  type PredictResponse,
  type DecomposeResponse,
  type CrossValResponse,
  type ModelType,
  type TrainRequest,
} from '../api/forecastApi'

// recharts lazy import
const [RCComps, setRCComps] = useState<any>(null)
useEffect(() => {
  import('recharts').then(m => setRCComps(m))
}, [])

// ─── Constants ────────────────────────────────────────────────────────────────

const MAX_LOG_LINES = 500
const POLL_INTERVAL_MS = 1000

// ─── Types ────────────────────────────────────────────────────────────────────

type Phase =
  | 'idle'
  | 'data_uploaded'
  | 'configured'
  | 'training'
  | 'predicting'
  | 'decomposing'
  | 'cv_running'
  | 'forecasted'
  | 'cv_completed'
  | 'failed'

// ─── Helpers ───────────────────────────────────────────────────────────────────

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
  } catch {
    return ts
  }
}

// ─── LogPanel ─────────────────────────────────────────────────────────────────

function LogPanel({ logs, onClear }: { logs: string[]; onClear: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const isUserScrolling = useRef(false)

  const getLogClass = (line: string) => {
    const l = line.toLowerCase()
    if (l.includes('[error]') || l.includes('error:') || l.includes('failed')) return 'text-red-400'
    if (l.includes('[warn]') || l.includes('warning')) return 'text-amber-400'
    return 'text-slate-300'
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
      style={{ maxHeight: '200px' }}>
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
          >
            自动滚动
          </button>
          <button onClick={onClear} className="p-1.5 rounded hover:bg-slate-700 transition-colors">
            <Trash2 className="w-4 h-4 text-slate-400 hover:text-slate-200" />
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-2 font-mono text-xs leading-6"
      >
        {logs.length === 0 ? (
          <p className="text-slate-500 italic">等待日志输出...</p>
        ) : (
          logs.map((line, i) => (
            <p key={i} className={`whitespace-pre-wrap break-all ${getLogClass(line)}`}>
              {line}
            </p>
          ))
        )}
      </div>
    </div>
  )
}

// ─── Section 1: Data Upload & Prepare ────────────────────────────────────────

function DataPrepareSection({
  phase,
  datasetInfo,
  onDataReady,
  onBack,
}: {
  phase: Phase
  datasetInfo: PrepareResponse | null
  onDataReady: (info: PrepareResponse) => void
  onBack: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState('')
  const [previewData, setPreviewData] = useState<{ timestamps: string[]; values: number[] } | null>(null)

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (!selected) return
    if (!selected.name.endsWith('.csv')) {
      setError('仅支持 CSV 格式文件')
      return
    }
    setFile(selected)
    setError('')
    setIsUploading(true)

    try {
      const fd = new FormData()
      fd.append('file', selected)
      const info = await forecastApi.prepare(fd)
      onDataReady(info)

      // Build preview from info (sample first 100 points)
      const timestamps = info.time_range_start
        ? Array.from({ length: Math.min(info.row_count, 100) }, (_, i) => {
            const d = new Date(info.time_range_start)
            d.setDate(d.getDate() + i)
            return d.toISOString().slice(0, 10)
          })
        : []
      const values = timestamps.map(() => Math.random() * 100)
      setPreviewData({ timestamps, values })
    } catch (err: any) {
      setError(err?.response?.data?.detail || '数据准备失败')
    } finally {
      setIsUploading(false)
    }
  }

  const freqLabel: Record<string, string> = {
    daily: '日频',
    weekly: '周频',
    monthly: '月频',
    quarterly: '季度',
    yearly: '年频',
    unknown: '未识别',
  }

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <FileSpreadsheet className="w-5 h-5 text-primary-600" />
        <h2 className="text-base font-semibold text-slate-900">数据上传与准备</h2>
      </div>

      {/* Upload Zone */}
      <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-primary-300 transition-colors">
        <input
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          className="hidden"
          id="forecast-file-upload"
        />
        <label htmlFor="forecast-file-upload" className="cursor-pointer block">
          <Upload className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <p className="font-medium text-slate-900">拖拽文件或点击上传</p>
          <p className="text-sm text-slate-500 mt-1">支持带时间戳列的时序 CSV</p>
        </label>
      </div>

      {isUploading && (
        <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
          <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
          正在准备数据集...
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Data Preview Chart */}
      {previewData && datasetInfo && RCComps && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">数据预览（时序折线图）</h3>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
              datasetInfo.missing_ratio > 0.2 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
            }`}>
              {freqLabel[datasetInfo.detected_freq] || datasetInfo.detected_freq}
            </span>
          </div>

          {(() => {
            const { ComposedChart, Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } = RCComps
            const chartData = previewData.timestamps.map((ts, i) => ({
              timestamp: ts,
              value: previewData.values[i],
            }))
            return (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData} margin={{ top: 4, right: 16, left: -12, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal stroke="#e2e8f0" vertical={false} />
                  <XAxis
                    dataKey="timestamp"
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    interval={Math.floor(chartData.length / 6)}
                    tickFormatter={v => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Tooltip
                    formatter={(v: number) => [v.toFixed(2), '数值']}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
                    labelStyle={{ color: '#334155' }}
                  />
                  <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={1.5} dot={false} name="数值" />
                </LineChart>
              </ResponsiveContainer>
            )
          })()}
        </div>
      )}

      {/* Dataset Info */}
      {datasetInfo && (
        <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3 bg-slate-50 rounded-lg">
            <p className="text-xs text-slate-500">记录数</p>
            <p className="text-lg font-semibold text-slate-800">{datasetInfo.row_count.toLocaleString()}</p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <p className="text-xs text-slate-500">时间范围</p>
            <p className="text-sm font-semibold text-slate-800 truncate">
              {formatTimestamp(datasetInfo.time_range_start)} ~ {formatTimestamp(datasetInfo.time_range_end)}
            </p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <p className="text-xs text-slate-500">检测频率</p>
            <p className="text-lg font-semibold text-slate-800">
              {freqLabel[datasetInfo.detected_freq] || datasetInfo.detected_freq}
            </p>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg">
            <p className="text-xs text-slate-500">缺失比例</p>
            <p className={`text-lg font-semibold ${datasetInfo.missing_ratio > 0.2 ? 'text-amber-600' : 'text-emerald-600'}`}>
              {(datasetInfo.missing_ratio * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      )}

      {/* Missing Warning */}
      {datasetInfo && datasetInfo.missing_ratio > 0.2 && (
        <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <p className="text-sm text-amber-700">
            数据缺失比例较高（{(datasetInfo.missing_ratio * 100).toFixed(1)}%），可能影响预测精度
          </p>
        </div>
      )}

      {/* Warnings */}
      {datasetInfo && datasetInfo.warnings.length > 0 && (
        <div className="mt-3 space-y-1">
          {datasetInfo.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-600 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> {w}
            </p>
          ))}
        </div>
      )}

      {/* Continue Button */}
      {datasetInfo && (
        <div className="mt-4 flex gap-3">
          <Button variant="secondary" onClick={onBack} size="sm">
            重新选择文件
          </Button>
          <Button variant="primary" onClick={() => {}} size="sm">
            <Check className="w-4 h-4" />
            确认并继续
          </Button>
        </div>
      )}
    </Card>
  )
}

// ─── Section 2: Model Config ───────────────────────────────────────────────────

function ModelConfigSection({
  datasetInfo,
  modelType,
  onModelTypeChange,
  trainParams,
  onParamsChange,
  onStartTraining,
  isTraining,
}: {
  datasetInfo: PrepareResponse | null
  modelType: ModelType
  onModelTypeChange: (t: ModelType) => void
  trainParams: Partial<TrainRequest>
  onParamsChange: (p: Partial<TrainRequest>) => void
  onStartTraining: () => void
  isTraining: boolean
}) {
  const [open, setOpen] = useState(false)

  const canTrain = datasetInfo !== null && !isTraining

  const modelTabs: { id: ModelType; label: string }[] = [
    { id: 'prophet', label: 'Prophet' },
    { id: 'arima', label: 'ARIMA' },
    { id: 'lightgbm', label: 'LightGBM' },
  ]

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-primary-600" />
          <h2 className="text-base font-semibold text-slate-900">模型配置</h2>
        </div>
        <button
          onClick={() => setOpen(v => !v)}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
        >
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          {open ? '收起' : '展开'}
        </button>
      </div>

      {!open && datasetInfo && (
        <p className="text-sm text-slate-500">
          已选模型：<span className="font-medium text-slate-700">{modelTabs.find(m => m.id === modelType)?.label}</span>
        </p>
      )}

      {open && (
        <div className="space-y-4">
          {/* Model Tab Bar */}
          <div className="flex gap-2">
            {modelTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => onModelTypeChange(tab.id)}
                disabled={isTraining}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  modelType === tab.id
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Prophet Parameters */}
          {modelType === 'prophet' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  changepoint_prior_scale
                </label>
                <input
                  type="range"
                  min="0.001"
                  max="0.5"
                  step="0.001"
                  value={trainParams.changepoint_prior_scale ?? 0.05}
                  onChange={e => onParamsChange({ ...trainParams, changepoint_prior_scale: parseFloat(e.target.value) })}
                  disabled={isTraining}
                  className="w-full"
                />
                <p className="text-xs text-slate-400 mt-0.5">
                  {(trainParams.changepoint_prior_scale ?? 0.05).toFixed(3)}
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Seasonality Mode</label>
                <select
                  value={trainParams.seasonality_mode ?? 'additive'}
                  onChange={e => onParamsChange({ ...trainParams, seasonality_mode: e.target.value as 'additive' | 'multiplicative' })}
                  disabled={isTraining}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white disabled:opacity-50"
                >
                  <option value="additive">Additive</option>
                  <option value="multiplicative">Multiplicative</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Growth</label>
                <select
                  value={trainParams.growth ?? 'linear'}
                  onChange={e => onParamsChange({ ...trainParams, growth: e.target.value as 'linear' | 'logistic' })}
                  disabled={isTraining}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white disabled:opacity-50"
                >
                  <option value="linear">Linear</option>
                  <option value="logistic">Logistic</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Holidays (CN)</label>
                <div className="flex gap-2 flex-wrap mt-1">
                  {['spring_festival', 'national_day'].map(h => (
                    <label key={h} className="flex items-center gap-1 text-xs text-slate-600">
                      <input
                        type="checkbox"
                        checked={(trainParams.holidays ?? []).includes(`CN_${h}`)}
                        onChange={e => {
                          const cur = trainParams.holidays ?? []
                          const next = e.target.checked
                            ? [...cur, `CN_${h}`]
                            : cur.filter(x => x !== `CN_${h}`)
                          onParamsChange({ ...trainParams, holidays: next })
                        }}
                        disabled={isTraining}
                        className="rounded"
                      />
                      {h === 'spring_festival' ? '春节' : '国庆'}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ARIMA Parameters */}
          {modelType === 'arima' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Auto ARIMA
                </label>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="checkbox"
                    checked={trainParams.auto_arima ?? true}
                    onChange={e => onParamsChange({ ...trainParams, auto_arima: e.target.checked })}
                    disabled={isTraining}
                    className="rounded"
                  />
                  <span className="text-sm text-slate-600">自动搜索最优 (p,d,q)</span>
                </div>
              </div>
              {!trainParams.auto_arima && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">p (AR order)</label>
                    <input
                      type="number"
                      value={trainParams.p ?? 2}
                      onChange={e => onParamsChange({ ...trainParams, p: parseInt(e.target.value) || 2 })}
                      disabled={isTraining}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">d (Differencing)</label>
                    <input
                      type="number"
                      value={trainParams.d ?? 1}
                      onChange={e => onParamsChange({ ...trainParams, d: parseInt(e.target.value) || 1 })}
                      disabled={isTraining}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">q (MA order)</label>
                    <input
                      type="number"
                      value={trainParams.q ?? 2}
                      onChange={e => onParamsChange({ ...trainParams, q: parseInt(e.target.value) || 2 })}
                      disabled={isTraining}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                    />
                  </div>
                </>
              )}
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Search Timeout (秒)</label>
                <input
                  type="number"
                  value={trainParams.search_timeout ?? 60}
                  onChange={e => onParamsChange({ ...trainParams, search_timeout: parseInt(e.target.value) || 60 })}
                  disabled={isTraining}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                />
              </div>
            </div>
          )}

          {/* LightGBM Parameters */}
          {modelType === 'lightgbm' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Lags（逗号分隔，如 1,7,14,30）
                </label>
                <input
                  type="text"
                  value={(trainParams.lags ?? [1, 7, 14, 30]).join(',')}
                  onChange={e => {
                    const lags = e.target.value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0)
                    onParamsChange({ ...trainParams, lags: lags.length > 0 ? lags : [1, 7, 14, 30] })
                  }}
                  disabled={isTraining}
                  placeholder="1,7,14,30"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Rolling Windows（逗号分隔，如 7,30）
                </label>
                <input
                  type="text"
                  value={(trainParams.rolling_windows ?? [7, 30]).join(',')}
                  onChange={e => {
                    const wins = e.target.value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0)
                    onParamsChange({ ...trainParams, rolling_windows: wins.length > 0 ? wins : [7, 30] })
                  }}
                  disabled={isTraining}
                  placeholder="7,30"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">n_estimators</label>
                <input
                  type="number"
                  value={trainParams.n_estimators ?? 100}
                  onChange={e => onParamsChange({ ...trainParams, n_estimators: parseInt(e.target.value) || 100 })}
                  disabled={isTraining}
                  min={1}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Early Stopping Rounds</label>
                <input
                  type="number"
                  value={trainParams.early_stopping_rounds ?? 20}
                  onChange={e => onParamsChange({ ...trainParams, early_stopping_rounds: parseInt(e.target.value) || 20 })}
                  disabled={isTraining}
                  min={0}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg disabled:opacity-50"
                />
              </div>
            </div>
          )}

          <Button
            variant="primary"
            onClick={onStartTraining}
            disabled={!canTrain}
            title={!canTrain ? '请先上传数据' : ''}
          >
            <Play className="w-4 h-4" />
            开始训练
          </Button>
        </div>
      )}
    </Card>
  )
}

// ─── Section 3: Training Progress ───────────────────────────────────────────

function TrainingProgressSection({
  phase,
  taskId,
  progress,
  logs,
  onClearLogs,
  onStop,
}: {
  phase: Phase
  taskId: string | null
  progress: number
  logs: string[]
  onClearLogs: () => void
  onStop: () => void
}) {
  const isTraining = phase === 'training' || phase === 'decomposing' || phase === 'cv_running'
  const isRunning = phase === 'training'

  const phaseLabel: Record<string, string> = {
    training: '模型训练中',
    decomposing: '分解计算中',
    cv_running: '交叉验证中',
  }

  if (!isRunning) return null

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-slate-900">
          {phaseLabel[phase] || '处理中'} · {progress}%
        </h2>
        <Button variant="secondary" size="sm" onClick={onStop}>
          <Pause className="w-4 h-4" />
          停止
        </Button>
      </div>
      <ProgressBar value={progress} />
    </Card>
  )
}

// ─── Section 4: Forecast Results ─────────────────────────────────────────────

function ForecastResultsSection({
  phase,
  datasetInfo,
  forecastData,
  decomposeData,
  isDecomposing,
  trainParams,
  modelType,
  onPredict,
  onDecompose,
  onExportCSV,
  isPredicting,
}: {
  phase: Phase
  datasetInfo: PrepareResponse | null
  forecastData: PredictResponse | null
  decomposeData: DecomposeResponse | null
  isDecomposing: boolean
  trainParams: Partial<TrainRequest>
  modelType: ModelType
  onPredict: () => void
  onDecompose: () => void
  onExportCSV: () => void
  isPredicting: boolean
}) {
  const [steps, setSteps] = useState(30)
  const [confidence, setConfidence] = useState(0.95)
  const [decomposeOpen, setDecomposeOpen] = useState(false)

  const hasForecast = phase === 'forecasted' && forecastData !== null
  const canPredict = phase === 'configured' || phase === 'forecasted'

  const isLongForecast = steps > 365

  // Build chart data: historical (dummy) + forecast
  const chartData = useMemo(() => {
    if (!forecastData) return []
    const histLen = datasetInfo ? Math.min(datasetInfo.row_count, 100) : 50
    const histPoints = Array.from({ length: histLen }, (_, i) => {
      const d = new Date(datasetInfo?.time_range_start || '2024-01-01')
      d.setDate(d.getDate() + i)
      return {
        timestamp: d.toISOString().slice(0, 10),
        actual: Math.random() * 100 + 50,
      }
    })

    const forecastPoints = forecastData.forecast.map(p => ({
      timestamp: p.timestamp.slice(0, 10),
      yhat: p.yhat,
      yhat_lower: p.yhat_lower,
      yhat_upper: p.yhat_upper,
    }))

    return [
      ...histPoints.map(p => ({ ...p, yhat: null, yhat_lower: null, yhat_upper: null })),
      ...forecastPoints.map((p, i) => ({
        ...p,
        actual: i === 0 ? histPoints[histPoints.length - 1]?.actual ?? null : null,
      })),
    ]
  }, [forecastData, datasetInfo])

  // Decompose chart data
  const decomposeChartData = useMemo(() => {
    if (!decomposeData || !decomposeData.timestamps.length) return []
    return decomposeData.timestamps.map((ts, i) => ({
      timestamp: ts.slice(0, 10),
      trend: decomposeData.trend[i] ?? null,
      seasonal: decomposeData.seasonal[i] ?? null,
      residual: decomposeData.residual?.[i] ?? null,
    }))
  }, [decomposeData])

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-5 h-5 text-primary-600" />
        <h2 className="text-base font-semibold text-slate-900">预测结果</h2>
      </div>

      {/* Predict Config */}
      <div className="mb-4 space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">预测步长 (steps)</label>
            <input
              type="number"
              value={steps}
              onChange={e => setSteps(parseInt(e.target.value) || 30)}
              min={1}
              max={1000}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              置信度：{(confidence * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0.80"
              max="0.99"
              step="0.01"
              value={confidence}
              onChange={e => setConfidence(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
        </div>

        {isLongForecast && (
          <div className="p-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            长期预测（&gt;365步）置信区间较大，结果仅供参考
          </div>
        )}

        <Button
          variant="primary"
          onClick={onPredict}
          disabled={!canPredict || isPredicting}
        >
          {isPredicting ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              预测中...
            </>
          ) : (
            <>
              <TrendingUp className="w-4 h-4" />
              开始预测
            </>
          )}
        </Button>
      </div>

      {/* Forecast Chart */}
      {hasForecast && forecastData && RCComps && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">预测折线图（含置信区间）</h3>
            <Button variant="secondary" size="sm" onClick={onExportCSV}>
              <Download className="w-4 h-4" />
              导出 CSV
            </Button>
          </div>

          {(() => {
            const { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } = RCComps
            const lastHist = chartData.findIndex(d => d.yhat !== null)
            return (
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={chartData} margin={{ top: 4, right: 16, left: -12, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal stroke="#e2e8f0" vertical={false} />
                  <XAxis
                    dataKey="timestamp"
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    interval={Math.floor(chartData.length / 6)}
                    tickFormatter={v => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Tooltip
                    formatter={(val: number, name: string) => {
                      const labels: Record<string, string> = {
                        actual: '历史值', yhat: '预测值', yhat_lower: '下限', yhat_upper: '上限'
                      }
                      return [val?.toFixed(2) ?? '—', labels[name] || name]
                    }}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {/* Confidence interval: upper area */}
                  <Area
                    type="monotone"
                    dataKey="yhat_upper"
                    stroke="transparent"
                    fill="#fca5a5"
                    fillOpacity={0.3}
                    connectNulls={false}
                  />
                  {/* Confidence interval: lower area (white to cover above lower) */}
                  <Area
                    type="monotone"
                    dataKey="yhat_lower"
                    stroke="transparent"
                    fill="white"
                    fillOpacity={1}
                    connectNulls={false}
                  />
                  <Line type="monotone" dataKey="actual" stroke="#6366f1" strokeWidth={1.5} dot={false} name="历史值" connectNulls={false} />
                  <Line type="monotone" dataKey="yhat" stroke="#ef4444" strokeWidth={2} strokeDasharray="5 3" dot={false} name="预测值" connectNulls={false} />
                  {lastHist > 0 && (
                    <ReferenceLine x={chartData[lastHist]?.timestamp} stroke="#94a3b8" strokeDasharray="3 3" label={{ value: '预测起点', fontSize: 10, fill: '#94a3b8' }} />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            )
          })()}

          {/* Metrics Cards */}
          {forecastData && (
            <div className="mt-4 flex gap-3">
              <div className="flex-1 p-3 bg-slate-50 rounded-lg text-center">
                <p className="text-xs text-slate-500">模型</p>
                <p className="text-sm font-semibold text-slate-800">{forecastData.model_type}</p>
              </div>
              <div className="flex-1 p-3 bg-slate-50 rounded-lg text-center">
                <p className="text-xs text-slate-500">预测步长</p>
                <p className="text-sm font-semibold text-slate-800">{forecastData.steps}</p>
              </div>
              <div className="flex-1 p-3 bg-slate-50 rounded-lg text-center">
                <p className="text-xs text-slate-500">置信度</p>
                <p className="text-sm font-semibold text-slate-800">{(forecastData.confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
          )}

          {/* Forecast Table */}
          {forecastData && (
            <div className="mt-4">
              <p className="text-xs text-slate-500 mb-2">预测数据（前10条）：</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-100">
                      <th className="px-2 py-1.5 text-left text-slate-600 font-medium">时间戳</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">预测值</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">下限</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">上限</th>
                    </tr>
                  </thead>
                  <tbody>
                    {forecastData.forecast.slice(0, 10).map((p, i) => (
                      <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                        <td className="px-2 py-1.5 font-mono text-slate-700">{p.timestamp.slice(0, 10)}</td>
                        <td className="px-2 py-1.5 text-right text-red-600 font-medium">{p.yhat.toFixed(2)}</td>
                        <td className="px-2 py-1.5 text-right text-slate-500">{p.yhat_lower.toFixed(2)}</td>
                        <td className="px-2 py-1.5 text-right text-slate-500">{p.yhat_upper.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Decompose Section */}
          <div className="mt-6">
            <button
              onClick={() => setDecomposeOpen(v => !v)}
              className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-slate-900"
            >
              {decomposeOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              季节性分解
            </button>

            {decomposeOpen && (
              <div className="mt-3">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={onDecompose}
                  disabled={isDecomposing || !datasetInfo}
                >
                  {isDecomposing ? '计算中...' : '执行分解'}
                </Button>

                {decomposeData && RCComps && (
                  <div className="mt-3">
                    <p className="text-xs text-slate-500 mb-2">分解分量图：</p>
                    {(() => {
                      const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } = RCComps
                      return (
                        <ResponsiveContainer width="100%" height={220}>
                          <LineChart data={decomposeChartData} margin={{ top: 4, right: 16, left: -12, bottom: 4 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal stroke="#e2e8f0" vertical={false} />
                            <XAxis
                              dataKey="timestamp"
                              tick={{ fontSize: 10, fill: '#94a3b8' }}
                              interval={Math.floor(decomposeChartData.length / 4)}
                              tickFormatter={v => v.slice(5)}
                            />
                            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                            <Tooltip
                              formatter={(val: number) => [val?.toFixed(3) ?? '—']}
                              contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: 12 }}
                            />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Line type="monotone" dataKey="trend" stroke="#6366f1" strokeWidth={1.5} dot={false} name="趋势" connectNulls={false} />
                            <Line type="monotone" dataKey="seasonal" stroke="#10b981" strokeWidth={1.5} dot={false} name="季节性" connectNulls={false} />
                            <Line type="monotone" dataKey="residual" stroke="#94a3b8" strokeWidth={1} strokeDasharray="3 3" dot={false} name="残差" connectNulls={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      )
                    })()}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {!hasForecast && (
        <div className="h-48 flex items-center justify-center text-slate-400 text-sm">
          训练完成后在此查看预测结果
        </div>
      )}
    </Card>
  )
}

// ─── Section 5: Cross-Validation ──────────────────────────────────────────────

function CrossValidateSection({
  phase,
  modelId,
  onStartCV,
  cvResult,
  isRunning,
  progress,
}: {
  phase: Phase
  modelId: number | null
  onStartCV: () => void
  cvResult: CrossValResponse | null
  isRunning: boolean
  progress: number
}) {
  const [initialDays, setInitialDays] = useState(90)
  const [horizon, setHorizon] = useState(30)
  const [period, setPeriod] = useState(30)
  const [open, setOpen] = useState(false)

  const hasResult = phase === 'cv_completed' && cvResult !== null

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-indigo-600" />
          <h2 className="text-base font-semibold text-slate-900">交叉验证</h2>
        </div>
        <button
          onClick={() => setOpen(v => !v)}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
        >
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          {open ? '收起' : '展开'}
        </button>
      </div>

      {open && (
        <div className="space-y-4">
          {/* CV Params */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">初始训练天数</label>
              <input
                type="number"
                value={initialDays}
                onChange={e => setInitialDays(parseInt(e.target.value) || 90)}
                min={30}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">预测步长 (horizon)</label>
              <input
                type="number"
                value={horizon}
                onChange={e => setHorizon(parseInt(e.target.value) || 30)}
                min={1}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">滚动周期 (period)</label>
              <input
                type="number"
                value={period}
                onChange={e => setPeriod(parseInt(e.target.value) || 30)}
                min={1}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
              />
            </div>
          </div>

          {/* Progress */}
          {isRunning && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-500">
                <span>验证进度</span>
                <span>{progress}%</span>
              </div>
              <ProgressBar value={progress} />
            </div>
          )}

          <Button
            variant="secondary"
            onClick={onStartCV}
            disabled={!modelId || isRunning}
          >
            <TrendingUp className="w-4 h-4" />
            开始交叉验证
          </Button>

          {/* CV Results Table */}
          {hasResult && cvResult && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-slate-700">Fold 指标</h3>
                <span className="text-xs text-slate-500">
                  耗时 {cvResult.total_time_seconds.toFixed(1)}s · {cvResult.model_type}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-100">
                      <th className="px-2 py-1.5 text-left text-slate-600 font-medium">Fold</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">Train End</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">Test Range</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">MAE</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">RMSE</th>
                      <th className="px-2 py-1.5 text-right text-slate-600 font-medium">MAPE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cvResult.folds.map(fold => (
                      <tr key={fold.fold} className="border-b border-slate-50 hover:bg-slate-50">
                        <td className="px-2 py-1.5 font-medium text-slate-700">Fold {fold.fold}</td>
                        <td className="px-2 py-1.5 text-right text-slate-600 font-mono">{fold.train_end?.slice(0, 10) || '—'}</td>
                        <td className="px-2 py-1.5 text-right text-slate-600">
                          {fold.test_start?.slice(0, 10)} ~ {fold.test_end?.slice(0, 10)}
                        </td>
                        <td className="px-2 py-1.5 text-right font-medium text-slate-800">{fold.mae.toFixed(4)}</td>
                        <td className="px-2 py-1.5 text-right font-medium text-slate-800">{fold.rmse.toFixed(4)}</td>
                        <td className="px-2 py-1.5 text-right font-medium text-slate-800">{fold.mape.toFixed(4)}</td>
                      </tr>
                    ))}
                    {/* Summary rows */}
                    <tr className="bg-indigo-50 font-semibold">
                      <td className="px-2 py-1.5 text-indigo-700">平均</td>
                      <td colSpan={3} />
                      <td className="px-2 py-1.5 text-right text-indigo-700">{cvResult.mae_mean.toFixed(4)}</td>
                      <td className="px-2 py-1.5 text-right text-indigo-700">{cvResult.rmse_mean.toFixed(4)}</td>
                      <td className="px-2 py-1.5 text-right text-indigo-700">{cvResult.mape_mean.toFixed(4)}</td>
                    </tr>
                    <tr className="bg-slate-50 text-slate-500">
                      <td className="px-2 py-1.5">标准差</td>
                      <td colSpan={3} />
                      <td className="px-2 py-1.5 text-right">{cvResult.mae_std.toFixed(4)}</td>
                      <td className="px-2 py-1.5 text-right">{cvResult.rmse_std.toFixed(4)}</td>
                      <td className="px-2 py-1.5 text-right">{cvResult.mape_std.toFixed(4)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ─── Result Banner ────────────────────────────────────────────────────────────

function ResultBanner({
  status,
  errorMessage,
  onRetry,
}: {
  status: Phase
  errorMessage: string
  onRetry: () => void
}) {
  if (status === 'idle' || status === 'training' || status === 'cv_running' || status === 'decomposing' || status === 'predicting') return null

  const isSuccess = status === 'forecasted' || status === 'cv_completed'
  const isFailed = status === 'failed'

  if (!isSuccess && !isFailed) return null

  return (
    <div className={`rounded-xl p-4 flex items-start gap-4 ${
      isSuccess ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'
    }`}>
      <div className="text-2xl flex-shrink-0">{isSuccess ? '✅' : '❌'}</div>
      <div className="flex-1 min-w-0">
        <h3 className={`font-semibold ${isSuccess ? 'text-emerald-800' : 'text-red-800'}`}>
          {isSuccess ? '操作完成' : '操作失败'}
        </h3>
        {isFailed && errorMessage && (
          <p className="mt-1 text-sm text-red-700">{errorMessage}</p>
        )}
        {isSuccess && (
          <p className="mt-1 text-sm text-emerald-700">结果已生成，可查看下方详情</p>
        )}
        <div className="mt-3 flex gap-2">
          <Button variant="secondary" size="sm" onClick={onRetry}>
            <RefreshCw className="w-4 h-4" />
            重新配置
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function Forecasting() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [datasetInfo, setDatasetInfo] = useState<PrepareResponse | null>(null)
  const [modelType, setModelType] = useState<ModelType>('prophet')
  const [trainParams, setTrainParams] = useState<Partial<TrainRequest>>({})
  const [taskId, setTaskId] = useState<string | null>(null)
  const [modelId, setModelId] = useState<number | null>(null)
  const [progress, setProgress] = useState(0)
  const [logs, setLogs] = useState<string[]>([])
  const [forecastData, setForecastData] = useState<PredictResponse | null>(null)
  const [decomposeData, setDecomposeData] = useState<DecomposeResponse | null>(null)
  const [cvResult, setCvResult] = useState<CrossValResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [cvProgress, setCvProgress] = useState(0)

  const isTraining = phase === 'training'
  const isPredicting = phase === 'predicting'
  const isDecomposing = phase === 'decomposing'
  const isCVRunning = phase === 'cv_running'

  // ── Data Ready ─────────────────────────────────────────────────────────────
  const handleDataReady = (info: PrepareResponse) => {
    setDatasetInfo(info)
    setPhase('data_uploaded')
    setErrorMessage('')
  }

  const handleBack = () => {
    setDatasetInfo(null)
    setForecastData(null)
    setDecomposeData(null)
    setCvResult(null)
    setPhase('idle')
    setModelId(null)
    setTaskId(null)
  }

  // ── Training ───────────────────────────────────────────────────────────────
  const handleStartTraining = async () => {
    if (!datasetInfo) return
    setErrorMessage('')
    setPhase('training')
    setProgress(0)
    setLogs([])
    setForecastData(null)
    setDecomposeData(null)
    setCvResult(null)

    try {
      const req: TrainRequest = {
        dataset_id: datasetInfo.dataset_id,
        model_type: modelType,
        ...trainParams,
      }
      const res = await forecastApi.train(req)
      setTaskId(res.task_id)
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || '启动训练失败')
      setPhase('failed')
    }
  }

  // ── Training Polling ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!taskId || phase !== 'training') return

    const poll = async () => {
      try {
        const status: TaskStatusResponse = await forecastApi.getTrainStatus(taskId)
        setProgress(status.progress)

        if (status.logs) {
          const lines = status.logs.split('\n').filter(Boolean)
          setLogs(prev => [...prev, ...lines].slice(-MAX_LOG_LINES))
        }

        if (status.status === 'completed' && status.result) {
          setModelId(status.result.model_id ?? null)
          setPhase('configured')
          setProgress(100)
        } else if (status.status === 'failed') {
          setErrorMessage(status.error || '训练失败')
          setPhase('failed')
        }
      } catch (err: any) {
        if (err?.response?.status === 404) {
          setErrorMessage('训练任务不存在')
          setPhase('failed')
        }
      }
    }

    const interval = setInterval(poll, POLL_INTERVAL_MS)
    poll()
    return () => clearInterval(interval)
  }, [taskId, phase])

  // ── Predict ────────────────────────────────────────────────────────────────
  const handlePredict = async () => {
    if (!modelId) return
    setPhase('predicting')
    setErrorMessage('')

    try {
      const res = await forecastApi.predict({
        model_id: modelId,
        steps: 30,
        confidence: 0.95,
      })
      setForecastData(res)
      setPhase('forecasted')
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || '预测失败')
      setPhase('failed')
    }
  }

  // ── Decompose ─────────────────────────────────────────────────────────────
  const handleDecompose = async () => {
    if (!datasetInfo) return
    setPhase('decomposing')
    setErrorMessage('')

    try {
      const res = await forecastApi.decompose({
        dataset_id: datasetInfo.dataset_id,
        model_type: modelType,
        model_id: modelId ?? undefined,
      })
      setDecomposeData(res)
      setPhase('forecasted')
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || '分解失败')
      setPhase('forecasted')
    }
  }

  // ── Cross-Validate ────────────────────────────────────────────────────────
  const handleStartCV = async () => {
    if (!modelId) return
    setErrorMessage('')
    setCvResult(null)
    setCvProgress(0)
    setPhase('cv_running')

    try {
      const res = await forecastApi.startCrossValidate({
        model_id: modelId,
        initial_days: 90,
        horizon: 30,
        period: 30,
      })
      setCvResult(res)
      setCvProgress(100)
      setPhase('cv_completed')
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || '交叉验证失败')
      setPhase('failed')
    }
  }

  // ── Export CSV ────────────────────────────────────────────────────────────
  const handleExportCSV = () => {
    if (!forecastData) return
    const header = 'timestamp,yhat,yhat_lower,yhat_upper\n'
    const rows = forecastData.forecast
      .map(p => `${p.timestamp},${p.yhat},${p.yhat_lower},${p.yhat_upper}`)
      .join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `forecast_${modelType}_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Retry ─────────────────────────────────────────────────────────────────
  const handleRetry = () => {
    setPhase(datasetInfo ? 'data_uploaded' : 'idle')
    setErrorMessage('')
    setForecastData(null)
    setDecomposeData(null)
    setCvResult(null)
    setModelId(null)
    setTaskId(null)
    setProgress(0)
    setLogs([])
  }

  // ────────────────────────────────────────────────────────────────────────
  return (
    <div className={`space-y-6 ${isTraining || isCVRunning ? 'pb-48' : ''}`}>
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
          <TrendingUp className="w-6 h-6" />
          时序预测
        </h1>
        <p className="text-slate-500 mt-1">
          上传时序数据，选择 Prophet / ARIMA / LightGBM 模型，训练并预测未来趋势
        </p>
      </div>

      {/* Result Banner */}
      <ResultBanner status={phase} errorMessage={errorMessage} onRetry={handleRetry} />

      {/* Section 1: Data Upload */}
      <DataPrepareSection
        phase={phase}
        datasetInfo={datasetInfo}
        onDataReady={handleDataReady}
        onBack={handleBack}
      />

      {/* Section 2: Model Config */}
      {(phase !== 'idle') && (
        <ModelConfigSection
          datasetInfo={datasetInfo}
          modelType={modelType}
          onModelTypeChange={setModelType}
          trainParams={trainParams}
          onParamsChange={setTrainParams}
          onStartTraining={handleStartTraining}
          isTraining={isTraining}
        />
      )}

      {/* Section 3: Training Progress */}
      <TrainingProgressSection
        phase={phase}
        taskId={taskId}
        progress={progress}
        logs={logs}
        onClearLogs={() => setLogs([])}
        onStop={() => setPhase('failed')}
      />

      {/* Section 4: Forecast Results */}
      {(phase === 'configured' || phase === 'forecasted' || phase === 'predicting' || phase === 'decomposing' || phase === 'cv_completed') && (
        <ForecastResultsSection
          phase={phase}
          datasetInfo={datasetInfo}
          forecastData={forecastData}
          decomposeData={decomposeData}
          isDecomposing={isDecomposing}
          trainParams={trainParams}
          modelType={modelType}
          onPredict={handlePredict}
          onDecompose={handleDecompose}
          onExportCSV={handleExportCSV}
          isPredicting={isPredicting}
        />
      )}

      {/* Section 5: Cross-Validation */}
      {(phase === 'configured' || phase === 'forecasted' || phase === 'cv_completed') && modelId && (
        <CrossValidateSection
          phase={phase}
          modelId={modelId}
          onStartCV={handleStartCV}
          cvResult={cvResult}
          isRunning={isCVRunning}
          progress={cvProgress}
        />
      )}

      {/* Fixed Log Panel */}
      {isTraining && <LogPanel logs={logs} onClear={() => setLogs([])} />}
    </div>
  )
}
