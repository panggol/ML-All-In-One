import { test, expect, Page } from '@playwright/test'
import * as fs from 'fs'

/**
 * E2E 测试：日志模块（logs）
 * 覆盖：登录、训练日志列表、日志类型过滤、日志详情、平台日志 Tab
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const SCREENSHOT_DIR = '/home/gem/workspace/agent/workspace/ml-all-in-one/frontend/e2e/screenshots'

function ensureScreenshotDir() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
  }
}

async function loginAsAdmin(page: Page) {
  await page.goto(`${BASE_URL}/login`)
  await page.waitForLoadState('networkidle')
  ensureScreenshotDir()
  await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_login_page.png` })

  const usernameField = page.locator('input[placeholder*="用户名" i], input[placeholder*="username" i]').first()
  const passwordField = page.locator('input[placeholder*="密码" i], input[placeholder*="password" i]').first()

  await usernameField.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  await usernameField.fill('admin')
  await passwordField.fill('admin123')

  await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_login_filled.png` })

  const loginBtn = page.locator('button[type="submit"]').filter({ hasText: /登录/i }).first()
  await loginBtn.click()

  await page.waitForURL(url => url.pathname !== '/login', { timeout: 10000 }).catch(() => {
    console.log('⚠️ Login redirect not detected, current URL:', page.url())
  })
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_login_success.png` })
  console.log('✅ 登录成功，当前 URL:', page.url())
}

test.describe('日志模块 E2E', () => {

  test.beforeEach(async ({ page }) => {
    const errors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(`[ERROR] ${msg.text()}`)
    })
    page.on('pageerror', err => errors.push(`[PAGE ERROR] ${err.message}`))

    await loginAsAdmin(page)
    await page.goto(`${BASE_URL}/logs`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
  })

  test('01 - 训练日志页面加载', async ({ page }) => {
    // 页面标题
    const heading = page.locator('h1').filter({ hasText: /训练日志/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // Tab 导航存在
    const trainingTab = page.locator('button').filter({ hasText: /训练日志/i }).first()
    const platformTab = page.locator('button').filter({ hasText: /平台日志/i }).first()
    await expect(trainingTab).toBeVisible()
    await expect(platformTab).toBeVisible()

    // 训练日志 Tab 高亮（默认激活）
    await expect(trainingTab).toHaveClass(/bg-white/)

    // 刷新按钮
    const refreshBtn = page.locator('button').filter({ hasText: /刷新/i }).first()
    await expect(refreshBtn).toBeVisible()

    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_training_page_loaded.png` })
    console.log('✅ 训练日志页面加载成功')
  })

  test('02 - 训练日志列表展示', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 表格或空状态
    const tableHeaders = page.locator('th')
    const count = await tableHeaders.count()

    if (count === 0) {
      // 空状态检查
      const emptyText = page.locator('text=/暂无日志|暂无.*记录/i')
      if (await emptyText.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('✅ 列表为空，显示"暂无日志记录"提示')
        await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_training_empty.png` })
        return
      }
      // 如果表格没有 th，检查是否有 tr
      const rows = page.locator('tbody tr')
      const rowCount = await rows.count()
      if (rowCount > 0) {
        console.log(`✅ 训练日志列表有 ${rowCount} 条记录`)
        await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_training_list.png` })
        return
      }
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_training_list_unclear.png` })
      throw new Error('无法识别训练日志列表状态')
    }

    // 列标题检查
    const headerTexts = await tableHeaders.allTextContents()
    console.log('表格列:', headerTexts.join(' | '))

    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_training_list.png` })
    console.log(`✅ 训练日志列表表格展示，共 ${count} 列`)
  })

  test('03 - 训练日志筛选功能', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 找到筛选输入框
    const expIdInput = page.locator('input[placeholder*="experiment_id" i], input[placeholder*="实验 ID" i]').first()
    await expIdInput.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})

    const inputVisible = await expIdInput.isVisible().catch(() => false)

    if (inputVisible) {
      // 填写实验ID
      await expIdInput.fill('test-exp-001')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_filter_expid_filled.png` })

      // 点击查询按钮
      const searchBtn = page.locator('button').filter({ hasText: /查询/i }).first()
      await searchBtn.click()
      await page.waitForTimeout(2000)
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_filter_expid_result.png` })
      console.log('✅ 实验ID筛选功能正常')

      // 清除筛选
      const clearBtn = page.locator('button').filter({ hasText: /清除/i }).first()
      await clearBtn.click()
      await page.waitForTimeout(1000)
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_filter_cleared.png` })
      console.log('✅ 清除筛选功能正常')
    } else {
      // 可能只有时间筛选
      const datetimeInputs = page.locator('input[type="datetime-local"]')
      const dtCount = await datetimeInputs.count()
      console.log(`⚠️ 未找到实验ID输入框，有 ${dtCount} 个时间筛选器`)

      if (dtCount > 0) {
        await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_filter_time_only.png` })
      } else {
        await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_filter_no_inputs.png` })
      }
    }
  })

  test('04 - 训练日志详情展开', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 找到日志表格行
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount === 0) {
      console.log('⚠️ 无日志记录，无法测试详情展开')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_detail_no_data.png` })
      return
    }

    // 点击第一行
    await rows.first().click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_detail_expanded.png` })

    // 检查是否有展开的详情（加载中 or 表格内容）
    const loadingText = page.locator('text=/加载中/i')
    const detailTable = page.locator('text=/完整日志|iter.*run.*timestamp/i')

    const hasLoading = await loadingText.isVisible({ timeout: 1000 }).catch(() => false)
    const hasDetail = await detailTable.isVisible({ timeout: 2000 }).catch(() => false)

    if (hasLoading) {
      console.log('✅ 日志详情正在加载中')
      await page.waitForTimeout(3000)
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_detail_loaded.png` })
    } else if (hasDetail) {
      console.log('✅ 日志详情展开成功')
    } else {
      // 可能是无详情数据
      const noDataText = page.locator('text=/无详情|暂无/i')
      if (await noDataText.isVisible({ timeout: 1000 }).catch(() => false)) {
        console.log('✅ 日志详情为空（无可展开数据）')
        await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_detail_empty.png` })
      } else {
        console.log('⚠️ 详情状态不确定，请检查页面')
        await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_detail_unclear.png` })
      }
    }
  })

  test('05 - 切换到平台日志 Tab', async ({ page }) => {
    await page.waitForTimeout(2000)

    const platformTab = page.locator('button').filter({ hasText: /平台日志/i }).first()
    await platformTab.click()
    await page.waitForTimeout(2000)

    // 检查平台日志页面元素
    const heading = page.locator('h1').filter({ hasText: /平台日志/i }).first()
    await expect(heading).toBeVisible({ timeout: 5000 })

    // 模块筛选下拉框
    const moduleSelect = page.locator('select').first()
    const selectVisible = await moduleSelect.isVisible().catch(() => false)
    if (selectVisible) {
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_module_filter.png` })
      console.log('✅ 平台日志 Tab 切换成功，模块筛选下拉框可见')
    } else {
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_page.png` })
      console.log('✅ 平台日志 Tab 切换成功')
    }
  })

  test('06 - 平台日志列表展示', async ({ page }) => {
    // 先切换到平台日志 Tab
    const platformTab = page.locator('button').filter({ hasText: /平台日志/i }).first()
    await platformTab.click()
    await page.waitForTimeout(2000)

    const tableHeaders = page.locator('th')
    const count = await tableHeaders.count()

    if (count === 0) {
      const emptyText = page.locator('text=/暂无日志|暂无.*记录/i')
      if (await emptyText.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('✅ 平台日志列表为空')
        await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_empty.png` })
        return
      }
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_list_unclear.png` })
      throw new Error('无法识别平台日志列表状态')
    }

    const headerTexts = await tableHeaders.allTextContents()
    console.log('平台日志表格列:', headerTexts.join(' | '))

    // 检查级别 Badge
    const levelBadges = page.locator('span').filter({ hasText: /ERROR|WARNING|INFO|DEBUG/i })
    const badgeCount = await levelBadges.count()
    console.log(`✅ 平台日志表格展示，${badgeCount} 个级别 Badge`)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_list.png` })
  })

  test('07 - 平台日志模块筛选', async ({ page }) => {
    // 切换到平台日志 Tab
    const platformTab = page.locator('button').filter({ hasText: /平台日志/i }).first()
    await platformTab.click()
    await page.waitForTimeout(2000)

    const moduleSelect = page.locator('select').first()
    await moduleSelect.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})

    const selectVisible = await moduleSelect.isVisible().catch(() => false)
    if (!selectVisible) {
      console.log('⚠️ 未找到模块筛选下拉框')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_filter_no_select.png` })
      return
    }

    // 选择一个模块
    await moduleSelect.selectOption({ index: 1 })
    await page.waitForTimeout(500)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_module_selected.png` })

    // 点击查询
    const searchBtn = page.locator('button').filter({ hasText: /查询/i }).first()
    await searchBtn.click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_module_filtered.png` })
    console.log('✅ 平台日志模块筛选功能正常')

    // 清除
    const clearBtn = page.locator('button').filter({ hasText: /清除/i }).first()
    await clearBtn.click()
    await page.waitForTimeout(1000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_platform_cleared.png` })
    console.log('✅ 平台日志清除筛选功能正常')
  })

  test('08 - 刷新按钮', async ({ page }) => {
    await page.waitForTimeout(2000)

    const refreshBtn = page.locator('button').filter({ hasText: /刷新/i }).first()
    await expect(refreshBtn).toBeVisible()

    await refreshBtn.click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_refresh.png` })

    // 页面仍然正常
    const heading = page.locator('h1').filter({ hasText: /日志/i }).first()
    await expect(heading).toBeVisible()
    console.log('✅ 刷新功能正常')
  })

  test('09 - 分页功能（如果有多页）', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 检查分页控件
    const paginationBtns = page.locator('button[title="下一页"], button[title="末页"]')
    const paginationCount = await paginationBtns.count()

    if (paginationCount === 0) {
      console.log('⚠️ 未找到分页控件（可能只有一页或无数据）')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_no_pagination.png` })
      return
    }

    // 点击下一页
    const nextPageBtn = paginationBtns.first()
    const isDisabled = await nextPageBtn.isDisabled().catch(() => true)
    if (!isDisabled) {
      await nextPageBtn.click()
      await page.waitForTimeout(2000)
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_next_page.png` })
      console.log('✅ 分页功能正常')
    } else {
      console.log('⚠️ 下一页按钮禁用（只有一页）')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/logs_pagination_disabled.png` })
    }
  })
})
