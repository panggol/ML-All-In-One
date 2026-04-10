import api from './client'

// ============ 类型定义 ============

export interface ImputerConfig {
  enabled: boolean
  strategy: string // 'mean' | 'median' | 'most_frequent' | 'constant'
}

export interface ScalerConfig {
  enabled: boolean
  type: 'minmax' | 'standard' | null
}

export interface FeatureSelectConfig {
  enabled: boolean
  threshold: number
  selected_columns: string[]
}

export interface PreprocessingSteps {
  imputer: ImputerConfig
  scaler: ScalerConfig
  feature_select: FeatureSelectConfig
}

export interface ColumnStats {
  column: string
  dtype: string
  original_mean: number | null
  original_std: number | null
  original_min: number | null
  original_max: number | null
  original_missing: number
  transformed_mean: number | null
  transformed_std: number | null
  transformed_min: number | null
  transformed_max: number | null
  transformed_missing: number
}

export interface PreviewResponse {
  original_preview: any[][]
  transformed_preview: any[][]
  columns: string[]
  stats: ColumnStats[]
  shape: [number, number]
}

export interface TransformResponse {
  data_file_id: number
  filename: string
  rows: number
  columns: number
}

// ============ API 客户端 ============

export const preprocessingApi = {
  /**
   * 预览预处理效果
   */
  preview: async (
    dataFileId: number,
    steps: PreprocessingSteps
  ): Promise<PreviewResponse> => {
    const response = await api.post('/preprocessing/preview', {
      data_file_id: dataFileId,
      steps,
    })
    return response.data
  },

  /**
   * 应用预处理并保存为新数据集
   */
  transform: async (
    dataFileId: number,
    steps: PreprocessingSteps,
    outputName?: string
  ): Promise<TransformResponse> => {
    const response = await api.post('/preprocessing/transform', {
      data_file_id: dataFileId,
      steps,
      output_name: outputName,
    })
    return response.data
  },
}

// ============ 默认配置 ============

export const DEFAULT_STEPS: PreprocessingSteps = {
  imputer: { enabled: false, strategy: 'mean' },
  scaler: { enabled: false, type: null },
  feature_select: { enabled: false, threshold: 0.0, selected_columns: [] },
}
