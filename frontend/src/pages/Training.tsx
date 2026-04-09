import { useState } from 'react'
import { Upload, Play, Pause, FileSpreadsheet } from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Select from '../components/Select'
import Input from '../components/Input'
import ProgressBar from '../components/ProgressBar'

const MODEL_OPTIONS = [
  { value: 'RandomForest', label: 'RandomForest' },
  { value: 'XGBoost', label: 'XGBoost' },
  { value: 'LightGBM', label: 'LightGBM' },
  { value: 'LogisticRegression', label: 'LogisticRegression' },
]

const TASK_OPTIONS = [
  { value: 'classification', label: '分类' },
  { value: 'regression', label: '回归' },
]

export default function Training() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [taskType, setTaskType] = useState<'classification' | 'regression'>('classification')
  const [targetColumn, setTargetColumn] = useState('')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [isTraining, setIsTraining] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentIter, setCurrentIter] = useState(0)
  const [accuracy, setAccuracy] = useState<number | null>(null)
  const [elapsedTime, setElapsedTime] = useState(0)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setSelectedFile(file)
  }

  const handleStartTraining = () => {
    if (!selectedFile || !targetColumn || !selectedModel) return
    
    setIsTraining(true)
    setProgress(0)
    setCurrentIter(0)
    setAccuracy(null)
    setElapsedTime(0)

    // 模拟训练过程
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          setIsTraining(false)
          setAccuracy(0.892)
          return 100
        }
        setCurrentIter(prev => prev + 1)
        setAccuracy((prevAcc) => {
          if (prevAcc === null) return 0.5
          return Math.min(prevAcc + 0.01, 0.95)
        })
        setElapsedTime((prev) => prev + 1)
        return prev + 2
      })
    }, 200)
  }

  const handleStopTraining = () => {
    setIsTraining(false)
    setProgress(0)
  }

  return (
    <div className="space-y-8">
      {/* Data Upload */}
      <Card>
        <h2 className="text-lg font-semibold text-slate-900 mb-6">数据上传</h2>
        
        <div className="border-2 border-dashed border-slate-200 rounded-xl p-12 text-center hover:border-primary-300 transition-colors">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
            {selectedFile ? (
              <div>
                <p className="font-medium text-slate-900">{selectedFile.name}</p>
                <p className="text-sm text-slate-500 mt-1">点击更换文件</p>
              </div>
            ) : (
              <div>
                <p className="font-medium text-slate-900">拖拽文件或点击上传</p>
                <p className="text-sm text-slate-500 mt-1">支持 CSV 格式，最大 100MB</p>
              </div>
            )}
          </label>
        </div>

        {selectedFile && (
          <div className="mt-6 flex items-center gap-4 p-4 bg-slate-50 rounded-lg">
            <FileSpreadsheet className="w-8 h-8 text-primary-600" />
            <div className="flex-1">
              <p className="font-medium text-slate-900">{selectedFile.name}</p>
              <p className="text-sm text-slate-500">{(selectedFile.size / 1024).toFixed(1)} KB</p>
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
            onChange={(e) => setTaskType(e.target.value as typeof taskType)}
          />
          <Input
            label="目标列"
            value={targetColumn}
            onChange={(e) => setTargetColumn(e.target.value)}
            placeholder="输入目标列名"
          />
        </div>

        {/* Model Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-3">选择模型</label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {MODEL_OPTIONS.map((model) => (
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
      {isTraining && (
        <Card>
          <h2 className="text-lg font-semibold text-slate-900 mb-4">训练进度</h2>
          <div className="space-y-6">
            <ProgressBar value={progress} />
            
            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100">
              <div className="text-center">
                <p className="text-2xl font-semibold text-slate-900">{currentIter}</p>
                <p className="text-sm text-slate-500">当前迭代</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-primary-600">
                  {accuracy !== null ? (accuracy * 100).toFixed(1) : '—'}%
                </p>
                <p className="text-sm text-slate-500">准确率</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-slate-900">{elapsedTime}s</p>
                <p className="text-sm text-slate-500">已用时间</p>
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
