import { useState, useEffect, useCallback } from 'react'
import { BarChart3, TrendingUp, Layers, RefreshCw, AlertCircle, Activity } from 'lucide-react'
import Card from '../components/Card'
import Select from '../components/Select'
import Button from '../components/Button'
import {
  HistogramChart,
  ScatterChartComponent,
  FeatureImportanceChart,
  TrainingCurvesChart,
  type HistogramDatum,
  type ScatterDatum,
  type FeatureImportanceDatum,
} from '../components/Charts'
import { dataApi, experimentApi, vizApi } from '../api'
import type { DataFile, Experiment } from '../api'
import type { TrainingCurvesResponse } from '../api/viz'

// ─── 工具函数 ────────────────────────────────────────────────────────────────

function toHistogramData(stats: any): HistogramDatum[] {
  const h = stats.histogram
  if (!h) return []
  return h.midpoints.map((_mid: number, i: number) => ({
    range: `${h.bins[i].toFixed(1)}-${h.bins[i + 1].toFixed(1)}`,
    count: h.counts[i],
    density: h.counts[i] / (h.bins[i + 1] - h.bins[i]) / (h.counts.reduce((s: number, c: number) => s + c, 0) || 1),
  }))
}

function toScatterData(actual: number[], predicted: number[]): ScatterDatum[] {
  return actual.map((a, i) => ({
    x: a,
    y: predicted[i],
    name: `样本-${i + 1}`,
    size: 20,
  }))
}

function toFeatureImportanceData(items: any[]): FeatureImportanceDatum[] {
  return items.map((item) => ({
    feature: item.feature,
    importance: Number(item.importance),
    color: undefined,
  }))
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DataVisualization() {
  const [dataFiles, setDataFiles] = useState<DataFile[]>([])
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [selectedDataFile, setSelectedDataFile] = useState<number | null>(null)
  const [selectedExp, setSelectedExp] = useState<number | null>(null)
  const [plotType, setPlotType] = useState<'histogram' | 'boxplot'>('histogram')
  const [selectedFeature, setSelectedFeature] = useState<string>('')
  const [selectedTab, setSelectedTab] = useState<'distribution' | 'importance' | 'evaluation' | 'training'>('distribution')

  const [loadingDist, setLoadingDist] = useState(false)
  const [loadingScatter, setLoadingScatter] = useState(false)
  const [loadingImportance, setLoadingImportance] = useState(false)
  const [distError, setDistError] = useState<string>('')
  const [impError, setImpError] = useState<string>('')

  const [distData, setDistData] = useState<HistogramDatum[]>([])
  const [scatterData, setScatterData] = useState<ScatterDatum[]>([])
  const [importanceData, setImportanceData] = useState<FeatureImportanceDatum[]>([])
  const [distLoaded, setDistLoaded] = useState(false)
  const [scatterLoaded, setScatterLoaded] = useState(false)
  const [importanceLoaded, setImportanceLoaded] = useState(false)
  const [loadingCurves, setLoadingCurves] = useState(false)
  const [curvesLoaded, setCurvesLoaded] = useState(false)
  const [curvesError, setCurvesError] = useState<string>('')
  const [curvesData, setCurvesData] = useState<TrainingCurvesResponse | null>(null)

  const [summary, setSummary] = useState<{ rows: number; columns: number; numeric_features: number } | null>(null)

  // 加载数据文件列表
  useEffect(() => {
    dataApi.list().then((files) => {
      setDataFiles(files)
      if (files.length > 0) setSelectedDataFile(files[0].id)
    }).catch(() => {})
    experimentApi.list().then((exps) => {
      setExperiments(exps)
      if (exps.length > 0) setSelectedExp(exps[0].id)
    }).catch(() => {})
  }, [])

  // 加载数据分布
  const loadDistributions = useCallback(async () => {
    if (!selectedDataFile) return
    setLoadingDist(true)
    setDistError('')
    setDistLoaded(false)
    try {
      const data = await vizApi.getDistributions(selectedDataFile, { plot_type: plotType })
      // 取第一个数值特征的直方图数据
      const numericPlot = data.plots.find((p) => p.dtype !== 'object' && p.stats.histogram)
      if (numericPlot?.stats.histogram) {
        setDistData(toHistogramData(numericPlot.stats))
        setSelectedFeature(numericPlot.feature)
      } else if (data.plots.length > 0) {
        setSelectedFeature(data.plots[0].feature)
        setDistData(toHistogramData(data.plots[0].stats))
      }
      setSummary({ rows: data.dataset_info.rows, columns: data.dataset_info.columns, numeric_features: data.plots.filter(p => p.dtype !== 'object').length })
      setDistLoaded(true)
    } catch (e: any) {
      setDistError(e?.response?.data?.detail || '加载失败')
    } finally {
      setLoadingDist(false)
    }
  }, [selectedDataFile, plotType])

  // 加载评估散点图（真实值 vs 预测值）
  const loadScatter = useCallback(async () => {
    if (!selectedExp) return
    setLoadingScatter(true)
    setScatterLoaded(false)
    try {
      const eval_ = await vizApi.getEvaluation(selectedExp)
      const scatterPlot = eval_.plots.find((p) => p.type === 'true_vs_predicted')
      const confusionPlot = eval_.plots.find((p) => p.type === 'confusion_matrix')
      if (scatterPlot) {
        const { actual, predicted } = scatterPlot.data
        setScatterData(toScatterData(actual, predicted))
      } else if (confusionPlot) {
        // 二分类混淆矩阵转散点：1D数据用对角线示意
        setScatterData([])
      }
      setScatterLoaded(true)
    } catch {
      setScatterLoaded(true)
    } finally {
      setLoadingScatter(false)
    }
  }, [selectedExp])

  // 加载特征重要性
  const loadImportance = useCallback(async () => {
    if (!selectedExp) return
    setLoadingImportance(true)
    setImpError('')
    setImportanceLoaded(false)
    try {
      const data = await vizApi.getFeatureImportance(selectedExp)
      if (data.importance.length > 0) {
        setImportanceData(toFeatureImportanceData(data.importance))
      } else {
        setImportanceData([])
      }
      setImportanceLoaded(true)
    } catch (e: any) {
      setImpError(e?.response?.data?.detail || '加载失败')
      setImportanceLoaded(true)
    } finally {
      setLoadingImportance(false)
    }
  }, [selectedExp])

  // 加载训练曲线
  const loadTrainingCurves = useCallback(async () => {
    if (!selectedExp) return
    setLoadingCurves(true)
    setCurvesError('')
    setCurvesLoaded(false)
    try {
      const data = await vizApi.getTrainingCurves(selectedExp)
      setCurvesData(data)
      setCurvesLoaded(true)
    } catch (e: any) {
      setCurvesError(e?.response?.data?.detail || '加载失败')
      setCurvesLoaded(true)
    } finally {
      setLoadingCurves(false)
    }
  }, [selectedExp])

  // 数据文件变化时自动加载
  useEffect(() => {
    if (selectedDataFile) loadDistributions()
  }, [selectedDataFile, plotType])

  // 实验变化时加载散点和重要性
  useEffect(() => {
    if (selectedExp) {
      loadScatter()
      loadImportance()
      loadTrainingCurves()
    }
  }, [selectedExp])

  const tabs = [
    { key: 'distribution', label: '数据分布', icon: BarChart3 },
    { key: 'importance', label: '特征重要性', icon: Layers },
    { key: 'evaluation', label: '评估', icon: TrendingUp },
    { key: 'training', label: '训练曲线', icon: Activity },
  ] as const

  const dataFileOptions = dataFiles.map((f) => ({ value: String(f.id), label: f.filename }))
  const expOptions = experiments.map((e) => ({ value: String(e.id), label: e.name }))

  const currentFile = dataFiles.find((f) => f.id === selectedDataFile)
  const featureOptions = currentFile?.columns.map((c) => ({ value: c, label: c })) || []

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">数据可视化</h1>
        <p className="text-slate-500 mt-1">探索数据分布、特征重要性与预测结果</p>
      </div>

      {/* Global Controls */}
      <Card>
        <div className="flex flex-col sm:flex-row sm:items-end gap-4 flex-wrap">
          <div className="flex-1 min-w-48">
            <Select
              label="数据集"
              options={dataFileOptions}
              value={String(selectedDataFile ?? '')}
              onChange={(e) => setSelectedDataFile(Number(e.target.value))}
            />
          </div>
          <div className="flex-1 min-w-48">
            <Select
              label="实验"
              options={expOptions}
              value={String(selectedExp ?? '')}
              onChange={(e) => setSelectedExp(Number(e.target.value))}
            />
          </div>
          <div className="flex gap-2 items-end">
            <Button variant="secondary" size="sm" onClick={loadDistributions} disabled={!selectedDataFile || loadingDist}>
              <RefreshCw className="w-4 h-4 mr-1" />
              刷新
            </Button>
          </div>
        </div>
      </Card>

      {/* Tab Navigation */}
      <Card>
        <div className="flex gap-1 overflow-x-auto">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setSelectedTab(key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                selectedTab === key
                  ? 'bg-primary-100 text-primary-700'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </Card>

      {/* Tab Content */}
      {selectedTab === 'distribution' && (
        <>
          {/* Summary Stats */}
          {summary && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <Card className="text-center py-4">
                <p className="text-2xl font-semibold text-slate-900">{summary.rows.toLocaleString()}</p>
                <p className="text-sm text-slate-500 mt-1">样本数</p>
              </Card>
              <Card className="text-center py-4">
                <p className="text-2xl font-semibold text-slate-900">{summary.columns}</p>
                <p className="text-sm text-slate-500 mt-1">特征数</p>
              </Card>
              <Card className="text-center py-4">
                <p className="text-2xl font-semibold text-slate-900">{summary.numeric_features}</p>
                <p className="text-sm text-slate-500 mt-1">数值特征</p>
              </Card>
            </div>
          )}

          {/* Histogram */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-primary-600" />
                <h2 className="text-lg font-semibold text-slate-900">数据分布</h2>
              </div>
              <div className="flex items-center gap-2">
                <Select
                  label="类型"
                  options={[
                    { value: 'histogram', label: '直方图' },
                    { value: 'boxplot', label: '箱线图' },
                  ]}
                  value={plotType}
                  onChange={(e) => setPlotType(e.target.value as 'histogram' | 'boxplot')}
                  className="w-28"
                />
                <Select
                  label="特征"
                  options={featureOptions}
                  value={selectedFeature}
                  onChange={(e) => setSelectedFeature(e.target.value)}
                  className="w-40"
                />
              </div>
            </div>

            {distError && (
              <div className="flex items-center gap-2 text-red-500 text-sm mb-3">
                <AlertCircle className="w-4 h-4" />
                {distError}
              </div>
            )}

            <HistogramChart
              data={distData}
              loading={loadingDist || !distLoaded}
              emptyText={selectedDataFile ? '暂无分布数据' : '请先选择数据集'}
              color="#6366f1"
              height={280}
            />

            {distLoaded && distData.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <p className="text-sm text-slate-500">
                  特征 <span className="font-medium text-slate-700">{selectedFeature}</span> 的分布
                  · 共 <span className="font-medium text-slate-700">{distData.reduce((s, d) => s + d.count, 0).toLocaleString()}</span> 条记录
                </p>
              </div>
            )}
          </Card>
        </>
      )}

      {selectedTab === 'importance' && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-violet-600" />
              <h2 className="text-lg font-semibold text-slate-900">特征重要性</h2>
            </div>
            <Button variant="ghost" size="sm" onClick={loadImportance} disabled={!selectedExp || loadingImportance}>
              <RefreshCw className="w-4 h-4 mr-1" />
              刷新
            </Button>
          </div>

          {impError && (
            <div className="flex items-center gap-2 text-red-500 text-sm mb-3">
              <AlertCircle className="w-4 h-4" />
              {impError}
            </div>
          )}

          <FeatureImportanceChart
            data={importanceData}
            loading={loadingImportance || !importanceLoaded}
            emptyText={selectedExp ? '该实验无特征重要性数据' : '请先选择实验'}
            color="#8b5cf6"
            height={320}
          />

          {importanceLoaded && importanceData.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-500">
                基于当前实验模型 · 共 <span className="font-medium text-slate-700">{importanceData.length}</span> 个特征
              </p>
            </div>
          )}
        </Card>
      )}

      {selectedTab === 'evaluation' && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-600" />
              <h2 className="text-lg font-semibold text-slate-900">预测结果</h2>
            </div>
            <span className="text-xs text-slate-400">{selectedExp ? `实验 #${selectedExp}` : '请选择实验'}</span>
          </div>

          <ScatterChartComponent
            data={scatterData}
            loading={loadingScatter || !scatterLoaded}
            emptyText={selectedExp ? '暂无预测数据' : '请先选择实验'}
            xLabel="真实值"
            yLabel="预测值"
            height={280}
            color="#10b981"
          />

          {scatterLoaded && scatterData.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-500">
                真实值 vs 预测值 · 共 <span className="font-medium text-slate-700">{scatterData.length}</span> 个样本
              </p>
            </div>
          )}
        </Card>
      )}

      {selectedTab === 'training' && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-amber-600" />
              <h2 className="text-lg font-semibold text-slate-900">训练曲线</h2>
            </div>
            <Button variant="ghost" size="sm" onClick={loadTrainingCurves} disabled={!selectedExp || loadingCurves}>
              <RefreshCw className="w-4 h-4 mr-1" />
              刷新
            </Button>
          </div>

          {curvesError && (
            <div className="flex items-center gap-2 text-red-500 text-sm mb-3">
              <AlertCircle className="w-4 h-4" />
              {curvesError}
            </div>
          )}

          <TrainingCurvesChart
            data={curvesData ? { epochs: curvesData.epochs, curves: curvesData.curves } : { epochs: [], curves: [] }}
            loading={loadingCurves || !curvesLoaded}
            height={320}
          />

          {curvesLoaded && curvesData && curvesData.curves.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-sm text-slate-500">
                基于实验 <span className="font-medium text-slate-700">#{selectedExp}</span> · 共 <span className="font-medium text-slate-700">{curvesData.epochs.length}</span> 个 Epoch · <span className="font-medium text-slate-700">{curvesData.curves.length}</span> 条曲线
              </p>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
