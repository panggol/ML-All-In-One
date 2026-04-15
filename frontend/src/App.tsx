import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Sparkles, Database, LineChart, LogOut, User, Wand, Cpu, FolderOpen, Activity, BarChart3, FileText, ShieldCheck, Package, TrendingUp, Clock, GitBranch } from 'lucide-react'
import { useState, useEffect, lazy, Suspense } from 'react'
// 懒加载页面组件，减少主包体积
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Monitor = lazy(() => import('./pages/Monitor'))
const Training = lazy(() => import('./pages/Training'))
const Forecasting = lazy(() => import('./pages/Forecasting'))
const Experiments = lazy(() => import('./pages/Experiments'))
const AutoML = lazy(() => import('./pages/AutoML'))
const Preprocessing = lazy(() => import('./pages/Preprocessing'))
const Inference = lazy(() => import('./pages/Inference'))
const DataManagement = lazy(() => import('./pages/DataManagement'))
const DataVisualization = lazy(() => import('./pages/DataVisualization'))
const AuthPage = lazy(() => import('./pages/AuthPage'))
const Logs = lazy(() => import('./pages/Logs'))
const AdminUsers = lazy(() => import('./pages/AdminUsers'))
const Models = lazy(() => import('./pages/Models'))
const Scheduler = lazy(() => import('./pages/Scheduler'))
const Pipelines = lazy(() => import('./pages/Pipelines'))

// 懒加载页面的加载状态
function PageLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-slate-500 text-sm">加载中...</span>
      </div>
    </div>
  )
}

type Tab = 'dashboard' | 'monitor' | 'training' | 'forecasting' | 'experiments' | 'automl' | 'preprocessing' | 'inference' | 'data' | 'visualization' | 'logs' | 'admin' | 'models' | 'scheduler'

const tabs = [
  { id: 'dashboard' as const, label: '仪表盘', icon: Sparkles },
  { id: 'monitor' as const, label: '系统监控', icon: Activity },
  { id: 'data' as const, label: '数据管理', icon: FolderOpen },
  { id: 'forecasting' as const, label: '时序预测', icon: TrendingUp },
  { id: 'training' as const, label: '模型训练', icon: Database },
  { id: 'experiments' as const, label: '实验记录', icon: LineChart },
  { id: 'models' as const, label: '模型管理', icon: Package },
  { id: 'preprocessing' as const, label: '预处理', icon: Wand },
  { id: 'inference' as const, label: '推理', icon: Cpu },
  { id: 'automl' as const, label: 'AutoML', icon: Sparkles },
  { id: 'visualization' as const, label: '数据可视化', icon: BarChart3 },
  { id: 'logs' as const, label: '日志', icon: FileText },
  { id: 'admin' as const, label: '用户管理', icon: ShieldCheck },
  { id: 'scheduler' as const, label: '任务调度', icon: Clock },
  { id: 'pipelines' as const, label: 'Pipeline 编排', icon: GitBranch },
]

// 私有路由包装
function PrivateRoute() {
  const token = localStorage.getItem('token')
  if (!token) {
    return <Navigate to="/login" replace />
  }
  // 权限检查（P0-F8/S6）：非 admin 用户不可访问管理路由
  const userStr = localStorage.getItem('user')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      const path = window.location.pathname
      if (path.startsWith('/admin') && user.role !== 'admin') {
        return <Navigate to="/dashboard" replace />
      }
    } catch {
      // ignore parse errors
    }
  }
  return <Outlet />
}

// 主布局
function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [user, setUser] = useState<{ username: string; email: string } | null>(null)
  const [showUserMenu, setShowUserMenu] = useState(false)

  // Sync activeTab with URL on mount and URL change
  useEffect(() => {
    const path = location.pathname
    if (path.includes('/admin')) setActiveTab('admin')
    else if (path.includes('/logs')) setActiveTab('logs')
    else if (path.includes('/visualization')) setActiveTab('visualization')
    else if (path.includes('/monitor')) setActiveTab('monitor')
    else if (path.includes('/data')) setActiveTab('data')
    else if (path.includes('/training')) setActiveTab('training')
    else if (path.includes('/forecasting')) setActiveTab('forecasting')
    else if (path.includes('/experiments')) setActiveTab('experiments')
    else if (path.includes('/automl')) setActiveTab('automl')
    else if (path.includes('/models')) setActiveTab('models')
    else if (path.includes('/preprocessing')) setActiveTab('preprocessing')
    else if (path.includes('/inference')) setActiveTab('inference')
    else if (path.includes('/scheduler')) setActiveTab('scheduler')
    else if (path.includes('/pipelines')) setActiveTab('pipelines')
    else setActiveTab('dashboard')
  }, [location.pathname])

  useEffect(() => {
    const userStr = localStorage.getItem('user')
    if (userStr) {
      setUser(JSON.parse(userStr))
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  // 计算当前用户角色，用于动态过滤侧边栏 tabs
  const userRole = (() => {
    const u = localStorage.getItem('user')
    if (!u) return 'user'
    try { return JSON.parse(u).role || 'user' } catch { return 'user' }
  })()

  // 动态 tabs（P0-S6）：非 admin 用户不显示"用户管理" tab
  const visibleTabs = tabs.filter(tab => tab.id !== 'admin' || userRole === 'admin')

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Left Sidebar */}
      <aside className="w-56 bg-white border-r border-slate-200 flex flex-col fixed left-0 top-0 h-screen">
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-5 border-b border-slate-200">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="text-base font-semibold text-slate-900">ML All In One</span>
        </div>

        {/* Nav Tabs */}
        <nav className="flex-1 py-4 px-3 overflow-y-auto">
          <div className="space-y-1">
            {visibleTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id)
                  navigate('/' + (tab.id === 'dashboard' ? 'dashboard' : tab.id))
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium transition-all duration-150 text-left ${
                  activeTab === tab.id
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <tab.icon className="w-4 h-4 flex-shrink-0" />
                <span className="text-sm">{tab.label}</span>
              </button>
            ))}
          </div>
        </nav>

        {/* User Menu */}
        <div className="p-3 border-t border-slate-200">
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <div className="w-7 h-7 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0">
                <User className="w-3.5 h-3.5 text-primary-600" />
              </div>
              <span className="text-sm font-medium text-slate-700 truncate">{user?.username || '用户'}</span>
            </button>

            {showUserMenu && (
              <div className="absolute left-0 bottom-full mb-1 w-full bg-white rounded-xl shadow-lg border border-slate-200 py-1">
                <div className="px-3 py-2 border-b border-slate-100">
                  <p className="font-medium text-slate-900 text-sm">{user?.username}</p>
                  <p className="text-xs text-slate-500 truncate">{user?.email}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  退出登录
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 ml-56">
        {/* Top Bar */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-50 h-16">
          <div className="h-full px-8 flex items-center">
            <h1 className="text-lg font-semibold text-slate-800">
              {tabs.find(t => t.id === activeTab)?.label || 'ML All In One'}
            </h1>
          </div>
        </header>

        {/* Page Content */}
        <main className="px-8 py-8">
          <Suspense fallback={<PageLoader />}>
            {activeTab === 'dashboard' && <Dashboard />}
            {activeTab === 'monitor' && <Monitor />}
            {activeTab === 'data' && <DataManagement />}
            {activeTab === 'training' && <Training />}
            {activeTab === 'forecasting' && <Forecasting />}
            {activeTab === 'experiments' && <Experiments />}
            {activeTab === 'preprocessing' && <Preprocessing />}
            {activeTab === 'inference' && <Inference />}
            {activeTab === 'automl' && <AutoML />}
            {activeTab === 'visualization' && <DataVisualization />}
            {activeTab === 'logs' && <Logs />}
            {activeTab === 'admin' && <AdminUsers />}
            {activeTab === 'models' && <Models />}
            {activeTab === 'scheduler' && <Scheduler />}
            {activeTab === 'pipelines' && <Pipelines />}
          </Suspense>
        </main>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<AuthPage />} />
          <Route element={<PrivateRoute />}>
            <Route path="/data" element={<Layout />} />
            <Route path="/monitor" element={<Layout />} />
            <Route path="/dashboard" element={<Layout />} />
            <Route path="/training" element={<Layout />} />
            <Route path="/forecasting" element={<Layout />} />
            <Route path="/experiments" element={<Layout />} />
            <Route path="/models" element={<Layout />} />
            <Route path="/preprocessing" element={<Layout />} />
            <Route path="/inference" element={<Layout />} />
            <Route path="/automl" element={<Layout />} />
            <Route path="/visualization" element={<Layout />} />
            <Route path="/logs" element={<Layout />} />
            <Route path="/admin/users" element={<Layout />} />
            <Route path="/scheduler" element={<Layout />} />
            <Route path="/pipelines" element={<Layout />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
