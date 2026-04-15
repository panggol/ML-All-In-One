/**
 * 调度器 API 客户端
 * 对接 /api/scheduler/* 后端接口
 */
import api from './client'

// ============ 类型定义 ============

export type JobType = 'preprocessing' | 'training' | 'pipeline'
export type JobStatus = 'active' | 'paused' | 'failed'
export type ExecutionStatus = 'SUCCESS' | 'FAILED' | 'RUNNING'
export type TriggerType = 'scheduled' | 'manual'

export interface Job {
  id: string
  name: string
  job_type: JobType
  target_id: number | null
  cron_expression: string
  status: JobStatus
  webhook_url: string | null
  retry_count: number
  params: Record<string, any>
  is_enabled: boolean
  next_run_time: string | null
  created_at: string
  updated_at: string
}

export interface Execution {
  id: string
  job_id: string
  status: ExecutionStatus
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  error_message: string | null
  triggered_by: TriggerType
}

export interface JobCreateRequest {
  name: string
  job_type: JobType
  target_id?: number | null
  cron_expression: string
  params?: Record<string, any>
  webhook_url?: string
  retry_count?: number
  is_enabled?: boolean
}

export interface JobUpdateRequest {
  name?: string
  cron_expression?: string
  params?: Record<string, any>
  webhook_url?: string
  retry_count?: number
  is_enabled?: boolean
  status?: JobStatus
}

export interface CronValidateRequest {
  cron_expression: string
}

export interface CronValidateResponse {
  valid: boolean
  next_run_time?: string
  description?: string
  error?: string
}

export interface PaginatedJobs {
  data: Job[]
  total: number
  page: number
  page_size: number
}

export interface PaginatedExecutions {
  data: Execution[]
  total: number
  page: number
  page_size: number
}

export interface TriggerResponse {
  message: string
  execution_id: string
}

// ============ API 函数 ============

export const schedulerApi = {
  /** 列出任务 */
  list: (params?: { page?: number; page_size?: number; status?: string; keyword?: string }) =>
    api.get<PaginatedJobs>('/scheduler/jobs', { params }),

  /** 获取单个任务 */
  get: (jobId: string) =>
    api.get<Job>(`/scheduler/jobs/${jobId}`),

  /** 创建任务 */
  create: (data: JobCreateRequest) =>
    api.post<Job>('/scheduler/jobs', data),

  /** 更新任务 */
  update: (jobId: string, data: JobUpdateRequest) =>
    api.patch<Job>(`/scheduler/jobs/${jobId}`, data),

  /** 删除任务 */
  delete: (jobId: string) =>
    api.delete(`/scheduler/jobs/${jobId}`),

  /** 获取执行历史 */
  history: (jobId: string, params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedExecutions>(`/scheduler/jobs/${jobId}/history`, { params }),

  /** 手动触发 */
  trigger: (jobId: string) =>
    api.post<TriggerResponse>(`/scheduler/jobs/${jobId}/trigger`),

  /** 校验 Cron 表达式 */
  validateCron: (cron: string) =>
    api.post<CronValidateResponse>('/scheduler/cron/validate', { cron_expression: cron }),
}
