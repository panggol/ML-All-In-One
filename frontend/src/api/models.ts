/**
 * 模型管理 API
 */
import api from './client'

export interface ModelInfo {
  id: number
  name: string
  model_type: string
  task_type?: string
  metrics: Record<string, number>
  created_at: string
}

export interface InferenceResult {
  predictions: (string | number)[]
  probabilities: number[][] | null
}

export const modelsApi = {
  /**
   * 获取模型列表
   */
  list: async (): Promise<ModelInfo[]> => {
    const response = await api.get('/models/')
    return response.data
  },

  /**
   * 获取模型详情
   */
  get: async (modelId: number): Promise<ModelInfo> => {
    const response = await api.get(`/models/${modelId}`)
    return response.data
  },

  /**
   * 推理预测
   * @param modelId 模型 ID
   * @param data 输入数据，格式为对象数组 [{col1: val, col2: val}, ...]
   */
  predict: async (modelId: number, data: Record<string, unknown>[]): Promise<InferenceResult> => {
    const response = await api.post(`/models/${modelId}/predict`, { data })
    return response.data
  },

  /**
   * 删除模型
   */
  delete: async (modelId: number): Promise<void> => {
    const response = await api.delete(`/models/${modelId}`)
    return response.data
  },
}
