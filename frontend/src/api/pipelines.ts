/**
 * Pipeline Orchestration API 客户端
 * 对接 GET/POST /api/pipelines/* 接口
 */
import api from './client'

// ============ 类型定义 ============

export type PipelineStatus = 'draft' | 'active' | 'archived'
export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'timeout' | 'cancelled'
export type StepStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped' | 'timeout'
export type StepType = 'preprocessing' | 'feature_engineering' | 'training' | 'automl' | 'evaluation' | 'model_registration'
export type TriggerType = 'manual' | 'scheduled' | 'api'

export interface PipelineStep {
  name: string
  type: StepType
  config: Record<string, any>
  depends_on: string[]
  timeout_seconds?: number
  max_retries?: number
}

export interface PipelineDSL {
  steps: PipelineStep[]
}

export interface Pipeline {
  id: number
  name: string
  description: string | null
  version: number
  status: PipelineStatus
  dsl_format: 'json' | 'yaml'
  dsl_content: string
  schedule_cron: string | null
  schedule_enabled: boolean
  schedule_job_id: string | null
  owner_id: number
  created_at: string
  updated_at: string
}

export interface PipelineRun {
  id: number
  pipeline_id: number
  pipeline_version: number
  run_number: number
  status: RunStatus
  triggered_by: TriggerType
  run_params: Record<string, any> | null
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  error_message: string | null
  created_at: string
}

export interface PipelineStepRun {
  id: number
  run_id: number
  step_name: string
  step_type: StepType
  status: StepStatus
  order_index: number
  retry_count: number
  input_data: Record<string, any> | null
  output_data: Record<string, any> | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
}

export interface PipelineVersion {
  id: number
  pipeline_id: number
  version: number
  dsl_format: 'json' | 'yaml'
  dsl_content: string
  changelog: string | null
  created_by: number | null
  created_at: string
}

export interface ScheduleConfig {
  pipeline_id: number
  schedule_cron: string | null
  schedule_enabled: boolean
  schedule_job_id: string | null
  next_run_time: string | null
  timeout_seconds: number
  auto_retry: boolean
  retry_count: number
  webhook_url: string | null
}

// ============ API 函数 ============

export const pipelinesApi = {
  // ── Pipeline CRUD ──────────────────────────────────────────────────────

  list: (params?: {
    page?: number
    page_size?: number
    status?: string
    q?: string
  }) =>
    api.get<{ data: Pipeline[]; total: number; page: number; page_size: number }>(
      '/pipelines',
      { params }
    ),

  get: (id: number) =>
    api.get<Pipeline>(`/pipelines/${id}`),

  create: (data: {
    name: string
    description?: string
    dsl_content: string
    dsl_format?: 'json' | 'yaml'
    status?: string
  }) =>
    api.post<Pipeline>('/pipelines', data),

  update: (id: number, data: {
    dsl_content?: string
    description?: string
    changelog?: string
    status?: string
  }) =>
    api.patch<Pipeline>(`/pipelines/${id}`, data),

  delete: (id: number) =>
    api.delete(`/pipelines/${id}`),

  // ── Versions ──────────────────────────────────────────────────────────

  listVersions: (id: number) =>
    api.get<PipelineVersion[]>(`/pipelines/${id}/versions`),

  getVersion: (id: number, version: number) =>
    api.get<PipelineVersion>(`/pipelines/${id}/versions/${version}`),

  // ── Runs ──────────────────────────────────────────────────────────────

  listRuns: (id: number, params?: {
    page?: number
    page_size?: number
    status?: string
  }) =>
    api.get<{ data: PipelineRun[]; total: number; page: number; page_size: number }>(
      `/pipelines/${id}/runs`,
      { params }
    ),

  getRun: (pipelineId: number, runId: number) =>
    api.get<{ run: PipelineRun; steps: PipelineStepRun[] }>(
      `/pipelines/${pipelineId}/runs/${runId}`
    ),

  triggerRun: (id: number, params?: Record<string, any>) =>
    api.post<PipelineRun>(`/pipelines/${id}/run`, params ?? {}),

  retryRun: (pipelineId: number, runId: number, opts?: {
    from_step?: string
    full_rerun?: boolean
  }) =>
    api.post<PipelineRun>(
      `/pipelines/${pipelineId}/runs/${runId}/retry`,
      opts ?? {}
    ),

  cancelRun: (pipelineId: number, runId: number) =>
    api.post<PipelineRun>(`/pipelines/${pipelineId}/runs/${runId}/cancel`),

  getRunLogs: (pipelineId: number, runId: number) =>
    api.get<{ logs: string }>(`/pipelines/${pipelineId}/runs/${runId}/logs`),

  // ── Schedule ──────────────────────────────────────────────────────────

  listStepRuns: (runId: number) =>
    api.get<PipelineStepRun[]>(`/pipelines/runs/${runId}/steps`),

  getSchedule: (id: number) =>
    api.get<ScheduleConfig>(`/pipelines/${id}/schedule`),

  setSchedule: (id: number, data: Partial<{
    cron_expression: string | null
    is_enabled: boolean
    timeout_seconds: number
    auto_retry: boolean
    retry_count: number
    webhook_url: string | null
  }>) =>
    api.post<ScheduleConfig>(`/pipelines/${id}/schedule`, data),

  updateSchedule: (id: number, data: Partial<{
    cron_expression: string | null
    is_enabled: boolean
  }>) =>
    api.patch<ScheduleConfig>(`/pipelines/${id}/schedule`, data),
}
