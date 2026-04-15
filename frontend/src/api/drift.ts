/**
 * 漂移检测 API
 * 提供前端与后端 /api/drift/* 的对接
 */
import api from './client'

// ============ 类型定义 ============

export interface ReferenceCreateResponse {
  id: number
  name: string
  model_id: number | null
  feature_names: string[]
  row_count: number
  feature_stats: Record<string, FeatureStat>
  created_at: string
}

export interface FeatureStat {
  mean: number
  std: number
  q25: number
  q50: number
  q75: number
  min: number
  max: number
}

export interface KSFeatureDetail {
  stat: number
  pvalue: number
  drifted: boolean
}

export interface DriftCheckResponse {
  check_id: string
  reference_id: number
  model_id: number | null
  recorded_at: string
  row_count: number
  psi_overall: number
  psi_features: Record<string, number>
  ks_features: Record<string, KSFeatureDetail>
  drift_level: 'none' | 'mild' | 'moderate' | 'severe' | 'undefined'
  alerted: boolean
  alert_rule_id: number | null
  warnings: string[]
}

export interface TopFeatureItem {
  feature: string
  psi: number
  ks_stat: number
  ks_pvalue: number
  recommendation: string
}

export interface DriftReportResponse {
  model_id: number
  report_time: string
  period_days: number
  total_checks: number
  drift_level: string
  psi_current: number
  psi_top_features: TopFeatureItem[]
  ks_drifted_features: string[]
  recommendations: string[]
  drift_history_summary: Record<string, number>
}

export interface TrendDataPoint {
  timestamp: string
  psi_overall: number
  psi_features: Record<string, number>
}

export interface DriftTrendResponse {
  model_id: number
  metric: string
  days: number
  data: TrendDataPoint[]
}

export interface DriftAlertResponse {
  id: number
  name: string
  model_id: number | null
  metric: string
  threshold: number
  webhook_url: string
  enabled: boolean
  created_at: string
}

export interface DriftAlertListResponse {
  total: number
  alerts: DriftAlertResponse[]
}

export interface DriftAlertCreate {
  name: string
  model_id?: number
  metric?: string
  threshold?: number
  webhook_url: string
}

// ============ API 方法 ============

export const driftApi = {
  /**
   * 上传基准数据集
   */
  createReference: (formData: FormData) =>
    api.postFormData<ReferenceCreateResponse>('/drift/reference', formData),

  /**
   * 获取基准数据集详情
   */
  getReference: (refId: number) =>
    api.get<ReferenceCreateResponse>(`/drift/reference/${refId}`),

  /**
   * 提交漂移检测
   */
  checkDrift: (formData: FormData) =>
    api.postFormData<DriftCheckResponse>('/drift/check', formData),

  /**
   * 获取漂移报告
   */
  getReport: (modelId: number, params?: { days?: number; format?: string }) =>
    api.get<DriftReportResponse>(`/drift/report/${modelId}`, { params }),

  /**
   * 获取漂移趋势
   */
  getTrend: (modelId: number, params?: { days?: number; metric?: string }) =>
    api.get<DriftTrendResponse>(`/drift/trend/${modelId}`, { params }),

  /**
   * 创建告警规则
   */
  createAlert: (data: DriftAlertCreate) =>
    api.post<DriftAlertResponse>('/drift/alerts', data),

  /**
   * 查询告警规则
   */
  listAlerts: (params?: { model_id?: number; enabled?: boolean }) =>
    api.get<DriftAlertListResponse>('/drift/alerts', { params }),

  /**
   * 更新告警规则
   */
  updateAlert: (ruleId: number, data: Partial<DriftAlertCreate>) =>
    api.patch<DriftAlertResponse>(`/drift/alerts/${ruleId}`, data),
}
