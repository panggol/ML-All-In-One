import api from './client'

export interface TrainRequest {
  data_file_id: number
  target_column: string
  task_type: 'classification' | 'regression'
  model_type: 'sklearn' | 'xgboost' | 'lightgbm' | 'pytorch'
  model_name: string
  params?: Record<string, any>
  feature_columns?: string[]  // 手动选择的特征列
}

export interface TrainJob {
  id: number
  data_file_id?: number
  model_name: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number
  current_iter: number
  metrics: Record<string, number>
  logs: string
  created_at: string
  finished_at?: string
}

export interface MetricsCurve {
  epochs: number[]
  train_loss: number[]
  val_loss: number[]
  train_accuracy: number[]
  val_accuracy: number[]
}

export interface TrainStatus {
  id: number
  status: string
  progress: number
  current_iter: number
  accuracy: number
  loss: number
  logs: string
  metrics_curve?: MetricsCurve
}

export const trainApi = {
  create: async (data: TrainRequest): Promise<TrainJob> => {
    const response = await api.post('/train', data)
    return response.data
  },

  list: async (): Promise<TrainJob[]> => {
    const response = await api.get('/train')
    return response.data
  },

  getStatus: async (jobId: number): Promise<TrainStatus> => {
    const response = await api.get(`/train/${jobId}/status`)
    return response.data
  },

  stop: async (jobId: number) => {
    await api.post(`/train/${jobId}/stop`)
  },
}
