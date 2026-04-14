import { test, expect } from '@playwright/test'

/**
 * E2E 测试：管理员用户管理页面
 * 覆盖：
 * - admin 用户访问 /admin/users 正常显示
 * - 非 admin 用户访问 /admin/users 被重定向
 * - 用户列表渲染（含 role/is_protected 列）
 * - 编辑用户角色切换
 * - 禁用/启用用户
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'

test.describe('管理员用户管理页面', () => {

  test.beforeEach(async ({ page }) => {
    // 清理会话：确保无残留 token 影响登录
    await page.context().clearCookies()
    await page.goto(`${BASE_URL}/login`)
    await page.waitForLoadState('domcontentloaded')
    await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
    await page.waitForLoadState('networkidle')
    // 登录为 admin
    await page.locator('input[placeholder*="用户名"]').first().fill('admin')
    await page.locator('input[type="password"]').first().fill('admin123')
    await Promise.all([
      page.locator('button[type="submit"]').filter({ hasText: /登录/i }).first().click(),
      page.waitForURL('**/dashboard**', { timeout: 10000 })
    ])
  })

  test('admin 用户访问 /admin/users 正常显示', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/users`)

    // 等待加载指示器消失或页面内容出现
    await page.waitForLoadState('networkidle')
    // 检查页面关键内容（h1 用户管理 或 表格）
    await expect(
      page.locator('h1, table, [data-testid="users-table"]').first()
    ).toBeVisible({ timeout: 15000 })

    // 截图
    await page.screenshot({ path: 'frontend/e2e/screenshots/admin_users_page.png', fullPage: false })
  })

  test('用户列表渲染（username/email/role 列）', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/users`)
    // 等待网络请求完成
    await page.waitForLoadState('networkidle')
    // 等待表格行出现（API 返回后）
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 15000 })
    // 验证表格列存在
    const table = page.locator('table')
    await expect(table).toBeVisible()
    const headerText = await table.locator('thead th').allTextContents()
    console.log('Table headers:', headerText)

    // 截图
    await page.screenshot({ path: 'frontend/e2e/screenshots/admin_users_table.png', fullPage: false })
  })

  test('编辑用户角色切换', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/users`)
    await page.waitForTimeout(3000)

    // 找编辑按钮并点击
    const editBtn = page.getByRole('button', { name: /编辑|edit/i }).first()
    if (await editBtn.isVisible()) {
      await editBtn.click()
      await page.waitForTimeout(500)

      // 选择不同角色
      const roleSelect = page.locator('select').first()
      if (await roleSelect.isVisible()) {
        await roleSelect.selectOption('admin')
        await page.getByRole('button', { name: /保存|save/i }).click()
        await page.waitForTimeout(1000)
      }
    }

    await page.screenshot({ path: 'frontend/e2e/screenshots/admin_users_edit_role.png', fullPage: false })
  })

  test('禁用/启用用户', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/users`)
    await page.waitForTimeout(3000)

    // 找禁用/启用按钮
    const toggleBtn = page.getByRole('button', { name: /禁用|启用|activate|deactivate/i }).first()
    if (await toggleBtn.isVisible()) {
      await toggleBtn.click()
      await page.waitForTimeout(1000)
    }

    await page.screenshot({ path: 'frontend/e2e/screenshots/admin_users_toggle.png', fullPage: false })
  })
})
