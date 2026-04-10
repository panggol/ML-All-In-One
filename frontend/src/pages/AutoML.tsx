import { useState, useEffect, useCallback, useRef } from 'react'
import { Sparkles, Play, Square, CheckCircle2, XCircle, AlertCircle, Clock } from 'lucide-react'
import Card from '../components/Card'
import Select from '../components/Select'
import Button from '../components/Button'
import ProgressBar from '../components/ProgressBar'
import { dataApi, automlApi } from '../api'
import type { DataFile } from '../api'
import type { AutoMLStatus, AutoMLReport, SearchSpaceItem } from '../api/automl'

// ─── 常量 ────────────────────────────────────────────────────────────────────

const STRATEGIES = [
  { value: 'random', label: 'Random Search', desc: '随机采样，推荐' },
  { value: 'grid', label: 'Grid Search', desc: '网格搜索，适合小空间' },
  { value: 'bayesian', label: 'Bayesian Optimization', desc: '贝叶斯优化，需安装 optuna' },
]

const TASK_TYPES = [
  { value: 'classification', label: '分类', metric: 'Accuracy' },
  { value: 'regression', label: '回归', metric: 'R² Score' },
]

const DEFAULT_SEARCH_SPACE: SearchSpaceItem[] = [
  { name: 'model_type', type: 'choice', values: ['random_forest', 'xgboost', 'lightgbm'] },
  { name: 'n_estimators', type: 'int', low: 50, high: 200, step: 10 },
  { name: 'max_depth', type: 'int', low: 3, high: 10, step: 1 },
  { name: 'learning_rate', type: 'float', low: 0.01, high: 0.3, log: true },
]

// ─── Markdown 渲染 ────────────────────────────────────────────────────────────

function renderMarkdown(md: string): string {
  // 简单实现：处理表格、粗体、标题
  return md
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-slate-800 mt-4 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-semibold text-slate-800 mt-6 mb-3">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-slate-900 mb-4">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-slate-700">$1</strong>')
    .replace(/`(.+?)`/g, '<code class="px-1.5 py-0.5 bg-slate-100 rounded text-sm font-mono text-slate-700">$1</code>')
    .replace(/^\|(.+)\|$/gm, (line) => {
      const cells = line.split('|').filter(c => c.trim())
      if (cells.every(c => /^[-: ]+$/.test(c))) return '' // separator row
      const isHeader = line.includes('---')
      return `<div class="flex ${isHeader ? '' : 'border-b border-slate-100'}">${
        cells.map(c =>
          `<div class="flex-1 px-3 py-2 ${isHeader ? 'font-semibold text-slate-700 text-sm' : 'text-sm text-slate-600'}">${c.trim()}</div>`
        ).join('')
      }</div>`
    })
    .replace(/\n\n/g, '<div class="h-3"/>')
    .replace(/\n/g, '<br/>')
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function AutoML() {
  // 数据集状态
  const [dataFiles, setDataFiles] = useState<DataFile[]>([])
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null)
  const [targetColumn, setTargetColumn] = useState<string>('')

  // 任务配置
  const [taskType, setTaskType] = useState<'classification' | 'regression'>('classification')
  const [strategy, setStrategy] = useState<'grid' | 'random' | 'bayesian'>('random')
  const [nTrials, setNTrials] = useState(10)
  const [timeout, setTimeout] = useState(300)
  const [searchSpace, setSearchSpace] = useState<SearchSpaceItem[]>(DEFAULT_SEARCH_SPACE)

  // 运行状态
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<AutoMLStatus | null>(null)
  const [report, setReport] = useState<AutoMLReport | null>(null)
  const [logs, setLogs] = useState('')
  const [polling, setPolling] = useState(false)
  const [startError, setStartError] = useState('')
  const [isRunning, setIsRunning] = useState(false)

  const logsEndRef = useRef<HTMLDivElement>(null)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 加载数据集
  useEffect(() => {
    dataApi.list().then(files => {
      setDataFiles(files)
      if (files.length > 0) setSelectedFileId(files[0].id)
    }).catch(() => {})
  }, [])

  // 自动滚动日志

  // Reset target column when selected file changes
  useEffect(() => {
    const file = dataFiles.find(f => f.id === selectedFileId)
    if (file && file.columns.length > 0) {
      setTargetColumn(file.columns[0])
    }
  }, [selectedFileId, dataFiles])
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  const selectedFile = dataFiles.find(f => f.id === selectedFileId)

  // 轮询状态
  const pollStatus = useCallback(async (id: string) => {
    if (!id) return
    try {
      const status = await automlApi.status(id)
      setJobStatus(status)
      setLogs(prev => {
        // 追加新日志，保留最近 2000 字符
        const combined = (prev + status.logs).slice(-2000)
        return combined
      })
      if (status.status === 'completed' || status.status === 'failed' || status.status === 'stopped') {
        setPolling(false)
        setIsRunning(false)
        if (status.status === 'completed') {
          const rep = await automlApi.report(id)
          setReport(rep)
        }
      }
    } catch {
      // ignore polling errors
    }
  }, [])

  // 启动轮询
  useEffect(() => {
    if (polling && jobId) {
      pollTimerRef.current = setInterval(() => pollStatus(jobId), 2000)
    }
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [polling, jobId, pollStatus])

  // 开始搜索
  const handleStart = async () => {
    if (!selectedFileId) return
    setStartError('')
    setReport(null)
    setLogs('')
    setJobStatus(null)

    try {
      const res = await automlApi.start({
        data_file_id: selectedFileId,
        target_column: targetColumn,
        task_type: taskType,
        strategy,
        search_space: searchSpace,
        n_trials: nTrials,
        timeout,
      })
      setJobId(res.job_id)
      setIsRunning(true)
      setPolling(true)
    } catch (e: any) {
      setStartError(e?.response?.data?.detail || '启动失败')
    }
  }

  // 停止搜索
  const handleStop = async () => {
    if (!jobId) return
    try {
      await automlApi.stop(jobId)
      setPolling(false)
      setIsRunning(false)
    } catch {}
  }

  // 搜索空间编辑
  const updateSpace = (index: number, field: keyof SearchSpaceItem, value: any) => {
    setSearchSpace(prev => {
      const next = [...prev]
      next[index] = { ...next[index], [field]: value }
      return next
    })
  }

  // 状态颜色
  const statusColor = (s: string) => {
    if (s === 'completed') return 'text-emerald-600'
    if (s === 'failed') return 'text-red-600'
    if (s === 'stopped') return 'text-amber-600'
    if (s === 'running') return 'text-blue-600'
    return 'text-slate-500'
  }

  const StatusIcon = ({ status: s }: { status: string }) => {
    if (s === 'completed') return <CheckCircle2 className="w-5 h-5 text-emerald-500" />
    if (s === 'failed') return <XCircle className="w-5 h-5 text-red-500" />
    if (s === 'stopped') return <AlertCircle className="w-5 h-5 text-amber-500" />
    if (s === 'running') return <Clock className="w-5 h-5 text-blue-500" style={{ animation: 'spin 1.5s linear infinite' }} />
    return <Clock className="w-5 h-5 text-slate-400" />
  }

  const dataFileOptions = dataFiles.map(f => ({ value: String(f.id), label: f.filename }))
  const targetOptions = selectedFile?.columns.map(c => ({ value: c, label: c })) || []
  const selectedTarget = targetOptions[0]?.value || ''

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-amber-500" />
          AutoML 自动化调参
        </h1>
        <p className="text-slate-500 mt-1">
          自动搜索最优模型和超参数组合 · 支持 Grid / Random / Bayesian 策略
        </p>
      </div>

      {/* 配置卡片 */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-900 mb-5">任务配置</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {/* 数据集 */}
          <div className="sm:col-span-2 lg:col-span-1">
            <Select
              label="数据集"
              options={dataFileOptions}
              value={String(selectedFileId ?? '')}
              onChange={e => setSelectedFileId(Number(e.target.value))}
            />
          </div>

          {/* 目标列 */}
          <div>
            <Select
              label="目标列"
              options={targetOptions}
              value={selectedTarget}
              onChange={_e => {
                setSearchSpace(prev => prev.map(s =>
                  s.name === 'target' ? { ...s } : s
                ))
              }}
            />
          </div>

          {/* 任务类型 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">任务类型</label>
            <div className="flex gap-3">
              {TASK_TYPES.map(t => (
                <button
                  key={t.value}
                  onClick={() => setTaskType(t.value as typeof taskType)}
                  className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-all ${
                    taskType === t.value
                      ? 'bg-primary-50 border-primary-300 text-primary-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {t.label}
                  <span className="block text-xs text-slate-400 mt-0.5">{t.metric}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 搜索策略 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">搜索策略</label>
            <div className="flex gap-2">
              {STRATEGIES.map(s => (
                <button
                  key={s.value}
                  onClick={() => setStrategy(s.value as typeof strategy)}
                  className={`flex-1 py-2 px-2 rounded-lg text-xs font-medium border transition-all ${
                    strategy === s.value
                      ? 'bg-violet-50 border-violet-300 text-violet-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                  title={s.desc}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* n_trials */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              搜索次数 (n_trials)
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={nTrials}
              onChange={e => setNTrials(Math.max(1, Math.min(100, Number(e.target.value))))}
              disabled={isRunning}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 disabled:bg-slate-50 disabled:text-slate-400"
            />
          </div>

          {/* timeout */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              总超时 (秒)
            </label>
            <input
              type="number"
              min={10}
              max={3600}
              value={timeout}
              onChange={e => setTimeout(Math.max(10, Number(e.target.value)))}
              disabled={isRunning}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 disabled:bg-slate-50 disabled:text-slate-400"
            />
          </div>
        </div>

        {/* 搜索空间 */}
        <div className="mt-6">
          <h3 className="text-sm font-medium text-slate-700 mb-3">搜索空间</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-100">
                  <th className="pb-2 pr-4 font-medium">参数名</th>
                  <th className="pb-2 pr-4 font-medium">类型</th>
                  <th className="pb-2 pr-4 font-medium">取值/范围</th>
                  <th className="pb-2 font-medium w-16">操作</th>
                </tr>
              </thead>
              <tbody>
                {searchSpace.map((item, idx) => (
                  <tr key={idx} className="border-b border-slate-50">
                    <td className="py-2 pr-4">
                      <input
                        value={item.name}
                        onChange={e => updateSpace(idx, 'name', e.target.value)}
                        disabled={isRunning}
                        className="w-full px-2 py-1 border border-slate-200 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary-300 disabled:bg-slate-50"
                      />
                    </td>
                    <td className="py-2 pr-4">
                      <select
                        value={item.type}
                        onChange={e => updateSpace(idx, 'type', e.target.value)}
                        disabled={isRunning}
                        className="px-2 py-1 border border-slate-200 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary-300 disabled:bg-slate-50"
                      >
                        <option value="choice">choice</option>
                        <option value="int">int</option>
                        <option value="float">float</option>
                      </select>
                    </td>
                    <td className="py-2 pr-4">
                      {item.type === 'choice' ? (
                        <input
                          value={(item.values || []).join(', ')}
                          onChange={e => updateSpace(idx, 'values', e.target.value.split(',').map(v => v.trim()).filter(Boolean))}
                          placeholder="rf, xgboost, lightgbm"
                          disabled={isRunning}
                          className="w-full px-2 py-1 border border-slate-200 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary-300 disabled:bg-slate-50"
                        />
                      ) : (
                        <div className="flex items-center gap-1">
                          <input
                            type="number"
                            value={item.low ?? ''}
                            onChange={e => updateSpace(idx, 'low', Number(e.target.value))}
                            placeholder="min"
                            disabled={isRunning}
                            className="w-16 px-2 py-1 border border-slate-200 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary-300 disabled:bg-slate-50"
                          />
                          <span className="text-slate-400">~</span>
                          <input
                            type="number"
                            value={item.high ?? ''}
                            onChange={e => updateSpace(idx, 'high', Number(e.target.value))}
                            placeholder="max"
                            disabled={isRunning}
                            className="w-16 px-2 py-1 border border-slate-200 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary-300 disabled:bg-slate-50"
                          />
                          {item.type === 'float' && (
                            <label className="flex items-center gap-1 ml-1 text-xs text-slate-500">
                              <input
                                type="checkbox"
                                checked={item.log || false}
                                onChange={e => updateSpace(idx, 'log', e.target.checked)}
                                disabled={isRunning}
                                className="w-3 h-3"
                              />
                              log
                            </label>
                          )}
                          {item.type === 'int' && (
                            <input
                              type="number"
                              value={item.step ?? 1}
                              onChange={e => updateSpace(idx, 'step', Number(e.target.value))}
                              placeholder="step"
                              disabled={isRunning}
                              className="w-14 px-2 py-1 border border-slate-200 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary-300 disabled:bg-slate-50"
                            />
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => setSearchSpace(prev => prev.filter((_, i) => i !== idx))}
                        disabled={isRunning || searchSpace.length <= 1}
                        className="text-red-400 hover:text-red-600 disabled:text-slate-300 text-xs"
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            onClick={() => setSearchSpace(prev => [
              ...prev,
              { name: 'new_param', type: 'int', low: 1, high: 10 }
            ])}
            disabled={isRunning}
            className="mt-2 text-xs text-primary-600 hover:text-primary-700 disabled:text-slate-400"
          >
            + 添加参数
          </button>
        </div>

        {/* 开始按钮 */}
        {startError && (
          <div className="mt-4 flex items-center gap-2 text-red-500 text-sm">
            <AlertCircle className="w-4 h-4" />
            {startError}
          </div>
        )}

        <div className="mt-5 flex gap-3">
          {!isRunning ? (
            <Button onClick={handleStart} disabled={!selectedFileId}>
              <Play className="w-4 h-4 mr-1" />
              开始搜索
            </Button>
          ) : (
            <Button variant="stop" onClick={handleStop}>
              <Square className="w-4 h-4 mr-1" />
              停止
            </Button>
          )}
        </div>
      </Card>

      {/* 进度卡片 */}
      {(isRunning || jobStatus) && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <StatusIcon status={jobStatus?.status || 'pending'} />
              <h2 className="text-lg font-semibold text-slate-900">搜索进度</h2>
              <span className={`text-sm font-medium ${statusColor(jobStatus?.status || '')}`}>
                {jobStatus?.status === 'running' ? `Trial ${jobStatus.current_trial}/${jobStatus.n_trials}` : ''}
                {jobStatus?.status === 'completed' && '✅ 完成'}
                {jobStatus?.status === 'failed' && '❌ 失败'}
                {jobStatus?.status === 'stopped' && '⏹ 已停止'}
                {jobStatus?.status === 'pending' && '⏳ 等待中'}
              </span>
            </div>
            {jobId && (
              <span className="text-xs text-slate-400 font-mono">job: {jobId}</span>
            )}
          </div>

          <ProgressBar
            value={jobStatus?.progress || 0}
            size="md"
            showLabel
            className="mb-5"
          />

          {/* 日志区域 */}
          <div className="bg-slate-900 rounded-lg p-4 max-h-64 overflow-y-auto">
            <pre className="text-green-400 text-xs font-mono leading-relaxed whitespace-pre-wrap">
              {logs || (isRunning ? '初始化中...\n' : '暂无日志')}
            </pre>
            <div ref={logsEndRef} />
          </div>
        </Card>
      )}

      {/* 报告卡片 */}
      {report && report.status === 'completed' && (
        <Card>
          <div className="flex items-center gap-2 mb-5">
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
            <h2 className="text-lg font-semibold text-slate-900">调优报告</h2>
            <span className="text-sm text-slate-500">
              最佳验证分数: <strong className="text-emerald-600">{report.best_val_score}</strong>
              · 策略: {report.strategy}
              · 用时: {report.total_time}s
            </span>
          </div>

          {/* Top-3 模型表格 */}
          {report.top_models.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Top-3 模型</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-200">
                      <th className="pb-2 pr-4 font-medium">排名</th>
                      <th className="pb-2 pr-4 font-medium">模型</th>
                      <th className="pb-2 pr-4 font-medium text-right">验证分数</th>
                      <th className="pb-2 pr-4 font-medium text-right">训练分数</th>
                      <th className="pb-2 pr-4 font-medium text-right">用时(s)</th>
                      <th className="pb-2 font-medium">超参数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.top_models.map((model, i) => (
                      <tr key={i} className="border-b border-slate-50">
                        <td className="py-3 pr-4">
                          <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                            i === 0 ? 'bg-amber-100 text-amber-700' :
                            i === 1 ? 'bg-slate-200 text-slate-600' :
                            'bg-orange-100 text-orange-700'
                          }`}>
                            {model.rank}
                          </span>
                        </td>
                        <td className="py-3 pr-4 font-medium text-slate-800">
                          {model.model_type}
                        </td>
                        <td className="py-3 pr-4 text-right font-mono text-emerald-600">
                          {model.val_score}
                        </td>
                        <td className="py-3 pr-4 text-right font-mono text-slate-500">
                          {model.train_score}
                        </td>
                        <td className="py-3 pr-4 text-right font-mono text-slate-500">
                          {model.train_time}s
                        </td>
                        <td className="py-3 text-xs text-slate-500 font-mono">
                          {Object.entries(model.params).map(([k, v]) => (
                            <span key={k} className="mr-2">
                              <span className="text-slate-400">{k}=</span>
                              <span>{String(v)}</span>
                            </span>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Markdown 报告 */}
          {report.report_md && (
            <div
              className="bg-slate-50 rounded-lg p-4 text-sm text-slate-700"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(report.report_md) }}
            />
          )}
        </Card>
      )}

      {/* 无数据提示 */}
      {!isRunning && !report && !jobStatus && (
        <div className="text-center py-16 text-slate-400">
          <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg">配置参数后点击「开始搜索」</p>
          <p className="text-sm mt-1">系统将自动探索最优模型和超参数组合</p>
        </div>
      )}
    </div>
  )
}
