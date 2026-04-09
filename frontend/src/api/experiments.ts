import api from './client'

export interface Experiment {
  id: number
  name: string
  description?: string
  params: Record<string, any>
  metrics: Record<string, number>
  status: string
  created_at: string
  finished_at?: string
}

export interface MetricsHistory {
  train_loss: number[]
  val_loss: number[]
  train_acc: number[]
  val_acc: number[]
  iterations: number[]
}

export const experimentApi = {
  list: async (): Promise<Experiment[]> => {
    const response = await api.get('/experiments')
    return response.data
  },

  get: async (id: number): Promise<Experiment> => {
    const response = await api.get(`/experiments/${id}`)
    return response.data
  },

  getMetrics: async (id: number): Promise<MetricsHistory> => {
    const response = await api.get(`/experiments/${id}/metrics`)
    return response.data
  },

  compare: async (ids: number[]): Promise<{ experiments: Experiment[] }> => {
    const response = await api.post('/experiments/compare', { experiment_ids: ids })
    return response.data
  },
}
