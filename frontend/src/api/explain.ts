/**
 * api/explain.ts — SHAP 可解释性 API 客户端
 * 对应后端 /api/explain/* 端点
 */

import api from "./client"

// =============================================================================
// 类型定义
// =============================================================================

export interface FeatureImportance {
  feature: string
  importance: number
  rank: number
}

export interface GlobalSHAPResponse {
  feature_names: string[]
  shap_values: number[][]
  expected_value: number
  feature_importance: FeatureImportance[]
  sample_count: number
  computation_time_ms: number
  explainer_type: string
}

export interface FeatureContribution {
  feature: string
  value: number
  original_value: unknown
  direction: "positive" | "negative" | "neutral"
}

export interface LocalSHAPResponse {
  sample: Record<string, unknown>
  shap_values: FeatureContribution[]
  expected_value: number
  model_output: number
  output_class: string | null
  computation_time_ms: number
}

export interface SHAPPlotResponse {
  image_base64: string
  image_type: "beeswarm" | "bar" | "waterfall" | "force"
  width_px: number
  height_px: number
  computation_time_ms: number
}

export interface ICEPoint {
  feature_value: number
  predicted_value: number
}

export interface ICECurve {
  sample_index: number
  points: ICEPoint[]
}

export interface ICEResponse {
  feature_name: string
  feature_values: number[]
  curves: ICECurve[]
  computation_time_ms: number
}

// =============================================================================
// 请求参数
// =============================================================================

export interface GlobalSHAPRequest {
  model_id: number
  sample_size?: number
  background_size?: number
}

export interface LocalSHAPRequest {
  model_id: number
  sample: Record<string, unknown>
}

export interface SHAPPlotRequest {
  model_id: number
  plot_type?: "beeswarm" | "bar" | "waterfall"
  sample_size?: number
  sample?: Record<string, unknown> | null
  max_display?: number
}

export interface ICERequest {
  model_id: number
  feature_name: string
  num_points?: number
  sample_size?: number
}

// =============================================================================
// API 函数
// =============================================================================

export const explainApi = {
  /**
   * 全局 SHAP 解释：计算测试集上所有样本的 SHAP 值
   */
  async global(request: GlobalSHAPRequest): Promise<GlobalSHAPResponse> {
    return api.post<GlobalSHAPResponse>("/explain/shap/global", request).then(r => r.data)
  },

  /**
   * 局部 SHAP 解释：计算单个样本每个特征的 SHAP 贡献值
   */
  async local(request: LocalSHAPRequest): Promise<LocalSHAPResponse> {
    return api.post<LocalSHAPResponse>("/explain/shap/local", request).then(r => r.data)
  },

  /**
   * SHAP 可视化图：生成 base64 编码的 SHAP 图
   * @param plot_type beeswarm（蜂群图，默认）/ bar（柱状图）/ waterfall（瀑布图）
   */
  async plot(request: SHAPPlotRequest): Promise<SHAPPlotResponse> {
    return api.post<SHAPPlotResponse>("/explain/shap/plot", request).then(r => r.data)
  },

  /**
   * ICE 曲线：计算指定特征的 ICE 曲线数据
   */
  async ice(request: ICERequest): Promise<ICEResponse> {
    return api.post<ICEResponse>("/explain/ice", request).then(r => r.data)
  },

  /**
   * 下载 SHAP PDF 报告
   * @param modelId 模型 ID
   * @param sampleSize 样本数量（默认 1000）
   * @param sections 包含章节（默认 summary,global,local,ice）
   */
  downloadReport(
    modelId: number,
    sampleSize: number = 1000,
    sections: string = "summary,global,local,ice"
  ): void {
    const token = localStorage.getItem("token")
    const params = new URLSearchParams({
      sample_size: String(sampleSize),
      include_sections: sections,
    })
    const url = `${api.defaults.baseURL}/explain/report/${modelId}?${params.toString()}`
    const a = document.createElement("a")
    a.href = url
    a.setAttribute("download", `shap_report_model_${modelId}.pdf`)
    if (token) {
      a.setAttribute("Authorization", `Bearer ${token}`)
    }
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  },
}
