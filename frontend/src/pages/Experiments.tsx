import { useState, useEffect } from 'react'
import { BarChart3, RotateCcw, CheckCircle2, XCircle, Clock, TrendingUp } from 'lucide-react'
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

export default function Experiments() {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedExp, setSelectedExp] = useState<number | null>(null)

  // Training Curves state
  const [curveTab, setCurveTab] = useState<'all' | 'loss' | 'accuracy'>('all')
  const [curvesData, setCurvesData] = useState<TrainingCurvesResponse | null>(null)
  const [curvesLoading, setCurvesLoading] = useState(false)

  // Load curves when experiment selected
  useEffect(() => {
    if (!selectedExp) return
    setCurvesLoading(true)
    vizApi.getTrainingCurves(selectedExp)
      .then((data) => { setCurvesData(data); setCurvesLoading(false) })
      .catch(() => { setCurvesData(null); setCurvesLoading(false) })
  }, [selectedExp])

  // Filter curves by tab
  const filteredCurves = curvesData?.curves.filter((c) => {
    if (curveTab === 'all') return true
    if (curveTab === 'loss') return c.name.toLowerCase().includes('loss')
    if (curveTab === 'accuracy') return c.name.toLowerCase().includes('acc') || c.name.toLowerCase().includes('metric')
    return true
  }) ?? []

  useEffect(() => {
    loadExperiments()
  }, [])

  const loadExperiments = async () => {
    setLoading(true)
    try {
      const data = await experimentApi.list()
      setExperiments(data)
    } catch (err) {
      console.error('Failed to load experiments:', err)
    } finally {
      setLoading(false)
    }
  }

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">实验记录</h1>
          <p className="text-slate-500 mt-1">追踪和对比所有训练实验</p>
        </div>
        <Button variant="secondary" onClick={loadExperiments}>
          <RotateCcw className="w-4 h-4" />
          刷新
        </Button>
      </div>

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
            {(['all', 'loss', 'accuracy'] as const).map((tab) => (
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
            <span className="text-sm">← 请先从上方选择一个实验查看训练曲线</span>
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

      {/* Experiments List */}
      <Card className="!p-0">
        {loading ? (
          <div className="p-8 text-center text-slate-500">加载中...</div>
        ) : experiments.length === 0 ? (
          <div className="p-8 text-center text-slate-500">暂无实验记录</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="text-left py-3 px-4 font-semibold text-slate-900">实验名称</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-900">状态</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-900">准确率</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-900">F1分数</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-900">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {experiments.map(exp => (
                  <tr
                    key={exp.id}
                    onClick={() => setSelectedExp(exp.id)}
                    className={`border-b border-slate-100 last:border-0 cursor-pointer transition-colors hover:bg-slate-50 ${
                      selectedExp === exp.id ? 'bg-primary-50' : ''
                    }`}
                  >
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
                ))}
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
    </div>
  )
}
