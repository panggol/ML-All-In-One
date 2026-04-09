import { useState, useEffect } from 'react'
import { BarChart3, RotateCcw, CheckCircle2, XCircle, Clock } from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Badge from '../components/Badge'
import { experimentApi, Experiment } from '../api'

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
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-4 px-4">
                      {exp.metrics?.f1 !== undefined ? (
                        <span className="font-medium text-slate-700">{(exp.metrics.f1 * 100).toFixed(1)}%</span>
                      ) : (
                        <span className="text-slate-400">—</span>
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
            <pre className="text-slate-700 whitespace-pre-wrap">
{`名称: ${selectedExperiment.name}
描述: ${selectedExperiment.description || '无'}
状态: ${selectedExperiment.status}
创建时间: ${selectedExperiment.created_at}
${selectedExperiment.finished_at ? `完成时间: ${selectedExperiment.finished_at}` : ''}

参数:
${JSON.stringify(selectedExperiment.params, null, 2)}

指标:
${JSON.stringify(selectedExperiment.metrics, null, 2)}
            </pre>
          </div>
        </Card>
      )}
    </div>
  )
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const hours = Math.floor(diff / (1000 * 60 * 60))
  
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}
