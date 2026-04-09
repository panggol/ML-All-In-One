import { useState } from 'react'
import { BarChart3, RotateCcw, CheckCircle2, XCircle, Clock } from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Badge from '../components/Badge'

interface Experiment {
  id: number
  name: string
  status: 'completed' | 'failed' | 'running'
  accuracy: number | null
  f1: number | null
  time: string
  duration: string
  params?: Record<string, string | number>
}

const experiments: Experiment[] = [
  { 
    id: 1, 
    name: 'RF-iris-baseline', 
    status: 'completed', 
    accuracy: 94.2, 
    f1: 93.8, 
    time: '2小时前', 
    duration: '45s',
    params: { n_estimators: 100, max_depth: 10, learning_rate: 0.1 }
  },
  { 
    id: 2, 
    name: 'XGB-iris-tuned', 
    status: 'completed', 
    accuracy: 95.1, 
    f1: 94.9, 
    time: '3小时前', 
    duration: '1m 12s',
    params: { n_estimators: 200, max_depth: 8, learning_rate: 0.05 }
  },
  { 
    id: 3, 
    name: 'LGBM-credit-v1', 
    status: 'failed', 
    accuracy: null, 
    f1: null, 
    time: '昨天', 
    duration: '—' 
  },
  { 
    id: 4, 
    name: 'RF-boston-v2', 
    status: 'running', 
    accuracy: null, 
    f1: null, 
    time: '5分钟前', 
    duration: '—' 
  },
  { 
    id: 5, 
    name: 'XGB-iris-v3', 
    status: 'completed', 
    accuracy: 94.8, 
    f1: 94.5, 
    time: '昨天', 
    duration: '58s',
    params: { n_estimators: 150, max_depth: 12, learning_rate: 0.08 }
  },
]

const StatusIcon = ({ status }: { status: Experiment['status'] }) => {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-3.5 h-3.5" />
    case 'failed':
      return <XCircle className="w-3.5 h-3.5" />
    case 'running':
      return <Clock className="w-3.5 h-3.5" />
  }
}

const StatusBadge = ({ status }: { status: Experiment['status'] }) => {
  const variant = status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'warning'
  const label = status === 'completed' ? '完成' : status === 'failed' ? '失败' : '运行中'
  
  return (
    <Badge variant={variant} icon={<StatusIcon status={status} />}>
      {label}
    </Badge>
  )
}

export default function Experiments() {
  const [selectedExp, setSelectedExp] = useState<number | null>(null)
  const [, setRefreshKey] = useState(0)

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1)
  }

  const selectedExperiment = experiments.find((e) => e.id === selectedExp)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">实验记录</h1>
          <p className="text-slate-500 mt-1">追踪和对比所有训练实验</p>
        </div>
        <Button variant="secondary" onClick={handleRefresh}>
          <RotateCcw className="w-4 h-4" />
          刷新
        </Button>
      </div>

      {/* Experiments List */}
      <Card className="!p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left py-3 px-4 font-semibold text-slate-900">实验名称</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900">状态</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900">准确率</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900">F1分数</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900">耗时</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900">时间</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
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
                    {exp.accuracy !== null ? (
                      <span className="font-medium text-primary-600">{exp.accuracy}%</span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="py-4 px-4">
                    {exp.f1 !== null ? (
                      <span className="font-medium text-slate-700">{exp.f1}%</span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="py-4 px-4 text-slate-600">{exp.duration}</td>
                  <td className="py-4 px-4 text-slate-500 text-sm">{exp.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Detail Panel */}
      {selectedExperiment && (
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-4">实验详情</h2>
          <div className="bg-slate-50 rounded-lg p-4 font-mono text-sm">
            <pre className="text-slate-700 whitespace-pre-wrap">
{`Experiment: ${selectedExperiment.name}
Status: ${selectedExperiment.status}
Model: RandomForestClassifier
Dataset: iris (150 samples, 4 features)
Split: 80% train, 20% test${selectedExperiment.params ? `
Parameters:
${Object.entries(selectedExperiment.params)
  .map(([key, value]) => `  - ${key}: ${value}`)
  .join('\n')}` : ''}`}
            </pre>
          </div>
        </Card>
      )}
    </div>
  )
}
