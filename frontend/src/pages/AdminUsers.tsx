/**
 * AdminUsers.tsx — 用户管理页面
 * 仅 role="admin" 可访问，提供用户 CRUD 操作界面
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Plus, Edit2, Trash2, ChevronLeft, ChevronRight,
  ShieldX, ShieldCheck, Users, Shield
} from 'lucide-react'
import Card from '../components/Card'
import Button from '../components/Button'
import Badge from '../components/Badge'
import UserModal from '../components/UserModal'
import { adminApi } from '../api/admin'
import type { AdminUser, CreateUserRequest, UpdateUserRequest } from '../api/admin'

// ============ 类型 ============

interface UserModalState {
  open: boolean
  mode: 'create' | 'edit'
  user: AdminUser | null
}

interface DeleteModalState {
  open: boolean
  user: AdminUser | null
}

// ============ 常量 ============

const PAGE_SIZE = 20

// ============ 辅助函数 ============

function formatDate(iso: string): string {
  if (!iso) return '—'
  try {
    return iso.split('T')[0]
  } catch {
    return iso
  }
}

// ============ 组件 ============

export default function AdminUsers() {
  // 用户列表状态
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(PAGE_SIZE)

  // 加载状态
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // 权限状态
  const [currentUserId, setCurrentUserId] = useState<number | null>(null)
  const [isAdmin, setIsAdmin] = useState(true) // 假设当前是admin，通过 localStorage user 获取
  const [permissionChecked, setPermissionChecked] = useState(false)

  // Modal 状态
  const [userModal, setUserModal] = useState<UserModalState>({
    open: false,
    mode: 'create',
    user: null,
  })
  const [deleteModal, setDeleteModal] = useState<DeleteModalState>({
    open: false,
    user: null,
  })

  // 乐观更新状态（用于 toggle 操作）
  const [optimisticUsers, setOptimisticUsers] = useState<Record<number, boolean>>({})

  // 操作错误
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // ============ 初始化：检查当前用户权限 ============
  useEffect(() => {
    const userStr = localStorage.getItem('user')
    if (userStr) {
      try {
        const userData = JSON.parse(userStr)
        setCurrentUserId(userData.id ?? null)
        setIsAdmin(userData.role === 'admin')
      } catch {
        setIsAdmin(false)
      }
    } else {
      setIsAdmin(false)
    }
    setPermissionChecked(true)
  }, [])

  // ============ 加载用户列表 ============
  const loadUsers = useCallback(async (pageNum: number) => {
    setLoading(true)
    setLoadError(null)
    try {
      const res = await adminApi.listUsers(pageNum, PAGE_SIZE)
      setUsers(res.users)
      setTotal(res.total)
      setPage(pageNum)
    } catch (err: any) {
      if (err.response?.status === 403) {
        setLoadError('管理员权限_required')
      } else if (err.response?.status === 401) {
        setLoadError('登录已过期，请重新登录')
      } else {
        setLoadError('加载失败，请重试')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (permissionChecked) {
      loadUsers(1)
    }
  }, [permissionChecked, loadUsers])

  // ============ 分页 ============
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  function goToPage(n: number) {
    if (n < 1 || n > totalPages) return
    loadUsers(n)
  }

  // ============ 统计数字 ============
  const adminCount = users.filter(u => u.role === 'admin').length
  const activeCount = users.filter(u => u.is_active).length

  // ============ 打开 Modal ============
  function openCreateModal() {
    setSubmitError(null)
    setUserModal({ open: true, mode: 'create', user: null })
  }

  function openEditModal(user: AdminUser) {
    setSubmitError(null)
    setUserModal({ open: true, mode: 'edit', user })
  }

  function openDeleteModal(user: AdminUser) {
    setDeleteError(null)
    setDeleteModal({ open: true, user })
  }

  // ============ 新建/编辑提交 ============
  async function handleCreateSubmit(data: CreateUserRequest) {
    try {
      await adminApi.createUser(data)
      setUserModal(prev => ({ ...prev, open: false }))
      loadUsers(1) // 刷新到第一页
    } catch (err: any) {
      const detail = err.response?.data?.detail || '创建失败，请重试'
      setSubmitError(detail)
    }
  }

  async function handleEditSubmit(data: UpdateUserRequest) {
    if (!userModal.user) return
    try {
      await adminApi.updateUser(userModal.user.id, data)
      setUserModal(prev => ({ ...prev, open: false }))
      loadUsers(page)
    } catch (err: any) {
      const detail = err.response?.data?.detail || '保存失败，请重试'
      setSubmitError(detail)
    }
  }

  function handleModalSubmit(data: CreateUserRequest | UpdateUserRequest) {
    if (userModal.mode === 'create') {
      return handleCreateSubmit(data as CreateUserRequest)
    } else {
      return handleEditSubmit(data)
    }
  }

  // ============ 启用/禁用切换 ============
  async function handleToggleActive(user: AdminUser) {
    // 乐观更新
    const newActive = !user.is_active
    setOptimisticUsers(prev => ({ ...prev, [user.id]: newActive }))

    try {
      await adminApi.updateUser(user.id, { is_active: newActive })
      // 更新成功后同步到 users
      setUsers(prev =>
        prev.map(u => (u.id === user.id ? { ...u, is_active: newActive } : u))
      )
    } catch (err: any) {
      // 回滚
      setOptimisticUsers(prev => {
        const next = { ...prev }
        delete next[user.id]
        return next
      })
      const detail = err.response?.data?.detail || '操作失败'
      alert(detail)
    }
  }

  // ============ 删除确认 ============
  async function handleConfirmDelete() {
    if (!deleteModal.user) return
    const userId = deleteModal.user.id

    try {
      await adminApi.deleteUser(userId)
      setDeleteModal({ open: false, user: null })
      loadUsers(page)
    } catch (err: any) {
      const detail = err.response?.data?.detail || '删除失败'
      setDeleteError(detail)
    }
  }

  // ============ 渲染：权限检查 ============
  if (permissionChecked && !isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <ShieldX className="w-16 h-16 text-red-400 mb-4" />
        <h2 className="text-xl font-semibold text-slate-900 mb-2">无权限访问</h2>
        <p className="text-slate-500 mb-6">此页面仅限管理员访问。</p>
        <Button variant="secondary" onClick={() => { window.location.href = '/dashboard' }}>
          返回首页
        </Button>
      </div>
    )
  }

  // ============ 渲染：主界面 ============
  return (
    <div className="space-y-6">
      {/* PageHeader */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">用户管理</h1>
          <p className="text-slate-500 mt-1">管理所有系统用户账户</p>
        </div>
        <Button variant="primary" onClick={openCreateModal}>
          <Plus className="w-4 h-4" />
          新建用户
        </Button>
      </div>

      {/* 统计概览 */}
      <div className="flex items-center gap-8">
        <div className="text-center">
          <div className="text-2xl font-bold text-slate-900">{total}</div>
          <div className="text-xs text-slate-500 mt-0.5">用户总数</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-primary-600">{adminCount}</div>
          <div className="text-xs text-slate-500 mt-0.5">管理员</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-emerald-600">{activeCount}</div>
          <div className="text-xs text-slate-500 mt-0.5">启用中</div>
        </div>
      </div>

      {/* 用户表格 */}
      <Card className="p-0 overflow-hidden">
        {/* 加载状态 */}
        {loading && (
          <div className="p-8 text-center text-slate-400">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm">加载中...</span>
            </div>
          </div>
        )}

        {/* 错误状态 */}
        {!loading && loadError && (
          <div className="p-8 text-center">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-600 text-sm inline-block">
              {loadError}
            </div>
            <div className="mt-4">
              <Button variant="secondary" size="sm" onClick={() => loadUsers(page)}>
                重新加载
              </Button>
            </div>
          </div>
        )}

        {/* 空状态 */}
        {!loading && !loadError && users.length === 0 && (
          <div className="p-12 text-center">
            <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 mb-4">暂无用户</p>
            <Button variant="primary" size="sm" onClick={openCreateModal}>
              新建第一个用户
            </Button>
          </div>
        )}

        {/* 表格 */}
        {!loading && !loadError && users.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white z-10 border-b border-slate-200">
                <tr>
                  <th className="text-xs font-medium text-slate-500 uppercase tracking-wider text-left px-3 py-2">
                    用户名
                  </th>
                  <th className="text-xs font-medium text-slate-500 uppercase tracking-wider text-left px-3 py-2">
                    邮箱
                  </th>
                  <th className="text-xs font-medium text-slate-500 uppercase tracking-wider text-left px-3 py-2 w-24">
                    角色
                  </th>
                  <th className="text-xs font-medium text-slate-500 uppercase tracking-wider text-left px-3 py-2 w-20">
                    保护
                  </th>
                  <th className="text-xs font-medium text-slate-500 uppercase tracking-wider text-left px-3 py-2 w-24">
                    状态
                  </th>
                  <th className="text-xs font-medium text-slate-500 uppercase tracking-wider text-left px-3 py-2 w-36">
                    创建时间
                  </th>
                  <th className="text-xs font-medium text-slate-500 uppercase tracking-wider text-left px-3 py-2 w-36">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => {
                  const optimisticActive = optimisticUsers[user.id] ?? user.is_active
                  const isSelf = user.id === currentUserId
                  const isProtected = user.is_protected

                  return (
                    <tr
                      key={user.id}
                      className={`border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors ${
                        isProtected ? 'border-l-[3px] border-l-amber-400' : ''
                      }`}
                    >
                      {/* 用户名 */}
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-900">{user.username}</span>
                          {isSelf && (
                            <span className="text-xs text-slate-400">(当前账户)</span>
                          )}
                        </div>
                      </td>

                      {/* 邮箱 */}
                      <td className="px-3 py-3 text-slate-600">{user.email}</td>

                      {/* 角色 */}
                      <td className="px-3 py-3">
                        <Badge variant={user.role === 'admin' ? 'info' : 'default'}>
                          {user.role === 'admin' ? (
                            <>
                              <ShieldCheck className="w-3 h-3" />
                              管理员
                            </>
                          ) : (
                            '用户'
                          )}
                        </Badge>
                      </td>

                      {/* 保护 */}
                      <td className="px-3 py-3">
                        {isProtected ? (
                          <Badge variant="warning">
                            <Shield className="w-3 h-3" />
                            受保护
                          </Badge>
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      {/* 状态 */}
                      <td className="px-3 py-3">
                        <Badge variant={optimisticActive ? 'success' : 'error'}>
                          {optimisticActive ? '启用' : '禁用'}
                        </Badge>
                      </td>

                      {/* 创建时间 */}
                      <td className="px-3 py-3 text-slate-500">{formatDate(user.created_at)}</td>

                      {/* 操作按钮 */}
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1">
                          {/* 编辑 */}
                          <button
                            onClick={() => openEditModal(user)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                            title="编辑用户"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>

                          {/* 启用/禁用切换 */}
                          <button
                            onClick={() => handleToggleActive(user)}
                            className={`p-1.5 rounded-lg transition-colors ${
                              optimisticActive
                                ? 'text-emerald-400 hover:text-emerald-600 hover:bg-emerald-50'
                                : 'text-slate-300 hover:text-slate-500 hover:bg-slate-100'
                            }`}
                            title={optimisticActive ? '点击禁用' : '点击启用'}
                          >
                            <div
                              className={`w-2 h-2 rounded-full ${
                                optimisticActive ? 'bg-emerald-400' : 'bg-slate-300'
                              }`}
                            />
                          </button>

                          {/* 删除 */}
                          <button
                            onClick={() => openDeleteModal(user)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                            title={
                              isProtected
                                ? '受保护用户不可删除'
                                : isSelf
                                ? '不能删除自己的账户'
                                : '删除用户'
                            }
                            disabled={isProtected || isSelf}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 分页 */}
      {!loading && !loadError && total > pageSize && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">
            共 {total} 条，第 {page}/{totalPages} 页
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => goToPage(page - 1)}
              disabled={page <= 1}
            >
              <ChevronLeft className="w-4 h-4" />
              上一页
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => goToPage(page + 1)}
              disabled={page >= totalPages}
            >
              下一页
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* 新建/编辑 Modal */}
      <UserModal
        open={userModal.open}
        mode={userModal.mode}
        user={userModal.user}
        onClose={() => setUserModal(prev => ({ ...prev, open: false }))}
        onSubmit={handleModalSubmit}
        error={submitError}
      />

      {/* 删除确认 Modal */}
      {deleteModal.open && (
        <DeleteConfirmModal
          user={deleteModal.user}
          error={deleteError}
          onClose={() => setDeleteModal({ open: false, user: null })}
          onConfirm={handleConfirmDelete}
        />
      )}
    </div>
  )
}

// ============ DeleteConfirmModal（内置） ============

interface DeleteModalProps {
  user: AdminUser | null
  error: string | null
  onClose: () => void
  onConfirm: () => void
}

function DeleteConfirmModal({ user, error, onClose, onConfirm }: DeleteModalProps) {
  const [confirming, setConfirming] = useState(false)
  const isProtected = user?.is_protected ?? false

  async function handleConfirm() {
    setConfirming(true)
    try {
      await onConfirm()
    } finally {
      setConfirming(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-sm"
        onClick={e => e.stopPropagation()}
      >
        {/* 内容 */}
        <div className="px-6 py-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-3">
            {isProtected ? '无法删除' : '确认删除用户'}
          </h2>
          {isProtected ? (
            <p className="text-sm text-slate-600">
              用户「<span className="font-medium">{user?.username}</span>」为受保护账户，无法删除。
            </p>
          ) : (
            <p className="text-sm text-slate-600">
              确定要删除用户「<span className="font-medium">{user?.username}</span>」吗？此操作不可撤销。
            </p>
          )}
          {error && (
            <div className="mt-3 bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          )}
        </div>

        {/* 按钮 */}
        <div className="px-6 pb-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>
            取消
          </Button>
          {isProtected ? (
            <Button variant="secondary" onClick={onClose}>
              知道了
            </Button>
          ) : (
            <Button variant="stop" onClick={handleConfirm} disabled={confirming}>
              {confirming ? '删除中...' : '删除'}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
