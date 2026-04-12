/**
 * Logs.tsx - 训练日志查看页面
 *
 * 功能：日志列表、分页、筛选（experiment_id + 时间范围）、
 *       单行展开详情、实时 WebSocket 追加、删除日志文件
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { FileText, Search, Trash2, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, X, LoaderCircle, RefreshCw } from 'lucide-react'
import { logsApi, type LogEntry, type LogsFilter } from '../api/logs'
import Card from '../components/Card'
import Button from '../components/Button'
import { useQuery } from '@tanstack/react-query'

// ============ 常量 ============
const PAGE_SIZE = 20
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8765'

// ============ 类型 ============
interface RealtimeMessage {
  type: 'log' | 'metric' | 'progress' | 'error' | 'system'
  content: unknown
  timestamp: string
  experiment_id: string | null
}

// ============ 工具函数 ============
function formatTimestamp(iso: string): string {
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

function formatMetrics(metrics: Record<string, unknown>): string {
  return Object.entries(metrics)
    .slice(0, 4)
    .map(([k, v]) => `${k}=${typeof v === 'number' ? (v as number).toFixed(4) : v}`)
    .join(', ')
}

// ============ WebSocket 实时推送 Hook ============
function useRealtimeLogs(onMessage: (entry: RealtimeMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      console.log('[Logs] WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg: RealtimeMessage = JSON.parse(event.data)
        onMessage(msg)
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => {
      // silent
    }

    ws.onclose = () => {
      // 自动重连
      reconnectTimer.current = setTimeout(connect, 5000)
    }

    wsRef.current = ws
  }, [onMessage])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return wsRef
}

// ============ 主组件 ============
export default function Logs() {
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<LogsFilter>({})
  const [filterDraft, setFilterDraft] = useState<LogsFilter>({})
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detailEntries, setDetailEntries] = useState<object[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [realtimeEntries, setRealtimeEntries] = useState<RealtimeMessage[]>([])
  const [newHighlight, setNewHighlight] = useState<Set<string>>(new Set())

  // 拉取日志列表
  const {
    data,
    isLoading,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['logs', page, filter],
    queryFn: () => logsApi.list(page, PAGE_SIZE, filter),
    placeholderData: (prev) => prev,
  })

  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  // WebSocket 实时追加
  const handleRealtimeMessage = useCallback((msg: RealtimeMessage) => {
    setRealtimeEntries(prev => [msg, ...prev].slice(0, 50))
    // 高亮最新 metric 条目
    if (msg.type === 'metric' && typeof msg.content === 'object') {
      const key = `${msg.type}-${msg.timestamp}`
      setNewHighlight(prev => new Set([...prev, key]))
      setTimeout(() => {
        setNewHighlight(prev => {
          const next = new Set(prev)
          next.delete(key)
          return next
        })
      }, 3000)
    }
  }, [])

  useRealtimeLogs(handleRealtimeMessage)

  // 展开行详情
  const handleExpand = async (entry: LogEntry) => {
    if (expandedId === entry.file_id) {
      setExpandedId(null)
      return
    }
    setExpandedId(entry.file_id)
    setDetailLoading(true)
    try {
      const detail = await logsApi.getDetail(entry.file_id)
      setDetailEntries(detail)
    } catch {
      setDetailEntries([])
    } finally {
      setDetailLoading(false)
    }
  }

  // 删除日志
  const handleDelete = async (fileId: string) => {
    setDeleteLoading(true)
    try {
      await logsApi.delete(fileId)
      setDeleteConfirm(null)
      // 刷新列表
      if (data && page > 1 && (data.data.length === 1)) {
        setPage(p => Math.max(1, p - 1))
      } else {
        refetch()
      }
    } catch (err) {
      console.error('Delete failed', err)
    } finally {
      setDeleteLoading(false)
    }
  }

  // 筛选
  const handleSearch = () => {
    setFilter(filterDraft)
    setPage(1)
  }

  const handleClear = () => {
    setFilterDraft({})
    setFilter({})
    setPage(1)
  }

  // 分页导航
  const goPage = (p: number) => {
    setPage(Math.max(1, Math.min(p, totalPages)))
  }

  const entries: LogEntry[] = data?.data ?? []

  // 高亮 metric 条目的最新几条
  const recentMetrics = realtimeEntries.filter(m => m.type === 'metric').slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
            <FileText className="w-6 h-6" />
            训练日志
          </h1>
          <p className="text-slate-500 mt-1">
            查看、筛选训练日志，实时追踪训练过程
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {/* 实时推送预览 */}
      {recentMetrics.length > 0 && (
        <Card className="border border-blue-200 bg-blue-50">
          <p className="text-xs font-medium text-blue-600 mb-2 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            实时指标推送
          </p>
          <div className="flex flex-wrap gap-2">
            {recentMetrics.map((m, i) => {
              const c = m.content as { name?: string; value?: number; step?: number }
              return (
                <span
                  key={i}
                  className="inline-flex items-center px-2 py-0.5 rounded bg-white border border-blue-200 text-xs font-mono text-slate-700"
                >
                  {c.name}={typeof c.value === 'number' ? c.value.toFixed(4) : String(c.value ?? '')} @iter{c.step}
                </span>
              )
            })}
          </div>
        </Card>
      )}

      {/* 筛选栏 */}
      <Card>
        <div className="flex flex-wrap gap-3 items-end">
          {/* 实验筛选 */}
          <div className="flex flex-col gap-1 min-w-[160px]">
            <label className="text-xs font-medium text-slate-500">实验 ID</label>
            <input
              type="text"
              placeholder="输入 experiment_id"
              value={filterDraft.experiment_id ?? ''}
              onChange={e => setFilterDraft(f => ({ ...f, experiment_id: e.target.value || undefined }))}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* 开始时间 */}
          <div className="flex flex-col gap-1 min-w-[160px]">
            <label className="text-xs font-medium text-slate-500">开始时间</label>
            <input
              type="datetime-local"
              value={filterDraft.start_time ? filterDraft.start_time.slice(0, 16) : ''}
              onChange={e =>
                setFilterDraft(f => ({
                  ...f,
                  start_time: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                }))
              }
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* 结束时间 */}
          <div className="flex flex-col gap-1 min-w-[160px]">
            <label className="text-xs font-medium text-slate-500">结束时间</label>
            <input
              type="datetime-local"
              value={filterDraft.end_time ? filterDraft.end_time.slice(0, 16) : ''}
              onChange={e =>
                setFilterDraft(f => ({
                  ...f,
                  end_time: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                }))
              }
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2 pb-0.5">
            <Button onClick={handleSearch} className="flex items-center gap-1.5">
              <Search className="w-3.5 h-3.5" />
              查询
            </Button>
            <button
              onClick={handleClear}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            >
              清除
            </button>
          </div>
        </div>
      </Card>

      {/* 统计信息 */}
      <div className="flex items-center gap-4 text-sm text-slate-500">
        <span>共 <strong className="text-slate-700">{total}</strong> 条日志</span>
        <span className="text-slate-300">|</span>
        <span>第 <strong className="text-slate-700">{page}</strong> / <strong>{totalPages}</strong> 页</span>
      </div>

      {/* 日志表格 */}
      <Card>
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <LoaderCircle className="w-6 h-6 animate-spin text-slate-400" />
            <span className="ml-2 text-slate-500">加载中...</span>
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <FileText className="w-12 h-12 mb-3 opacity-40" />
            <p className="text-base font-medium">暂无日志记录</p>
            <p className="text-sm mt-1">开始训练后，日志将自动显示在此处</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left py-3 px-3 font-medium text-slate-500 w-8"></th>
                  <th className="text-left py-3 px-3 font-medium text-slate-500">时间</th>
                  <th className="text-left py-3 px-3 font-medium text-slate-500">Run</th>
                  <th className="text-left py-3 px-3 font-medium text-slate-500">迭代</th>
                  <th className="text-left py-3 px-3 font-medium text-slate-500">实验 ID</th>
                  <th className="text-left py-3 px-3 font-medium text-slate-500">指标摘要</th>
                  <th className="text-left py-3 px-3 font-medium text-slate-500 w-20">操作</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, idx) => (
                  <>
                    <tr
                      key={entry.file_id}
                      className={`border-b border-slate-50 hover:bg-slate-50 transition-colors cursor-pointer ${idx === 0 && newHighlight.size > 0 ? 'bg-blue-50' : ''}`}
                      onClick={() => handleExpand(entry)}
                    >
                      <td className="py-3 px-3">
                        <span className={`inline-block w-2 h-2 rounded-full transition-colors ${expandedId === entry.file_id ? 'bg-primary-500' : 'bg-slate-300'}`} />
                      </td>
                      <td className="py-3 px-3 font-mono text-xs text-slate-600 whitespace-nowrap">
                        {formatTimestamp(entry.timestamp)}
                      </td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-medium text-xs">
                          {entry.run}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-600">{entry.iter}</td>
                      <td className="py-3 px-3 text-slate-500 text-xs">
                        {entry.experiment_id ?? <span className="text-slate-300">—</span>}
                      </td>
                      <td className="py-3 px-3 text-xs text-slate-500 max-w-xs truncate">
                        {formatMetrics(entry.metrics)}
                      </td>
                      <td className="py-3 px-3">
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            setDeleteConfirm(entry.file_id)
                          }}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                          title="删除日志"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>

                    {/* 展开详情 */}
                    {expandedId === entry.file_id && (
                      <tr key={`${entry.file_id}-detail`} className="bg-slate-50">
                        <td colSpan={7} className="px-6 py-4">
                          {detailLoading ? (
                            <div className="flex items-center gap-2 text-slate-400 text-sm">
                              <LoaderCircle className="w-4 h-4 animate-spin" />
                              加载详情...
                            </div>
                          ) : detailEntries.length > 0 ? (
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <p className="text-xs font-medium text-slate-500">
                                  完整日志（共 {detailEntries.length} 条）
                                </p>
                                <button
                                  onClick={e => {
                                    e.stopPropagation()
                                    setExpandedId(null)
                                  }}
                                  className="p-1 rounded hover:bg-slate-200 transition-colors"
                                >
                                  <X className="w-3.5 h-3.5 text-slate-400" />
                                </button>
                              </div>
                              <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                                <table className="w-full text-xs">
                                  <thead>
                                    <tr className="bg-slate-100">
                                      <th className="py-2 px-3 text-left font-medium text-slate-500">iter</th>
                                      <th className="py-2 px-3 text-left font-medium text-slate-500">run</th>
                                      <th className="py-2 px-3 text-left font-medium text-slate-500">timestamp</th>
                                      <th className="py-2 px-3 text-left font-medium text-slate-500">metrics</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {detailEntries.slice(0, 200).map((e, i) => {
                                      const entry2 = e as Record<string, unknown>
                                      const metricsKeys = ['iter', 'run', 'timestamp', 'experiment_id']
                                        .filter(k => k in entry2)
                                      const otherMetrics = Object.entries(entry2)
                                        .filter(([k]) => !metricsKeys.includes(k))
                                      return (
                                        <tr key={i} className="border-t border-slate-100">
                                          <td className="py-1.5 px-3 font-mono">{String(entry2.iter ?? '')}</td>
                                          <td className="py-1.5 px-3">{String(entry2.run ?? '')}</td>
                                          <td className="py-1.5 px-3 font-mono text-slate-500">
                                            {typeof entry2.timestamp === 'number'
                                              ? new Date(entry2.timestamp as number * 1000).toLocaleTimeString()
                                              : String(entry2.timestamp ?? '')}
                                          </td>
                                          <td className="py-1.5 px-3">
                                            <span className="text-slate-600">
                                              {otherMetrics.map(([k, v]) => (
                                                <span key={k} className="mr-2">
                                                  <span className="text-slate-400">{k}=</span>
                                                  {typeof v === 'number' ? (v as number).toFixed(4) : String(v)}
                                                </span>
                                              ))}
                                            </span>
                                          </td>
                                        </tr>
                                      )
                                    })}
                                    {detailEntries.length > 200 && (
                                      <tr className="border-t border-slate-100">
                                        <td colSpan={4} className="py-2 px-3 text-center text-slate-400 text-xs">
                                          ... 还有 {detailEntries.length - 200} 条未显示
                                        </td>
                                      </tr>
                                    )}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ) : (
                            <p className="text-sm text-slate-400">无详情数据</p>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 分页控件 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => goPage(1)}
            disabled={page === 1}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50 transition-colors"
            title="首页"
          >
            <ChevronsLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => goPage(page - 1)}
            disabled={page === 1}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50 transition-colors"
            title="上一页"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
              let p: number
              if (totalPages <= 7) {
                p = i + 1
              } else if (page <= 4) {
                p = i + 1
              } else if (page >= totalPages - 3) {
                p = totalPages - 6 + i
              } else {
                p = page - 3 + i
              }
              return (
                <button
                  key={p}
                  onClick={() => goPage(p)}
                  className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                    page === p
                      ? 'bg-primary-500 text-white'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {p}
                </button>
              )
            })}
          </div>

          <button
            onClick={() => goPage(page + 1)}
            disabled={page === totalPages}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50 transition-colors"
            title="下一页"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          <button
            onClick={() => goPage(totalPages)}
            disabled={page === totalPages}
            className="p-1.5 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50 transition-colors"
            title="末页"
          >
            <ChevronsRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 删除确认对话框 */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <Card className="w-full max-w-sm mx-4">
            <h3 className="text-lg font-semibold text-slate-900 mb-2">确认删除</h3>
            <p className="text-sm text-slate-600 mb-4">
              确定要删除日志文件 <code className="bg-slate-100 px-1 rounded">{deleteConfirm}</code> 吗？此操作不可恢复。
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                disabled={deleteLoading}
              >
                取消
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                disabled={deleteLoading}
                className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                {deleteLoading && <LoaderCircle className="w-3.5 h-3.5 animate-spin" />}
                删除
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
