import { test, expect, Page } from '@playwright/test'
import * as fs from 'fs'

/**
 * E2E 测试：任务调度模块（Scheduler）
 * Iteration 2 — 修复 P0 语法错误后补充 E2E 验证
 *
 * 覆盖场景：
 * 1. 访问 /scheduler 页面（应该正常加载，无白屏/崩溃）
 * 2. 验证 Scheduler Tab 在导航栏可见
 * 3. 点击「新建任务」按钮（应该打开 Modal）
 * 4. Cron 表达式输入（应该显示下次执行时间）
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'
const SCREENSHOT_DIR = '/home/gem/workspace/agent/workspace/ml-all-in-one/frontend/e2e/screenshots/scheduler'

function ensureScreenshotDir() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
  }
}

// ============================================================
// 辅助函数：登录（复用 training.spec.ts 的模式）
// ============================================================
async function loginAsAdmin(page: Page) {
  await page.goto(`${BASE_URL}/login`)
  await page.waitForLoadState('networkidle')

  ensureScreenshotDir()

  const usernameInput = page.locator('input[placeholder*="用户名" i], input[placeholder*="username" i]').first()
  const passwordInput = page.locator('input[placeholder*="密码" i], input[placeholder*="password" i]').first()

  const filled = await usernameInput.isVisible().catch(() => false)
  if (!filled) {
    // 可能是已登录状态，跳过
    return
  }

  await usernameInput.fill('admin')
  await passwordInput.fill('admin123')

  const loginBtn = page.locator('button[type="submit"]').filter({ hasText: /登录/i }).first()
  await loginBtn.click()

  // 等待跳转到 dashboard
  await page.waitForURL('**/dashboard**', { timeout: 10000 }).catch(() => {
    console.log('⚠️ 登录后未检测到跳转，当前 URL:', page.url())
  })
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
}

// ============================================================
// 测试用例
// ============================================================
test.describe('Scheduler — 任务调度模块', () => {

  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('P1: 访问 /scheduler 页面（应该正常加载，无崩溃）', async ({ page }) => {
    await page.goto(`${BASE_URL}/scheduler`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_page_load.png` })

    // 页面标题应该可见
    const heading = page.locator('h1').filter({ hasText: '任务调度' })
    await expect(heading).toBeVisible({ timeout: 5000 })

    // 统计栏应该可见（任务总数）
    const statsBar = page.locator('text=任务总数')
    await expect(statsBar).toBeVisible()

    // 表格区域或"暂无定时任务"提示应该可见
    const tableOrEmpty = page.locator('table').or(page.locator('text=暂无定时任务'))
    await expect(tableOrEmpty.first()).toBeVisible({ timeout: 3000 })

    console.log('✅ Scheduler 页面加载正常，无崩溃')
  })

  test('P1: Scheduler Tab 在导航栏可见', async ({ page }) => {
    // 先导航到任意页面使导航栏渲染
    await page.goto(`${BASE_URL}/dashboard`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    ensureScreenshotDir()

    // 查找 Scheduler Tab（Clock 图标 + "任务调度" 文字）
    const schedulerTab = page.locator('button, [role="tab"]').filter({ hasText: '任务调度' })
    await expect(schedulerTab.first()).toBeVisible({ timeout: 5000 })

    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_tab_visible.png` })

    // 点击 Tab 跳转到 Scheduler 页面
    await schedulerTab.first().click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // 验证 URL 变化或页面内容
    const heading = page.locator('h1').filter({ hasText: '任务调度' })
    await expect(heading).toBeVisible({ timeout: 5000 })

    console.log('✅ Scheduler Tab 在导航栏可见且可点击')
  })

  test('P1: 点击「新建任务」按钮应该打开 Modal', async ({ page }) => {
    await page.goto(`${BASE_URL}/scheduler`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_before_modal.png` })

    // 查找「新建任务」按钮
    const createBtn = page.locator('button').filter({ hasText: '新建任务' })
    await createBtn.waitFor({ state: 'visible', timeout: 5000 })
    await createBtn.click()

    // Modal 应该打开
    const modal = page.locator('h2').filter({ hasText: '新建定时任务' })
    await expect(modal).toBeVisible({ timeout: 3000 })

    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_modal_open.png` })

    // 关闭 Modal
    const closeBtn = page.locator('button').filter({ hasText: '取消' }).first()
    await closeBtn.click()
    await expect(modal).not.toBeVisible({ timeout: 3000 })

    console.log('✅ 新建任务 Modal 打开和关闭正常')
  })

  test('P1: CronInput 实时校验 — 输入合法表达式应显示下次执行时间', async ({ page }) => {
    await page.goto(`${BASE_URL}/scheduler`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    ensureScreenshotDir()

    // 打开新建任务 Modal
    const createBtn = page.locator('button').filter({ hasText: '新建任务' })
    await createBtn.click()

    const modalTitle = page.locator('h2').filter({ hasText: '新建定时任务' })
    await modalTitle.waitFor({ state: 'visible', timeout: 5000 })

    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_cron_input_empty.png` })

    // 找到 Cron 输入框（font-mono placeholder）
    const cronInput = page.locator('input[placeholder*="分 时"]')
    await expect(cronInput).toBeVisible({ timeout: 3000 })

    // 输入合法的 Cron 表达式
    await cronInput.clear()
    await cronInput.fill('0 8 * * *')

    // 等待 debounce (300ms) + API 响应
    await page.waitForTimeout(1500)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_cron_valid_next_run.png` })

    // 应该显示"下次执行"文字（绿色文字，包含"下次执行"字样）
    const nextRunLabel = page.locator('text=下次执行').first()
    await expect(nextRunLabel).toBeVisible({ timeout: 5000 })

    console.log('✅ Cron 表达式校验通过，显示下次执行时间')
  })

  test('P1: CronInput 实时校验 — 输入非法表达式应显示错误', async ({ page }) => {
    await page.goto(`${BASE_URL}/scheduler`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    ensureScreenshotDir()

    // 打开新建任务 Modal
    const createBtn = page.locator('button').filter({ hasText: '新建任务' })
    await createBtn.click()
    await page.locator('h2').filter({ hasText: '新建定时任务' }).waitFor({ state: 'visible', timeout: 5000 })

    // 找到 Cron 输入框并输入非法表达式
    const cronInput = page.locator('input[placeholder*="分 时"]')
    await cronInput.clear()
    await cronInput.fill('invalid-cron-expression')

    // 等待 debounce + API 响应
    await page.waitForTimeout(1500)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_cron_invalid.png` })

    // 应该显示错误提示（红色文字）
    const errorLabel = page.locator('text=无效').first()
    await expect(errorLabel).toBeVisible({ timeout: 5000 })

    console.log('✅ 非法 Cron 表达式正确显示错误提示')
  })

  test('P1: CronInput 预设快捷按钮点击后更新输入框值', async ({ page }) => {
    await page.goto(`${BASE_URL}/scheduler`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    ensureScreenshotDir()

    // 打开新建任务 Modal
    const createBtn = page.locator('button').filter({ hasText: '新建任务' })
    await createBtn.click()
    await page.locator('h2').filter({ hasText: '新建定时任务' }).waitFor({ state: 'visible', timeout: 5000 })

    // 点击第一个预设按钮（每天早上 08:00）
    const presetBtn = page.locator('button').filter({ hasText: '每天早上 08:00' })
    await presetBtn.click()

    await page.screenshot({ path: `${SCREENSHOT_DIR}/scheduler_cron_preset_clicked.png` })

    // Cron 输入框值应该更新
    const cronInput = page.locator('input[placeholder*="分 时"]')
    const inputValue = await cronInput.inputValue()
    expect(inputValue).toBe('0 8 * * *')

    // 应该显示下次执行时间（因为预设是合法的）
    const nextRunLabel = page.locator('text=下次执行').first()
    await expect(nextRunLabel).toBeVisible({ timeout: 5000 })

    console.log('✅ Cron 预设快捷按钮正常更新输入框并显示下次执行时间')
  })
})
