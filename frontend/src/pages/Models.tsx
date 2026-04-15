import { useState, useEffect, useCallback } from 'react'
import { Package, GitBranch, ArrowLeftRight, RotateCcw, RefreshCw, Tag, Check, Clock, AlertCircle } from 'lucide-react'
import { api } from '../api'

// ─── Types ────────────────────────────────────────────────────────────────────

interface ModelVersion {
  version: number
  tag: 'staging' | 'production' | 'archived'
  algorithm_type: string | null
  metrics: Record<string, number>
  registered_at: string
  registered_by: number | null
}

interface VersionListResponse {
  total: number
  page: number
  items: ModelVersion[]
}

interface VersionDetail {
  id: number
  model_id: number
  version: number
  tag: string
  algorithm_type: string | null
  model_type: string | null
  task_type: string | null
  dataset_name: string | null
  dataset_hash: string | null
  training_params: Record<string, unknown>
  training_time: number | null
  metrics: Record<string, number>
  training_job_id: number | null
  model_file_path: string | null
  model_file_size: number | null
  registered_by: number | null
  registered_at: string
}

interface CompareResult {
  version_a: number
  version_b: number
  metrics_a: Record<string, number>
  metrics_b: Record<string, number>
  comparison: Array<{
    metric: string
    value_a: number
    value_b: number
    delta: number | null
    winner: string | null
  }>
  unique_to_a: string[]
  unique_to_b: string[]
  common_metrics_only: boolean
}

interface HistoryItem {
  id: number
  model_id: number
  version: number
  action: string
  actor_id: number | null
  details: Record<string, unknown>
  created_at: string
}

interface HistoryResponse {
  total: number
  page: number
  items: HistoryItem[]
}

interface TrainedModel {
  id: number
  name: string
  model_type: string
  metrics: Record<string, number>
  created_at: string
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const TAG_COLORS: Record<string, string> = {
  staging: 'bg-yellow-100 text-yellow-800',
  production: 'bg-green-100 text-green-800',
  archived: 'bg-gray-100 text-gray-600',
}

const TAG_LABELS: Record<string, string> = {
  staging: 'Staging',
  production: 'Production',
  archived: 'Archived',
}

const ACTION_LABELS: Record<string, string> = {
  register: '注册',
  tag_change: '标签变更',
  rollback: '回滚',
  archive: '归档',
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function MetricBadge({ value }: { value: number }) {
  const color = value >= 0.9 ? 'text-green-600' : value >= 0.8 ? 'text-yellow-600' : 'text-red-600'
  return <span className={`font-mono text-sm font-medium ${color}`}>{value.toFixed(4)}</span>
}

// ─── Compare Modal ─────────────────────────────────────────────────────────────

function CompareModal({
  modelId,
  selectedVersions,
  onClose,
  onRefresh,
}: {
  modelId: number
  selectedVersions: number[]
  onClose: () => void
  onRefresh: () => void
}) {
  const [result, setResult] = useState<CompareResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (selectedVersions.length < 2) return
    const [a, b] = selectedVersions
    api.get(`/models/${modelId}/compare?version_a=${a}&version_b=${b}`)
      .then(r => r.json())
      .then(data => { setResult(data); setLoading(false) })
      .catch(e => { setError(String(e)); setLoading(false) })
  }, [modelId, selectedVersions])

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-[700px] max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <ArrowLeftRight className="w-5 h-5 text-primary-600" />
            <h2 className="text-lg font-semibold text-slate-800">
              版本对比 — v{selectedVersions[0]} vs v{selectedVersions[1]}
            </h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <AlertCircle className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4">
          {loading && <div className="text-center py-10 text-slate-500">加载中...</div>}
          {error && <div className="text-center py-10 text-red-500">错误：{error}</div>}
          {result && (
            <div className="space-y-4">
              {/* Metrics comparison table */}
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">指标</th>
                      <th className="px-4 py-3 text-center font-medium text-slate-600">
                        v{result.version_a}
                      </th>
                      <th className="px-4 py-3 text-center font-medium text-slate-600">
                        v{result.version_b}
                      </th>
                      <th className="px-4 py-3 text-center font-medium text-slate-600">Δ</th>
                      <th className="px-4 py-3 text-center font-medium text-slate-600">胜出</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.comparison.map((row, i) => (
                      <tr key={i} className={`border-t border-slate-100 ${i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}`}>
                        <td className="px-4 py-3 font-medium text-slate-700">{row.metric}</td>
                        <td className="px-4 py-3 text-center">
                          {row.value_a !== null ? <MetricBadge value={row.value_a as unknown as number} /> : '-'}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.value_b !== null ? <MetricBadge value={row.value_b as unknown as number} /> : '-'}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.delta !== null ? (
                            <span className={`font-mono ${row.delta > 0 ? 'text-green-600' : row.delta < 0 ? 'text-red-500' : 'text-slate-400'}`}>
                              {row.delta > 0 ? '+' : ''}{row.delta.toFixed(4)}
                            </span>
                          ) : <span className="text-slate-400">-</span>}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {row.winner === 'b' && <span className="inline-flex items-center gap-1 text-green-600 font-medium">v{result.version_b} ↑</span>}
                          {row.winner === 'a' && <span className="inline-flex items-center gap-1 text-red-500 font-medium">v{result.version_a} ↑</span>}
                          {row.winner === 'tie' && <span className="text-slate-400">=</span>}
                          {row.winner === null && <span className="text-slate-400">-</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Unique metrics */}
              {(result.unique_to_a.length > 0 || result.unique_to_b.length > 0) && (
                <div className="grid grid-cols-2 gap-4">
                  {result.unique_to_a.length > 0 && (
                    <div className="bg-blue-50 rounded-xl p-4">
                      <p className="text-sm font-medium text-blue-700 mb-1">v{result.version_a} 独有指标</p>
                      {result.unique_to_a.map(m => (
                        <span key={m} className="inline-block bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full mr-1 mb-1">{m}</span>
                      ))}
                    </div>
                  )}
                  {result.unique_to_b.length > 0 && (
                    <div className="bg-purple-50 rounded-xl p-4">
                      <p className="text-sm font-medium text-purple-700 mb-1">v{result.version_b} 独有指标</p>
                      {result.unique_to_b.map(m => (
                        <span key={m} className="inline-block bg-purple-100 text-purple-700 text-xs px-2 py-0.5 rounded-full mr-1 mb-1">{m}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Tag Change Modal ─────────────────────────────────────────────────────────

function TagChangeModal({
  modelId,
  version,
  currentTag,
  onClose,
  onSuccess,
}: {
  modelId: number
  version: number
  currentTag: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [selectedTag, setSelectedTag] = useState(currentTag)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const isAdmin = user.role === 'admin'

  const handleSubmit = async () => {
    if (selectedTag === currentTag) { onClose(); return }
    setLoading(true)
    setError(null)
    setMessage(null)
    try {
      const resp = await api.patch(`/models/${modelId}/versions/${version}/tags`, {
        body: JSON.stringify({ tag: selectedTag }),
      })
      if (!resp.ok) {
        const data = await resp.json()
        setError(data.detail || '变更失败')
        return
      }
      const data = await resp.json()
      setMessage(data.message || '标签已更新')
      onSuccess()
      setTimeout(onClose, 1200)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-[420px]">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800">变更标签 — v{version}</h2>
          <p className="text-sm text-slate-500 mt-1">当前标签：{TAG_LABELS[currentTag]}</p>
        </div>
        <div className="px-6 py-4 space-y-3">
          {!isAdmin && (
            <div className="bg-yellow-50 text-yellow-700 text-sm px-3 py-2 rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              只有管理员可以变更 production 标签
            </div>
          )}
          {(['staging', 'production', 'archived'] as const).map(tag => (
            <button
              key={tag}
              onClick={() => setSelectedTag(tag)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all ${
                selectedTag === tag
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <span className={`inline-block w-3 h-3 rounded-full ${TAG_COLORS[tag].split(' ')[0].replace('bg-', 'bg-').replace('-100', '-500')}`}
                style={{ background: tag === 'staging' ? '#facc15' : tag === 'production' ? '#4ade80' : '#d1d5db' }} />
              <span className="font-medium text-slate-700">{TAG_LABELS[tag]}</span>
              {selectedTag === tag && <Check className="w-4 h-4 text-primary-600 ml-auto" />}
            </button>
          ))}
          {error && <p className="text-red-500 text-sm">{error}</p>}
          {message && <p className="text-green-600 text-sm">{message}</p>}
        </div>
        <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">取消</button>
          <button
            onClick={handleSubmit}
            disabled={loading || selectedTag === currentTag}
            className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            {loading ? '变更中...' : '确认变更'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Models Page ─────────────────────────────────────────────────────────

export default function Models() {
  const [models, setModels] = useState<TrainedModel[]>([])
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [versions, setVersions] = useState<ModelVersion[]>([])
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [filterTag, setFilterTag] = useState<string | null>(null)
  const [selectedVersions, setSelectedVersions] = useState<number[]>([])
  const [activeTab, setActiveTab] = useState<'versions' | 'history'>('versions')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Modals
  const [compareModalOpen, setCompareModalOpen] = useState(false)
  const [tagChangeModal, setTagChangeModal] = useState<{ version: number; tag: string } | null>(null)

  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const isAdmin = user.role === 'admin'

  // 加载模型列表
  const loadModels = useCallback(async () => {
    // ── Test mode: allow E2E tests to inject mock data via localStorage ──
    if (typeof window !== 'undefined') {
      const testModels = localStorage.getItem('__TEST_MOCK_MODELS__')
      if (testModels) {
        const data: TrainedModel[] = JSON.parse(testModels)
        setModels(data)
        if (data.length > 0) {
          setSelectedModelId(data[0].id)
        }
        return
      }
    }
    try {
      const resp = await api.get('/models/')
      if (resp.ok) {
        const data = await resp.json()
        setModels(data)
        if (data.length > 0) {
          setSelectedModelId(data[0].id)
        }
      }
    } catch (e) {
      console.error('Failed to load models:', e)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 加载版本列表
  const loadVersions = useCallback(async () => {
    if (!selectedModelId) return
    setLoading(true)
    setError(null)
    // ── Test mode ──
    if (typeof window !== 'undefined') {
      const raw = localStorage.getItem('__TEST_MOCK_VERSIONS__')
      if (raw) {
        const data: VersionListResponse = JSON.parse(raw)
        setVersions(data.items)
        setLoading(false)
        return
      }
    }
    try {
      const url = filterTag
        ? `/models/${selectedModelId}/versions?tag=${filterTag}`
        : `/models/${selectedModelId}/versions`
      const resp = await api.get(url)
      if (resp.ok) {
        const data: VersionListResponse = await resp.json()
        setVersions(data.items)
      } else {
        setError(`加载失败：${resp.status}`)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [selectedModelId, filterTag])

  // 加载操作历史
  const loadHistory = useCallback(async () => {
    if (!selectedModelId) return
    setLoading(true)
    // ── Test mode ──
    if (typeof window !== 'undefined') {
      const raw = localStorage.getItem('__TEST_MOCK_HISTORY__')
      if (raw) {
        const data: HistoryResponse = JSON.parse(raw)
        setHistory(data.items)
        setLoading(false)
        return
      }
    }
    try {
      const resp = await api.get(`/models/${selectedModelId}/history`)
      if (resp.ok) {
        const data: HistoryResponse = await resp.json()
        setHistory(data.items)
      }
    } catch (e) {
      console.error('Failed to load history:', e)
    } finally {
      setLoading(false)
    }
  }, [selectedModelId])

  // 回滚
  const handleRollback = async (targetVersion: number) => {
    if (!selectedModelId || !confirm(`确定要回滚到 v${targetVersion} 吗？`)) return
    try {
      const resp = await api.post(`/models/${selectedModelId}/rollback?target_version=${targetVersion}`)
      if (resp.ok) {
        loadVersions()
        loadHistory()
      } else {
        const data = await resp.json()
        alert(data.detail || '回滚失败')
      }
    } catch (e) {
      alert(String(e))
    }
  }

  // 版本勾选
  const toggleVersionSelect = (version: number) => {
    setSelectedVersions(prev =>
      prev.includes(version)
        ? prev.filter(v => v !== version)
        : prev.length < 2 ? [...prev, version] : prev
    )
  }

  useEffect(() => { loadModels() }, [])
  useEffect(() => { if (selectedModelId) { loadVersions(); loadHistory() } }, [selectedModelId, filterTag])
  useEffect(() => { if (activeTab === 'history') loadHistory() }, [activeTab])

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
            <Package className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-800">模型版本管理</h1>
            <p className="text-sm text-slate-500">注册、对比、回滚模型版本</p>
          </div>
        </div>
        <button
          onClick={() => { loadVersions(); loadHistory() }}
          className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-800 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          刷新
        </button>
      </div>

      {/* Model selector */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <label className="text-sm font-medium text-slate-600 mb-2 block">选择模型</label>
        <div className="flex flex-wrap gap-2">
          {models.map(m => (
            <button
              key={m.id}
              onClick={() => setSelectedModelId(m.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedModelId === m.id
                  ? 'bg-primary-100 text-primary-700 border border-primary-300'
                  : 'bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              {m.name}
            </button>
          ))}
          {models.length === 0 && (
            <p className="text-sm text-slate-400 py-2">暂无模型，请先完成训练</p>
          )}
        </div>
      </div>

      {selectedModelId && (
        <>
          {/* Tab bar */}
          <div className="flex items-center gap-1 bg-white rounded-xl border border-slate-200 p-1">
            <button
              onClick={() => setActiveTab('versions')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'versions' ? 'bg-primary-50 text-primary-700' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <GitBranch className="w-4 h-4" />
              版本列表
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'history' ? 'bg-primary-50 text-primary-700' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Clock className="w-4 h-4" />
              操作历史
            </button>
          </div>

          {/* Versions Tab */}
          {activeTab === 'versions' && (
            <div className="space-y-4">
              {/* Toolbar */}
              <div className="flex items-center gap-3 flex-wrap">
                {/* Tag filter */}
                <div className="flex items-center gap-2">
                  <Tag className="w-4 h-4 text-slate-400" />
                  <select
                    value={filterTag || ''}
                    onChange={e => setFilterTag(e.target.value || null)}
                    className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 text-slate-600 focus:outline-none focus:ring-2 focus:ring-primary-300"
                  >
                    <option value="">全部标签</option>
                    <option value="staging">Staging</option>
                    <option value="production">Production</option>
                    <option value="archived">Archived</option>
                  </select>
                </div>

                {/* Compare button */}
                {selectedVersions.length === 2 && (
                  <button
                    onClick={() => setCompareModalOpen(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
                  >
                    <ArrowLeftRight className="w-4 h-4" />
                    对比 v{selectedVersions[0]} vs v{selectedVersions[1]}
                  </button>
                )}
                {selectedVersions.length > 0 && selectedVersions.length < 2 && (
                  <span className="text-sm text-slate-500">再选一个版本以对比</span>
                )}

                {/* Legend */}
                <div className="ml-auto flex items-center gap-3 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <input type="checkbox" className="accent-primary-600" disabled />
                    勾选两个版本对比
                  </span>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  {error}
                </div>
              )}

              {/* Versions table */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium text-slate-600 w-10"></th>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">版本</th>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">标签</th>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">算法</th>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">主要指标</th>
                      <th className="px-4 py-3 text-left font-medium text-slate-600">注册时间</th>
                      <th className="px-4 py-3 text-right font-medium text-slate-600">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && (
                      <tr>
                        <td colSpan={7} className="text-center py-10 text-slate-400">加载中...</td>
                      </tr>
                    )}
                    {!loading && versions.length === 0 && (
                      <tr>
                        <td colSpan={7} className="text-center py-10 text-slate-400">暂无版本记录</td>
                      </tr>
                    )}
                    {versions.map((v, i) => (
                      <tr key={v.version} className={`border-b border-slate-100 hover:bg-slate-50/50 transition-colors ${i % 2 === 0 ? 'bg-white' : 'bg-slate-50/30'}`}>
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedVersions.includes(v.version)}
                            onChange={() => toggleVersionSelect(v.version)}
                            className="accent-primary-600 rounded"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono font-semibold text-slate-800">v{v.version}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${TAG_COLORS[v.tag]}`}>
                            {TAG_LABELS[v.tag]}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {v.algorithm_type || '-'}
                        </td>
                        <td className="px-4 py-3">
                          {v.metrics && Object.keys(v.metrics).length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {Object.entries(v.metrics)
                                .filter(([, v]) => typeof v === 'number')
                                .slice(0, 2)
                                .map(([k, val]) => (
                                  <span key={k} className="inline-flex items-center gap-1 bg-slate-100 rounded px-2 py-0.5 text-xs">
                                    <span className="text-slate-500">{k}:</span>
                                    <MetricBadge value={val as number} />
                                  </span>
                                ))}
                              {Object.keys(v.metrics).length > 2 && (
                                <span className="text-xs text-slate-400">+{Object.keys(v.metrics).length - 2}</span>
                              )}
                            </div>
                          ) : <span className="text-slate-400">-</span>}
                        </td>
                        <td className="px-4 py-3 text-slate-500 text-xs">
                          {formatDate(v.registered_at)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => setTagChangeModal({ version: v.version, tag: v.tag })}
                              className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                              title="变更标签"
                            >
                              <Tag className="w-3.5 h-3.5" />
                            </button>
                            {isAdmin && v.tag !== 'archived' && (
                              <button
                                onClick={() => handleRollback(v.version)}
                                className="text-xs text-orange-600 hover:text-orange-700 font-medium flex items-center gap-1"
                                title="回滚到此版本"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* History Tab */}
          {activeTab === 'history' && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">时间</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">版本</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">操作</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">详情</th>
                    <th className="px-4 py-3 text-left font-medium text-slate-600">操作人</th>
                  </tr>
                </thead>
                <tbody>
                  {history.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-center py-10 text-slate-400">暂无操作历史</td>
                    </tr>
                  )}
                  {history.map(h => (
                    <tr key={h.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="px-4 py-3 text-slate-500 text-xs">{formatDate(h.created_at)}</td>
                      <td className="px-4 py-3"><span className="font-mono font-medium">v{h.version}</span></td>
                      <td className="px-4 py-3">
                        <span className="bg-primary-50 text-primary-700 px-2 py-0.5 rounded text-xs font-medium">
                          {ACTION_LABELS[h.action] || h.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600 text-xs max-w-xs truncate">
                        {JSON.stringify(h.details)}
                      </td>
                      <td className="px-4 py-3 text-slate-500 text-xs">
                        {h.actor_id ? `User #${h.actor_id}` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Modals */}
      {compareModalOpen && selectedVersions.length === 2 && (
        <CompareModal
          modelId={selectedModelId!}
          selectedVersions={selectedVersions}
          onClose={() => { setCompareModalOpen(false); setSelectedVersions([]) }}
          onRefresh={loadVersions}
        />
      )}
      {tagChangeModal && (
        <TagChangeModal
          modelId={selectedModelId!}
          version={tagChangeModal.version}
          currentTag={tagChangeModal.tag}
          onClose={() => setTagChangeModal(null)}
          onSuccess={() => { loadVersions(); loadHistory(); setTagChangeModal(null) }}
        />
      )}
    </div>
  )
}
