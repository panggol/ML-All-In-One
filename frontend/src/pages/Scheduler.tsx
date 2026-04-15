/**
 * Scheduler.tsx — 任务调度管理页面
 *
 * 功能：定时任务（Job）的 CRUD、状态管理、执行历史、手动触发、Cron 实时校验
 */
import { useState, useEffect, useCallback, Fragment } from 'react'
import {
  Clock, Plus, Zap, Pencil, Pause, Play, Trash2, X,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  LoaderCircle, Search, History, AlertTriangle,
} from 'lucide-react'
import { schedulerApi, type Job, type Execution, type JobStatus } from '../api/scheduler'
import Card from '../components/Card'
import Button from '../components/Button'

// ============ 常量 ============
const PAGE_SIZE = 20

// 常用 Cron 预设
const CRON_PRESETS = [
  { label: '每天早上 08:00', value: '0 8 * * *' },
  { label: '每小时整点', value: '0 * * * *' },
  { label: '每周一 00:00', value: '0 0 * * 1' },
  { label: '每天凌晨 02:00', value: '0 2 * * *' },
  { label: '每 30 分钟', value: '*/30 * * * *' },
  { label: '每 15 分钟', value: '*/15 * * * *' },
]

// ============ 工具函数 ============
function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}分${s}秒` : `${m}分`
}

// ============ Badge 组件 ============
function StatusBadge({ status }: { status: JobStatus | string }) {
  const map: Record<string, { cls: string; dot: string; label: string }> = {
    active:   { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: 'bg-emerald-500', label: '运行中' },
    paused:   { cls: 'bg-slate-100 text-slate-600 border-slate-200', dot: 'bg-slate-400', label: '已暂停' },
    failed:   { cls: 'bg-red-50 text-red-700 border-red-200', dot: 'bg-red-500', label: '失败' },
  }
  const cfg = map[status] || map.paused
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${cfg.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

function TaskTypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    preprocessing: 'bg-purple-100 text-purple-700',
    training: 'bg-blue-100 text-blue-700',
    pipeline: 'bg-cyan-100 text-cyan-700',
  }
  const label: Record<string, string> = {
    preprocessing: '预处理',
    training: '训练',
    pipeline: '管道',
  }
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${map[type] || 'bg-slate-100 text-slate-600'}`}>
      {label[type] || type}
    </span>
  )
}

function ExecStatusBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string; pulse?: boolean }> = {
    SUCCESS: { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', label: '成功' },
    FAILED:  { cls: 'bg-red-50 text-red-700 border-red-200', label: '失败' },
    RUNNING: { cls: 'bg-blue-50 text-blue-700 border-blue-200', label: '运行中', pulse: true },
  }
  const cfg = map[status] || { cls: 'bg-slate-100 text-slate-600 border-slate-200', label: status }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${cfg.cls}`}>
      {cfg.pulse && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />}
      {cfg.label}
    </span>
  )
}

// ============ CronInput 组件 ============
function CronInput({
  value, onChange, error, nextRunTime,
}: {
  value: string
  onChange: (v: string) => void
  error?: string | null
  nextRunTime?: string | null
}) {
  const [localValue, setLocalValue] = useState(value)
  const [validating, setValidating] = useState(false)
  const [localNextRun, setLocalNextRun] = useState<string | null>(nextRunTime || null)
  const [localError, setLocalError] = useState<string | null>(error || null)

  // debounce 300ms 后校验
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (!localValue.trim()) {
        setLocalError(null)
        setLocalNextRun(null)
        return
      }
      setValidating(true)
      try {
        const res = await schedulerApi.validateCron(localValue)
        if (res.data.valid) {
          setLocalError(null)
          setLocalNextRun(res.data.next_run_time || null)
          onChange(localValue)
        } else {
          setLocalError(res.data.error || '无效的 Cron 表达式')
          setLocalNextRun(null)
        }
      } catch {
        setLocalError('校验失败')
        setLocalNextRun(null)
      } finally {
        setValidating(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [localValue])

  const handlePreset = (cron: string) => {
    setLocalValue(cron)
    onChange(cron)
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          type="text"
          value={localValue}
          onChange={e => setLocalValue(e.target.value)}
          placeholder="* * * * *（分 时 日 月 周）"
          className={`flex-1 font-mono text-sm border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 ${
            (error || localError) ? 'border-red-500' : 'border-slate-200'
          }`}
        />
        {validating && <LoaderCircle className="w-5 h-5 text-slate-400 animate-spin" />}
      </div>

      {/* 预设快捷按钮 */}
      <div className="flex flex-wrap gap-1">
        {CRON_PRESETS.map(p => (
          <button
            key={p.value}
            type="button"
            onClick={() => handlePreset(p.value)}
            className="px-2 py-0.5 rounded text-xs border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* 预览下次执行时间 */}
      {localNextRun && (
        <p className="text-xs text-emerald-600 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          下次执行：{localNextRun}
        </p>
      )}
      {(error || localError) && (
        <p className="text-xs text-red-500">{error || localError}</p>
      )}
    </div>
  )
}

// ============ JobModal 组件 ============
function JobModal({
  open, mode, job, onClose, onSuccess,
}: {
  open: boolean
  mode: 'create' | 'edit'
  job: Job | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [name, setName] = useState('')
  const [jobType, setJobType] = useState<'preprocessing' | 'training' | 'pipeline'>('training')
  const [targetId, setTargetId] = useState<string>('')
  const [cron, setCron] = useState('0 8 * * *')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [isEnabled, setIsEnabled] = useState(true)
  const [params, setParams] = useState('')
  const [cronError, setCronError] = useState<string | null>(null)
  const [nextRunTime] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  // 填充表单（编辑模式）
  useEffect(() => {
    if (mode === 'edit' && job) {
      setName(job.name)
      setJobType(job.job_type as any)
      setTargetId(job.target_id?.toString() || '')
      setCron(job.cron_expression)
      setWebhookUrl(job.webhook_url || '')
      setRetryCount(job.retry_count)
      setIsEnabled(job.is_enabled)
      setParams(JSON.stringify(job.params || {}, null, 2))
    } else if (mode === 'create') {
      setName('')
      setJobType('training')
      setTargetId('')
      setCron('0 8 * * *')
      setWebhookUrl('')
      setRetryCount(0)
      setIsEnabled(true)
      setParams('')
    }
    setFormError(null)
    setCronError(null)
  }, [mode, job, open])

  const handleSubmit = async () => {
    if (!name.trim()) { setFormError('任务名称不能为空'); return }
    if (!cron.trim()) { setFormError('Cron 表达式不能为空'); return }
    if (['preprocessing', 'training'].includes(jobType) && !targetId) {
      setFormError('请填写关联任务 ID'); return
    }

    setSubmitting(true)
    setFormError(null)
    try {
      let parsedParams: Record<string, any> = {}
      if (params.trim()) {
        try { parsedParams = JSON.parse(params) } catch { parsedParams = {} }
      }

      if (mode === 'create') {
        await schedulerApi.create({
          name: name.trim(),
          job_type: jobType,
          target_id: targetId ? parseInt(targetId) : undefined,
          cron_expression: cron,
          webhook_url: webhookUrl || undefined,
          retry_count: retryCount,
          is_enabled: isEnabled,
          params: parsedParams,
        })
      } else if (job) {
        await schedulerApi.update(job.id, {
          name: name.trim(),
          cron_expression: cron,
          webhook_url: webhookUrl || undefined,
          retry_count: retryCount,
          is_enabled: isEnabled,
          params: parsedParams,
        })
      }
      onSuccess()
    } catch (e: any) {
      setFormError(e.response?.data?.detail || '提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">
            {mode === 'create' ? '新建定时任务' : `编辑定时任务 — ${job?.name || ''}`}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Form */}
        <div className="px-6 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {formError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
              {formError}
            </div>
          )}

          {/* 任务名称 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">任务名称 <span className="text-red-500">*</span></label>
            <input
              type="text" value={name} onChange={e => setName(e.target.value)}
              placeholder="输入任务名称" maxLength={128}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* 任务类型 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">任务类型 <span className="text-red-500">*</span></label>
            {mode === 'edit' ? (
              <input type="text" value={jobType} readOnly disabled
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-500" />
            ) : (
              <select value={jobType} onChange={e => setJobType(e.target.value as any)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
                <option value="preprocessing">预处理（preprocessing）</option>
                <option value="training">训练（training）</option>
                <option value="pipeline">管道（pipeline）</option>
              </select>
            )}
          </div>

          {/* 关联任务 ID */}
          {mode === 'create' && jobType !== 'pipeline' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                关联任务 ID <span className="text-red-500">*</span>
              </label>
              <input
                type="number" value={targetId} onChange={e => setTargetId(e.target.value)}
                placeholder={`输入 ${jobType === 'preprocessing' ? '预处理' : '训练'} 任务 ID`}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          )}

          {/* Cron 表达式 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Cron 表达式 <span className="text-red-500">*</span></label>
            <CronInput
              value={cron}
              onChange={v => setCron(v)}
              error={cronError}
              nextRunTime={nextRunTime}
            />
            <p className="text-xs text-slate-400 mt-1">格式：分(0-59) 时(0-23) 日(1-31) 月(1-12) 周(0-6/日-6)</p>
          </div>

          {/* 任务参数字段 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              任务参数（JSON，选填）
            </label>
            <textarea
              value={params} onChange={e => setParams(e.target.value)}
              placeholder='{"target_column": "label", "task_type": "classification"}'
              rows={3}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
            />
          </div>

          {/* 飞书 WebHook */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">飞书 WebHook URL（选填）</label>
            <input
              type="url" value={webhookUrl} onChange={e => setWebhookUrl(e.target.value)}
              placeholder="https://open.feishu.cn/..."
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <p className="text-xs text-slate-400 mt-1">仅支持 https://，用于任务失败时发送告警</p>
          </div>

          {/* 失败重试次数 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">失败重试次数（选填）</label>
            <input
              type="number" value={retryCount} onChange={e => setRetryCount(parseInt(e.target.value) || 0)}
              min={0} max={5}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* 启用开关 */}
          {mode === 'edit' && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setIsEnabled(!isEnabled)}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${isEnabled ? 'bg-emerald-500' : 'bg-slate-300'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${isEnabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
              </button>
              <span className="text-sm text-slate-700">{isEnabled ? '启用任务' : '暂停任务'}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-200">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            disabled={submitting}
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            {submitting && <LoaderCircle className="w-3.5 h-3.5 animate-spin" />}
            {mode === 'create' ? '创建' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============ HistoryDrawer 组件 ============
function HistoryDrawer({
  job, open, onClose,
}: {
  job: Job | null
  open: boolean
  onClose: () => void
}) {
  const [history, setHistory] = useState<Execution[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [expandedError, setExpandedError] = useState<string | null>(null)
  const PAGE_SIZE_H = 20

  useEffect(() => {
    if (open && job) {
      fetchHistory(job.id, 1)
    }
  }, [open, job])

  const fetchHistory = async (jobId: string, p: number) => {
    setLoading(true)
    try {
      const res = await schedulerApi.history(jobId, { page: p, page_size: PAGE_SIZE_H })
      setHistory(res.data.data)
      setTotal(res.data.total)
      setPage(p)
    } catch {
      setHistory([])
    } finally {
      setLoading(false)
    }
  }

  if (!open || !job) return null

  const successCount = history.filter(e => e.status === 'SUCCESS').length
  const failedCount = history.filter(e => e.status === 'FAILED').length
  const runningCount = history.filter(e => e.status === 'RUNNING').length
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE_H))

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-2xl bg-white shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{job.name} — 执行历史</h2>
            <p className="text-xs text-slate-500 mt-0.5">最近 100 条记录</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Stats */}
        <div className="px-6 py-3 bg-slate-50 border-b border-slate-100 flex gap-6 text-sm">
          <span>成功：<strong className="text-emerald-600">{successCount}</strong></span>
          <span>失败：<strong className="text-red-600">{failedCount}</strong></span>
          <span>运行中：<strong className="text-blue-600">{runningCount}</strong></span>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <LoaderCircle className="w-6 h-6 animate-spin text-slate-400" />
            </div>
          ) : history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <History className="w-10 h-10 mb-3 opacity-40" />
              <p>暂无执行记录</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white z-10 border-b border-slate-100">
                <tr>
                  <th className="text-left py-2.5 px-4 font-medium text-slate-500 text-xs">执行时间</th>
                  <th className="text-left py-2.5 px-4 font-medium text-slate-500 text-xs">耗时</th>
                  <th className="text-left py-2.5 px-4 font-medium text-slate-500 text-xs">状态</th>
                  <th className="text-left py-2.5 px-4 font-medium text-slate-500 text-xs">触发</th>
                  <th className="text-left py-2.5 px-4 font-medium text-slate-500 text-xs">操作</th>
                </tr>
              </thead>
              <tbody>
                {history.map(exec => (
                  <Fragment key={exec.id}>
                    <tr className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                      <td className="py-3 px-4 font-mono text-xs text-slate-600 whitespace-nowrap">
                        {formatDateTime(exec.started_at)}
                      </td>
                      <td className="py-3 px-4 text-slate-600">
                        {exec.status === 'RUNNING' ? (
                          <span className="text-blue-600 flex items-center gap-1">
                            <LoaderCircle className="w-3 h-3 animate-spin" />运行中...
                          </span>
                        ) : formatDuration(exec.duration_seconds)}
                      </td>
                      <td className="py-3 px-4"><ExecStatusBadge status={exec.status} /></td>
                      <td className="py-3 px-4">
                        <span className="text-xs text-slate-500">
                          {exec.triggered_by === 'manual' ? '手动' : '定时'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {exec.status === 'FAILED' && (
                          <button
                            onClick={() => setExpandedError(expandedError === exec.id ? null : exec.id)}
                            className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1"
                          >
                            <AlertTriangle className="w-3 h-3" />
                            {expandedError === exec.id ? '收起' : '查看日志'}
                          </button>
                        )}
                      </td>
                    </tr>
                    {expandedError === exec.id && exec.error_message && (
                      <tr key={`${exec.id}-error`} className="bg-red-50">
                        <td colSpan={5} className="px-4 py-3">
                          <pre className="text-xs font-mono text-red-700 bg-white border border-red-200 rounded p-3 overflow-x-auto whitespace-pre-wrap">
                            {exec.error_message}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-center gap-2">
            <button onClick={() => job && fetchHistory(job.id, page - 1)} disabled={page === 1}
              className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm text-slate-600">{page} / {totalPages}</span>
            <button onClick={() => job && fetchHistory(job.id, page + 1)} disabled={page >= totalPages}
              className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </>
  )
}

// ============ ConfirmModal ============
function ConfirmModal({
  open, job, onClose, onConfirm,
}: {
  open: boolean
  job: Job | null
  onClose: () => void
  onConfirm: () => void
}) {
  const [loading, setLoading] = useState(false)

  if (!open || !job) return null

  const handleConfirm = async () => {
    setLoading(true)
    try { await onConfirm() } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-auto p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-2">确认删除任务</h3>
        <p className="text-sm text-slate-600 mb-1">
          确定要删除任务「<strong>{job.name}</strong>」吗？删除后：
        </p>
        <ul className="text-sm text-slate-500 mb-4 list-disc pl-4">
          <li>所有执行历史将被清除</li>
          <li>正在运行的任务将立即停止</li>
        </ul>
        <p className="text-sm text-red-500 mb-4">此操作不可撤销。</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} disabled={loading}
            className="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50">
            取消
          </button>
          <button onClick={handleConfirm} disabled={loading}
            className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 disabled:opacity-50 flex items-center gap-1.5">
            {loading && <LoaderCircle className="w-3.5 h-3.5 animate-spin" />}
            删除
          </button>
        </div>
      </div>
    </div>
  )
}

// ============ 主组件 ============
export default function Scheduler() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)

  // Filter
  const [statusFilter, setStatusFilter] = useState('')
  const [keyword, setKeyword] = useState('')

  // Modals
  const [jobModal, setJobModal] = useState<{ open: boolean; mode: 'create' | 'edit'; job: Job | null }>({
    open: false, mode: 'create', job: null,
  })
  const [deleteModal, setDeleteModal] = useState<{ open: boolean; job: Job | null }>({
    open: false, job: null,
  })
  const [historyDrawer, setHistoryDrawer] = useState<{ open: boolean; job: Job | null }>({
    open: false, job: null,
  })

  // Toast
  const [toast, setToast] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)

  const showToast = (type: 'success' | 'error', msg: string) => {
    setToast({ type, msg })
    setTimeout(() => setToast(null), 4000)
  }

  const fetchJobs = useCallback(async (p: number) => {
    setLoading(true)
    setFetchError(null)
    try {
      const res = await schedulerApi.list({
        page: p,
        page_size: PAGE_SIZE,
        status: statusFilter || undefined,
        keyword: keyword || undefined,
      })
      setJobs(res.data.data)
      setTotal(res.data.total)
      setPage(p)
    } catch (e: any) {
      setFetchError('加载失败，请重试')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, keyword])

  useEffect(() => { fetchJobs(1) }, [statusFilter, keyword])

  // 分页
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const goPage = (p: number) => fetchJobs(Math.max(1, Math.min(p, totalPages)))

  // 操作处理
  const handleTrigger = async (job: Job) => {
    try {
      await schedulerApi.trigger(job.id)
      showToast('success', `任务「${job.name}」已触发，将在后台执行`)
      // 3秒后刷新历史
      setTimeout(() => {
        if (historyDrawer.open) {
          setHistoryDrawer(d => ({ ...d, open: false }))
          setTimeout(() => setHistoryDrawer({ open: true, job }), 300)
        }
      }, 3000)
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || '触发失败')
    }
  }

  const handlePauseResume = async (job: Job) => {
    const newStatus = job.status === 'active' ? 'paused' : 'active'
    try {
      await schedulerApi.update(job.id, { status: newStatus })
      showToast('success', newStatus === 'paused' ? '任务已暂停' : '任务已恢复')
      fetchJobs(page)
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || '操作失败')
    }
  }

  const handleDelete = async () => {
    if (!deleteModal.job) return
    try {
      await schedulerApi.delete(deleteModal.job.id)
      showToast('success', '任务已删除')
      setDeleteModal({ open: false, job: null })
      fetchJobs(page)
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || '删除失败')
    }
  }

  // 统计
  const activeCount = jobs.filter(j => j.status === 'active').length
  const failedCount = jobs.filter(j => j.status === 'failed').length

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg text-sm font-medium shadow-lg flex items-center gap-2 max-w-sm ${
          toast.type === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {toast.type === 'success' ? '✓' : '✗'}
          {toast.msg}
        </div>
      )}

      {/* PageHeader */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
            <Clock className="w-6 h-6" />
            任务调度
          </h1>
          <p className="text-slate-500 mt-1">管理自动化定时任务，监控执行状态</p>
        </div>
        <Button onClick={() => setJobModal({ open: true, mode: 'create', job: null })}>
          <Plus className="w-4 h-4" />
          新建任务
        </Button>
      </div>

      {/* StatsBar */}
      <div className="flex items-center gap-8">
        {[
          { label: '任务总数', value: total, cls: 'text-slate-900' },
          { label: '活跃任务', value: activeCount, cls: 'text-emerald-600' },
          { label: '失败任务', value: failedCount, cls: 'text-red-600' },
        ].map(s => (
          <div key={s.label} className="text-center">
            <div className={`text-2xl font-bold ${s.cls}`}>{s.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* FilterBar */}
      <Card>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1 min-w-[160px]">
            <label className="text-xs font-medium text-slate-500">状态筛选</label>
            <select
              value={statusFilter}
              onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
            >
              <option value="">全部</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
            <label className="text-xs font-medium text-slate-500">关键词搜索</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text" value={keyword}
                  onChange={e => setKeyword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && fetchJobs(1)}
                  placeholder="搜索任务名称"
                  className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>
          <button
            onClick={() => fetchJobs(page)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            刷新
          </button>
        </div>
      </Card>

      {/* Table */}
      <Card>
        {fetchError ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-600 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            {fetchError}
            <button onClick={() => fetchJobs(page)} className="ml-auto underline">重试</button>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-16">
            <LoaderCircle className="w-6 h-6 animate-spin text-slate-400" />
            <span className="ml-2 text-slate-500">加载中...</span>
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Clock className="w-12 h-12 mb-3 opacity-40" />
            <p className="text-base font-medium">暂无定时任务</p>
            <p className="text-sm mt-1">创建第一个自动化任务，系统将按设定时间自动执行</p>
            <Button onClick={() => setJobModal({ open: true, mode: 'create', job: null })} className="mt-4">
              <Plus className="w-4 h-4" />
              新建任务
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  {['任务名称', '类型', 'Cron', '状态', '下次执行', '创建时间', '操作'].map(h => (
                    <th key={h} className="text-left py-3 px-3 font-medium text-slate-500 text-xs uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className={`border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors ${
                      job.status === 'failed' ? 'border-l-3 border-red-400' :
                      job.status === 'active' ? 'border-l-3 border-transparent' : ''
                    }`}
                  >
                    <td className="py-3 px-3 font-medium text-slate-900 whitespace-nowrap min-w-36">{job.name}</td>
                    <td className="py-3 px-3 whitespace-nowrap"><TaskTypeBadge type={job.job_type} /></td>
                    <td className="py-3 px-3 font-mono text-xs text-slate-600 whitespace-nowrap min-w-32">{job.cron_expression}</td>
                    <td className="py-3 px-3 whitespace-nowrap"><StatusBadge status={job.status} /></td>
                    <td className="py-3 px-3 font-mono text-xs text-slate-600 whitespace-nowrap w-40">
                      {job.next_run_time ? formatDateTime(job.next_run_time) : '—'}
                    </td>
                    <td className="py-3 px-3 text-slate-500 whitespace-nowrap w-36">{formatDate(job.created_at)}</td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        {/* 编辑 */}
                        <button
                          onClick={() => setJobModal({ open: true, mode: 'edit', job })}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                          title="编辑"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        {/* 暂停/恢复 */}
                        <button
                          onClick={() => handlePauseResume(job)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                          title={job.status === 'active' ? '暂停' : '恢复'}
                        >
                          {job.status === 'active' ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                        </button>
                        {/* 手动触发 */}
                        <button
                          onClick={() => handleTrigger(job)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                          title="手动触发"
                        >
                          <Zap className="w-3.5 h-3.5" />
                        </button>
                        {/* 历史 */}
                        <button
                          onClick={() => setHistoryDrawer({ open: true, job })}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                          title="执行历史"
                        >
                          <History className="w-3.5 h-3.5" />
                        </button>
                        {/* 删除 */}
                        <button
                          onClick={() => setDeleteModal({ open: true, job })}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                          title="删除"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => goPage(1)} disabled={page === 1}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50" title="首页">
            <ChevronsLeft className="w-4 h-4" />
          </button>
          <button onClick={() => goPage(page - 1)} disabled={page === 1}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50" title="上一页">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
              let p: number
              if (totalPages <= 7) p = i + 1
              else if (page <= 4) p = i + 1
              else if (page >= totalPages - 3) p = totalPages - 6 + i
              else p = page - 3 + i
              return (
                <button key={p} onClick={() => goPage(p)}
                  className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                    page === p ? 'bg-primary-500 text-white' : 'text-slate-600 hover:bg-slate-100'
                  }`}>
                  {p}
                </button>
              )
            })}
          </div>
          <button onClick={() => goPage(page + 1)} disabled={page >= totalPages}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50" title="下一页">
            <ChevronRight className="w-4 h-4" />
          </button>
          <button onClick={() => goPage(totalPages)} disabled={page >= totalPages}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50" title="末页">
            <ChevronsRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Modals */}
      <JobModal
        open={jobModal.open}
        mode={jobModal.mode}
        job={jobModal.job}
        onClose={() => setJobModal(m => ({ ...m, open: false }))}
        onSuccess={() => {
          setJobModal(m => ({ ...m, open: false }))
          fetchJobs(page)
        }}
      />

      <HistoryDrawer
        job={historyDrawer.job}
        open={historyDrawer.open}
        onClose={() => setHistoryDrawer(d => ({ ...d, open: false }))}
      />

      <ConfirmModal
        open={deleteModal.open}
        job={deleteModal.job}
        onClose={() => setDeleteModal({ open: false, job: null })}
        onConfirm={handleDelete}
      />
    </div>
  )
}
