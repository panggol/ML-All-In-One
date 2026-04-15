import api from './client'

// ─── 数据分布 ────────────────────────────────────────────────────────────────

export interface DistributionStats {
  count: number
  missing: number
  mean?: number
  std?: number
  min?: number
  max?: number
  median?: number
  histogram?: { bins: number[]; counts: number[]; midpoints: number[] }
  boxplot?: {
    min: number; q1: number; median: number; q3: number; max: number
    whisker_low: number; whisker_high: number; outliers: number[]
  }
  unique?: number
  top_values?: Array<{ value: string; count: number }>
  pie_image?: string  // base64 PNG
}

export interface FeatureDistribution {
  feature: string
  dtype: string
  stats: DistributionStats
}

export interface DataDistributionsResponse {
  dataset_info: { rows: number; columns: number; preview_rows: number }
  plot_type?: string
  plots: FeatureDistribution[]
  scatter?: {
    x_feature: string
    y_feature: string
    image: string  // base64 PNG
  }
  line?: {
    feature: string
    x: number[]
    y: number[]
    min: number
    max: number
    median: number
    count: number
  }
  correlation_matrix?: { features: string[]; matrix: number[][] }
  missing_values?: Array<{ feature: string; missing_count: number; missing_rate: number }>
}

export interface DataSummary {
  rows: number
  columns: number
  numeric_features: number
  categorical_features: number
  total_missing_rate: number
  numeric_columns: string[]
  categorical_columns: string[]
}

// ─── 特征重要性 ──────────────────────────────────────────────────────────────

export interface FeatureImportanceItem {
  feature: string
  importance: number
}

export interface FeatureImportanceResponse {
  experiment_id: number
  model_type: string
  importance: FeatureImportanceItem[]
  note?: string
}

// ─── 预测评估 ────────────────────────────────────────────────────────────────

export interface EvaluationResponse {
  experiment_id: number
  task_type: 'classification' | 'regression'
  plots: Array<{
    type: string
    data: any
    labels?: string[]
  }>
  summary: Record<string, any>
}

// ─── 训练曲线 ────────────────────────────────────────────────────────────────

export interface TrainingCurve {
  name: string
  values: number[]
}

export interface TrainingCurvesResponse {
  experiment_id: number
  epochs: number[]
  curves: TrainingCurve[]
}

// ─── API 函数 ────────────────────────────────────────────────────────────────

export const vizApi = {
  // 数据分布
  getDistributions: async (
    dataFileId: number,
    options?: { features?: string; plot_type?: string; sample_size?: number }
  ): Promise<DataDistributionsResponse> => {
    const params = new URLSearchParams()
    if (options?.features) params.set('features', options.features)
    if (options?.plot_type) params.set('plot_type', options.plot_type)
    if (options?.sample_size) params.set('sample_size', String(options.sample_size))
    const response = await api.get(`/viz/data/${dataFileId}/distributions?${params}`)
    return response.data
  },

  // 数据摘要
  getDataSummary: async (dataFileId: number): Promise<DataSummary> => {
    const response = await api.get(`/viz/data/${dataFileId}/summary`)
    return response.data
  },

  // 特征重要性
  getFeatureImportance: async (expId: number, topK = 20): Promise<FeatureImportanceResponse> => {
    const response = await api.get(`/viz/experiments/${expId}/feature-importance?top_k=${topK}`)
    return response.data
  },

  // 预测评估
  getEvaluation: async (expId: number): Promise<EvaluationResponse> => {
    const response = await api.get(`/viz/experiments/${expId}/evaluation`)
    return response.data
  },

  // 训练曲线
  getTrainingCurves: async (expId: number): Promise<TrainingCurvesResponse> => {
    const response = await api.get(`/viz/experiments/${expId}/training-curves`)
    return response.data
  },

  // 图表图片（PNG）
  getChartImage: (expId: number, chartType: string): string => {
    const token = localStorage.getItem('token')
    return `/api/viz/experiments/${expId}/chart/${chartType}${token ? `?token=${token}` : ''}`
  },
}
