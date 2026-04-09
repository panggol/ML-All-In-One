import { Activity, TrendingUp, Clock, Award, Upload, Brain, LineChart } from 'lucide-react'
import Card from '../components/Card'
import StatCard from '../components/StatCard'

interface ModelRecord {
  name: string
  accuracy: number
  dataset: string
  time: string
}

const stats = [
  { label: '总训练次数', value: '128', icon: Activity, color: 'primary' as const },
  { label: '活跃实验', value: '12', icon: TrendingUp, color: 'emerald' as const },
  { label: '运行时长', value: '48h', icon: Clock, color: 'amber' as const },
  { label: '最优模型', value: '94.2%', icon: Award, color: 'violet' as const },
]

const recentModels: ModelRecord[] = [
  { name: 'RF-分类器-v3', accuracy: 94.2, dataset: 'iris', time: '2小时前' },
  { name: 'XGB-回归-v1', accuracy: 87.5, dataset: 'boston', time: '5小时前' },
  { name: 'LGBM-欺诈检测', accuracy: 91.8, dataset: 'credit', time: '昨天' },
]

const quickActions = [
  { 
    icon: Upload, 
    title: '上传数据集', 
    description: '支持 CSV、Excel 格式',
    action: 'upload'
  },
  { 
    icon: Brain, 
    title: '自动机器学习', 
    description: '一键找到最优模型和参数',
    action: 'automl'
  },
  { 
    icon: LineChart, 
    title: '模型预测', 
    description: '批量预测新数据',
    action: 'predict'
  },
]

export default function Dashboard() {
  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">仪表盘</h1>
        <p className="text-slate-500 mt-1">欢迎使用 ML All In One</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      {/* Quick Actions & Recent */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick Start */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-4">快速开始</h2>
          <div className="space-y-3">
            {quickActions.map((action) => (
              <button
                key={action.action}
                className="w-full text-left px-4 py-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors flex items-center gap-4"
              >
                <div className="w-10 h-10 rounded-lg bg-white flex items-center justify-center shadow-sm">
                  <action.icon className="w-5 h-5 text-primary-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-900">{action.title}</p>
                  <p className="text-sm text-slate-500">{action.description}</p>
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* Recent Models */}
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-4">最近模型</h2>
          <div className="space-y-4">
            {recentModels.map((model, index) => (
              <div 
                key={model.name} 
                className={`flex items-center justify-between py-2 ${index !== recentModels.length - 1 ? 'border-b border-slate-100' : ''}`}
              >
                <div>
                  <p className="font-medium text-slate-900">{model.name}</p>
                  <p className="text-sm text-slate-500">{model.dataset} · {model.time}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-primary-600">{model.accuracy}%</p>
                  <p className="text-xs text-slate-400">准确率</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* System Status */}
      <Card>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <h2 className="text-lg font-semibold text-slate-900">系统状态</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <span className="text-sm text-slate-600">API 服务</span>
            <span className="text-sm font-medium text-emerald-600">正常运行</span>
          </div>
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <span className="text-sm text-slate-600">GPU 内存</span>
            <span className="text-sm font-medium text-slate-700">2.1 GB / 8 GB</span>
          </div>
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <span className="text-sm text-slate-600">磁盘使用</span>
            <span className="text-sm font-medium text-slate-700">12.4 GB / 100 GB</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
