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
  BoxplotChart,
  SingleVarLineChart,
  type HistogramDatum,
  type ScatterDatum,
  type FeatureImportanceDatum,
  type BoxplotDatum,
  type SingleVarLineDatum,
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
  const [plotType, setPlotType] = useState<'histogram' | 'boxplot' | 'scatter' | 'pie' | 'line'>('histogram')
  const [selectedFeature, setSelectedFeature] = useState<string>('')
  const [xFeature, setXFeature] = useState<string>('')
  const [yFeature, setYFeature] = useState<string>('')
  const [selectedTab, setSelectedTab] = useState<'distribution' | 'importance' | 'evaluation' | 'training'>('distribution')

  const [loadingDist, setLoadingDist] = useState(false)
  const [loadingScatter, setLoadingScatter] = useState(false)
  const [loadingImportance, setLoadingImportance] = useState(false)
  const [distError, setDistError] = useState<string>('')
  const [impError, setImpError] = useState<string>('')

  const [distData, setDistData] = useState<HistogramDatum[]>([])
  const [boxplotData, setBoxplotData] = useState<BoxplotDatum[]>([])
  const [scatterData, setScatterData] = useState<ScatterDatum[]>([])
  const [pieImage, setPieImage] = useState<string>('')
  const [lineData, setLineData] = useState<SingleVarLineDatum[]>([])
  const [lineStats, setLineStats] = useState<{ min: number; max: number; median: number; count: number } | null>(null)
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
    setDistData([])
    setBoxplotData([])
    setScatterData([])
    setPieImage('')
    setLineData([])
    setLineStats(null)
    try {
      const data = await vizApi.getDistributions(selectedDataFile, {
        plot_type: plotType,
        features: plotType === 'scatter'
          ? `${xFeature || ''},${yFeature || ''}`
          : (plotType === 'line' ? selectedFeature : selectedFeature) || undefined,
      })

      if (plotType === 'scatter') {
        // 后端返回 scatter.image（base64 PNG）
        const img = data.scatter?.image
        if (img) {
          setScatterData([{ x: 0, y: 0, name: img }] as unknown as ScatterDatum[])
          ;(window as any).__scatterImg = img
        }
        setDistLoaded(true)
        return
      }

      // line 模式：单变量折线图
      if (plotType === 'line') {
        const line = data.line
        if (line && line.x && line.y) {
          setSelectedFeature(line.feature)
          setLineData(line.x.map((v: number, i: number) => ({ index: v, value: line.y[i] })))
          setLineStats({ min: line.min, max: line.max, median: line.median, count: line.count })
        }
        // 同步 dtype 列表
        const nums = (data.plots || []).filter((p: any) => p.dtype !== 'object').map((p: any) => p.feature)
        const cats = (data.plots || []).filter((p: any) => p.dtype === 'object').map((p: any) => p.feature)
        setNumericColumns(nums)
        setCategoricalColumns(cats)
        setDistLoaded(true)
        return
      }

      // histogram / boxplot / pie
      const numericPlot = data.plots.find(
        (p) => p.dtype !== 'object' && (p.stats.histogram || p.stats.boxplot)
      )
      // 同步 dtype 列表
      const nums = data.plots.filter((p) => p.dtype !== 'object').map((p) => p.feature)
      const cats = data.plots.filter((p) => p.dtype === 'object').map((p) => p.feature)
      setNumericColumns(nums)
      setCategoricalColumns(cats)
      if (nums.length >= 2 && !xFeature && !yFeature) {
        setXFeature(nums[0])
        setYFeature(nums[1])
      }
      if (numericPlot) {
        setSelectedFeature(numericPlot.feature)
        if (numericPlot.stats.histogram) {
          setDistData(toHistogramData(numericPlot.stats))
        }
        if (numericPlot.stats.boxplot) {
          setBoxplotData([{ feature: numericPlot.feature, ...numericPlot.stats.boxplot }])
        }
      } else if (data.plots.length > 0) {
        const first = data.plots[0]
        setSelectedFeature(first.feature)
        if (first.stats.histogram) setDistData(toHistogramData(first.stats))
        if (first.stats.boxplot) setBoxplotData([{ feature: first.feature, ...first.stats.boxplot }])
        if (first.stats.pie_image) setPieImage(first.stats.pie_image)
      }
      setSummary({
        rows: data.dataset_info.rows,
        columns: data.dataset_info.columns,
        numeric_features: data.plots.filter((p) => p.dtype !== 'object').length,
      })
      setDistLoaded(true)
    } catch (e: any) {
      setDistError(e?.response?.data?.detail || e?.message || '加载失败')
      setDistLoaded(true)
    } finally {
      setLoadingDist(false)
    }
  }, [selectedDataFile, plotType, selectedFeature, xFeature, yFeature])

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

  // 从 summary 中获取数值列 / 类别列
  const [numericColumns, setNumericColumns] = useState<string[]>([])
  const [categoricalColumns, setCategoricalColumns] = useState<string[]>([])

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
                    ...(numericColumns.length >= 1
                      ? [{ value: 'line', label: '折线图' }]
                      : []),
                    ...(numericColumns.length >= 2
                      ? [{ value: 'scatter', label: '散点图' }]
                      : []),
                    ...(categoricalColumns.length > 0
                      ? [{ value: 'pie', label: '饼图' }]
                      : []),
                  ]}
                  value={plotType}
                  onChange={(e) => {
                    const val = e.target.value as 'histogram' | 'boxplot' | 'scatter' | 'pie'
                    setPlotType(val)
                    setDistData([])
                    setBoxplotData([])
                    setPieImage('')
                    setScatterData([])
                    // scatter 模式下默认选两个数值列
                    if (val === 'scatter' && numericColumns.length >= 2) {
                      setXFeature(numericColumns[0])
                      setYFeature(numericColumns[1])
                    }
                  }}
                  className="w-28"
                />

                {/* 散点图：两个特征选择 */}
                {plotType === 'scatter' && (
                  <>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">X 轴特征</label>
                      <select
                        value={xFeature}
                        onChange={(e) => setXFeature(e.target.value)}
                        className="border border-slate-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-400"
                      >
                        {numericColumns.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Y 轴特征</label>
                      <select
                        value={yFeature}
                        onChange={(e) => setYFeature(e.target.value)}
                        className="border border-slate-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-400"
                      >
                        {numericColumns.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}

                {/* histogram / boxplot / line：单个特征选择 */}
                {(plotType === 'histogram' || plotType === 'boxplot' || plotType === 'line') && (
                  <Select
                    label="特征"
                    options={featureOptions}
                    value={selectedFeature}
                    onChange={(e) => setSelectedFeature(e.target.value)}
                    className="w-40"
                  />
                )}
              </div>
            </div>

            {distError && (
              <div className="flex items-center gap-2 text-red-500 text-sm mb-3">
                <AlertCircle className="w-4 h-4" />
                {distError}
              </div>
            )}

            {plotType === 'histogram' && (
              <HistogramChart
                data={distData}
                loading={loadingDist || !distLoaded}
                emptyText={selectedDataFile ? '暂无直方图数据' : '请先选择数据集'}
                color="#6366f1"
                height={280}
              />
            )}
            {plotType === 'boxplot' && (
              <BoxplotChart
                data={boxplotData}
                loading={loadingDist || !distLoaded}
                emptyText={selectedDataFile ? '暂无箱线图数据' : '请先选择数据集'}
                color="#6366f1"
                height={280}
              />
            )}

            {/* 折线图（单变量，按值排序后连线） */}
            {plotType === 'line' && (
              <SingleVarLineChart
                data={lineData}
                loading={loadingDist || !distLoaded}
                emptyText={selectedDataFile ? '暂无折线图数据' : '请先选择数据集'}
                color="#6366f1"
                height={280}
                featureName={selectedFeature}
                stats={lineStats ?? undefined}
              />
            )}

            {/* 散点图（后端返回 base64 图片） */}
            {plotType === 'scatter' && distLoaded && !loadingDist && !distError && (
              <div className="flex justify-center">
                {(window as any).__scatterImg ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={(window as any).__scatterImg}
                    alt="scatter plot"
                    style={{ maxWidth: '100%', height: 280 }}
                  />
                ) : (
                  <div className="flex items-center gap-2 text-slate-400" style={{ height: 280 }}>
                    <AlertCircle className="w-5 h-5" />
                    <span className="text-sm">散点图需要至少两个数值列</span>
                  </div>
                )}
              </div>
            )}
            {plotType === 'scatter' && (loadingDist || !distLoaded) && (
              <div className="flex items-center justify-center" style={{ height: 280 }}>
                <div className="flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-3 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
                  <span className="text-sm text-slate-400">加载中…</span>
                </div>
              </div>
            )}

            {/* 饼图 */}
            {plotType === 'pie' && pieImage && (
              <div className="flex justify-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={pieImage} alt="pie chart" style={{ maxWidth: '100%', height: 300 }} />
              </div>
            )}
            {plotType === 'pie' && !pieImage && distLoaded && !loadingDist && (
              <div className="flex items-center gap-2 text-slate-400 justify-center" style={{ height: 280 }}>
                <AlertCircle className="w-5 h-5" />
                <span className="text-sm">请选择类别型特征查看饼图</span>
              </div>
            )}
            {plotType === 'pie' && (loadingDist || !distLoaded) && (
              <div className="flex items-center justify-center" style={{ height: 280 }}>
                <div className="flex flex-col items-center gap-3">
                  <div className="w-8 h-8 border-3 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
                  <span className="text-sm text-slate-400">加载中…</span>
                </div>
              </div>
            )}

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
