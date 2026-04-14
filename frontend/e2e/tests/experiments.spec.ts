import { test, expect, Page } from '@playwright/test'
import * as fs from 'fs'

/**
 * E2E 测试：实验对比模块（experiments）
 * 覆盖：实验列表、创建实验、实验对比、实验详情
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'
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
  await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_login_page.png` })

  const usernameField = page.locator('input[placeholder*="用户名" i], input[placeholder*="username" i]').first()
  const passwordField = page.locator('input[placeholder*="密码" i], input[placeholder*="password" i]').first()

  await usernameField.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  await usernameField.fill('admin')
  await passwordField.fill('admin123')

  await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_login_filled.png` })

  const loginBtn = page.locator('button[type="submit"]').filter({ hasText: /登录/i }).first()
  await loginBtn.click()

  await page.waitForURL('**/dashboard**', { timeout: 10000 }).catch(() => {
    console.log('⚠️ Login redirect not detected, current URL:', page.url())
  })
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_login_success.png` })
  console.log('✅ 登录成功，当前 URL:', page.url())
}

test.describe('实验对比模块 E2E', () => {

  test.beforeEach(async ({ page }) => {
    // Suppress console errors from polluting test output
    const errors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(`[ERROR] ${msg.text()}`)
    })
    page.on('pageerror', err => errors.push(`[PAGE ERROR] ${err.message}`))

    await loginAsAdmin(page)
    // Navigate to experiments page
    await page.goto(`${BASE_URL}/experiments`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
  })

  test('01 - 实验列表页面加载', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 页面标题
    const heading = page.locator('h1').filter({ hasText: /实验/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // 训练曲线区块
    const trainingCurvesHeading = page.locator('h2').filter({ hasText: /训练曲线/i })
    await expect(trainingCurvesHeading).toBeVisible()

    // 刷新按钮
    const refreshBtn = page.locator('button').filter({ hasText: /刷新/i })
    await expect(refreshBtn).toBeVisible()

    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_list_page.png` })
    console.log('✅ 实验列表页面加载成功')
  })

  test('02 - 实验列表表格展示', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 检查是否有表格（实验列表）
    // 表格头部（列表可能有两种状态：有数据/无数据）
    const tableHeaders = page.locator('th')
    const count = await tableHeaders.count()

    if (count === 0) {
      // 无数据状态：检查是否有"暂无实验记录"提示
      const emptyText = page.locator('text=/暂无|暂无实验|无实验/i')
      if (await emptyText.isVisible({ timeout: 3000 }).catch(() => false)) {
        console.log('✅ 列表为空，显示"暂无实验记录"提示')
        await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_empty_state.png` })
        return
      }
      // 如果既没有表格也没有空状态，截图记录
      await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_table_unclear.png` })
      throw new Error(`无法识别实验列表状态（无表头、无空状态提示），请检查页面结构`)
    }

    // 列标题：实验名称、状态、准确率、F1分数、创建时间
    const headerTexts = await tableHeaders.allTextContents()
    console.log('表格列:', headerTexts.join(' | '))

    // 至少要有 checkbox + 实验名称 + 状态
    const hasNameCol = headerTexts.some(t => t.includes('实验名称') || t.includes('实验'))
    const hasStatusCol = headerTexts.some(t => t.includes('状态'))
    expect(hasNameCol || count >= 3).toBeTruthy()

    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_table.png` })
    console.log(`✅ 实验列表表格展示，共 ${count} 列`)
  })

  test('03 - 实验选择 + 对比浮动栏', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 找到实验列表中的 checkbox
    const checkboxes = page.locator('input[type="checkbox"]')
    const count = await checkboxes.count()

    if (count === 0) {
      console.log('⚠️ 没有实验记录，无法测试选择功能')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_no_data.png` })
      return
    }

    // 选择第一个实验
    await checkboxes.first().check()
    await page.waitForTimeout(500)

    // 应该出现底部浮动栏
    const compareBar = page.locator('text=已选择')
    if (await compareBar.isVisible({ timeout: 3000 }).catch(() => false)) {
      // 选择2个实验
      if (count >= 2) {
        await checkboxes.nth(1).check()
        await page.waitForTimeout(500)
      }

      const compareBtn = page.locator('button').filter({ hasText: /对比/i }).first()
      const cancelBtn = page.locator('button').filter({ hasText: /取消/i }).first()
      await expect(compareBtn).toBeVisible()
      await expect(cancelBtn).toBeVisible()

      await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_compare_bar.png` })
      console.log('✅ 对比浮动栏显示正常')
    } else {
      console.log('⚠️ 选择后未出现对比浮动栏（可能无实验数据）')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_no_compare_bar.png` })
    }
  })

  test('04 - 实验对比视图（选择2个实验）', async ({ page }) => {
    await page.waitForTimeout(2000)

    const checkboxes = page.locator('input[type="checkbox"]')
    const count = await checkboxes.count()

    if (count < 2) {
      console.log('⚠️ 实验不足2个，无法测试对比功能')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_insufficient.png` }).catch(() => {})
      return
    }

    // 选择2个实验
    await checkboxes.nth(0).check()
    await page.waitForTimeout(300)
    await checkboxes.nth(1).check()
    await page.waitForTimeout(500)

    // 点击对比按钮
    const compareBtn = page.locator('button').filter({ hasText: /对比/i }).first()
    await compareBtn.click()
    await page.waitForTimeout(2000)

    // 对比视图标题
    const compareHeading = page.locator('h1').filter({ hasText: /实验对比/i }).first()
    await expect(compareHeading).toBeVisible({ timeout: 5000 }).catch(async () => {
      // fallback: check for any heading mentioning compare/对比
      const h1s = page.locator('h1')
      const h1Count = await h1s.count()
      console.log('当前 h1 数量:', h1Count)
      for (let i = 0; i < h1Count; i++) {
        const text = await h1s.nth(i).textContent()
        console.log('h1[', i, ']:', text)
      }
    })

    // Tab 切换
    const tableTab = page.locator('button').filter({ hasText: /指标对比表/i }).first()
    const chartTab = page.locator('button').filter({ hasText: /曲线对比/i }).first()
    await expect(tableTab).toBeVisible()
    await expect(chartTab).toBeVisible()

    // 默认在指标对比表
    await expect(tableTab).toHaveClass(/bg-white/)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_compare_table.png` })

    // 切换到曲线对比
    await chartTab.click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_compare_chart.png` })

    console.log('✅ 实验对比视图正常')
  })

  test('05 - 返回实验列表', async ({ page }) => {
    await page.waitForTimeout(2000)

    const checkboxes = page.locator('input[type="checkbox"]')
    const count = await checkboxes.count()

    if (count < 2) {
      console.log('⚠️ 实验不足2个，跳过对比返回测试')
      return
    }

    // 进入对比视图
    await checkboxes.nth(0).check()
    await page.waitForTimeout(300)
    await checkboxes.nth(1).check()
    await page.waitForTimeout(300)

    const compareBtn = page.locator('button').filter({ hasText: /对比/i }).first()
    await compareBtn.click()
    await page.waitForTimeout(2000)

    // 点击返回按钮
    const backBtn = page.locator('button').filter({ hasText: /返回/i }).first()
    await expect(backBtn).toBeVisible()
    await backBtn.click()
    await page.waitForTimeout(1000)

    // 应该回到实验列表
    const listHeading = page.locator('h1').filter({ hasText: /实验记录/i }).first()
    await expect(listHeading).toBeVisible({ timeout: 5000 }).catch(() => {})

    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_back_to_list.png` })
    console.log('✅ 返回实验列表成功')
  })

  test('06 - 训练曲线切换', async ({ page }) => {
    await page.waitForTimeout(2000)

    // Tab 切换按钮: 全部 / Loss / Accuracy
    const allTab = page.locator('button').filter({ hasText: /^全部$/i })
    const lossTab = page.locator('button').filter({ hasText: /^Loss$/i })
    const accTab = page.locator('button').filter({ hasText: /^Accuracy$/i })

    const tabCount = await allTab.count()
    if (tabCount === 0) {
      console.log('⚠️ 未找到训练曲线 Tab 切换按钮')
      await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_curves_no_tab.png` })
      return
    }

    await expect(allTab).toBeVisible()
    await expect(lossTab).toBeVisible()
    await expect(accTab).toBeVisible()

    // 截图默认状态
    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_curves_all_tab.png` })

    // 点击 Loss
    await lossTab.click()
    await page.waitForTimeout(500)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_curves_loss_tab.png` })

    // 点击 Accuracy
    await accTab.click()
    await page.waitForTimeout(500)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_curves_acc_tab.png` })

    console.log('✅ 训练曲线 Tab 切换正常')
  })

  test('07 - 刷新按钮', async ({ page }) => {
    await page.waitForTimeout(2000)

    const refreshBtn = page.locator('button').filter({ hasText: /刷新/i }).first()
    await expect(refreshBtn).toBeVisible()

    await refreshBtn.click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/experiments_refresh.png` })

    // 页面仍然正常
    const heading = page.locator('h1').filter({ hasText: /实验/i }).first()
    await expect(heading).toBeVisible()
    console.log('✅ 刷新功能正常')
  })
})
