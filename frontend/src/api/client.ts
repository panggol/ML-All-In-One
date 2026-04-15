import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：添加 token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：处理 401
// 注意：只有在有 token 的情况下才 redirect（token 过期）。
// 登录失败（无 token 或凭据错误）不应 redirect，由调用方处理错误。
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 只有用户已登录（有 token）时才 redirect
      const token = localStorage.getItem('token')
      if (token) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

// ============ FormData 上传支持 ============

export const apiFormData = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 上传文件需要更长的超时
  headers: {
    // 不设置 Content-Type，让浏览器自动设置 multipart/form-data
  },
})

apiFormData.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiFormData.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const token = localStorage.getItem('token')
      if (token) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// 为 api 对象补充 FormData 方法
;(api as any).postFormData = function <T>(url: string, formData: FormData, params?: Record<string, any>) {
  return apiFormData.post<T>(url, formData, { params })
}

