import { useState, useEffect } from 'react'
import {
  Upload, FileSpreadsheet, CheckSquare, Square, ChevronDown, ChevronRight,
  Eye, Save, Loader2, AlertCircle, Check
} from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Select from '../components/Select'
import Input from '../components/Input'
import {
  dataApi,
  preprocessingApi,
  DEFAULT_STEPS,
  type PreprocessingSteps,
  type PreviewResponse,
  type DataFile,
  type ColumnStats,
} from '../api'

// ============ 类型定义 ============

type ImputerStrategy = 'mean' | 'median' | 'most_frequent' | 'constant'
type ScalerType = 'minmax' | 'standard'

const IMPUTER_OPTIONS = [
  { value: 'mean', label: '均值填充' },
  { value: 'median', label: '中位数填充' },
  { value: 'most_frequent', label: '众数填充' },
  { value: 'constant', label: '常量填充 (0)' },
]

const SCALER_OPTIONS = [
  { value: 'none', label: '不缩放' },
  { value: 'minmax', label: '归一化 (0~1)' },
  { value: 'standard', label: '标准化 (均值0方差1)' },
]

// ============ 主组件 ============

export default function Preprocessing() {
  // 数据加载状态
  const [files, setFiles] = useState<DataFile[]>([])
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null)
  const [originalPreview, setOriginalPreview] = useState<any[][]>([])
  const [originalColumns, setOriginalColumns] = useState<string[]>([])

  // 预处理配置
  const [steps, setSteps] = useState<PreprocessingSteps>(DEFAULT_STEPS)

  // 预览状态
  const [previewResult, setPreviewResult] = useState<PreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

  // 保存状态
  const [saving, setSaving] = useState(false)
  const [savedResult, setSavedResult] = useState<{ id: number; filename: string } | null>(null)

  // 折叠状态
  const [imputerExpanded, setImputerExpanded] = useState(false)
  const [scalerExpanded, setScalerExpanded] = useState(false)
  const [featureExpanded, setFeatureExpanded] = useState(false)

  // 加载文件列表
  useEffect(() => {
    loadFiles()
  }, [])

  // 加载文件详情
  useEffect(() => {
    if (selectedFileId) {
      loadFilePreview(selectedFileId)
    } else {
      setOriginalPreview([])
      setOriginalColumns([])
      setPreviewResult(null)
    }
    // 重置预览
    setPreviewResult(null)
    setPreviewError(null)
    setSavedResult(null)
  }, [selectedFileId])

  const loadFiles = async () => {
    try {
      const fileList = await dataApi.list()
      setFiles(fileList)
    } catch (err) {
      console.error('Failed to load files:', err)
    }
  }

  const loadFilePreview = async (fileId: number) => {
    try {
      const stats = await dataApi.stats(fileId)
      const preview = await dataApi.preview(fileId)
      setOriginalPreview(preview.rows || [])
      setOriginalColumns(stats.columns || [])

      // 默认全选所有列用于特征选择
      setSteps(prev => ({
        ...prev,
        feature_select: {
          ...prev.feature_select,
          selected_columns: stats.columns || [],
        },
      }))
    } catch (err) {
      console.error('Failed to load file preview:', err)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const uploadedFile = await dataApi.upload(file)
      setFiles([uploadedFile, ...files])
      setSelectedFileId(uploadedFile.id)
    } catch (err) {
      console.error('Failed to upload file:', err)
    }
    // 清空 input
    e.target.value = ''
  }

  const handleStepChange = (key: keyof PreprocessingSteps, value: any) => {
    setSteps(prev => ({
      ...prev,
      [key]: typeof value === 'object' ? { ...prev[key], ...value } : value,
    }))
    setPreviewResult(null)
    setSavedResult(null)
  }

  const handleFeatureToggle = (col: string) => {
    setSteps(prev => {
      const current = prev.feature_select.selected_columns
      const updated = current.includes(col)
        ? current.filter(c => c !== col)
        : [...current, col]
      return {
        ...prev,
        feature_select: {
          ...prev.feature_select,
          selected_columns: updated,
        },
      }
    })
    setPreviewResult(null)
  }

  const handleScalerChange = (value: string) => {
    if (value === 'none') {
      handleStepChange('scaler', { enabled: false, type: null })
    } else {
      handleStepChange('scaler', { enabled: true, type: value as ScalerType })
    }
  }

  const hasAnyStepEnabled = () => {
    return (
      steps.imputer.enabled ||
      steps.scaler.enabled ||
      steps.feature_select.enabled
    )
  }

  const handlePreview = async () => {
    if (!selectedFileId) return

    setPreviewLoading(true)
    setPreviewError(null)

    try {
      const result = await preprocessingApi.preview(selectedFileId, steps)
      setPreviewResult(result)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '预览失败'
      setPreviewError(msg)
      setPreviewResult(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleSave = async () => {
    if (!selectedFileId) return

    setSaving(true)
    setSavedResult(null)

    try {
      const result = await preprocessingApi.transform(selectedFileId, steps)
      setSavedResult({ id: result.data_file_id, filename: result.filename })
      // 刷新文件列表
      await loadFiles()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '保存失败'
      setPreviewError(msg)
    } finally {
      setSaving(false)
    }
  }

  const selectedFile = files.find(f => f.id === selectedFileId)

  // 流水线执行顺序
  const pipelineOrder = [
    steps.imputer.enabled && '1. 缺失值填充',
    steps.scaler.enabled && '2. 归一化/标准化',
    steps.feature_select.enabled && '3. 特征选择',
  ].filter(Boolean) as string[]

  // 预览表格数据
  const displayColumns = previewResult?.columns || originalColumns
  const displayOriginal = previewResult?.original_preview || originalPreview

  return (
    <div className="space-y-8">
      {/* 标题区 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">数据预处理</h1>
          <p className="text-slate-500 mt-1">配置预处理流水线，预览处理效果，保存处理后的数据集</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ====== 左侧配置面板 (40%) ====== */}
        <div className="lg:col-span-2 space-y-6">

          {/* ① 数据选择 */}
          <Card>
            <h2 className="text-base font-semibold text-slate-900 mb-4">① 选择数据集</h2>

            {/* 上传区域 */}
            <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 text-center hover:border-primary-300 transition-colors mb-4">
              <input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="hidden"
                id="preprocessing-upload"
              />
              <label htmlFor="preprocessing-upload" className="cursor-pointer">
                <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <p className="text-sm font-medium text-slate-700">上传 CSV 文件</p>
              </label>
            </div>

            {/* 已有文件列表 */}
            {files.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">已有数据集</p>
                {files.map(file => (
                  <div
                    key={file.id}
                    onClick={() => setSelectedFileId(file.id)}
                    className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                      selectedFileId === file.id
                        ? 'bg-primary-50 border border-primary-300'
                        : 'bg-slate-50 hover:bg-slate-100 border border-transparent'
                    }`}
                  >
                    <FileSpreadsheet className="w-5 h-5 text-slate-400 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{file.filename}</p>
                      <p className="text-xs text-slate-500">
                        {file.rows} 行 · {file.columns?.length || 0} 列
                      </p>
                    </div>
                    {selectedFileId === file.id && (
                      <Check className="w-4 h-4 text-primary-600 flex-shrink-0 ml-auto" />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* 选中文件信息 */}
            {selectedFile && (
              <div className="mt-4 p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                <p className="text-sm font-medium text-emerald-800">
                  ✓ 已选择: {selectedFile.filename}
                </p>
                <p className="text-xs text-emerald-600 mt-1">
                  {selectedFile.rows} 行 · {originalColumns.length} 列
                </p>
              </div>
            )}
          </Card>

          {/* ② 预处理步骤配置 */}
          {selectedFileId && (
            <Card>
              <h2 className="text-base font-semibold text-slate-900 mb-4">② 预处理步骤</h2>
              <div className="space-y-3">

                {/* 缺失值填充 */}
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => {
                      const newEnabled = !steps.imputer.enabled
                      handleStepChange('imputer', { enabled: newEnabled })
                      if (newEnabled) setImputerExpanded(true)
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
                  >
                    {steps.imputer.enabled
                      ? <CheckSquare className="w-5 h-5 text-primary-600 flex-shrink-0" />
                      : <Square className="w-5 h-5 text-slate-400 flex-shrink-0" />
                    }
                    <span className="text-sm font-medium text-slate-900">缺失值填充</span>
                    <span className="text-xs text-slate-500 ml-auto">{steps.imputer.strategy === 'mean' ? '均值' : steps.imputer.strategy === 'median' ? '中位数' : steps.imputer.strategy === 'most_frequent' ? '众数' : '常量'}</span>
                    {imputerExpanded ? (
                      <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    )}
                  </button>
                  {imputerExpanded && (
                    <div className="px-4 py-3 border-t border-slate-200 bg-white">
                      <Select
                        label="填充策略"
                        options={IMPUTER_OPTIONS}
                        value={steps.imputer.strategy}
                        onChange={e => handleStepChange('imputer', { strategy: e.target.value as ImputerStrategy })}
                      />
                    </div>
                  )}
                </div>

                {/* 归一化/标准化 */}
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => {
                      const newEnabled = !steps.scaler.enabled
                      handleStepChange('scaler', { enabled: newEnabled, type: newEnabled ? 'minmax' : null })
                      if (newEnabled) setScalerExpanded(true)
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
                  >
                    {steps.scaler.enabled
                      ? <CheckSquare className="w-5 h-5 text-primary-600 flex-shrink-0" />
                      : <Square className="w-5 h-5 text-slate-400 flex-shrink-0" />
                    }
                    <span className="text-sm font-medium text-slate-900">归一化 / 标准化</span>
                    <span className="text-xs text-slate-500 ml-auto">
                      {steps.scaler.type === 'minmax' ? 'MinMax (0~1)' : steps.scaler.type === 'standard' ? 'Standard' : '未启用'}
                    </span>
                    {scalerExpanded ? (
                      <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    )}
                  </button>
                  {scalerExpanded && (
                    <div className="px-4 py-3 border-t border-slate-200 bg-white">
                      <Select
                        label="缩放方式"
                        options={SCALER_OPTIONS}
                        value={steps.scaler.type || 'none'}
                        onChange={e => handleScalerChange(e.target.value)}
                      />
                    </div>
                  )}
                </div>

                {/* 特征选择 */}
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => {
                      const newEnabled = !steps.feature_select.enabled
                      handleStepChange('feature_select', { enabled: newEnabled })
                      if (newEnabled) setFeatureExpanded(true)
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
                  >
                    {steps.feature_select.enabled
                      ? <CheckSquare className="w-5 h-5 text-primary-600 flex-shrink-0" />
                      : <Square className="w-5 h-5 text-slate-400 flex-shrink-0" />
                    }
                    <span className="text-sm font-medium text-slate-900">特征选择</span>
                    <span className="text-xs text-slate-500 ml-auto">
                      {steps.feature_select.selected_columns.length} / {originalColumns.length} 列
                    </span>
                    {featureExpanded ? (
                      <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    )}
                  </button>
                  {featureExpanded && (
                    <div className="px-4 py-3 border-t border-slate-200 bg-white space-y-3">
                      <Input
                        label="方差阈值"
                        type="number"
                        step="0.01"
                        value={steps.feature_select.threshold}
                        onChange={e => handleStepChange('feature_select', { threshold: parseFloat(e.target.value) || 0 })}
                        placeholder="0.0"
                      />
                      <div>
                        <p className="text-xs text-slate-500 mb-2">选择保留的列（空白或0阈值 = 保留所有）：</p>
                        <div className="grid grid-cols-2 gap-1 max-h-40 overflow-y-auto">
                          {originalColumns.map(col => {
                            const isSelected = steps.feature_select.selected_columns.includes(col)
                            return (
                              <button
                                key={col}
                                onClick={() => handleFeatureToggle(col)}
                                className={`text-left px-2 py-1 rounded text-xs transition-all ${
                                  isSelected
                                    ? 'bg-primary-50 border border-primary-300 text-primary-700'
                                    : 'bg-slate-50 border border-slate-200 text-slate-600 hover:bg-slate-100'
                                }`}
                              >
                                <div className="flex items-center gap-1">
                                  <div className={`w-3 h-3 rounded border flex items-center justify-center flex-shrink-0 ${
                                    isSelected ? 'bg-primary-500 border-primary-500' : 'border-slate-300'
                                  }`}>
                                    {isSelected && (
                                      <svg className="w-2 h-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* ③ 流水线概览 + 操作按钮 */}
          {selectedFileId && (
            <Card>
              <h2 className="text-base font-semibold text-slate-900 mb-4">③ 流水线预览</h2>

              {/* 流水线顺序 */}
              {pipelineOrder.length > 0 ? (
                <div className="space-y-2 mb-4">
                  {pipelineOrder.map((step, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="w-6 h-6 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-bold flex-shrink-0">
                        {i + 1}
                      </span>
                      <span className="text-slate-700">{step}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400 mb-4">未启用任何预处理步骤</p>
              )}

              {/* 错误提示 */}
              {previewError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">{previewError}</p>
                </div>
              )}

              {/* 保存成功 */}
              {savedResult && (
                <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                  <p className="text-sm text-emerald-700 font-medium">
                    ✓ 已保存: {savedResult.filename}
                  </p>
                  <p className="text-xs text-emerald-600 mt-1">
                    数据集 ID: {savedResult.id}，可在训练页面使用
                  </p>
                </div>
              )}

              {/* 按钮组 */}
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  onClick={handlePreview}
                  disabled={previewLoading || !selectedFileId}
                  className="flex-1"
                >
                  {previewLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                  预览
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSave}
                  disabled={saving || !selectedFileId}
                  className="flex-1"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  保存
                </Button>
              </div>

              {!hasAnyStepEnabled() && selectedFileId && (
                <p className="text-xs text-amber-600 mt-2">
                  ⚠️ 未启用任何预处理步骤，保存将直接保存原始数据
                </p>
              )}
            </Card>
          )}
        </div>

        {/* ====== 右侧预览面板 (60%) ====== */}
        <div className="lg:col-span-3 space-y-6">
          {/* 数据预览表格 */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-slate-900">
                {previewResult ? '处理前后对比' : '原始数据预览'}
              </h2>
              {previewResult && (
                <span className="text-xs text-slate-500">
                  预览 {previewResult.shape[0]} 行 × {previewResult.shape[1]} 列
                </span>
              )}
            </div>

            {!selectedFileId && (
              <div className="text-center py-16 text-slate-400">
                <FileSpreadsheet className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p className="font-medium">请先选择数据集</p>
              </div>
            )}

            {selectedFileId && displayColumns.length > 0 && (
              <div className="overflow-x-auto">
                {/* 列标签 */}
                <div className="flex mb-1">
                  <div className="w-12 flex-shrink-0" />
                  {displayColumns.map((col, i) => (
                    <div
                      key={i}
                      className="min-w-[100px] max-w-[140px] px-2 py-1 text-xs font-semibold text-slate-600 truncate text-center"
                      title={col}
                    >
                      {col}
                    </div>
                  ))}
                </div>

                {/* 原始数据（预览模式） */}
                {previewResult && (
                  <div className="mb-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded font-medium">原始</span>
                      <span className="text-xs text-slate-400">处理前</span>
                    </div>
                    <div className="border border-blue-200 rounded-lg overflow-hidden">
                      {previewResult.original_preview.map((row, rowIdx) => (
                        <div key={rowIdx} className="flex border-b border-slate-100 last:border-0">
                          <div className="w-12 flex-shrink-0 px-2 py-1.5 text-xs text-slate-400 text-center bg-slate-50 border-r border-slate-100">
                            {rowIdx + 1}
                          </div>
                          {displayColumns.map((_col, colIdx) => {
                            const val = row[colIdx < row.length ? colIdx : colIdx]
                            return (
                              <div
                                key={colIdx}
                                className="min-w-[100px] max-w-[140px] px-2 py-1.5 text-xs text-slate-700 truncate text-center border-r border-slate-100 last:border-0"
                                title={String(val ?? '')}
                              >
                                {val === null || val === undefined ? (
                                  <span className="text-red-400">null</span>
                                ) : typeof val === 'number' ? (
                                  Number(val).toFixed(4)
                                ) : (
                                  String(val)
                                )}
                              </div>
                            )
                          })}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 处理后数据（预览模式）或原始数据（未预览） */}
                <div>
                  {previewResult ? (
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="px-2 py-0.5 text-xs bg-emerald-100 text-emerald-700 rounded font-medium">处理后</span>
                        <span className="text-xs text-slate-400">处理后</span>
                      </div>
                      <div className="border border-emerald-200 rounded-lg overflow-hidden">
                        {(previewResult.transformed_preview.length > 0
                          ? previewResult.transformed_preview
                          : displayOriginal
                        ).map((_row, rowIdx) => (
                          <div key={rowIdx} className="flex border-b border-slate-100 last:border-0">
                            <div className="w-12 flex-shrink-0 px-2 py-1.5 text-xs text-slate-400 text-center bg-slate-50 border-r border-slate-100">
                              {rowIdx + 1}
                            </div>
                            {(previewResult.transformed_preview.length > 0
                              ? previewResult.transformed_preview
                              : displayOriginal
                            )[rowIdx]?.map((val: any, colIdx: number) => (
                              <div
                                key={colIdx}
                                className="min-w-[100px] max-w-[140px] px-2 py-1.5 text-xs text-slate-700 truncate text-center border-r border-slate-100 last:border-0"
                                title={String(val ?? '')}
                              >
                                {val === null || val === undefined ? (
                                  <span className="text-red-400">null</span>
                                ) : typeof val === 'number' ? (
                                  Number(val).toFixed(4)
                                ) : (
                                  String(val)
                                )}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                      {displayOriginal.slice(0, 10).map((row, rowIdx) => (
                        <div key={rowIdx} className="flex border-b border-slate-100 last:border-0">
                          <div className="w-12 flex-shrink-0 px-2 py-1.5 text-xs text-slate-400 text-center bg-slate-50 border-r border-slate-100">
                            {rowIdx + 1}
                          </div>
                          {row.map((val, colIdx) => (
                            <div
                              key={colIdx}
                              className="min-w-[100px] max-w-[140px] px-2 py-1.5 text-xs text-slate-700 truncate text-center border-r border-slate-100 last:border-0"
                              title={String(val ?? '')}
                            >
                              {val === null || val === undefined ? (
                                <span className="text-red-400">null</span>
                              ) : typeof val === 'number' ? (
                                Number(val).toFixed(4)
                              ) : (
                                String(val)
                              )}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>

          {/* 统计信息 */}
          {previewResult && previewResult.stats.length > 0 && (
            <Card>
              <h2 className="text-base font-semibold text-slate-900 mb-4">列统计对比</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="text-left py-2 pr-4 font-semibold text-slate-600">列名</th>
                      <th className="text-center py-2 px-2 font-semibold text-slate-600">类型</th>
                      <th className="text-right py-2 px-2 font-semibold text-blue-600">原始均值</th>
                      <th className="text-right py-2 px-2 font-semibold text-blue-600">原始缺失</th>
                      <th className="text-right py-2 px-2 font-semibold text-emerald-600">处理后均值</th>
                      <th className="text-right py-2 px-2 font-semibold text-emerald-600">处理后缺失</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewResult.stats.map((stat: ColumnStats, idx: number) => (
                      <tr key={idx} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                        <td className="py-2 pr-4 font-medium text-slate-800 truncate max-w-[120px]">{stat.column}</td>
                        <td className="py-2 px-2 text-center text-slate-500">{stat.dtype}</td>
                        <td className="py-2 px-2 text-right text-slate-600">
                          {stat.original_mean !== null ? Number(stat.original_mean).toFixed(3) : '—'}
                        </td>
                        <td className="py-2 px-2 text-right">
                          {stat.original_missing > 0 ? (
                            <span className="text-red-500">{stat.original_missing}</span>
                          ) : (
                            <span className="text-slate-400">0</span>
                          )}
                        </td>
                        <td className="py-2 px-2 text-right text-slate-600">
                          {stat.transformed_mean !== null ? Number(stat.transformed_mean).toFixed(3) : '—'}
                        </td>
                        <td className="py-2 px-2 text-right">
                          {stat.transformed_missing > 0 ? (
                            <span className="text-red-500">{stat.transformed_missing}</span>
                          ) : (
                            <span className="text-emerald-500">0</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
