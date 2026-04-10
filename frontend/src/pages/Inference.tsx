import { useState, useEffect, useRef } from 'react'
import {
  Cpu, Upload, FileSpreadsheet, Play, Loader2, AlertCircle,
  Download, CheckCircle2, XCircle, Trash2
} from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import { modelsApi, dataApi, type ModelInfo, type InferenceResult } from '../api'

// ============ 类型定义 ============

type InferenceMode = 'json' | 'csv' | 'path'

interface InferenceRow {
  _index: number
  _original: Record<string, unknown>
  prediction: string | number | null
  probability: number | null
  error?: string | null
}

interface DataFileInfo {
  id: number
  filename: string
  rows: number
  columns: string[]
}

// ============ 主组件 ============

export default function Inference() {
  // 模型列表
  const [models, setModels] = useState<ModelInfo[]>([])
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [selectedModel, setSelectedModel] = useState<ModelInfo | null>(null)
  const [loadingModels, setLoadingModels] = useState(false)

  // 数据文件列表（路径模式）
  const [dataFiles, setDataFiles] = useState<DataFileInfo[]>([])
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null)

  // 推理模式
  const [mode, setMode] = useState<InferenceMode>('json')

  // JSON 模式输入
  const [jsonInput, setJsonInput] = useState('')
  const [jsonError, setJsonError] = useState<string | null>(null)

  // CSV 模式
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [csvPreview, setCsvPreview] = useState<{ rows: Record<string, unknown>[]; columns: string[] } | null>(null)
  const [csvLoading, setCsvLoading] = useState(false)

  // 推理状态
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<InferenceRow[]>([])
  const [inferenceError, setInferenceError] = useState<string | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  // ============ 加载数据 ============

  useEffect(() => {
    loadModels()
    loadDataFiles()
  }, [])

  // 选中模型详情
  useEffect(() => {
    if (selectedModelId) {
      modelsApi.get(selectedModelId).then(setSelectedModel).catch(() => setSelectedModel(null))
    } else {
      setSelectedModel(null)
    }
    // 切换模型 → 重置
    setResults([])
    setInferenceError(null)
  }, [selectedModelId])

  // 切换模式 → 重置结果
  useEffect(() => {
    setResults([])
    setInferenceError(null)
  }, [mode])

  const loadModels = async () => {
    setLoadingModels(true)
    try {
      const list = await modelsApi.list()
      setModels(list)
    } catch (err) {
      console.error('Failed to load models:', err)
    } finally {
      setLoadingModels(false)
    }
  }

  const loadDataFiles = async () => {
    try {
      const files = await dataApi.list()
      setDataFiles(files as unknown as DataFileInfo[])
    } catch (err) {
      console.error('Failed to load data files:', err)
    }
  }

  // ============ JSON 校验 ============

  const validateJson = (raw: string): Record<string, unknown>[] | null => {
    const trimmed = raw.trim()
    if (!trimmed) {
      setJsonError('请输入 JSON 数据')
      return null
    }
    try {
      const parsed = JSON.parse(trimmed)
      if (!Array.isArray(parsed)) {
        setJsonError('数据格式错误：需要 JSON 数组，如 [{...}, {...}]')
        return null
      }
      if (parsed.length === 0) {
        setJsonError('数组不能为空')
        return null
      }
      if (typeof parsed[0] !== 'object' || parsed[0] === null) {
        setJsonError('数组元素必须是对象，如 {col1: val, col2: val}')
        return null
      }
      setJsonError(null)
      return parsed
    } catch (e: any) {
      setJsonError(`JSON 解析错误：${e.message}`)
      return null
    }
  }

  // ============ CSV 处理 ============

  const handleCsvUpload = async (file: File) => {
    setCsvFile(file)
    setCsvLoading(true)
    setInferenceError(null)

    try {
      const text = await file.text()
      const lines = text.split('\n').filter(l => l.trim())
      if (lines.length < 2) {
        setInferenceError('CSV 文件至少需要 1 行表头 + 1 行数据')
        return
      }

      const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
      const rows: Record<string, unknown>[] = []

      for (let i = 1; i < Math.min(lines.length, 11); i++) {
        const values = lines[i].split(',').map(v => v.trim().replace(/^"|"$/g, ''))
        const row: Record<string, unknown> = {}
        headers.forEach((h, idx) => {
          const raw = values[idx] ?? ''
          // 尝试转为数字
          const num = Number(raw)
          row[h] = raw === '' ? null : (isNaN(num) ? raw : num)
        })
        rows.push(row)
      }

      setCsvPreview({ rows, columns: headers })
    } catch (err: any) {
      setInferenceError(`CSV 解析失败：${err.message}`)
    } finally {
      setCsvLoading(false)
    }
  }

  const handleCsvDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.name.endsWith('.csv')) {
      handleCsvUpload(file)
    } else {
      setInferenceError('只支持 CSV 文件')
    }
  }

  // ============ 推理执行 ============

  const runInference = async () => {
    if (!selectedModelId) return

    let payload: Record<string, unknown>[] = []

    if (mode === 'json') {
      const parsed = validateJson(jsonInput)
      if (!parsed) return
      payload = parsed
    } else if (mode === 'csv') {
      if (!csvPreview) {
        setInferenceError('请先上传 CSV 文件')
        return
      }
      // CSV 模式下取全部行（不只预览），这里简化为用预览行
      // 完整实现：读取全部 CSV 内容
      if (csvFile) {
        try {
          const text = await csvFile.text()
          const lines = text.split('\n').filter(l => l.trim())
          const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
          const allRows: Record<string, unknown>[] = []
          for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim().replace(/^"|"$/g, ''))
            const row: Record<string, unknown> = {}
            headers.forEach((h, idx) => {
              const raw = values[idx] ?? ''
              const num = Number(raw)
              row[h] = raw === '' ? null : (isNaN(num) ? raw : num)
            })
            allRows.push(row)
          }
          payload = allRows
        } catch {
          payload = csvPreview.rows
        }
      } else {
        payload = csvPreview.rows
      }
    } else if (mode === 'path') {
      if (!selectedFileId) {
        setInferenceError('请先选择数据集')
        return
      }
      // 路径模式：从后端加载全部数据
      try {
        const preview = await dataApi.preview(selectedFileId)
        // preview.rows 是原始数组的数组，需要转换为对象数组
        // 假设后端返回 rows 和 columns
        if (Array.isArray(preview.rows) && preview.rows.length > 0) {
          // 获取列名需要额外请求 stats
          const stats = await dataApi.stats(selectedFileId)
          const cols = (stats as any).columns || []
          payload = (preview.rows as unknown[][]).map(row => {
            const obj: Record<string, unknown> = {}
            cols.forEach((c: string, i: number) => {
              const raw = row[i]
              const num = Number(raw)
              obj[c] = raw === null || raw === undefined ? null : (isNaN(num) ? raw : num)
            })
            return obj
          })
        }
      } catch (err: any) {
        setInferenceError(`加载数据集失败：${err.message}`)
        return
      }
    }

    if (payload.length === 0) {
      setInferenceError('没有可推理的数据')
      return
    }

    setRunning(true)
    setInferenceError(null)
    setResults([])

    try {
      const result: InferenceResult = await modelsApi.predict(selectedModelId, payload)

      const rows: InferenceRow[] = payload.map((item, idx) => {
        const pred = Array.isArray(result.predictions) ? result.predictions[idx] : null
        const proba = result.probabilities ? result.probabilities[idx] : null
        // 分类任务取最大概率作为 confidence
        const confidence = proba && Array.isArray(proba) ? Math.max(...proba.map(Number)) : null

        return {
          _index: idx,
          _original: item,
          prediction: pred,
          probability: confidence,
          error: null,
        }
      })

      setResults(rows)

      // 滚动到结果
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '推理失败'
      setInferenceError(msg)
    } finally {
      setRunning(false)
    }
  }

  // ============ 下载结果 ============

  const downloadResults = () => {
    if (results.length === 0) return
    const cols = selectedModel ? ['_index', ...Object.keys(results[0]._original), 'prediction', 'probability'] : ['_index', 'prediction']
    const header = cols.join(',')
    const lines = results.map(r => {
      const vals = [
        r._index,
        ...Object.values(r._original).map(v => `"${String(v ?? '')}"`),
        `"${String(r.prediction ?? '')}"`,
        r.probability != null ? (r.probability as number).toFixed(4) : '',
      ]
      return vals.join(',')
    })
    const csv = [header, ...lines].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `inference_results_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ============ 统计 ============

  const totalCount = results.length
  const successCount = results.filter(r => !r.error && r.prediction !== null).length
  const failCount = results.filter(r => r.error || r.prediction === null).length

  // 列名（用于表格渲染）
  const inputColumns = results.length > 0 ? Object.keys(results[0]._original) : []

  const selectedFile = dataFiles.find(f => f.id === selectedFileId)

  // ============ 渲染 ============

  return (
    <div className="space-y-8">
      {/* 标题区 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">模型推理</h1>
          <p className="text-slate-500 mt-1">选择模型，输入数据，执行批量推理</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ====== 左侧配置面板 (40%) ====== */}
        <div className="lg:col-span-2 space-y-6">

          {/* ① 模型选择 */}
          <Card>
            <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Cpu className="w-4 h-4" />
              ① 选择模型
            </h2>

            {loadingModels ? (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">加载中...</span>
              </div>
            ) : models.length === 0 ? (
              <div className="text-center py-6 text-slate-400">
                <Cpu className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">暂无训练好的模型</p>
                <p className="text-xs mt-1">请先在训练页面训练模型</p>
              </div>
            ) : (
              <div className="space-y-2">
                {models.map(model => (
                  <div
                    key={model.id}
                    onClick={() => setSelectedModelId(model.id)}
                    className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                      selectedModelId === model.id
                        ? 'bg-primary-50 border border-primary-300'
                        : 'bg-slate-50 hover:bg-slate-100 border border-transparent'
                    }`}
                  >
                    <Cpu className="w-5 h-5 text-slate-400 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900 truncate">{model.name}</p>
                      <p className="text-xs text-slate-500 flex items-center gap-2">
                        <span>{model.model_type}</span>
                        <span>·</span>
                        <span>{new Date(model.created_at).toLocaleDateString('zh-CN')}</span>
                      </p>
                    </div>
                    {selectedModelId === model.id && (
                      <CheckCircle2 className="w-4 h-4 text-primary-600 flex-shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* 选中模型信息 */}
            {selectedModel && (
              <div className="mt-4 p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                <p className="text-sm font-medium text-emerald-800">
                  ✓ 已选择: {selectedModel.name}
                </p>
                <p className="text-xs text-emerald-600 mt-1">
                  类型: {selectedModel.model_type} · 创建: {new Date(selectedModel.created_at).toLocaleString('zh-CN')}
                </p>
                {Object.keys(selectedModel.metrics || {}).length > 0 && (
                  <p className="text-xs text-emerald-600 mt-1">
                    指标: {Object.entries(selectedModel.metrics).map(([k, v]) => `${k}=${(v as number).toFixed(4)}`).join(' · ')}
                  </p>
                )}
              </div>
            )}
          </Card>

          {/* ② 推理模式 */}
          {selectedModelId && (
            <Card>
              <h2 className="text-base font-semibold text-slate-900 mb-4">② 输入方式</h2>

              {/* 模式切换 Tab */}
              <div className="flex border-b border-slate-200 mb-4">
                {[
                  { id: 'json' as InferenceMode, label: 'JSON', desc: '粘贴 JSON 数据' },
                  { id: 'csv' as InferenceMode, label: 'CSV', desc: '上传 CSV 文件' },
                  { id: 'path' as InferenceMode, label: '数据集', desc: '从已上传文件选择' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setMode(tab.id)}
                    className={`flex-1 px-3 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
                      mode === tab.id
                        ? 'border-primary-500 text-primary-700'
                        : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {tab.label}
                    <p className="text-xs text-slate-400 font-normal">{tab.desc}</p>
                  </button>
                ))}
              </div>

              {/* JSON 模式 */}
              {mode === 'json' && (
                <div className="space-y-3">
                  <div>
                    <textarea
                      value={jsonInput}
                      onChange={e => {
                        setJsonInput(e.target.value)
                        if (e.target.value.trim()) validateJson(e.target.value)
                        else setJsonError(null)
                      }}
                      placeholder={'[\n  {"feature1": 1.0, "feature2": 2.5, "feature3": 0},\n  {"feature1": 0.5, "feature2": 3.1, "feature3": 1}\n]'}
                      rows={10}
                      className={`w-full px-3 py-2 text-sm font-mono border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-300 transition-all ${
                        jsonError ? 'border-red-300 bg-red-50' : 'border-slate-300 bg-slate-50'
                      }`}
                    />
                    {jsonError && (
                      <div className="flex items-start gap-1 mt-1">
                        <AlertCircle className="w-3 h-3 text-red-500 flex-shrink-0 mt-0.5" />
                        <p className="text-xs text-red-600">{jsonError}</p>
                      </div>
                    )}
                    <p className="text-xs text-slate-400 mt-1">
                      支持多行 JSON 数组，每行一个对象，字段名需与模型输入特征一致
                    </p>
                  </div>
                </div>
              )}

              {/* CSV 模式 */}
              {mode === 'csv' && (
                <div className="space-y-3">
                  {!csvFile ? (
                    <div
                      onDragOver={e => e.preventDefault()}
                      onDrop={handleCsvDrop}
                      className="border-2 border-dashed border-slate-200 rounded-xl p-6 text-center hover:border-primary-300 transition-colors cursor-pointer"
                      onClick={() => document.getElementById('csv-upload')?.click()}
                    >
                      <input
                        id="csv-upload"
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={e => {
                          const f = e.target.files?.[0]
                          if (f) handleCsvUpload(f)
                        }}
                      />
                      <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                      <p className="text-sm font-medium text-slate-700">点击上传或拖拽 CSV 文件</p>
                      <p className="text-xs text-slate-400 mt-1">支持 .csv 格式，建议不超过 10MB</p>
                    </div>
                  ) : (
                    <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
                          <span className="text-sm font-medium text-emerald-800 truncate max-w-[200px]">{csvFile.name}</span>
                        </div>
                        <button
                          onClick={() => {
                            setCsvFile(null)
                            setCsvPreview(null)
                          }}
                          className="text-slate-400 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      {csvPreview && (
                        <p className="text-xs text-emerald-600 mt-1">
                          {csvPreview.rows.length} 行（预览前{csvPreview.rows.length}行） · {csvPreview.columns.length} 列
                        </p>
                      )}
                    </div>
                  )}

                  {/* CSV 预览 */}
                  {csvPreview && (
                    <div className="overflow-x-auto border border-slate-200 rounded-lg">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-slate-50 border-b border-slate-200">
                            <th className="px-2 py-1.5 text-left font-semibold text-slate-600">#</th>
                            {csvPreview.columns.map(col => (
                              <th key={col} className="px-2 py-1.5 text-center font-semibold text-slate-600 truncate max-w-[100px]">{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {csvPreview.rows.slice(0, 5).map((row, i) => (
                            <tr key={i} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                              <td className="px-2 py-1.5 text-slate-400">{i + 1}</td>
                              {csvPreview.columns.map(col => (
                                <td key={col} className="px-2 py-1.5 text-slate-700 truncate max-w-[100px]" title={String(row[col] ?? '')}>
                                  {row[col] === null || row[col] === undefined ? <span className="text-slate-400 italic">null</span> : String(row[col])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {csvPreview.rows.length > 5 && (
                        <p className="text-xs text-slate-400 p-2">... 共 {csvPreview.rows.length} 行</p>
                      )}
                    </div>
                  )}

                  {csvLoading && (
                    <div className="flex items-center gap-2 text-slate-500">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-sm">解析中...</span>
                    </div>
                  )}
                </div>
              )}

              {/* 路径模式 */}
              {mode === 'path' && (
                <div className="space-y-3">
                  {dataFiles.length === 0 ? (
                    <div className="text-center py-6 text-slate-400">
                      <FileSpreadsheet className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">暂无已上传的数据集</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {dataFiles.map(file => (
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
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-slate-900 truncate">{file.filename}</p>
                            <p className="text-xs text-slate-500">
                              {file.rows} 行 · {file.columns?.length || 0} 列
                            </p>
                          </div>
                          {selectedFileId === file.id && (
                            <CheckCircle2 className="w-4 h-4 text-primary-600 flex-shrink-0" />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {selectedFile && (
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-sm text-blue-800 font-medium">
                        已选择: {selectedFile.filename}
                      </p>
                      <p className="text-xs text-blue-600 mt-1">
                        共 {selectedFile.rows} 行 · {selectedFile.columns.length} 列
                      </p>
                      <p className="text-xs text-blue-500 mt-1">
                        推理将对全部 {selectedFile.rows} 行数据进行预测
                      </p>
                    </div>
                  )}
                </div>
              )}
            </Card>
          )}

          {/* ③ 操作 */}
          {selectedModelId && (
            <Card>
              {/* 错误提示 */}
              {inferenceError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">{inferenceError}</p>
                </div>
              )}

              <Button
                variant="primary"
                onClick={runInference}
                disabled={running || !selectedModelId}
                className="w-full"
              >
                {running ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> 推理中...</>
                ) : (
                  <><Play className="w-4 h-4" /> 开始推理</>
                )}
              </Button>

              {results.length > 0 && (
                <Button
                  variant="secondary"
                  onClick={downloadResults}
                  className="w-full mt-2"
                >
                  <Download className="w-4 h-4" />
                  下载结果 CSV
                </Button>
              )}
            </Card>
          )}
        </div>

        {/* ====== 右侧结果面板 (60%) ====== */}
        <div className="lg:col-span-3 space-y-6" ref={resultsRef}>
          {/* 结果表格 */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-slate-900">推理结果</h2>
              {results.length > 0 && (
                <span className="text-xs text-slate-500">
                  共 {totalCount} 条 · 成功 {successCount} · 失败 {failCount}
                </span>
              )}
            </div>

            {!selectedModelId && (
              <div className="text-center py-16 text-slate-400">
                <Cpu className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p className="font-medium">请先选择模型</p>
              </div>
            )}

            {selectedModelId && results.length === 0 && !running && (
              <div className="text-center py-16 text-slate-400">
                <Play className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p className="font-medium">推理结果将在此处显示</p>
                <p className="text-sm mt-1">选择模型和输入数据后，点击"开始推理"</p>
              </div>
            )}

            {running && (
              <div className="text-center py-16 text-slate-400">
                <Loader2 className="w-12 h-12 mx-auto mb-3 animate-spin text-primary-500" />
                <p className="font-medium text-primary-600">推理中...</p>
                <p className="text-sm mt-1">请稍候</p>
              </div>
            )}

            {results.length > 0 && (
              <div className="space-y-3">
                {/* 汇总统计 */}
                <div className="flex gap-3">
                  <div className="flex-1 p-3 bg-slate-50 rounded-lg border border-slate-200 text-center">
                    <p className="text-2xl font-bold text-slate-900">{totalCount}</p>
                    <p className="text-xs text-slate-500">总数</p>
                  </div>
                  <div className="flex-1 p-3 bg-emerald-50 rounded-lg border border-emerald-200 text-center">
                    <p className="text-2xl font-bold text-emerald-700">{successCount}</p>
                    <p className="text-xs text-emerald-600">成功</p>
                  </div>
                  <div className="flex-1 p-3 bg-red-50 rounded-lg border border-red-200 text-center">
                    <p className="text-2xl font-bold text-red-700">{failCount}</p>
                    <p className="text-xs text-red-600">失败</p>
                  </div>
                </div>

                {/* 结果表格 */}
                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-100 border-b border-slate-200">
                        <th className="px-2 py-2 text-center font-semibold text-slate-600 w-10">#</th>
                        {inputColumns.map(col => (
                          <th key={col} className="px-2 py-2 text-center font-semibold text-slate-600 truncate max-w-[120px]" title={col}>
                            {col}
                          </th>
                        ))}
                        <th className="px-2 py-2 text-center font-semibold text-primary-700 bg-primary-50 min-w-[80px]">预测结果</th>
                        {results.some(r => r.probability !== null) && (
                          <th className="px-2 py-2 text-center font-semibold text-blue-700 bg-blue-50 min-w-[80px]">置信度</th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {results.map((row, rowIdx) => (
                        <tr key={rowIdx} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                          <td className="px-2 py-2 text-center text-slate-400">{row._index + 1}</td>
                          {inputColumns.map(col => {
                            const val = row._original[col]
                            return (
                              <td
                                key={col}
                                className="px-2 py-2 text-center text-slate-700 truncate max-w-[120px]"
                                title={String(val ?? '')}
                              >
                                {val === null || val === undefined ? (
                                  <span className="text-slate-400 italic">null</span>
                                ) : typeof val === 'number' ? (
                                  Number(val).toFixed(4)
                                ) : (
                                  String(val)
                                )}
                              </td>
                            )
                          })}
                          <td className="px-2 py-2 text-center font-semibold bg-primary-50">
                            {row.error ? (
                              <span className="flex items-center gap-1 text-red-600 justify-center">
                                <XCircle className="w-3 h-3" />
                                失败
                              </span>
                            ) : (
                              <span className="text-primary-700">
                                {row.prediction === null ? (
                                  <span className="text-slate-400 italic">—</span>
                                ) : String(row.prediction)}
                              </span>
                            )}
                          </td>
                          {results.some(r => r.probability !== null) && (
                            <td className="px-2 py-2 text-center bg-blue-50">
                              {row.probability !== null ? (
                                <span className="text-blue-700">{(row.probability as number * 100).toFixed(1)}%</span>
                              ) : (
                                <span className="text-slate-400 italic">—</span>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
