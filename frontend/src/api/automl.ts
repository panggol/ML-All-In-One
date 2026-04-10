import api from './client'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SearchSpaceItem {
  name: string
  type: 'choice' | 'int' | 'float'
  values?: string[]
  low?: number
  high?: number
  step?: number
  log?: boolean
}

export interface AutoMLRequest {
  data_file_id: number
  target_column: string
  task_type: 'classification' | 'regression'
  strategy: 'grid' | 'random' | 'bayesian'
  search_space: SearchSpaceItem[]
  n_trials: number
  timeout: number
}

export interface AutoMLStatus {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number
  current_trial: number
  n_trials: number
  logs: string
}

export interface TopModel {
  rank: number
  model_type: string
  val_score: number
  train_score: number
  train_time: number
  params: Record<string, any>
}

export interface AutoMLReport {
  job_id: string
  status: string
  best_params: Record<string, any>
  best_val_score: number
  best_train_score: number
  strategy: string
  n_trials: number
  total_time: number
  top_models: TopModel[]
  report_md: string
}

// ─── API ──────────────────────────────────────────────────────────────────────

export const automlApi = {
  start: async (params: AutoMLRequest): Promise<{ job_id: string }> => {
    const response = await api.post('/automl/start', params)
    return response.data
  },

  status: async (jobId: string): Promise<AutoMLStatus> => {
    const response = await api.get(`/automl/status/${jobId}`)
    return response.data
  },

  report: async (jobId: string): Promise<AutoMLReport> => {
    const response = await api.get(`/automl/report/${jobId}`)
    return response.data
  },

  stop: async (jobId: string) => {
    await api.post(`/automl/stop/${jobId}`)
  },
}
