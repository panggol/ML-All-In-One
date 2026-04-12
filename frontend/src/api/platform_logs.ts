/**
 * platform_logs.ts - 平台日志 API 客户端
 * 对应后端 GET /api/platform-logs
 */
import api from './client'

/** 单条平台日志条目 */
export interface PlatformLogEntry {
  timestamp: string      // ISO8601, e.g. "2026-04-12T17:30:00.123Z"
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  module: string         // "api" | "auth" | "preprocessing" | "error" | "system"
  message: string
  request_id: string
  user_id: string | null
  extra: Record<string, unknown>
}

/** 平台日志列表响应 */
export interface PlatformLogsResponse {
  data: PlatformLogEntry[]
  total: number
  page: number
  page_size: number
  next_token: string | null
}

/** 筛选参数 */
export interface PlatformLogsFilter {
  module?: 'api' | 'auth' | 'preprocessing' | 'error' | 'system'
  level?: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  start_time?: string   // ISO8601
  end_time?: string     // ISO8601
  keyword?: string
}

function buildParams(
  filter: PlatformLogsFilter,
  page: number,
  pageSize: number,
  nextToken?: string | null,
): Record<string, string> {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  }
  if (filter.module) params.module = filter.module
  if (filter.level) params.level = filter.level
  if (filter.start_time) params.start_time = filter.start_time
  if (filter.end_time) params.end_time = filter.end_time
  if (filter.keyword) params.keyword = filter.keyword
  if (nextToken) params.next_token = nextToken
  return params
}

export const platformLogsApi = {
  /**
   * 分页列出平台日志
   * @param filter 筛选条件
   * @param page 页码（从 1 开始）
   * @param pageSize 每页条数（默认 100，最大 500）
   * @param nextToken 追加加载 token（覆盖 page 参数）
   */
  list: async (
    filter: PlatformLogsFilter = {},
    page: number = 1,
    pageSize: number = 100,
    nextToken?: string | null,
  ): Promise<PlatformLogsResponse> => {
    const response = await api.get('/platform-logs', {
      params: buildParams(filter, page, pageSize, nextToken),
    })
    return response.data
  },
}
