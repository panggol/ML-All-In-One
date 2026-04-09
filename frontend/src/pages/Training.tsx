import { useState, useEffect } from 'react'
import { Upload, Play, Pause, FileSpreadsheet } from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Select from '../components/Select'
import Input from '../components/Input'
import ProgressBar from '../components/ProgressBar'
import { dataApi, trainApi, TrainJob } from '../api'

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

export default function Training() {
  const [files, setFiles] = useState<any[]>([])
  const [selectedFile, setSelectedFile] = useState<number | null>(null)
  const [taskType, setTaskType] = useState<'classification' | 'regression'>('classification')
  const [targetColumn, setTargetColumn] = useState('')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [isTraining, setIsTraining] = useState(false)
  const [currentJob, setCurrentJob] = useState<TrainJob | null>(null)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    loadFiles()
  }, [])

  // 轮询训练状态
  useEffect(() => {
    if (!currentJob || currentJob.status !== 'running') return
    
    const interval = setInterval(async () => {
      try {
        const status = await trainApi.getStatus(currentJob.id)
        setProgress(status.progress)
        
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'stopped') {
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

  const loadFiles = async () => {
    try {
      const fileList = await dataApi.list()
      setFiles(fileList)
    } catch (err) {
      console.error('Failed to load files:', err)
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
      if (stats.columns.length > 0) {
        setTargetColumn(stats.columns[stats.columns.length - 1])
      }
    } catch (err) {
      console.error('Failed to upload file:', err)
    }
  }

  const handleStartTraining = async () => {
    if (!selectedFile || !targetColumn || !selectedModel) return
    
    try {
      const job = await trainApi.create({
        data_file_id: selectedFile,
        target_column: targetColumn,
        task_type: taskType,
        model_type: 'sklearn',
        model_name: selectedModel,
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
                {selectedFileData.rows} 行 · {selectedFileData.columns?.length || 0} 列
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
            disabled={!selectedFile || !targetColumn || !selectedModel}
          >
            <Play className="w-6 h-6" />
            开始训练
          </Button>
        )}
      </div>

      {/* Training Progress */}
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
    </div>
  )
}
