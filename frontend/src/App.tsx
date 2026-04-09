import { useState } from 'react'
import { Sparkles, Database, LineChart, Settings } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Training from './pages/Training'
import Experiments from './pages/Experiments'

type Tab = 'dashboard' | 'training' | 'experiments'

const tabs = [
  { id: 'dashboard' as const, label: '仪表盘', icon: Sparkles },
  { id: 'training' as const, label: '模型训练', icon: Database },
  { id: 'experiments' as const, label: '实验记录', icon: LineChart },
]

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')

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
                onClick={() => setActiveTab(tab.id)}
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

export default App
