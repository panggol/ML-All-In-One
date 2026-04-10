import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Sparkles, Database, LineChart, LogOut, User, Wand, Cpu, FolderOpen, Activity } from 'lucide-react'
import { useState, useEffect, lazy, Suspense } from 'react'
// 懒加载页面组件，减少主包体积
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Monitor = lazy(() => import('./pages/Monitor'))
const Training = lazy(() => import('./pages/Training'))
const Experiments = lazy(() => import('./pages/Experiments'))
const AutoML = lazy(() => import('./pages/AutoML'))
const Preprocessing = lazy(() => import('./pages/Preprocessing'))
const Inference = lazy(() => import('./pages/Inference'))
const DataManagement = lazy(() => import('./pages/DataManagement'))
const AuthPage = lazy(() => import('./pages/AuthPage'))

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

type Tab = 'dashboard' | 'monitor' | 'training' | 'experiments' | 'automl' | 'preprocessing' | 'inference' | 'data'

const tabs = [
  { id: 'dashboard' as const, label: '仪表盘', icon: Sparkles },
  { id: 'monitor' as const, label: '系统监控', icon: Activity },
  { id: 'data' as const, label: '数据管理', icon: FolderOpen },
  { id: 'training' as const, label: '模型训练', icon: Database },
  { id: 'experiments' as const, label: '实验记录', icon: LineChart },
  { id: 'preprocessing' as const, label: '预处理', icon: Wand },
  { id: 'inference' as const, label: '推理', icon: Cpu },
  { id: 'automl' as const, label: 'AutoML', icon: Sparkles },
]

// 私有路由包装
function PrivateRoute() {
  const token = localStorage.getItem('token')
  if (!token) {
    return <Navigate to="/login" replace />
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
    if (path.includes('/monitor')) setActiveTab('monitor')
    else if (path.includes('/data')) setActiveTab('data')
    else if (path.includes('/training')) setActiveTab('training')
    else if (path.includes('/experiments')) setActiveTab('experiments')
    else if (path.includes('/automl')) setActiveTab('automl')
    else if (path.includes('/preprocessing')) setActiveTab('preprocessing')
    else if (path.includes('/inference')) setActiveTab('inference')
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

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-semibold text-slate-900">ML All In One</span>
          </div>
          
          <nav className="flex items-center gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id)
                  navigate('/' + (tab.id === 'dashboard' ? 'dashboard' : tab.id))
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-150 ${
                  activeTab === tab.id
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>

          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
                <User className="w-4 h-4 text-primary-600" />
              </div>
              <span className="text-sm font-medium text-slate-700">{user?.username || '用户'}</span>
            </button>
            
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1">
                <div className="px-4 py-2 border-b border-slate-100">
                  <p className="font-medium text-slate-900">{user?.username}</p>
                  <p className="text-xs text-slate-500">{user?.email}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  退出登录
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Suspense fallback={<PageLoader />}>
          {activeTab === 'dashboard' && <Dashboard />}
          {activeTab === 'monitor' && <Monitor />}
          {activeTab === 'data' && <DataManagement />}
          {activeTab === 'training' && <Training />}
          {activeTab === 'experiments' && <Experiments />}
          {activeTab === 'preprocessing' && <Preprocessing />}
          {activeTab === 'inference' && <Inference />}
          {activeTab === 'automl' && <AutoML />}
        </Suspense>
      </main>
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
            <Route path="/experiments" element={<Layout />} />
            <Route path="/preprocessing" element={<Layout />} />
            <Route path="/inference" element={<Layout />} />
            <Route path="/automl" element={<Layout />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
