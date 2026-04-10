import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, TrendingUp, Clock, Award, Upload, Brain, LineChart } from 'lucide-react'
import Card from '../components/Card'
import StatCard from '../components/StatCard'
import { trainApi, experimentApi } from '../api'

interface ModelRecord {
  name: string
  accuracy: number
  dataset: string
  time: string
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [recentModels, setRecentModels] = useState<ModelRecord[]>([])
  const [stats, setStats] = useState({
    totalJobs: 0,
    activeExperiments: 0,
    runtime: '0h',
    bestAccuracy: '0%'
  })

  const quickActions = [
    {
      icon: Upload,
      title: '上传数据集',
      description: '支持 CSV、Excel 格式',
      action: 'upload',
      onClick: () => document.getElementById('file-upload')?.click()
    },
    {
      icon: Brain,
      title: '自动机器学习',
      description: '一键找到最优模型和参数',
      action: 'automl',
      onClick: () => navigate('/training')
    },
    {
      icon: LineChart,
      title: '模型预测',
      description: '批量预测新数据',
      action: 'predict',
      onClick: () => navigate('/experiments')
    },
  ]

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    setLoading(true)
    try {
      // 获取训练任务列表
      const jobs = await trainApi.list()
      const completedJobs = jobs.filter(j => j.status === 'completed')
      
      // 获取实验列表
      const experiments = await experimentApi.list()
      const activeExps = experiments.filter(e => e.status === 'running' || e.status === 'pending')
      
      // 计算统计数据
      const bestJob = completedJobs.reduce((best, job) => {
        const acc = job.metrics?.accuracy || 0
        const bestAcc = best?.metrics?.accuracy || 0
        return acc > bestAcc ? job : best
      }, null as any)

      setStats({
        totalJobs: completedJobs.length,
        activeExperiments: activeExps.length,
        runtime: calculateRuntime(jobs),
        bestAccuracy: bestJob ? `${(bestJob.metrics.accuracy * 100).toFixed(1)}%` : '0%'
      })

      // 设置最近模型
      setRecentModels(completedJobs.slice(0, 5).map(job => ({
        name: job.model_name,
        accuracy: job.metrics?.accuracy ? job.metrics.accuracy * 100 : 0,
        dataset: `Dataset #${job.data_file_id || '?'}`,
        time: formatTime(job.created_at)
      })))
    } catch (err) {
      console.error('Failed to load dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">仪表盘</h1>
        <p className="text-slate-500 mt-1">欢迎使用 ML All In One</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="总训练次数" value={stats.totalJobs.toString()} icon={Activity} color="primary" />
        <StatCard label="活跃实验" value={stats.activeExperiments.toString()} icon={TrendingUp} color="emerald" />
        <StatCard label="运行时长" value={stats.runtime} icon={Clock} color="amber" />
        <StatCard label="最优模型" value={stats.bestAccuracy} icon={Award} color="violet" />
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
                onClick={action.onClick}
                className="w-full text-left px-4 py-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors flex items-center gap-4 cursor-pointer"
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
          {loading ? (
            <div className="text-center py-8 text-slate-500">加载中...</div>
          ) : recentModels.length === 0 ? (
            <div className="text-center py-8 text-slate-500">暂无训练记录</div>
          ) : (
            <div className="space-y-4">
              {recentModels.map((model, index) => (
                <div 
                  key={index}
                  className={`flex items-center justify-between py-2 ${index !== recentModels.length - 1 ? 'border-b border-slate-100' : ''}`}
                >
                  <div>
                    <p className="font-medium text-slate-900">{model.name}</p>
                    <p className="text-sm text-slate-500">{model.dataset} · {model.time}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-primary-600">{model.accuracy.toFixed(1)}%</p>
                    <p className="text-xs text-slate-400">准确率</p>
                  </div>
                </div>
              ))}
            </div>
          )}
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

function calculateRuntime(jobs: any[]): string {
  const completedJobs = jobs.filter(j => j.status === 'completed' && j.finished_at && j.created_at)
  if (completedJobs.length === 0) return '0h'
  
  let totalMs = 0
  completedJobs.forEach(job => {
    const start = new Date(job.created_at).getTime()
    const end = new Date(job.finished_at).getTime()
    totalMs += end - start
  })
  
  const hours = Math.floor(totalMs / (1000 * 60 * 60))
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}
