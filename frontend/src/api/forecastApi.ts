/**
 * Forecast API Client
 * 时序预测模块前端 API 封装
 */
import { client } from './client'

export interface PrepareResponse {
  dataset_id: number
  name: string
  freq: string
  detected_freq: string
  freq_confidence: number
  time_range_start: string
  time_range_end: string
  row_count: number
  missing_ratio: number
  duplicate_count: number
  feature_names: string[]
  warnings: string[]
}

export interface TrainResponse {
  task_id: string
  model_id: number | null
  model_type: string
  status: string
  progress: number
  message: string
}

export interface TaskStatusResponse {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  current_phase: string | null
  result: {
    model_id: number
    train_time: number
    metrics: Record<string, number>
  } | null
  error: string | null
  logs: string | null
}

export interface ForecastPoint {
  timestamp: string
  yhat: number
  yhat_lower: number
  yhat_upper: number
  confidence: number
}

export interface PredictResponse {
  model_id: number
  model_type: string
  steps: number
  confidence: number
  forecast: ForecastPoint[]
  warnings: string[]
}

export interface DecomposeResponse {
  model_type: string
  timestamps: string[]
  trend: number[]
  seasonal: number[]
  residual: number[] | null
  yearly: number[] | null
  weekly: number[] | null
  holidays: number[] | null
}

export interface FoldMetrics {
  fold: number
  train_start: string
  train_end: string
  test_start: string
  test_end: string
  n_train: number
  n_test: number
  mae: number
  rmse: number
  mape: number
}

export interface CrossValResponse {
  task_id: string
  status: string
  model_type: string
  model_id: number
  initial_days: number
  horizon: number
  period: number
  folds: FoldMetrics[]
  mae_mean: number
  mae_std: number
  rmse_mean: number
  rmse_std: number
  mape_mean: number
  mape_std: number
  total_time_seconds: number
}

export interface CVProgressResponse {
  task_id: string
  status: string
  progress: number
  current_fold: number
  current_metrics: FoldMetrics | null
}

export type ModelType = 'prophet' | 'arima' | 'lightgbm'

export interface TrainRequest {
  dataset_id: number
  model_type: ModelType
  // Prophet
  changepoint_prior_scale?: number
  seasonality_mode?: 'additive' | 'multiplicative'
  growth?: 'linear' | 'logistic'
  holidays?: string[]
  // ARIMA
  auto_arima?: boolean
  p?: number
  d?: number
  q?: number
  search_timeout?: number
  // LightGBM
  lags?: number[]
  rolling_windows?: number[]
  n_estimators?: number
  early_stopping_rounds?: number
}

export interface PredictRequest {
  model_id: number
  steps: number
  confidence: number
}

export interface CrossValRequest {
  model_id: number
  initial_days: number
  horizon: number
  period: number
}

// API functions
export const forecastApi = {
  /** 准备数据集：上传 CSV，自动检测频率 */
  async prepare(formData: FormData): Promise<PrepareResponse> {
    const res = await client.post('/api/forecast/prepare', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  /** 训练模型（异步） */
  async train(req: TrainRequest): Promise<TrainResponse> {
    const res = await client.post('/api/forecast/train', req)
    return res.data
  },

  /** 查询训练状态 */
  async getTrainStatus(taskId: string): Promise<TaskStatusResponse> {
    const res = await client.get(`/api/forecast/train/${taskId}/status`)
    return res.data
  },

  /** 预测 */
  async predict(req: PredictRequest): Promise<PredictResponse> {
    const res = await client.post('/api/forecast/predict', req)
    return res.data
  },

  /** 季节性分解 */
  async decompose(params: {
    dataset_id: number
    model_type?: ModelType
    model_id?: number
  }): Promise<DecomposeResponse> {
    const res = await client.get('/api/forecast/decompose', { params })
    return res.data
  },

  /** 启动交叉验证（异步） */
  async crossValidate(req: CrossValRequest): Promise<CrossValResponse> {
    const res = await client.get('/api/forecast/cross-validate', { params: req as any })
    return res.data
  },

  /** 启动交叉验证（POST） */
  async startCrossValidate(req: CrossValRequest): Promise<CrossValResponse> {
    const res = await client.post('/api/forecast/cross-validate', null, { params: req as any })
    return res.data
  },

  /** 查询 CV 进度 */
  async getCVProgress(taskId: string): Promise<CVProgressResponse> {
    const res = await client.get(`/api/forecast/cross-validate/${taskId}/progress`)
    return res.data
  },

  /** 获取 CV 最终结果 */
  async getCVResult(taskId: string): Promise<CrossValResponse> {
    const res = await client.get(`/api/forecast/cross-validate/${taskId}/result`)
    return res.data
  },
}
