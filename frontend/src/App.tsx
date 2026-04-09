import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { Sparkles, Database, LineChart, LogOut, User } from 'lucide-react'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import Training from './pages/Training'
import Experiments from './pages/Experiments'
import AuthPage from './pages/AuthPage'

type Tab = 'dashboard' | 'training' | 'experiments'

const tabs = [
  { id: 'dashboard' as const, label: '仪表盘', icon: Sparkles },
  { id: 'training' as const, label: '模型训练', icon: Database },
  { id: 'experiments' as const, label: '实验记录', icon: LineChart },
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
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [user, setUser] = useState<{ username: string; email: string } | null>(null)
  const [showUserMenu, setShowUserMenu] = useState(false)

  // Sync activeTab with URL on mount and URL change
  useEffect(() => {
    const path = location.pathname
    if (path.includes('/training')) setActiveTab('training')
    else if (path.includes('/experiments')) setActiveTab('experiments')
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
    window.location.href = '/login'
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
                  window.location.href = '/' + tab.id
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
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'training' && <Training />}
        {activeTab === 'experiments' && <Experiments />}
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<AuthPage />} />
        <Route element={<PrivateRoute />}>
          <Route path="/dashboard" element={<Layout />} />
          <Route path="/training" element={<Layout />} />
          <Route path="/experiments" element={<Layout />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
