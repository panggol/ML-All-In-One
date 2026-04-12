/**
 * logs.ts - 日志 API 客户端
 * 对应后端 GET /api/logs, GET /api/logs/{file_id}, DELETE /api/logs/{file_id}
 */
import api from './client'

export interface LogEntry {
  file_id: string
  run: number
  iter: number
  timestamp: string
  experiment_id: string | null
  metrics: Record<string, unknown>
}

export interface LogListResponse {
  data: LogEntry[]
  total: number
  page: number
  page_size: number
}

export interface LogsFilter {
  experiment_id?: string
  start_time?: string   // ISO8601
  end_time?: string     // ISO8601
}

function buildParams(page: number, pageSize: number, filter?: LogsFilter): Record<string, string> {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  }
  if (filter?.experiment_id) params.experiment_id = filter.experiment_id
  if (filter?.start_time) params.start_time = filter.start_time
  if (filter?.end_time) params.end_time = filter.end_time
  return params
}

export const logsApi = {
  /**
   * 分页列出日志条目
   */
  list: async (
    page: number = 1,
    pageSize: number = 20,
    filter?: LogsFilter,
  ): Promise<LogListResponse> => {
    const response = await api.get('/logs', {
      params: buildParams(page, pageSize, filter),
    })
    return response.data
  },

  /**
   * 获取单个日志文件的完整内容
   */
  getDetail: async (fileId: string): Promise<object[]> => {
    const response = await api.get(`/logs/${encodeURIComponent(fileId)}`)
    return response.data
  },

  /**
   * 删除指定的日志文件
   */
  delete: async (fileId: string): Promise<{ message: string }> => {
    const response = await api.delete(`/logs/${encodeURIComponent(fileId)}`)
    return response.data
  },
}
