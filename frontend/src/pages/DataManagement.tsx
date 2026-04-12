import { useState, useEffect } from 'react'
import {
  Upload, FileSpreadsheet, Eye, BarChart3, Trash2, X,
  Download, Loader2, AlertCircle, CheckCircle2, FolderOpen
} from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import { dataApi, type DataFile } from '../api'

// ============ 类型定义 ============

interface PreviewResponse {
  rows: unknown[][]
  columns: string[]
  total_rows: number
}

interface ColumnStats {
  column: string
  dtype: string
  null_count: number
  unique_count?: number
  min?: number
  max?: number
  mean?: number
  std?: number
  top_values?: { value: string; count: number }[]
}

interface StatsResponse {
  total_rows: number
  total_columns: number
  column_stats: ColumnStats[]
}

// ============ 工具函数 ============

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 7) return `${days} 天前`
  return date.toLocaleDateString('zh-CN')
}

// ============ 主组件 ============

export default function DataManagement() {
  // 数据状态
  const [files, setFiles] = useState<DataFile[]>([])
  const [loading, setLoading] = useState(true)
  
  // 上传状态
  const [uploading, setUploading] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState(false)
  
  // 详情面板状态
  const [selectedFile, setSelectedFile] = useState<DataFile | null>(null)
  const [detailTab, setDetailTab] = useState<'preview' | 'stats'>('preview')
  const [previewData, setPreviewData] = useState<PreviewResponse | null>(null)
  const [statsData, setStatsData] = useState<StatsResponse | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  
  // 删除确认
  const [deleteConfirm, setDeleteConfirm] = useState<DataFile | null>(null)
  const [deleting, setDeleting] = useState(false)
  
  // 错误状态
  const [error, setError] = useState<string | null>(null)

  // 加载文件列表
  useEffect(() => {
    loadFiles()
  }, [])

  // 加载选中文件的详情
  useEffect(() => {
    if (selectedFile) {
      loadDetail(detailTab)
    }
  }, [selectedFile, detailTab])

  const loadFiles = async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await dataApi.list()
      setFiles(list)
    } catch (err: any) {
      console.error('Failed to load files:', err)
      setError('加载文件列表失败')
    } finally {
      setLoading(false)
    }
  }

  const loadDetail = async (tab: 'preview' | 'stats') => {
    if (!selectedFile) return
    
    setLoadingDetail(true)
    try {
      if (tab === 'preview') {
        const data = await dataApi.preview(selectedFile.id)
        setPreviewData(data as PreviewResponse)
      } else {
        const data = await dataApi.stats(selectedFile.id)
        setStatsData(data as StatsResponse)
      }
    } catch (err: any) {
      console.error('Failed to load detail:', err)
      setError(err?.response?.data?.detail || err?.message || '加载失败')
    } finally {
      setLoadingDetail(false)
    }
  }

  // 上传文件
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    setUploading(true)
    setUploadSuccess(false)
    setError(null)
    
    try {
      await dataApi.upload(file)
      setUploadSuccess(true)
      await loadFiles()
      setTimeout(() => setUploadSuccess(false), 3000)
    } catch (err: any) {
      console.error('Upload failed:', err)
      setError(err?.response?.data?.detail || '上传失败')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  // 拖拽上传
  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (!file) return
    
    if (!file.name.endsWith('.csv')) {
      setError('只支持 CSV 格式文件')
      return
    }
    
    setUploading(true)
    setUploadSuccess(false)
    setError(null)
    
    try {
      await dataApi.upload(file)
      setUploadSuccess(true)
      await loadFiles()
      setTimeout(() => setUploadSuccess(false), 3000)
    } catch (err: any) {
      console.error('Upload failed:', err)
      setError(err?.response?.data?.detail || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  // 选择文件查看详情
  const handleSelectFile = (file: DataFile) => {
    if (selectedFile?.id === file.id) {
      setSelectedFile(null)
      setPreviewData(null)
      setStatsData(null)
    } else {
      setSelectedFile(file)
      setDetailTab('preview')
    }
  }

  // 删除文件
  const handleDelete = async () => {
    if (!deleteConfirm) return
    
    setDeleting(true)
    try {
      await dataApi.delete(deleteConfirm.id)
      setDeleteConfirm(null)
      if (selectedFile?.id === deleteConfirm.id) {
        setSelectedFile(null)
        setPreviewData(null)
        setStatsData(null)
      }
      await loadFiles()
    } catch (err: any) {
      console.error('Delete failed:', err)
      setError(err?.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  // 导出文件
  const handleExport = async (file: DataFile) => {
    try {
      const blob = await dataApi.export(file.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error('Export failed:', err)
      setError('导出失败')
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">数据管理</h1>
        <p className="text-slate-500 mt-1">数据集的上传、浏览、预览和管理</p>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm text-red-700">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 上传区域 */}
      <Card>
        <div
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
            uploading
              ? 'border-primary-300 bg-primary-50'
              : 'border-slate-200 hover:border-primary-300'
          }`}
        >
          <input
            type="file"
            accept=".csv"
            onChange={handleUpload}
            className="hidden"
            id="data-upload"
            disabled={uploading}
          />
          <label htmlFor="data-upload" className={`cursor-pointer ${uploading ? 'cursor-not-allowed' : ''}`}>
            {uploading ? (
              <>
                <Loader2 className="w-12 h-12 text-primary-500 mx-auto mb-4 animate-spin" />
                <p className="font-medium text-primary-700">上传中...</p>
              </>
            ) : uploadSuccess ? (
              <>
                <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
                <p className="font-medium text-emerald-700">上传成功</p>
              </>
            ) : (
              <>
                <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                <p className="font-medium text-slate-900">拖拽文件或点击上传</p>
                <p className="text-sm text-slate-500 mt-1">支持 CSV 格式</p>
              </>
            )}
          </label>
        </div>
      </Card>

      {/* 数据集列表 */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">数据集列表</h2>
        
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-primary-500 animate-spin mr-2" />
            <span className="text-slate-500">加载中...</span>
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-12">
            <FolderOpen className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="font-medium text-slate-500">暂无数据集</p>
            <p className="text-sm text-slate-400 mt-1">点击上方上传按钮开始上传</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="text-left py-3 px-4 text-sm font-semibold text-slate-600">文件名</th>
                  <th className="text-right py-3 px-4 text-sm font-semibold text-slate-600">大小</th>
                  <th className="text-right py-3 px-4 text-sm font-semibold text-slate-600">行数</th>
                  <th className="text-right py-3 px-4 text-sm font-semibold text-slate-600">列数</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold text-slate-600">上传时间</th>
                  <th className="text-center py-3 px-4 text-sm font-semibold text-slate-600">操作</th>
                </tr>
              </thead>
              <tbody>
                {files.map(file => (
                  <tr
                    key={file.id}
                    className={`border-b border-slate-100 hover:bg-slate-50 transition-colors ${
                      selectedFile?.id === file.id ? 'bg-primary-50' : ''
                    }`}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <FileSpreadsheet className={`w-5 h-5 flex-shrink-0 ${
                          selectedFile?.id === file.id ? 'text-primary-600' : 'text-slate-400'
                        }`} />
                        <span className="font-medium text-slate-900 truncate max-w-[200px]">
                          {file.filename}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-slate-500">
                      {formatBytes(file.size)}
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-slate-600">
                      {file.rows.toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right text-sm text-slate-600">
                      {file.columns.length}
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-500">
                      {formatRelativeTime(file.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-center gap-1">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleSelectFile(file)}
                        >
                          <Eye className="w-4 h-4" />
                          预览
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setSelectedFile(file)
                            setDetailTab('stats')
                          }}
                        >
                          <BarChart3 className="w-4 h-4" />
                          统计
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleExport(file)}
                        >
                          <Download className="w-4 h-4" />
                          导出
                        </Button>
                        <Button
                          variant="stop"
                          size="sm"
                          onClick={() => setDeleteConfirm(file)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 详情面板 */}
      {selectedFile && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-slate-900">{selectedFile.filename}</h2>
              
              {/* Tab 切换 */}
              <div className="flex border-b border-slate-200 ml-6">
                <button
                  onClick={() => setDetailTab('preview')}
                  className={`px-4 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
                    detailTab === 'preview'
                      ? 'border-primary-500 text-primary-700'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  预览 {previewData && `(${previewData.total_rows})`}
                </button>
                <button
                  onClick={() => setDetailTab('stats')}
                  className={`px-4 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
                    detailTab === 'stats'
                      ? 'border-primary-500 text-primary-700'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  统计
                </button>
              </div>
            </div>
            
            <Button variant="ghost" size="sm" onClick={() => setSelectedFile(null)}>
              <X className="w-4 h-4" />
            </Button>
          </div>

          {/* 预览内容 */}
          {detailTab === 'preview' && (
            <div>
              {loadingDetail ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 text-primary-500 animate-spin mr-2" />
                  <span className="text-slate-500">加载中...</span>
                </div>
              ) : previewData ? (
                <div className="space-y-3">
                  <p className="text-sm text-slate-500">
                    共 {previewData.total_rows.toLocaleString()} 行，显示前 {previewData.rows.length} 行
                  </p>
                  
                  <div className="overflow-x-auto border border-slate-200 rounded-lg">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-slate-50 border-b border-slate-200">
                          <th className="px-3 py-2 text-center font-semibold text-slate-600 w-12">#</th>
                          {previewData.columns.map(col => (
                            <th
                              key={col}
                              className="px-3 py-2 text-center font-semibold text-slate-600 truncate max-w-[150px]"
                              title={col}
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.rows.map((row, rowIdx) => (
                          <tr key={rowIdx} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                            <td className="px-3 py-2 text-center text-slate-400">{rowIdx + 1}</td>
                            {(row as unknown[]).map((cell, colIdx) => (
                              <td
                                key={colIdx}
                                className="px-3 py-2 text-center text-slate-700 truncate max-w-[150px]"
                                title={String(cell ?? '')}
                              >
                                {cell === null || cell === undefined ? (
                                  <span className="text-slate-400 italic">null</span>
                                ) : typeof cell === 'number' ? (
                                  Number(cell).toFixed(4).replace(/\.?0+$/, '')
                                ) : (
                                  String(cell)
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : previewData === null && error ? (
                <div className="text-center py-12">
                  <AlertCircle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
                  <p className="font-medium text-slate-700 mb-1">数据加载失败</p>
                  <p className="text-sm text-slate-500">{error}</p>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-400">
                  <FolderOpen className="w-10 h-10 mx-auto mb-3" />
                  <p>暂无预览数据</p>
                </div>
              )}
            </div>
          )}

          {/* 统计内容 */}
          {detailTab === 'stats' && (
            <div>
              {loadingDetail ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 text-primary-500 animate-spin mr-2" />
                  <span className="text-slate-500">加载中...</span>
                </div>
              ) : statsData ? (
                <div className="space-y-4">
                  <div className="flex gap-4 p-4 bg-slate-50 rounded-lg">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-slate-900">{statsData.total_rows.toLocaleString()}</p>
                      <p className="text-xs text-slate-500">总行数</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-slate-900">{statsData.total_columns}</p>
                      <p className="text-xs text-slate-500">总列数</p>
                    </div>
                  </div>

                  {/* 列统计 */}
                  <div className="space-y-3">
                    {statsData.column_stats.map(stat => (
                      <div key={stat.column} className="border border-slate-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-medium text-slate-900">{stat.column}</h4>
                          <span className={`px-2 py-0.5 text-xs rounded ${
                            stat.dtype === 'object' || stat.dtype === 'string'
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-blue-100 text-blue-700'
                          }`}>
                            {stat.dtype === 'object' || stat.dtype === 'string' ? '分类' : '数值'}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <p className="text-slate-500">计数</p>
                            <p className="font-medium text-slate-900">
                              {(statsData.total_rows - stat.null_count).toLocaleString()}
                            </p>
                          </div>
                          <div>
                            <p className="text-slate-500">缺失值</p>
                            <p className={`font-medium ${stat.null_count > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
                              {stat.null_count} ({((stat.null_count / statsData.total_rows) * 100).toFixed(1)}%)
                            </p>
                          </div>
                          {stat.unique_count !== undefined && (
                            <div>
                              <p className="text-slate-500">唯一值</p>
                              <p className="font-medium text-slate-900">{stat.unique_count}</p>
                            </div>
                          )}
                          {stat.min !== undefined && (
                            <div>
                              <p className="text-slate-500">范围</p>
                              <p className="font-medium text-slate-900">
                                [{stat.min.toFixed(2)}, {stat.max?.toFixed(2)}]
                              </p>
                            </div>
                          )}
                        </div>

                        {/* 数值列额外统计 */}
                        {stat.mean !== undefined && (
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mt-3 pt-3 border-t border-slate-100">
                            <div>
                              <p className="text-slate-500">均值</p>
                              <p className="font-medium text-slate-900">{stat.mean.toFixed(4)}</p>
                            </div>
                            <div>
                              <p className="text-slate-500">标准差</p>
                              <p className="font-medium text-slate-900">{stat.std?.toFixed(4)}</p>
                            </div>
                            <div>
                              <p className="text-slate-500">最小值</p>
                              <p className="font-medium text-slate-900">{stat.min?.toFixed(4)}</p>
                            </div>
                            <div>
                              <p className="text-slate-500">最大值</p>
                              <p className="font-medium text-slate-900">{stat.max?.toFixed(4)}</p>
                            </div>
                          </div>
                        )}

                        {/* 分类列 Top 值 */}
                        {stat.top_values && stat.top_values.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-slate-100">
                            <p className="text-sm text-slate-500 mb-2">Top 值:</p>
                            <div className="flex flex-wrap gap-2">
                              {stat.top_values.map((item, idx) => (
                                <span key={idx} className="px-2 py-1 bg-slate-100 rounded text-sm">
                                  {item.value} ({item.count}, {((item.count / statsData.total_rows) * 100).toFixed(1)}%)
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : error ? (
                <div className="text-center py-12">
                  <AlertCircle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
                  <p className="font-medium text-slate-700 mb-1">数据加载失败</p>
                  <p className="text-sm text-slate-500">{error}</p>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-400">
                  <FolderOpen className="w-10 h-10 mx-auto mb-3" />
                  <p>暂无统计数据</p>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* 删除确认对话框 */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">确认删除</h3>
            </div>
            
            <p className="text-slate-600 mb-6">
              确定删除 <span className="font-medium text-slate-900">{deleteConfirm.filename}</span> 吗？
              <br />
              <span className="text-sm">此操作不可撤销。</span>
            </p>
            
            <div className="flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={() => setDeleteConfirm(null)}
                disabled={deleting}
              >
                取消
              </Button>
              <Button
                variant="stop"
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    删除中...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    确认删除
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
