/**
 * 管理员用户管理 API
 */
import api from './client'

// ============ 类型定义 ============

export interface AdminUser {
  id: number
  username: string
  email: string
  role: 'user' | 'admin'
  is_protected: boolean
  is_active: boolean
  created_at: string
}

export interface UserListResponse {
  total: number
  page: number
  page_size: number
  users: AdminUser[]
}

export interface CreateUserRequest {
  username: string
  email: string
  password: string
  role: 'user' | 'admin'
}

export interface UpdateUserRequest {
  email?: string
  role?: 'user' | 'admin'
  is_active?: boolean
}

// ============ API 实现 ============

export const adminApi = {
  /**
   * 获取用户列表（分页）
   */
  listUsers: async (page = 1, pageSize = 20): Promise<UserListResponse> => {
    const response = await api.get('/admin/users', {
      params: { page, page_size: pageSize },
    })
    return response.data
  },

  /**
   * 创建新用户
   */
  createUser: async (data: CreateUserRequest): Promise<AdminUser> => {
    const response = await api.post('/admin/users', data)
    return response.data
  },

  /**
   * 更新用户信息
   */
  updateUser: async (userId: number, data: UpdateUserRequest): Promise<AdminUser> => {
    const response = await api.put(`/admin/users/${userId}`, data)
    return response.data
  },

  /**
   * 删除用户
   */
  deleteUser: async (userId: number): Promise<void> => {
    await api.delete(`/admin/users/${userId}`)
  },
}
