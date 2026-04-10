import api from './client'

export interface DataFile {
  id: number
  filename: string
  size: number
  rows: number
  columns: string[]
  created_at: string
}

export const dataApi = {
  upload: async (file: File): Promise<DataFile> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await api.post('/data/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  list: async (): Promise<DataFile[]> => {
    const response = await api.get('/data/list')
    return response.data
  },

  get: async (id: number): Promise<DataFile> => {
    const response = await api.get(`/data/${id}`)
    return response.data
  },

  delete: async (id: number) => {
    await api.delete(`/data/${id}`)
  },

  preview: async (id: number) => {
    const response = await api.get(`/data/${id}/preview`)
    return response.data
  },

  stats: async (id: number) => {
    const response = await api.get(`/data/${id}/stats`)
    return response.data
  },

  featureSelection: async (id: number, params: {
    target_column: string
    method: string
    threshold?: number
  }): Promise<{
    selected_features: string[]
    all_features: string[]
    method: string
    removed_features: string[]
    reason?: Record<string, any>
  }> => {
    const response = await api.post(`/data/${id}/feature-selection`, params)
    return response.data
  },
}
