/**
 * 系统监控模块常量
 * 集中定义所有阈值和配置，避免魔法数字散落在多处
 */

// ============ 使用率阈值 ============
/** 绿色（正常）上限 */
export const THRESHOLD_GREEN_MAX = 60
/** 黄色（警告）上限 */
export const THRESHOLD_YELLOW_MAX = 85
/** 红色（危险）下限 */
export const THRESHOLD_DANGER_MIN = 85

// ============ GPU 温度阈值 ============
/** GPU 温度正常上限 */
export const GPU_TEMP_NORMAL_MAX = 70
/** GPU 温度警告上限 */
export const GPU_TEMP_WARNING_MAX = 80

// ============ 环形缓冲区配置 ============
/** 缓冲区最大数据条数（5 分钟 × 12 条/分钟） */
export const MAX_BUFFER_SIZE = 60
/** 刷新间隔（毫秒） */
export const POLL_INTERVAL_MS = 5000
/** Dashboard 刷新间隔（毫秒，30 秒） */
export const DASHBOARD_POLL_INTERVAL_MS = 30000

// ============ 样式映射 ============
/** 使用率文本颜色 */
export function getUsageColorClass(percent: number): string {
  if (percent >= THRESHOLD_YELLOW_MAX) return 'text-red-600'
  if (percent >= THRESHOLD_GREEN_MAX) return 'text-amber-600'
  return 'text-emerald-600'
}

/** 使用率进度条颜色 */
export function getUsageBarColor(percent: number): string {
  if (percent >= THRESHOLD_YELLOW_MAX) return 'bg-red-500'
  if (percent >= THRESHOLD_GREEN_MAX) return 'bg-amber-500'
  return 'bg-sky-500'
}

/** 使用率渐变色 */
export function getUsageGradient(percent: number): string {
  if (percent >= THRESHOLD_YELLOW_MAX) return 'from-red-500 to-red-400'
  if (percent >= THRESHOLD_GREEN_MAX) return 'from-amber-500 to-amber-400'
  return 'from-sky-500 to-sky-400'
}

/** GPU 利用率条形颜色 */
export function getGpuUtilColor(percent: number): string {
  if (percent >= THRESHOLD_YELLOW_MAX) return 'bg-red-500'
  if (percent >= THRESHOLD_GREEN_MAX) return 'bg-amber-500'
  return 'bg-sky-500'
}

/** GPU 温度颜色 */
export function getGpuTempColor(temp: number): string {
  if (temp >= GPU_TEMP_WARNING_MAX) return 'text-red-600'
  if (temp >= GPU_TEMP_NORMAL_MAX) return 'text-amber-600'
  return 'text-sky-600'
}
