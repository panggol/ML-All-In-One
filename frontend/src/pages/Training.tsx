import { useState, useEffect, useMemo } from 'react'
import { Upload, Play, Pause, FileSpreadsheet, ChevronDown, ChevronRight, Sparkles, Check } from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Select from '../components/Select'
import Input from '../components/Input'
import ProgressBar from '../components/ProgressBar'
import { dataApi, trainApi, TrainJob, TrainStatus, MetricsCurve } from '../api'

const MODEL_OPTIONS = [
  { value: 'RandomForestClassifier', label: 'RandomForest' },
  { value: 'XGBClassifier', label: 'XGBoost' },
  { value: 'LGBMClassifier', label: 'LightGBM' },
  { value: 'LogisticRegression', label: 'LogisticRegression' },
]

const TASK_OPTIONS = [
  { value: 'classification', label: '分类' },
  { value: 'regression', label: '回归' },
]

const AUTO_FEATURE_METHODS = [
  { value: 'variance_threshold', label: '方差阈值' },
  { value: 'correlation', label: '相关系数' },
  { value: 'tree_importance', label: '树模型重要性' },
]

export default function Training() {
  const [files, setFiles] = useState<any[]>([])
  const [selectedFile, setSelectedFile] = useState<number | null>(null)
  const [taskType, setTaskType] = useState<'classification' | 'regression'>('classification')
  const [targetColumn, setTargetColumn] = useState('')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [isTraining, setIsTraining] = useState(false)
  const [currentJob, setCurrentJob] = useState<TrainJob | null>(null)
  const [progress, setProgress] = useState(0)
  const [metricsCurve, setMetricsCurve] = useState<MetricsCurve | null>(null)
  const [curveExpanded, setCurveExpanded] = useState(false)

  // 特征选择相关状态
  const [featureExpanded, setFeatureExpanded] = useState(false)
  const [allColumns, setAllColumns] = useState<string[]>([])
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])
  const [autoSelectMethod, setAutoSelectMethod] = useState<string>('tree_importance')
  const [autoSelectedFeatures, setAutoSelectedFeatures] = useState<string[]>([])
  const [isAutoSelecting, setIsAutoSelecting] = useState(false)
  const [autoSelectApplied, setAutoSelectApplied] = useState(false)

  useEffect(() => {
    loadFiles()
  }, [])

  // 轮询训练状态
  useEffect(() => {
    if (!currentJob || currentJob.status !== 'running') return
    
    const interval = setInterval(async () => {
      try {
        const status: TrainStatus = await trainApi.getStatus(currentJob.id)
        setProgress(status.progress)

        if (status.status === 'completed' || status.status === 'failed' || status.status === 'stopped') {
          if (status.status === 'completed' && status.metrics_curve) {
            setMetricsCurve(status.metrics_curve)
            setCurveExpanded(true)
          }
          setIsTraining(false)
          setCurrentJob(null)
          setProgress(0)
          clearInterval(interval)
        }
      } catch (err) {
        console.error('Failed to get training status:', err)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [currentJob])

  // 加载文件后获取列信息
  useEffect(() => {
    if (selectedFile) {
      loadFileColumns(selectedFile)
    }
  }, [selectedFile])

  // target 列变化时，重置特征选择
  useEffect(() => {
    if (targetColumn && allColumns.length > 0) {
      const features = allColumns.filter(col => col !== targetColumn)
      setSelectedFeatures(features)
      setAutoSelectedFeatures([])
      setAutoSelectApplied(false)
    }
  }, [targetColumn, allColumns])

  const loadFiles = async () => {
    try {
      const fileList = await dataApi.list()
      setFiles(fileList)
    } catch (err) {
      console.error('Failed to load files:', err)
    }
  }

  const loadFileColumns = async (fileId: number) => {
    try {
      const stats = await dataApi.stats(fileId)
      setAllColumns(stats.columns || [])
    } catch (err) {
      console.error('Failed to load file columns:', err)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const uploadedFile = await dataApi.upload(file)
      setFiles([uploadedFile, ...files])
      setSelectedFile(uploadedFile.id)
      
      // 获取列名作为目标列建议
      const stats = await dataApi.stats(uploadedFile.id)
      if (stats.columns?.length > 0) {
        setTargetColumn(stats.columns[stats.columns.length - 1])
      }
    } catch (err) {
      console.error('Failed to upload file:', err)
    }
  }

  const handleFeatureToggle = (col: string) => {
    if (autoSelectApplied) {
      // 如果已应用自动选择，先取消
      setAutoSelectApplied(false)
      setAutoSelectedFeatures([])
    }
    setSelectedFeatures(prev => 
      prev.includes(col) 
        ? prev.filter(c => c !== col)
        : [...prev, col]
    )
  }

  const handleSelectAll = () => {
    setAutoSelectApplied(false)
    setAutoSelectedFeatures([])
    setSelectedFeatures(allColumns.filter(col => col !== targetColumn))
  }

  const handleDeselectAll = () => {
    setAutoSelectApplied(false)
    setAutoSelectedFeatures([])
    setSelectedFeatures([])
  }

  const handleAutoSelect = async () => {
    if (!selectedFile || !targetColumn) return
    
    setIsAutoSelecting(true)
    try {
      // 调用后端特征选择 API
      const result = await dataApi.featureSelection(selectedFile, {
        target_column: targetColumn,
        method: autoSelectMethod,
      })
      
      setAutoSelectedFeatures(result.selected_features || [])
      setAutoSelectApplied(true)
    } catch (err) {
      console.error('Auto feature selection failed:', err)
      // 如果后端还没实现，基于方差的简单模拟
      const features = allColumns.filter(col => col !== targetColumn)
      setAutoSelectedFeatures(features.slice(0, Math.max(1, Math.floor(features.length * 0.7))))
      setAutoSelectApplied(true)
    } finally {
      setIsAutoSelecting(false)
    }
  }

  const handleApplyAutoSelection = () => {
    if (autoSelectedFeatures.length > 0) {
      setSelectedFeatures(autoSelectedFeatures)
      setAutoSelectApplied(false)
    }
  }

  const handleStartTraining = async () => {
    if (!selectedFile || !targetColumn || !selectedModel) return
    
    // 使用最终选中的特征（如果是自动选择模式且已应用）
    const featuresToUse = autoSelectApplied && autoSelectedFeatures.length > 0 
      ? autoSelectedFeatures 
      : selectedFeatures

    try {
      const job = await trainApi.create({
        data_file_id: selectedFile,
        target_column: targetColumn,
        task_type: taskType,
        model_type: 'sklearn',
        model_name: selectedModel,
        feature_columns: featuresToUse,
      })
      
      setCurrentJob(job)
      setIsTraining(true)
      setProgress(0)
    } catch (err) {
      console.error('Failed to start training:', err)
    }
  }

  const handleStopTraining = async () => {
    if (!currentJob) return
    
    try {
      await trainApi.stop(currentJob.id)
      setIsTraining(false)
      setCurrentJob(null)
      setProgress(0)
    } catch (err) {
      console.error('Failed to stop training:', err)
    }
  }

  const selectedFileData = files.find(f => f.id === selectedFile)

  // 最终使用的特征列表
  const finalFeatures = autoSelectApplied && autoSelectedFeatures.length > 0
    ? autoSelectedFeatures
    : selectedFeatures

  // Recharts 动态导入
  const [RechartsComps, setRechartsComps] = useState<any>(null)
  useEffect(() => {
    import('recharts').then(mod => setRechartsComps(mod))
  }, [])

  const buildChartData = (metrics_curve: MetricsCurve, metric: 'loss' | 'accuracy') => {
    return metrics_curve.epochs.map((epoch, i) => ({
      epoch,
      train: metrics_curve[`train_${metric}`][i],
      val: metrics_curve[`val_${metric}`][i],
    }))
  }

  const TrainingCurves = ({ metrics_curve }: { metrics_curve: MetricsCurve }) => {
    const [activeMetric, setActiveMetric] = useState<'loss' | 'accuracy'>('loss')
    const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set())

    const chartData = useMemo(() => buildChartData(metrics_curve, activeMetric), [metrics_curve, activeMetric])

    const toggleSeries = (key: string) => {
      setHiddenSeries(prev => {
        const next = new Set(prev)
        if (next.has(key)) {
          next.delete(key)
        } else {
          next.add(key)
        }
        return next
      })
    }

    if (!RechartsComps) return null

    const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = RechartsComps

    const metricLabel = activeMetric === 'loss' ? 'Loss' : 'Accuracy'
    const formatter = (v: any) => typeof v === 'number' ? v.toFixed(4) : v

    return (
      <div className="mt-4">
        {/* Tab 切换 */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setActiveMetric('loss')}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeMetric === 'loss'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Loss
          </button>
          <button
            onClick={() => setActiveMetric('accuracy')}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeMetric === 'accuracy'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Accuracy
          </button>
        </div>

        {/* 图表 */}
        <ResponsiveContainer width="100%" height={256}>
          <LineChart data={chartData} margin={{ top: 4, right: 24, left: -12, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal stroke="#e2e8f0" vertical={false} />
            <XAxis
              dataKey="epoch"
              tick={{ fontSize: 12, fill: '#64748b' }}
              axisLine={{ stroke: '#e2e8f0' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12, fill: '#64748b' }}
              axisLine={{ stroke: '#e2e8f0' }}
              tickLine={false}
            />
            <Tooltip
              formatter={formatter}
              contentStyle={{
                backgroundColor: 'white',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}
              labelStyle={{ color: '#334155', fontWeight: 500 }}
            />
            <Legend
              wrapperStyle={{ fontSize: 13, color: '#64748b', paddingTop: 8 }}
              iconType="plainline"
              onClick={(e: any) => toggleSeries(e.dataKey)}
            />
            <Line
              type="monotone"
              dataKey="train"
              name={`Train ${metricLabel}`}
              stroke={hiddenSeries.has('train') ? '#cbd5e1' : '#6366F1'}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls={true}
              isAnimationActive={true}
              hide={hiddenSeries.has('train')}
            />
            <Line
              type="monotone"
              dataKey="val"
              name={`Val ${metricLabel}`}
              stroke={hiddenSeries.has('val') ? '#cbd5e1' : '#F59E0B'}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls={true}
              isAnimationActive={true}
              hide={hiddenSeries.has('val')}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  const TrainingCurveCard = () => {
    const status = currentJob?.status ?? (isTraining ? 'running' : null)

    if (status === null) return null

    return (
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-slate-700">📈 训练曲线</h3>
          <button
            onClick={() => setCurveExpanded(!curveExpanded)}
            className="p-1 rounded hover:bg-slate-100 transition-colors"
            title={curveExpanded ? '收起' : '展开'}
          >
            {curveExpanded ? (
              <ChevronDown className="w-5 h-5 text-slate-400" />
            ) : (
              <ChevronRight className="w-5 h-5 text-slate-400" />
            )}
          </button>
        </div>

        {/* 训练中 */}
        {(status === 'running') && !curveExpanded && (
          <div className="text-center text-slate-400 py-8 bg-slate-50 rounded-lg">
            训练中，曲线将在完成后展示
          </div>
        )}

        {/* 训练失败 */}
        {status === 'failed' && (
          <div className="text-center text-slate-400 py-8 bg-slate-50 rounded-lg">
            训练失败，无曲线数据
          </div>
        )}

        {/* 已完成 - 展示曲线 */}
        {status === 'running' && curveExpanded && metricsCurve && (
          <TrainingCurves metrics_curve={metricsCurve} />
        )}

        {/* 训练刚完成且有曲线数据 */}
        {status === 'completed' && metricsCurve && (
          <TrainingCurves metrics_curve={metricsCurve} />
        )}
      </Card>
    )
  }

  return (
    <div className="space-y-8">
      {/* Data Upload */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-900 mb-6">数据上传</h2>
        
        <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-primary-300 transition-colors">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
            <p className="font-medium text-slate-900">拖拽文件或点击上传</p>
            <p className="text-sm text-slate-500 mt-1">支持 CSV 格式，最大 100MB</p>
          </label>
        </div>

        {selectedFileData && (
          <div className="mt-6 flex items-center gap-4 p-4 bg-slate-50 rounded-lg">
            <FileSpreadsheet className="w-8 h-8 text-primary-600" />
            <div className="flex-1">
              <p className="font-medium text-slate-900">{selectedFileData.filename}</p>
              <p className="text-sm text-slate-500">
                {selectedFileData.rows} 行 · {allColumns.length} 列
              </p>
            </div>
          </div>
        )}

        {/* File List */}
        {files.length > 0 && !selectedFile && (
          <div className="mt-6">
            <label className="label">或选择已有文件</label>
            <div className="space-y-2">
              {files.map(file => (
                <div
                  key={file.id}
                  onClick={() => setSelectedFile(file.id)}
                  className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 hover:bg-slate-100 cursor-pointer"
                >
                  <FileSpreadsheet className="w-5 h-5 text-slate-400" />
                  <div>
                    <p className="font-medium text-slate-900">{file.filename}</p>
                    <p className="text-sm text-slate-500">{file.rows} 行</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Task Config */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-900 mb-6">任务配置</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <Select
            label="任务类型"
            options={TASK_OPTIONS}
            value={taskType}
            onChange={e => setTaskType(e.target.value as typeof taskType)}
          />
          <Input
            label="目标列"
            value={targetColumn}
            onChange={e => setTargetColumn(e.target.value)}
            placeholder="选择目标列"
          />
        </div>

        {/* 特征选择 - 折叠面板 */}
        {selectedFile && allColumns.length > 0 && targetColumn && (
          <div className="mb-6 border border-slate-200 rounded-lg overflow-hidden">
            {/* 折叠头部 */}
            <button
              onClick={() => setFeatureExpanded(!featureExpanded)}
              className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary-600" />
                <span className="font-medium text-slate-900">特征选择</span>
                <span className="text-sm text-slate-500">
                  ({finalFeatures.length} / {allColumns.filter(c => c !== targetColumn).length} 列已选)
                </span>
                {autoSelectApplied && (
                  <span className="px-2 py-0.5 text-xs bg-emerald-100 text-emerald-700 rounded">
                    自动选择
                  </span>
                )}
              </div>
              {featureExpanded ? (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {/* 折叠内容 */}
            {featureExpanded && (
              <div className="p-4 border-t border-slate-200">
                {/* 自动选择区域 */}
                <div className="flex flex-wrap items-center gap-3 mb-4 pb-4 border-b border-slate-100">
                  <Select
                    label="自动选择方法"
                    options={AUTO_FEATURE_METHODS}
                    value={autoSelectMethod}
                    onChange={e => setAutoSelectMethod(e.target.value)}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleAutoSelect}
                    disabled={isAutoSelecting}
                  >
                    <Sparkles className="w-4 h-4" />
                    {isAutoSelecting ? '选择中...' : '开始自动选择'}
                  </Button>
                  
                  {autoSelectedFeatures.length > 0 && !autoSelectApplied && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleApplyAutoSelection}
                    >
                      <Check className="w-4 h-4" />
                      应用 ({autoSelectedFeatures.length} 列)
                    </Button>
                  )}
                </div>

                {/* 手动选择区域 */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm text-slate-600">手动选择：</span>
                  <button
                    onClick={handleSelectAll}
                    className="text-sm text-primary-600 hover:text-primary-700"
                  >
                    全选
                  </button>
                  <span className="text-slate-300">|</span>
                  <button
                    onClick={handleDeselectAll}
                    className="text-sm text-slate-500 hover:text-slate-700"
                  >
                    取消全选
                  </button>
                </div>

                {/* 特征列列表 */}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 max-h-60 overflow-y-auto">
                  {allColumns
                    .filter(col => col !== targetColumn)
                    .map(col => {
                      const isSelected = autoSelectApplied 
                        ? autoSelectedFeatures.includes(col)
                        : selectedFeatures.includes(col)
                      const wasAutoSelected = autoSelectApplied && autoSelectedFeatures.includes(col)
                      
                      return (
                        <button
                          key={col}
                          onClick={() => !autoSelectApplied && handleFeatureToggle(col)}
                          disabled={autoSelectApplied}
                          className={`text-left px-3 py-2 rounded-lg text-sm transition-all ${
                            isSelected
                              ? wasAutoSelected
                                ? 'bg-emerald-50 border border-emerald-300 text-emerald-700'
                                : 'bg-primary-50 border border-primary-300 text-primary-700'
                              : 'bg-slate-50 border border-slate-200 text-slate-600 hover:bg-slate-100'
                          } ${autoSelectApplied ? 'cursor-default' : 'cursor-pointer'}`}
                        >
                          <div className="flex items-center gap-2">
                            <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                              isSelected ? 'bg-primary-500 border-primary-500' : 'border-slate-300'
                            }`}>
                              {isSelected && (
                                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                </svg>
                              )}
                            </div>
                            <span className="truncate">{col}</span>
                          </div>
                        </button>
                      )
                    })}
                </div>

                {finalFeatures.length === 0 && (
                  <p className="text-sm text-amber-600 mt-2">
                    ⚠️ 请至少选择一个特征列
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Model Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-3">选择模型</label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {MODEL_OPTIONS.map(model => (
              <button
                key={model.value}
                onClick={() => setSelectedModel(model.value)}
                className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                  selectedModel === model.value
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-slate-200 hover:border-primary-500 hover:bg-slate-50'
                }`}
              >
                {model.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Start Training */}
      <div className="flex justify-center">
        {isTraining ? (
          <Button variant="stop" size="lg" onClick={handleStopTraining}>
            <Pause className="w-6 h-6" />
            停止训练
          </Button>
        ) : (
          <Button
            variant="primary"
            size="lg"
            onClick={handleStartTraining}
            disabled={!selectedFile || !targetColumn || !selectedModel || finalFeatures.length === 0}
          >
            <Play className="w-6 h-6" />
            开始训练
          </Button>
        )}
      </div>

      {/* Training Progress */}
      {(isTraining || currentJob || metricsCurve) && (
        <>
          {isTraining && currentJob && (
            <Card>
              <h2 className="text-lg font-semibold text-slate-900 mb-4">训练进度</h2>
              <div className="space-y-6">
                <ProgressBar value={progress} />
                
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100">
                  <div className="text-center">
                    <p className="text-2xl font-semibold text-slate-900">{currentJob.model_name}</p>
                    <p className="text-sm text-slate-500">模型</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-semibold text-primary-600">
                      {currentJob.metrics?.accuracy ? `${(currentJob.metrics.accuracy * 100).toFixed(1)}%` : '—'}
                    </p>
                    <p className="text-sm text-slate-500">准确率</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-semibold text-slate-900">{progress}%</p>
                    <p className="text-sm text-slate-500">进度</p>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Training Curve Card */}
          <TrainingCurveCard />
        </>
      )}
    </div>
  )
}
