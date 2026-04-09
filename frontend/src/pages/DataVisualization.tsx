import { useState } from 'react'
import { BarChart3, TrendingUp, Layers } from 'lucide-react'
import Card from '../components/Card'
import Select from '../components/Select'
import Input from '../components/Input'
import Button from '../components/Button'
import {
  HistogramChart,
  ScatterChartComponent,
  FeatureImportanceChart,
  type HistogramDatum,
  type ScatterDatum,
  type FeatureImportanceDatum,
} from '../components/Charts'

// ─── Mock Data ───────────────────────────────────────────────────────────────

const generateHistogramData = (_feature: string): HistogramDatum[] => {
  const ranges = ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-100']
  const counts = Array.from({ length: 10 }, () => Math.floor(Math.random() * 200 + 20))
  return ranges.map((range, i) => ({ range, count: counts[i], density: counts[i] / 1000 }))
}

const generateScatterData = (n = 80): ScatterDatum[] =>
  Array.from({ length: n }, (_, i) => ({
    x: Math.random() * 100,
    y: Math.random() * 100 + (i % 3 === 0 ? 10 : 0),
    name: `点-${i + 1}`,
    size: Math.floor(Math.random() * 30 + 10),
  }))

const FEATURE_NAMES = [
  'sepal_length', 'sepal_width', 'petal_length', 'petal_width',
  'age', 'income', 'score', 'duration', 'balance', 'campaign',
]

const generateFeatureImportance = (): FeatureImportanceDatum[] =>
  FEATURE_NAMES.map((feature, i) => ({
    feature,
    importance: parseFloat((Math.random() * (0.9 - i * 0.08) + 0.05).toFixed(4)),
    color: undefined,
  })).sort((a, b) => b.importance - a.importance)

// ─── Options ──────────────────────────────────────────────────────────────────

const FEATURE_OPTIONS = FEATURE_NAMES.map((f) => ({ value: f, label: f }))

const DATASET_OPTIONS = [
  { value: 'iris', label: 'Iris 数据集' },
  { value: 'wine', label: 'Wine 数据集' },
  { value: 'boston', label: 'Boston Housing' },
  { value: 'custom', label: '自定义上传' },
]

const SCATTER_X_OPTIONS = FEATURE_NAMES.map((f) => ({ value: f, label: f }))
const SCATTER_Y_OPTIONS = FEATURE_NAMES.map((f) => ({ value: f, label: f }))

// ─── Component ────────────────────────────────────────────────────────────────

export default function DataVisualization() {
  const [dataset, setDataset] = useState('iris')
  const [histogramFeature, setHistogramFeature] = useState('sepal_length')
  const [scatterX, setScatterX] = useState('sepal_length')
  const [scatterY, setScatterY] = useState('sepal_width')
  const [topN, setTopN] = useState<string>('10')

  const [loadingHistogram, setLoadingHistogram] = useState(false)
  const [loadingScatter, setLoadingScatter] = useState(false)
  const [loadingImportance, setLoadingImportance] = useState(false)

  const [histogramData, setHistogramData] = useState<HistogramDatum[]>([])
  const [scatterData, setScatterData] = useState<ScatterDatum[]>([])
  const [importanceData, setImportanceData] = useState<FeatureImportanceDatum[]>([])

  const [histogramLoaded, setHistogramLoaded] = useState(false)
  const [scatterLoaded, setScatterLoaded] = useState(false)
  const [importanceLoaded, setImportanceLoaded] = useState(false)

  const simulateLoad = (setLoading: (v: boolean) => void, setData: (v: any[]) => void, setLoaded: (v: boolean) => void, genFn: () => any[]) => {
    setLoading(true)
    setLoaded(false)
    setTimeout(() => {
      setData(genFn())
      setLoading(false)
      setLoaded(true)
    }, 800)
  }

  const handleRefreshHistogram = () =>
    simulateLoad(setLoadingHistogram, setHistogramData, setHistogramLoaded, () =>
      generateHistogramData(histogramFeature)
    )

  const handleRefreshScatter = () =>
    simulateLoad(setLoadingScatter, setScatterData, setScatterLoaded, generateScatterData)

  const handleRefreshImportance = () =>
    simulateLoad(setLoadingImportance, setImportanceData, setImportanceLoaded, generateFeatureImportance)

  // Auto-load on mount
  const [initialized, setInitialized] = useState(false)
  if (!initialized) {
    setInitialized(true)
    setTimeout(() => {
      setHistogramData(generateHistogramData(histogramFeature))
      setHistogramLoaded(true)
      setScatterData(generateScatterData())
      setScatterLoaded(true)
      setImportanceData(generateFeatureImportance())
      setImportanceLoaded(true)
    }, 300)
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">数据可视化</h1>
        <p className="text-slate-500 mt-1">探索数据分布、变量关系与特征重要性</p>
      </div>

      {/* Global Controls */}
      <Card>
        <div className="flex flex-col sm:flex-row sm:items-end gap-4">
          <div className="flex-1">
            <Select
              label="数据集"
              options={DATASET_OPTIONS}
              value={dataset}
              onChange={(e) => setDataset(e.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" size="sm" onClick={handleRefreshHistogram}>
              刷新全部
            </Button>
          </div>
        </div>
      </Card>

      {/* Charts Row 1: Histogram + Scatter */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Histogram */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary-600" />
              <h2 className="text-lg font-semibold text-slate-900">数据分布</h2>
            </div>
            <div className="flex items-center gap-2">
              <Select
                options={FEATURE_OPTIONS}
                value={histogramFeature}
                onChange={(e) => setHistogramFeature(e.target.value)}
                className="w-36"
              />
              <Button variant="ghost" size="sm" onClick={handleRefreshHistogram}>
                刷新
              </Button>
            </div>
          </div>

          <HistogramChart
            data={histogramData}
            loading={loadingHistogram || !histogramLoaded}
            emptyText="请先加载数据"
            color="#6366f1"
            height={280}
          />

          {histogramLoaded && histogramData.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-500">
                特征 <span className="font-medium text-slate-700">{histogramFeature}</span> 的分布
                · 共 <span className="font-medium text-slate-700">{histogramData.reduce((s, d) => s + d.count, 0)}</span> 条记录
              </p>
            </div>
          )}
        </Card>

        {/* Scatter */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-600" />
              <h2 className="text-lg font-semibold text-slate-900">散点图</h2>
            </div>
            <div className="flex items-center gap-2">
              <Select
                label="X 轴"
                options={SCATTER_X_OPTIONS}
                value={scatterX}
                onChange={(e) => setScatterX(e.target.value)}
                className="w-36"
              />
              <span className="text-slate-400 mt-4">×</span>
              <Select
                label="Y 轴"
                options={SCATTER_Y_OPTIONS}
                value={scatterY}
                onChange={(e) => setScatterY(e.target.value)}
                className="w-36"
              />
              <Button variant="ghost" size="sm" onClick={handleRefreshScatter}>
                刷新
              </Button>
            </div>
          </div>

          <ScatterChartComponent
            data={scatterData}
            loading={loadingScatter || !scatterLoaded}
            emptyText="请先加载数据"
            xLabel={scatterX}
            yLabel={scatterY}
            height={280}
            color="#10b981"
          />

          {scatterLoaded && scatterData.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-500">
                {scatterX} × {scatterY} · 共 <span className="font-medium text-slate-700">{scatterData.length}</span> 个数据点
              </p>
            </div>
          )}
        </Card>
      </div>

      {/* Feature Importance */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-violet-600" />
            <h2 className="text-lg font-semibold text-slate-900">特征重要性</h2>
          </div>
          <div className="flex items-center gap-2">
            <Input
              label="显示 Top N"
              value={topN}
              onChange={(e) => setTopN(e.target.value)}
              className="w-20 text-center"
              type="number"
              min="1"
              max="20"
            />
            <Button variant="ghost" size="sm" onClick={handleRefreshImportance}>
              刷新
            </Button>
          </div>
        </div>

        <FeatureImportanceChart
          data={importanceData}
          loading={loadingImportance || !importanceLoaded}
          emptyText="暂无特征重要性数据"
          color="#8b5cf6"
          height={320}
          topN={parseInt(topN) || undefined}
        />

        {importanceLoaded && importanceData.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-sm text-slate-500">
              基于当前模型评估 · 共 <span className="font-medium text-slate-700">{importanceData.length}</span> 个特征
            </p>
          </div>
        )}
      </Card>
    </div>
  )
}
