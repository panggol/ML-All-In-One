/**
 * Pipelines.tsx — Pipeline 编排管理页面
 *
 * 功能：
 * - Pipeline 列表（卡片/表格视图，创建/编辑/删除）
 * - Pipeline 编辑器（JSON/YAML DSL 编辑器，支持语法高亮）
 * - Run 历史（状态列表：pending/running/success/failed）
 * - 单次 Run 详情（步骤状态 + DAG 可视化）
 * - Cron 调度配置
 */
import { useState, useEffect, useCallback, Fragment, useMemo } from 'react'
import {
  GitBranch, Plus, Pencil, Trash2, X, Search,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  LoaderCircle, RefreshCw, Play, Pause, Clock, Check,
  AlertCircle, SkipForward, Eye, EyeOff, Code2, LayoutGrid,
  ArrowRight, CheckCircle2, XCircle, Timer, RotateCcw,
  Zap, Database, Wand, Cpu, BarChart3, Package, Tag,
} from 'lucide-react'
import {
  pipelinesApi,
  type Pipeline, type PipelineRun, type PipelineStepRun,
  type PipelineVersion, type ScheduleConfig,
  type PipelineStatus, type RunStatus, type StepStatus,
  type PipelineDSL, type PipelineStep,
} from '../api/pipelines'
import Card from '../components/Card'
import Button from '../components/Button'

// ============ 常量 ============
const PAGE_SIZE = 20

// Cron 预设
const CRON_PRESETS = [
  { label: '每天 08:00', value: '0 8 * * *' },
  { label: '每小时整点', value: '0 * * * *' },
  { label: '每周一 00:00', value: '0 0 * * 1' },
  { label: '每天凌晨 02:00', value: '0 2 * * *' },
  { label: '每 30 分钟', value: '*/30 * * * *' },
  { label: '每 15 分钟', value: '*/15 * * * *' },
]

// 步骤类型中文映射
const STEP_TYPE_LABELS: Record<string, string> = {
  preprocessing: '预处理',
  feature_engineering: '特征工程',
  training: '训练',
  automl: 'AutoML',
  evaluation: '评估',
  model_registration: '模型注册',
}

const STEP_TYPE_ICONS: Record<string, React.FC<{ className?: string }>> = {
  preprocessing: Wand,
  feature_engineering: Database,
  training: Zap,
  automl: Cpu,
  evaluation: BarChart3,
  model_registration: Package,
}

// ============ 工具函数 ============
function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch { return iso }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
    })
  } catch { return iso }
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}分${s}秒` : `${m}分`
}

// ============ Badge 组件 ============
function StatusBadge({ status }: { status: PipelineStatus | string }) {
  const cfg: Record<string, { cls: string; dot: string; label: string }> = {
    draft:    { cls: 'bg-slate-100 text-slate-600 border-slate-200', dot: 'bg-slate-400', label: '草稿' },
    active:   { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: 'bg-emerald-500', label: '已激活' },
    archived: { cls: 'bg-amber-50 text-amber-700 border-amber-200', dot: 'bg-amber-500', label: '已归档' },
  }
  const c = cfg[status] || cfg.draft
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${c.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  )
}

function RunStatusBadge({ status }: { status: RunStatus | string }) {
  const cfg: Record<string, { cls: string; label: string; pulse?: boolean }> = {
    pending:   { cls: 'bg-slate-100 text-slate-600 border-slate-200', label: '等待中' },
    running:   { cls: 'bg-blue-50 text-blue-700 border-blue-200', label: '运行中', pulse: true },
    success:   { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', label: '成功' },
    failed:    { cls: 'bg-red-50 text-red-700 border-red-200', label: '失败' },
    timeout:   { cls: 'bg-amber-50 text-amber-700 border-amber-200', label: '超时' },
    cancelled: { cls: 'bg-slate-100 text-slate-500 border-slate-200', label: '已取消' },
  }
  const c = cfg[status] || cfg.pending
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${c.cls}`}>
      {status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />}
      {c.label}
    </span>
  )
}

function StepStatusBadge({ status }: { status: StepStatus | string }) {
  const cfg: Record<string, { cls: string; label: string }> = {
    pending:   { cls: 'bg-slate-100 text-slate-600', label: '等待' },
    running:   { cls: 'bg-blue-100 text-blue-700', label: '运行' },
    success:   { cls: 'bg-emerald-100 text-emerald-700', label: '成功' },
    failed:    { cls: 'bg-red-100 text-red-700', label: '失败' },
    skipped:   { cls: 'bg-amber-100 text-amber-700', label: '跳过' },
    timeout:   { cls: 'bg-orange-100 text-orange-700', label: '超时' },
  }
  const c = cfg[status] || cfg.pending
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${c.cls}`}>
      {c.label}
    </span>
  )
}

// ============ DAG 可视化组件 ============
interface DAGNode {
  name: string
  type: string
  status: StepStatus | string
  order_index: number
  depends_on: string[]
  error_message?: string | null
}

interface DAGEdge {
  from: string
  to: string
}

function DAGVisualization({ steps, stepRuns }: {
  steps: PipelineStep[]
  stepRuns: PipelineStepRun[]
}) {
  // 构建节点和边
  const nodes: DAGNode[] = steps.map((s, i) => {
    const run = stepRuns.find(r => r.step_name === s.name)
    return {
      name: s.name,
      type: s.type,
      status: run?.status || 'pending',
      order_index: run?.order_index ?? i,
      depends_on: s.depends_on,
      error_message: run?.error_message,
    }
  })

  // 拓扑排序顺序排列
  const sorted = [...nodes].sort((a, b) => a.order_index - b.order_index)

  // 计算层级（基于依赖深度）
  const levels = useMemo(() => {
    const depth: Record<string, number> = {}
    for (const n of sorted) {
      if (n.depends_on.length === 0) {
        depth[n.name] = 0
      } else {
        depth[n.name] = Math.max(...n.depends_on.map(d => (depth[d] ?? 0) + 1))
      }
    }
    return depth
  }, [sorted])

  // 构建边
  const edges: DAGEdge[] = []
  for (const n of nodes) {
    for (const dep of n.depends_on) {
      edges.push({ from: dep, to: n.name })
    }
  }

  const maxLevel = Math.max(...Object.values(levels), 0)

  // 节点宽高
  const NODE_W = 140
  const NODE_H = 52
  const GAP_X = 60
  const GAP_Y = 40
  const svgW = (maxLevel + 1) * (NODE_W + GAP_X) + GAP_X
  const svgH = Math.max(nodes.length, 1) * (NODE_H + GAP_Y) + GAP_Y

  // 计算每个节点的 x, y
  const nodePos: Record<string, { x: number; y: number }> = {}
  const levelGroups: Record<number, string[]> = {}
  for (const n of sorted) {
    const lv = levels[n.name]
    if (!levelGroups[lv]) levelGroups[lv] = []
    levelGroups[lv].push(n.name)
  }
  for (const [lv, names] of Object.entries(levelGroups)) {
    const l = parseInt(lv)
    const x = GAP_X + l * (NODE_W + GAP_X)
    names.forEach((name, idx) => {
      const y = GAP_Y + idx * (NODE_H + GAP_Y)
      nodePos[name] = { x, y }
    })
  }

  // 状态颜色
  const statusColor: Record<string, string> = {
    pending:   '#94a3b8',
    running:   '#3b82f6',
    success:   '#10b981',
    failed:    '#ef4444',
    skipped:   '#f59e0b',
    timeout:   '#f97316',
  }

  return (
    <div className="overflow-x-auto py-2">
      <svg width={Math.max(svgW, 400)} height={svgH} className="block">
        {/* 边 */}
        {edges.map((e, i) => {
          const from = nodePos[e.from]
          const to = nodePos[e.to]
          if (!from || !to) return null
          const x1 = from.x + NODE_W
          const y1 = from.y + NODE_H / 2
          const x2 = to.x
          const y2 = to.y + NODE_H / 2
          const cx = (x1 + x2) / 2
          return (
            <g key={i}>
              <path
                d={`M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`}
                stroke="#cbd5e1"
                strokeWidth={2}
                fill="none"
                markerEnd="url(#arrowhead)"
              />
            </g>
          )
        })}
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
          </marker>
        </defs>
        {/* 节点 */}
        {sorted.map(n => {
          const pos = nodePos[n.name]
          if (!pos) return null
          const color = statusColor[n.status] || statusColor.pending
          const Icon = STEP_TYPE_ICONS[n.type] || GitBranch
          return (
            <g key={n.name} transform={`translate(${pos.x}, ${pos.y})`}>
              <rect
                width={NODE_W} height={NODE_H}
                rx={8}
                fill="white"
                stroke={color}
                strokeWidth={2}
              />
              {/* 顶部状态条 */}
              <rect width={NODE_W} height={4} rx={2} fill={color} />
              <foreignObject x={6} y={10} width={NODE_W - 12} height={NODE_H - 16}>
                <div className="flex flex-col items-center justify-center h-full gap-0.5">
                  <div className="flex items-center gap-1">
                    <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color }} />
                    <span className="text-xs font-semibold text-slate-800 truncate max-w-full">{n.name}</span>
                  </div>
                  <span className="text-xs text-slate-400 truncate max-w-full">
                    {STEP_TYPE_LABELS[n.type] || n.type}
                  </span>
                </div>
              </foreignObject>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ============ JSON/YAML 编辑器组件 ============
function CodeEditor({ value, onChange, format }: {
  value: string
  onChange: (v: string) => void
  format: 'json' | 'yaml'
}) {
  const [localValue, setLocalValue] = useState(value)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { setLocalValue(value) }, [value])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value
    setLocalValue(v)
    try {
      if (format === 'json') JSON.parse(v)
      setError(null)
      onChange(v)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleFormat = () => {
    try {
      if (format === 'json') {
        const parsed = JSON.parse(localValue)
        const formatted = JSON.stringify(parsed, null, 2)
        setLocalValue(formatted)
        setError(null)
        onChange(formatted)
      }
    } catch (err: any) {
      setError(err.message)
    }
  }

  // 简单语法高亮（行号 + 高亮关键字）
  const highlighted = useMemo(() => {
    if (format === 'json') {
      try {
        const parsed = JSON.parse(localValue)
        return JSON.stringify(parsed, null, 2)
      } catch {
        return localValue
      }
    }
    return localValue
  }, [localValue, format])

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          {format === 'json' ? 'JSON' : 'YAML'} DSL
        </span>
        <div className="flex gap-2">
          {error && (
            <span className="text-xs text-red-500 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              格式错误
            </span>
          )}
          <button
            onClick={handleFormat}
            className="text-xs text-slate-500 hover:text-slate-700 px-2 py-0.5 rounded border border-slate-200 hover:bg-slate-50"
          >
            格式化
          </button>
        </div>
      </div>
      <div className="relative flex-1">
        {/* 行号 */}
        <div className="absolute left-0 top-0 bottom-0 w-10 bg-slate-50 border-r border-slate-200 overflow-hidden pointer-events-none flex flex-col pt-3">
          {localValue.split('\n').map((_, i) => (
            <span key={i} className="text-xs text-slate-400 leading-6 pl-2">{i + 1}</span>
          ))}
        </div>
        <textarea
          value={localValue}
          onChange={handleChange}
          spellCheck={false}
          className={`w-full font-mono text-xs leading-6 pl-12 pr-3 py-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[240px] ${
            error ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'
          }`}
          style={{ tabSize: 2 }}
        />
      </div>
      {error && (
        <p className="text-xs text-red-500 font-mono bg-red-50 rounded px-2 py-1 border border-red-200">
          {error}
        </p>
      )}
    </div>
  )
}

// ============ DSL 示例模板 ============
const DEFAULT_DSL_JSON = JSON.stringify({
  steps: [
    {
      name: "load_data",
      type: "preprocessing",
      config: { dataset_path: "/data/sample.csv" },
      depends_on: [],
      timeout_seconds: 300,
    },
    {
      name: "feature_engineering",
      type: "feature_engineering",
      config: { method: "standard_scaler" },
      depends_on: ["load_data"],
      timeout_seconds: 300,
    },
    {
      name: "train_model",
      type: "training",
      config: { algorithm: "random_forest", n_estimators: 100 },
      depends_on: ["feature_engineering"],
      timeout_seconds: 1800,
    },
    {
      name: "evaluate_model",
      type: "evaluation",
      config: { metrics: ["accuracy", "f1"] },
      depends_on: ["train_model"],
      timeout_seconds: 600,
    },
  ],
}, null, 2)

// ============ 主页面组件 ============
export default function Pipelines() {
  // ── 列表视图状态 ──────────────────────────────────────────────────────
  const [pipelines, setPipelines] = useState<Pipeline[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [viewMode, setViewMode] = useState<'card' | 'table'>('card')
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  // ── 编辑器状态 ─────────────────────────────────────────────────────────
  const [editPipeline, setEditPipeline] = useState<Pipeline | null>(null)
  const [editorDslContent, setEditorDslContent] = useState(DEFAULT_DSL_JSON)
  const [editorDslFormat, setEditorDslFormat] = useState<'json' | 'yaml'>('json')
  const [editorDescription, setEditorDescription] = useState('')
  const [editorChangelog, setEditorChangelog] = useState('')
  const [editorSaving, setEditorSaving] = useState(false)

  // ── 调度配置状态 ───────────────────────────────────────────────────────
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig | null>(null)
  const [scheduleCron, setScheduleCron] = useState('')
  const [scheduleEnabled, setScheduleEnabled] = useState(false)
  const [scheduleSaving, setScheduleSaving] = useState(false)

  // ── Run 详情状态 ───────────────────────────────────────────────────────
  const [runHistory, setRunHistory] = useState<PipelineRun[]>([])
  const [runHistoryTotal, setRunHistoryTotal] = useState(0)
  const [runHistoryPage, setRunHistoryPage] = useState(1)
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null)
  const [stepRuns, setStepRuns] = useState<PipelineStepRun[]>([])
  const [versions, setVersions] = useState<PipelineVersion[]>([])

  // ── Run 触发 ──────────────────────────────────────────────────────────
  const [triggering, setTriggering] = useState(false)

  // ── 侧边抽屉状态 ──────────────────────────────────────────────────────
  type DrawerTab = 'editor' | 'runs' | 'schedule' | 'run_detail'
  const [drawerPipeline, setDrawerPipeline] = useState<Pipeline | null>(null)
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('editor')

  // ── 加载 Pipeline 列表 ─────────────────────────────────────────────────
  const loadPipelines = useCallback(async () => {
    setLoading(true)
    try {
      const res = await pipelinesApi.list({ page, page_size: PAGE_SIZE, q: q || undefined, status: statusFilter || undefined })
      setPipelines(res.data.data)
      setTotal(res.data.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [page, q, statusFilter])

  useEffect(() => { loadPipelines() }, [loadPipelines])

  // ── 创建 Pipeline ──────────────────────────────────────────────────────
  const handleCreate = async () => {
    setCreating(true)
    try {
      await pipelinesApi.create({
        name: `pipeline_${Date.now()}`,
        description: '',
        dsl_content: DEFAULT_DSL_JSON,
        dsl_format: 'json',
        status: 'draft',
      })
      await loadPipelines()
    } finally {
      setCreating(false)
    }
  }

  // ── 删除 Pipeline ──────────────────────────────────────────────────────
  const handleDelete = async (id: number) => {
    if (!confirm('确定删除该 Pipeline？此操作不可撤销。')) return
    setDeletingId(id)
    try {
      await pipelinesApi.delete(id)
      await loadPipelines()
    } finally {
      setDeletingId(null)
    }
  }

  // ── 打开 Pipeline 编辑器 ───────────────────────────────────────────────
  const openEditor = async (p: Pipeline) => {
    setDrawerPipeline(p)
    setDrawerTab('editor')
    setEditorDslContent(p.dsl_content)
    setEditorDslFormat(p.dsl_format as 'json' | 'yaml')
    setEditorDescription(p.description || '')
    setEditorChangelog('')
    setEditPipeline(p)
  }

  // ── 保存 Pipeline ──────────────────────────────────────────────────────
  const handleSavePipeline = async () => {
    if (!editPipeline) return
    setEditorSaving(true)
    try {
      await pipelinesApi.update(editPipeline.id, {
        dsl_content: editorDslContent,
        description: editorDescription,
        changelog: editorChangelog || undefined,
      })
      // 更新本地状态
      setPipelines(prev => prev.map(p =>
        p.id === editPipeline.id
          ? { ...p, dsl_content: editorDslContent, description: editorDescription, updated_at: new Date().toISOString() }
          : p
      ))
      setEditPipeline(prev => prev ? { ...prev, dsl_content: editorDslContent, description: editorDescription } : null)
      setEditorChangelog('')
    } finally {
      setEditorSaving(false)
    }
  }

  // ── 更新 Pipeline 状态 ─────────────────────────────────────────────────
  const handleUpdateStatus = async (p: Pipeline, newStatus: PipelineStatus) => {
    try {
      await pipelinesApi.update(p.id, { status: newStatus })
      setPipelines(prev => prev.map(pl => pl.id === p.id ? { ...pl, status: newStatus } : pl))
    } catch {}
  }

  // ── 触发 Run ───────────────────────────────────────────────────────────
  const handleTriggerRun = async (p: Pipeline) => {
    setTriggering(true)
    try {
      await pipelinesApi.triggerRun(p.id, {})
      await loadPipelines()
    } catch {} finally {
      setTriggering(false)
    }
  }

  // ── 加载 Run 历史 ──────────────────────────────────────────────────────
  const loadRunHistory = useCallback(async (p: Pipeline) => {
    try {
      const res = await pipelinesApi.listRuns(p.id, { page: runHistoryPage, page_size: 10 })
      setRunHistory(res.data.data)
      setRunHistoryTotal(res.data.total)
    } catch {}
  }, [runHistoryPage])

  // ── 加载 Run 详情 ─────────────────────────────────────────────────────
  const loadRunDetail = async (run: PipelineRun) => {
    try {
      const [stepRunsRes, versionsRes] = await Promise.all([
        pipelinesApi.getRun(run.pipeline_id, run.run_id).then(r => r.data.steps),
        pipelinesApi.listVersions(run.pipeline_id),
      ])
      setStepRuns(stepRunsRes.data || [])
      setVersions(versionsRes.data || [])
    } catch {}
  }

  // ── 打开 Runs 抽屉 ─────────────────────────────────────────────────────
  const openRuns = async (p: Pipeline) => {
    setDrawerPipeline(p)
    setDrawerTab('runs')
    setRunHistoryPage(1)
    setSelectedRun(null)
    await loadRunHistory(p)
  }

  // ── 加载调度配置 ──────────────────────────────────────────────────────
  const loadSchedule = async (p: Pipeline) => {
    setDrawerPipeline(p)
    setDrawerTab('schedule')
    try {
      const res = await pipelinesApi.getSchedule(p.id)
      setScheduleConfig(res.data)
      setScheduleCron(res.data.schedule_cron || '')
      setScheduleEnabled(res.data.schedule_enabled)
    } catch {
      setScheduleCron(p.schedule_cron || '')
      setScheduleEnabled(p.schedule_enabled || false)
    }
  }

  // ── 保存调度配置 ──────────────────────────────────────────────────────
  const handleSaveSchedule = async () => {
    if (!drawerPipeline) return
    setScheduleSaving(true)
    try {
      await pipelinesApi.updateSchedule(drawerPipeline.id, {
        schedule_cron: scheduleCron || null,
        schedule_enabled: scheduleEnabled,
      })
      setPipelines(prev => prev.map(p =>
        p.id === drawerPipeline.id
          ? { ...p, schedule_cron: scheduleCron || null, schedule_enabled: scheduleEnabled }
          : p
      ))
    } finally {
      setScheduleSaving(false)
    }
  }

  // ── 加载版本历史 ──────────────────────────────────────────────────────
  const loadVersions = async (p: Pipeline) => {
    try {
      const res = await pipelinesApi.listVersions(p.id)
      setVersions(res.data || [])
    } catch {}
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const runTotalPages = Math.ceil(runHistoryTotal / 10)

  return (
    <div className="space-y-6">
      {/* ── 页面标题栏 ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Pipeline 编排</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            全量 {total} 个 Pipeline，支持 DSL 编辑、DAG 执行、Run 历史追踪
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* 搜索 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="搜索 Pipeline..."
              value={q}
              onChange={e => { setQ(e.target.value); setPage(1) }}
              className="pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg w-56 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          {/* 状态筛选 */}
          <select
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="active">已激活</option>
            <option value="archived">已归档</option>
          </select>
          {/* 视图切换 */}
          <div className="flex border border-slate-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('card')}
              className={`px-3 py-2 text-xs ${viewMode === 'card' ? 'bg-primary-50 text-primary-700' : 'text-slate-500 hover:bg-slate-50'}`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-2 text-xs border-l border-slate-200 ${viewMode === 'table' ? 'bg-primary-50 text-primary-700' : 'text-slate-500 hover:bg-slate-50'}`}
            >
              <Code2 className="w-4 h-4" />
            </button>
          </div>
          {/* 新建 */}
          <Button
            onClick={handleCreate}
            disabled={creating}
            icon={creating ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          >
            {creating ? '创建中...' : '新建 Pipeline'}
          </Button>
        </div>
      </div>

      {/* ── Pipeline 列表：卡片视图 ────────────────────────────────── */}
      {viewMode === 'card' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-48 bg-slate-100 rounded-xl animate-pulse" />
            ))
          ) : pipelines.length === 0 ? (
            <div className="col-span-full flex flex-col items-center py-16 text-slate-400">
              <GitBranch className="w-12 h-12 mb-3 opacity-40" />
              <p className="font-medium">暂无 Pipeline</p>
              <p className="text-sm mt-1">点击右上角「新建 Pipeline」开始</p>
            </div>
          ) : (
            pipelines.map(p => (
              <Card key={p.id} className="p-5 flex flex-col gap-3 hover:shadow-md transition-shadow">
                {/* 卡片头部 */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <GitBranch className="w-5 h-5 text-primary-500 flex-shrink-0" />
                    <span className="font-semibold text-slate-900 truncate">{p.name}</span>
                  </div>
                  <StatusBadge status={p.status} />
                </div>
                {/* 描述 */}
                <p className="text-sm text-slate-500 line-clamp-2 min-h-[40px]">
                  {p.description || '暂无描述'}
                </p>
                {/* 元信息 */}
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span>v{p.version}</span>
                  <span>·</span>
                  <span>{p.dsl_format.toUpperCase()}</span>
                  {p.schedule_cron && (
                    <>
                      <span>·</span>
                      <Clock className="w-3 h-3" />
                      <span>{p.schedule_cron}</span>
                    </>
                  )}
                </div>
                {/* 操作按钮 */}
                <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
                  <button
                    onClick={() => openEditor(p)}
                    className="flex items-center gap-1 text-xs text-slate-600 hover:text-primary-600 px-2 py-1 rounded hover:bg-primary-50 transition-colors"
                  >
                    <Pencil className="w-3 h-3" />
                    编辑
                  </button>
                  <button
                    onClick={() => openRuns(p)}
                    className="flex items-center gap-1 text-xs text-slate-600 hover:text-primary-600 px-2 py-1 rounded hover:bg-primary-50 transition-colors"
                  >
                    <History className="w-3 h-3" />
                    Runs
                  </button>
                  <button
                    onClick={() => loadSchedule(p)}
                    className="flex items-center gap-1 text-xs text-slate-600 hover:text-primary-600 px-2 py-1 rounded hover:bg-primary-50 transition-colors"
                  >
                    <Clock className="w-3 h-3" />
                    调度
                  </button>
                  <button
                    onClick={() => handleTriggerRun(p)}
                    disabled={triggering}
                    className="flex items-center gap-1 text-xs text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50 transition-colors disabled:opacity-50"
                  >
                    <Play className="w-3 h-3" />
                    触发
                  </button>
                  {p.status !== 'active' && (
                    <button
                      onClick={() => handleUpdateStatus(p, 'active')}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 px-2 py-1 rounded hover:bg-blue-50 transition-colors ml-auto"
                    >
                      <Zap className="w-3 h-3" />
                      激活
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(p.id)}
                    disabled={deletingId === p.id}
                    className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 transition-colors ml-auto disabled:opacity-50"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* ── Pipeline 列表：表格视图 ────────────────────────────────── */}
      {viewMode === 'table' && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-4 py-3 text-left font-medium text-slate-600">名称</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">状态</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">版本</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">格式</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">调度</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">更新时间</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 bg-slate-100 rounded animate-pulse w-24" /></td>
                    ))}
                  </tr>
                ))
              ) : pipelines.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-400">暂无 Pipeline</td>
                </tr>
              ) : (
                pipelines.map(p => (
                  <tr key={p.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900">{p.name}</td>
                    <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
                    <td className="px-4 py-3 text-slate-500">v{p.version}</td>
                    <td className="px-4 py-3 text-slate-500">{p.dsl_format.toUpperCase()}</td>
                    <td className="px-4 py-3 text-slate-500">
                      {p.schedule_cron
                        ? <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{p.schedule_cron}</span>
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(p.updated_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => openEditor(p)} className="p-1.5 rounded hover:bg-primary-50 text-slate-500 hover:text-primary-600">
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => openRuns(p)} className="p-1.5 rounded hover:bg-primary-50 text-slate-500 hover:text-primary-600">
                          <History className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => loadSchedule(p)} className="p-1.5 rounded hover:bg-primary-50 text-slate-500 hover:text-primary-600">
                          <Clock className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleTriggerRun(p)}
                          disabled={triggering}
                          className="p-1.5 rounded hover:bg-emerald-50 text-emerald-500 hover:text-emerald-600 disabled:opacity-50"
                        >
                          <Play className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(p.id)}
                          disabled={deletingId === p.id}
                          className="p-1.5 rounded hover:bg-red-50 text-red-400 hover:text-red-600 disabled:opacity-50"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      )}

      {/* ── 分页 ───────────────────────────────────────────────────── */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">
            第 {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} 条，共 {total} 条
          </span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(1)} disabled={page === 1} className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30">
              <ChevronsLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30">
              <ChevronLeft className="w-4 h-4" />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(1, Math.min(page - 2 + i, totalPages))
              return (
                <button key={p} onClick={() => setPage(p)} className={`w-8 h-8 text-sm rounded ${p === page ? 'bg-primary-500 text-white' : 'hover:bg-slate-100 text-slate-600'}`}>
                  {p}
                </button>
              )
            })}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30">
              <ChevronRight className="w-4 h-4" />
            </button>
            <button onClick={() => setPage(totalPages)} disabled={page === totalPages} className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30">
              <ChevronsRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── 侧边抽屉 ────────────────────────────────────────────────── */}
      {drawerPipeline && (
        <div className="fixed inset-0 z-50 flex">
          {/* 遮罩 */}
          <div className="flex-1 bg-black/30 backdrop-blur-sm" onClick={() => setDrawerPipeline(null)} />

          {/* 抽屉主体 */}
          <div className="w-[900px] max-w-full bg-white shadow-2xl flex flex-col overflow-hidden">
            {/* 抽屉头部 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
              <div>
                <h3 className="text-base font-semibold text-slate-900">{drawerPipeline.name}</h3>
                <div className="flex items-center gap-2 mt-0.5">
                  <StatusBadge status={drawerPipeline.status} />
                  <span className="text-xs text-slate-400">v{drawerPipeline.version}</span>
                </div>
              </div>
              <button
                onClick={() => setDrawerPipeline(null)}
                className="p-2 rounded-lg hover:bg-slate-200 text-slate-500 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 抽屉 Tab 导航 */}
            <div className="flex border-b border-slate-200 px-6 bg-white">
              {([
                { id: 'editor', label: 'DSL 编辑器', icon: Code2 },
                { id: 'runs', label: 'Run 历史', icon: History },
                { id: 'schedule', label: '调度配置', icon: Clock },
              ] as { id: DrawerTab; label: string; icon: React.FC<{ className?: string }> }[]).map(tab => (
                <button
                  key={tab.id}
                  onClick={async () => {
                    setDrawerTab(tab.id)
                    if (tab.id === 'runs') {
                      setRunHistoryPage(1)
                      await loadRunHistory(drawerPipeline)
                    } else if (tab.id === 'schedule') {
                      await loadSchedule(drawerPipeline)
                    } else if (tab.id === 'editor') {
                      await loadVersions(drawerPipeline)
                    }
                  }}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    drawerTab === tab.id
                      ? 'border-primary-500 text-primary-700'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* 抽屉内容 */}
            <div className="flex-1 overflow-y-auto p-6">
              {/* ── DSL 编辑器 ────────────────────────────────────── */}
              {drawerTab === 'editor' && (
                <div className="space-y-5">
                  <div className="flex items-center gap-3">
                    {/* 格式切换 */}
                    <div className="flex border border-slate-200 rounded-lg overflow-hidden">
                      {(['json', 'yaml'] as const).map(fmt => (
                        <button
                          key={fmt}
                          onClick={() => setEditorDslFormat(fmt)}
                          className={`px-3 py-1.5 text-xs font-medium ${editorDslFormat === fmt ? 'bg-primary-50 text-primary-700' : 'text-slate-500 hover:bg-slate-50'}`}
                        >
                          {fmt.toUpperCase()}
                        </button>
                      ))}
                    </div>
                    <span className="text-xs text-slate-400">v{drawerPipeline.version}</span>
                  </div>

                  {/* DSL 编辑器 */}
                  <CodeEditor
                    value={editorDslContent}
                    onChange={setEditorDslContent}
                    format={editorDslFormat}
                  />

                  {/* 变更说明 */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">版本变更说明（可选）</label>
                    <textarea
                      value={editorChangelog}
                      onChange={e => setEditorChangelog(e.target.value)}
                      placeholder="本次修改的变更说明，将记录到版本历史..."
                      rows={2}
                      className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                    />
                  </div>

                  {/* 版本历史 */}
                  {versions.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-slate-700 mb-2">版本历史</h4>
                      <div className="space-y-2">
                        {versions.slice(0, 5).map(v => (
                          <div key={v.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
                            <div>
                              <span className="text-sm font-medium text-slate-700">v{v.version}</span>
                              <span className="text-xs text-slate-400 ml-2">{formatDateTime(v.created_at)}</span>
                            </div>
                            {v.changelog && <p className="text-xs text-slate-500">{v.changelog}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 保存按钮 */}
                  <div className="flex items-center gap-3 pt-2 border-t border-slate-100">
                    <Button
                      onClick={handleSavePipeline}
                      disabled={editorSaving}
                      icon={editorSaving ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                    >
                      {editorSaving ? '保存中...' : '保存 Pipeline'}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => handleUpdateStatus(drawerPipeline, drawerPipeline.status === 'draft' ? 'active' : 'draft')}
                      icon={<Zap className="w-4 h-4" />}
                    >
                      {drawerPipeline.status === 'draft' ? '激活' : '设为草稿'}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => handleTriggerRun(drawerPipeline)}
                      disabled={triggering}
                      icon={triggering ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    >
                      {triggering ? '触发中...' : '手动触发 Run'}
                    </Button>
                  </div>
                </div>
              )}

              {/* ── Run 历史 ──────────────────────────────────────── */}
              {drawerTab === 'runs' && (
                <div className="space-y-4">
                  {/* Run 列表 */}
                  <div className="space-y-2">
                    {runHistory.length === 0 ? (
                      <div className="flex flex-col items-center py-12 text-slate-400">
                        <History className="w-10 h-10 mb-3 opacity-40" />
                        <p className="text-sm">暂无 Run 记录</p>
                      </div>
                    ) : (
                      runHistory.map(run => (
                        <div
                          key={run.id}
                          onClick={() => { setSelectedRun(run); loadRunDetail(run); setDrawerTab('run_detail' as any) }}
                          className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-xl cursor-pointer hover:border-primary-300 hover:shadow-sm transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <RunStatusBadge status={run.status} />
                            <div>
                              <span className="text-sm font-medium text-slate-700">#{run.run_number}</span>
                              <span className="text-xs text-slate-400 ml-2">
                                by {run.triggered_by}
                              </span>
                            </div>
                            <span className="text-xs text-slate-400">v{run.pipeline_version}</span>
                          </div>
                          <div className="flex items-center gap-4 text-xs text-slate-400">
                            <span>{formatDateTime(run.started_at)}</span>
                            <span>{formatDuration(run.duration_seconds)}</span>
                            <span className="w-4 h-4"><ArrowRight className="w-4 h-4" /></span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Run 分页 */}
                  {runTotalPages > 1 && (
                    <div className="flex items-center justify-center gap-2">
                      <button onClick={() => setRunHistoryPage(p => Math.max(1, p - 1))} disabled={runHistoryPage === 1}
                        className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30">
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <span className="text-xs text-slate-500">{runHistoryPage} / {runTotalPages}</span>
                      <button onClick={() => setRunHistoryPage(p => Math.min(runTotalPages, p + 1))} disabled={runHistoryPage === runTotalPages}
                        className="p-1.5 rounded hover:bg-slate-100 disabled:opacity-30">
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* ── Run 详情（DAG 可视化）──────────────────────────── */}
              {drawerTab === 'run_detail' && selectedRun && (
                <div className="space-y-5">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => { setDrawerTab('runs'); setSelectedRun(null) }}
                      className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
                    >
                      <ChevronLeft className="w-4 h-4" />
                      返回 Run 历史
                    </button>
                    <span className="text-slate-300">·</span>
                    <RunStatusBadge status={selectedRun.status} />
                    <span className="text-sm text-slate-600">#{selectedRun.run_number}</span>
                  </div>

                  {/* Run 信息卡片 */}
                  <div className="grid grid-cols-4 gap-3">
                    {[
                      { label: '触发方式', value: selectedRun.triggered_by },
                      { label: 'Pipeline 版本', value: `v${selectedRun.pipeline_version}` },
                      { label: '运行时长', value: formatDuration(selectedRun.duration_seconds) },
                      { label: '开始时间', value: formatDateTime(selectedRun.started_at) },
                    ].map(item => (
                      <div key={item.label} className="bg-slate-50 rounded-lg p-3">
                        <p className="text-xs text-slate-400 mb-1">{item.label}</p>
                        <p className="text-sm font-medium text-slate-700">{item.value}</p>
                      </div>
                    ))}
                  </div>

                  {/* 错误信息 */}
                  {selectedRun.error_message && (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertCircle className="w-4 h-4 text-red-500" />
                        <span className="text-sm font-medium text-red-700">执行错误</span>
                      </div>
                      <p className="text-xs text-red-600 font-mono whitespace-pre-wrap">{selectedRun.error_message}</p>
                    </div>
                  )}

                  {/* DAG 可视化 */}
                  <div>
                    <h4 className="text-sm font-medium text-slate-700 mb-3">DAG 执行图</h4>
                    <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 overflow-x-auto">
                      {(() => {
                        let dsl: PipelineDSL | null = null
                        try {
                          dsl = JSON.parse(drawerPipeline.dsl_content)
                        } catch {
                          dsl = null
                        }
                        if (!dsl || !dsl.steps.length) {
                          return <p className="text-sm text-slate-400 text-center py-8">无法解析 DSL，请检查 DSL 内容</p>
                        }
                        return <DAGVisualization steps={dsl.steps} stepRuns={stepRuns} />
                      })()}
                    </div>
                  </div>

                  {/* 步骤详情列表 */}
                  <div>
                    <h4 className="text-sm font-medium text-slate-700 mb-3">步骤详情</h4>
                    <div className="space-y-2">
                      {stepRuns.length === 0 && (
                        <p className="text-sm text-slate-400 text-center py-6">暂无步骤运行记录</p>
                      )}
                      {stepRuns.map(step => (
                        <div key={step.id} className="border border-slate-200 rounded-xl p-4 bg-white">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              {(() => {
                                const Icon = STEP_TYPE_ICONS[step.step_type] || GitBranch
                                return <Icon className="w-4 h-4 text-slate-400" />
                              })()}
                              <span className="text-sm font-semibold text-slate-800">{step.step_name}</span>
                              <StepStatusBadge status={step.status} />
                            </div>
                            <div className="flex items-center gap-3 text-xs text-slate-400">
                              <span>#{step.order_index + 1}</span>
                              <span>{formatDuration(step.duration_seconds)}</span>
                              {step.retry_count > 0 && (
                                <span className="text-amber-500">↺ {step.retry_count}次重试</span>
                              )}
                            </div>
                          </div>
                          {step.error_message && (
                            <p className="text-xs text-red-500 font-mono bg-red-50 rounded px-2 py-1 mt-1">
                              {step.error_message}
                            </p>
                          )}
                          {step.output_data && Object.keys(step.output_data).length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs text-slate-400 mb-1">输出：</p>
                              <code className="text-xs text-slate-600 bg-slate-50 rounded px-2 py-1 block overflow-x-auto">
                                {JSON.stringify(step.output_data).slice(0, 200)}
                              </code>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* ── 调度配置 ──────────────────────────────────────── */}
              {drawerTab === 'schedule' && (
                <div className="space-y-5 max-w-xl">
                  {/* 启用开关 */}
                  <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200">
                    <div>
                      <h4 className="text-sm font-medium text-slate-700">定时调度</h4>
                      <p className="text-xs text-slate-400 mt-0.5">开启后将按照 Cron 表达式自动触发 Pipeline</p>
                    </div>
                    <button
                      onClick={() => setScheduleEnabled(v => !v)}
                      className={`relative w-11 h-6 rounded-full transition-colors ${scheduleEnabled ? 'bg-primary-500' : 'bg-slate-300'}`}
                    >
                      <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${scheduleEnabled ? 'translate-x-5' : ''}`} />
                    </button>
                  </div>

                  {/* Cron 输入 */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Cron 表达式</label>
                    <input
                      type="text"
                      value={scheduleCron}
                      onChange={e => setScheduleCron(e.target.value)}
                      placeholder="0 8 * * *"
                      disabled={!scheduleEnabled}
                      className="w-full text-sm font-mono border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-slate-100 disabled:text-slate-400"
                    />
                    {/* Cron 预设 */}
                    <div className="flex flex-wrap gap-2 mt-2">
                      {CRON_PRESETS.map(preset => (
                        <button
                          key={preset.value}
                          onClick={() => { setScheduleCron(preset.value); setScheduleEnabled(true) }}
                          className="text-xs px-2 py-1 rounded border border-slate-200 text-slate-600 hover:border-primary-300 hover:text-primary-600 hover:bg-primary-50 transition-colors"
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                    {/* 当前配置显示 */}
                    {scheduleConfig?.next_run_time && scheduleEnabled && (
                      <p className="text-xs text-emerald-600 mt-2 flex items-center gap-1">
                        <Timer className="w-3 h-3" />
                        下次执行：{formatDateTime(scheduleConfig.next_run_time)}
                      </p>
                    )}
                  </div>

                  {/* 保存 */}
                  <Button
                    onClick={handleSaveSchedule}
                    disabled={scheduleSaving}
                    icon={scheduleSaving ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  >
                    {scheduleSaving ? '保存中...' : '保存调度配置'}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
