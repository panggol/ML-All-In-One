/**
 * UserModal — 新建/编辑用户 Modal
 */
import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import Button from './Button'
import type { AdminUser, CreateUserRequest, UpdateUserRequest } from '../api/admin'

// ============ 类型 ============

interface UserModalProps {
  /** Modal 是否打开 */
  open: boolean
  /** 模式：create 新建 | edit 编辑 */
  mode: 'create' | 'edit'
  /** 编辑模式时传入目标用户数据 */
  user?: AdminUser | null
  /** 关闭回调 */
  onClose: () => void
  /** 提交回调 */
  onSubmit: (data: CreateUserRequest | UpdateUserRequest) => Promise<void>
  /** API 错误信息 */
  error?: string | null
}

interface FormState {
  username: string
  email: string
  password: string
  role: 'user' | 'admin'
}

interface FormErrors {
  username?: string
  email?: string
  password?: string
  role?: string
}

// ============ 组件 ============

export default function UserModal({
  open,
  mode,
  user,
  onClose,
  onSubmit,
  error,
}: UserModalProps) {
  const [form, setForm] = useState<FormState>({
    username: '',
    email: '',
    password: '',
    role: 'user',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)

  // 编辑模式：预填表单
  useEffect(() => {
    if (open && mode === 'edit' && user) {
      setForm({
        username: user.username,
        email: user.email,
        password: '',
        role: user.role,
      })
    } else if (open && mode === 'create') {
      setForm({ username: '', email: '', password: '', role: 'user' })
    }
    setErrors({})
  }, [open, mode, user])

  // ESC 关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  // ============ 校验 ============
  function validate(): boolean {
    const errs: FormErrors = {}

    if (mode === 'create') {
      if (!form.username.trim()) {
        errs.username = '用户名不能为空'
      } else if (form.username.trim().length < 3) {
        errs.username = '用户名至少 3 个字符'
      }
    }

    if (!form.email.trim()) {
      errs.email = '邮箱不能为空'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      errs.email = '请输入有效的邮箱地址'
    }

    if (mode === 'create') {
      if (!form.password) {
        errs.password = '密码不能为空'
      } else if (form.password.length < 6) {
        errs.password = '密码至少 6 个字符'
      }
    }

    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  // ============ 提交 ============
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    setSubmitting(true)
    try {
      if (mode === 'create') {
        const payload: CreateUserRequest = {
          username: form.username.trim(),
          email: form.email.trim(),
          password: form.password,
          role: form.role,
        }
        await onSubmit(payload)
      } else {
        const payload: UpdateUserRequest = {}
        if (form.email.trim()) payload.email = form.email.trim()
        payload.role = form.role
        // 过滤掉空 password 字段（编辑模式不需要）
        await onSubmit(payload as UpdateUserRequest)
      }
    } finally {
      setSubmitting(false)
    }
  }

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }))
    // 清除对应字段错误
    if (errors[key]) {
      setErrors(prev => ({ ...prev, [key]: undefined }))
    }
  }

  const isProtectedUser = mode === 'edit' && user?.is_protected === true

  return (
    // 遮罩层
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      {/* Modal 主体 */}
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-md"
        onClick={e => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">
            {mode === 'create' ? '新建用户' : `编辑用户 — ${user?.username}`}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 表单 */}
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {/* 错误提示 */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {/* 用户名（仅创建时显示） */}
          {mode === 'create' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                用户名 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.username}
                onChange={e => setField('username', e.target.value)}
                placeholder="输入用户名"
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  errors.username ? 'border-red-500' : 'border-slate-200'
                }`}
                autoFocus
              />
              {errors.username && (
                <p className="mt-1 text-xs text-red-500">{errors.username}</p>
              )}
            </div>
          )}

          {/* 邮箱 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              邮箱 <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              value={form.email}
              onChange={e => setField('email', e.target.value)}
              placeholder="输入邮箱"
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                errors.email ? 'border-red-500' : 'border-slate-200'
              }`}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-500">{errors.email}</p>
            )}
          </div>

          {/* 密码（仅创建时显示） */}
          {mode === 'create' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                密码 <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                value={form.password}
                onChange={e => setField('password', e.target.value)}
                placeholder="至少 6 个字符"
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  errors.password ? 'border-red-500' : 'border-slate-200'
                }`}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-500">{errors.password}</p>
              )}
            </div>
          )}

          {/* 角色 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              角色
            </label>
            {isProtectedUser ? (
              <div>
                <input
                  type="text"
                  value={user?.role === 'admin' ? '管理员' : '普通用户'}
                  readOnly
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-500 cursor-not-allowed"
                />
                <p className="mt-1 text-xs text-amber-600">
                  此为受保护账户，角色不可修改
                </p>
              </div>
            ) : (
              <select
                value={form.role}
                onChange={e => setField('role', e.target.value as 'user' | 'admin')}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
              </select>
            )}
          </div>

          {/* 操作按钮 */}
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="secondary" type="button" onClick={onClose}>
              取消
            </Button>
            <Button variant="primary" type="submit" disabled={submitting}>
              {submitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  {mode === 'create' ? '创建中...' : '保存中...'}
                </>
              ) : (
                mode === 'create' ? '创建' : '保存'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
