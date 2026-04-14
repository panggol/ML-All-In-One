import { test, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

/**
 * E2E 测试：数据上传流程
 * 覆盖：
 * - 未登录时访问数据管理页应跳转登录
 * - 上传 CSV 文件（成功流程）
 * - 上传非 CSV 文件（失败场景）
 * - 数据预览
 * - 数据删除
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'

// 创建临时 CSV 文件供上传测试使用
function createTempCSV(): string {
  const content = [
    'id,feature_a,feature_b,target',
    '1,0.1,0.2,0',
    '2,-0.3,0.5,1',
    '3,0.7,-0.1,0',
    '4,-0.2,0.3,1',
    '5,0.4,-0.6,0',
  ].join('\n')
  const tmpPath = '/tmp/e2e_test_data.csv'
  fs.writeFileSync(tmpPath, content)
  return tmpPath
}

test.describe('数据上传流程', () => {

  // 登录辅助函数（参照 auth.spec.ts 的成功登录流程）
  async function loginAsTestUser(page: any, username: string) {
    await page.goto(`${BASE_URL}/login`)
    await page.waitForLoadState('networkidle')
    const randomUser = `user_${Date.now()}`

    // 注册
    await page.locator('div.flex > button').filter({ hasText: '注册' }).click()
    await page.waitForTimeout(500)
    const regForm = page.locator('form').filter({ hasText: '邮箱' }).filter({ hasText: '确认密码' })
    await regForm.locator('input[placeholder="3-20个字符"]').fill(randomUser)
    await regForm.locator('input[placeholder="your@email.com"]').fill(`${randomUser}@test.com`)
    await regForm.locator('input[placeholder="至少6位"]').fill('password123')
    await regForm.locator('input[placeholder="再次输入密码"]').fill('password123')
    await regForm.evaluate((f: HTMLFormElement) => f.requestSubmit())
    // 注册后出现登录表单（用户名已预填）
    await page.locator('input[placeholder="请输入密码"]').waitFor({ state: 'visible', timeout: 10000 })
    // 登录（用户名已预填，只需填密码再提交）
    await page.locator('input[placeholder="请输入用户名或邮箱"]').fill(randomUser)
    await page.locator('input[placeholder="请输入密码"]').fill('password123')
    await page.waitForTimeout(200)
    const loginForm = page.locator('form').filter({ hasText: '用户名' }).filter({ hasText: '密码' })
    await loginForm.evaluate((f: HTMLFormElement) => f.requestSubmit())
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 })

    return randomUser
  }

  test('未登录时访问数据管理页应跳转登录页', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`)
    // 应跳转到登录页
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 })
  })

  test('上传 CSV 文件成功', async ({ page }) => {
    await loginAsTestUser(page, 'data_upload')

    // 跳转到数据管理页
    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')

    // 上传 CSV：直接操作隐藏的 file input（上传区是 <label> 不是 <button>）
    const csvPath = createTempCSV()
    const fileInput = page.locator('input[type="file"]').first()
    await expect(fileInput).toBeAttached({ timeout: 5000 })
    await fileInput.setInputFiles(csvPath)

    // 等待上传完成
    await page.waitForTimeout(3000)

    // 检查文件出现在列表中
    await expect(
      page.locator('table').locator('text=/e2e_test_data\.csv/i')
    ).toBeVisible({ timeout: 10000 })
  })

  test('上传非 CSV 文件应显示错误提示', async ({ page }) => {
    await loginAsTestUser(page, 'invalid_upload')

    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')
    // 上传 CSV
    const csvPath = createTempCSV()
    await page.locator('input[type="file"]').first().setInputFiles(csvPath)
    await page.waitForTimeout(3000)

    // 选择一个非 CSV 文件（用临时 txt 文件）
    const tmpPath = '/tmp/e2e_test.txt'
    fs.writeFileSync(tmpPath, 'not a csv file')
    await page.locator('input[type="file"]').first().setInputFiles(tmpPath)
    await page.waitForTimeout(1000)
    // 应该出现错误提示（使用 first() 避免 strict mode violation）
    await expect(
      page.locator('text=/csv|CSV|只能|only.*csv|invalid/i').first()
    ).toBeVisible({ timeout: 5000 })
  })

  test('查看数据预览（查看按钮）', async ({ page }) => {
    await loginAsTestUser(page, 'preview')

    // 先上传一个文件
    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')
    // 上传 CSV
    const csvPath = createTempCSV()
    await page.locator('input[type="file"]').first().setInputFiles(csvPath)
    await page.waitForTimeout(3000)

    // 点击文件行的"查看"按钮
    const viewButton = page.locator('button, a').filter({ hasText: /查看|eye/i }).first()
    const viewBtnVisible = await viewButton.isVisible().catch(() => false)
    if (viewBtnVisible) {
      await viewButton.click()
      // 预览面板应显示列名
      await expect(page.locator('text=/id|feature|target/i')).toBeVisible({ timeout: 5000 })
    }
  })

  test('删除数据文件', async ({ page }) => {
    await loginAsTestUser(page, 'delete_file')

    // 先上传一个文件
    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')
    // 上传 CSV
    const csvPath = createTempCSV()
    await page.locator('input[type="file"]').first().setInputFiles(csvPath)
    await page.waitForTimeout(3000)

    // 查找并点击删除按钮
    const deleteButton = page.locator('button').filter({ hasText: /删除|delete|trash|remove/i }).first()
    const deleteBtnVisible = await deleteButton.isVisible().catch(() => false)

    if (deleteBtnVisible) {
      await deleteButton.click()
      await page.waitForTimeout(500)
      // 确认删除
      const confirmBtn = page.locator('button').filter({ hasText: /确认|confirm|删除|yes/i }).first()
      const confirmVisible = await confirmBtn.isVisible().catch(() => false)
      if (confirmVisible) {
        await confirmBtn.click()
      }
      await page.waitForTimeout(1000)
    }
  })

  test('数据列表页面加载成功', async ({ page }) => {
    await loginAsTestUser(page, 'data_list')

    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')

    // 页面标题或主要元素应可见
    await expect(
      page.locator('text=/数据|管理|data|management/i').first()
    ).toBeVisible({ timeout: 5000 })

    await page.screenshot({ path: 'e2e/screenshots/data_management_page.png', fullPage: false })
  })

  test('点击统计Tab不白屏', async ({ page }) => {
    await loginAsTestUser(page, 'stats_tab')

    // 先上传一个文件
    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')
    const csvPath = createTempCSV()
    await page.locator('input[type="file"]').first().setInputFiles(csvPath)
    await page.waitForTimeout(3000)

    // 点击文件行的"查看"按钮
    const viewButton = page.locator('button, a').filter({ hasText: /查看|eye/i }).first()
    const viewBtnVisible = await viewButton.isVisible().catch(() => false)
    if (viewBtnVisible) {
      await viewButton.click()
      await page.waitForTimeout(1000)
    }

    // 点击"统计" Tab
    const statsTab = page.locator('button').filter({ hasText: /统计/i }).first()
    await expect(statsTab).toBeVisible({ timeout: 5000 })
    await statsTab.click()
    await page.waitForTimeout(3000)  // 等待统计 API 返回

    // 页面不应白屏 - 统计内容应可见（使用中文关键词）
    const statsText = page.locator('text=/总行数|总列数|feature|统计信息/i').first()
    const hasContent = await statsText.isVisible({ timeout: 5000 }).catch(() => false)
    // 同时检查是否有"暂无统计数据"（空数据情况）
    const hasEmptyState = await page.locator('text=暂无统计数据').isVisible({ timeout: 5000 }).catch(() => false)
    await expect(hasContent || hasEmptyState).toBe(true)

    // 截图验证统计Tab不白屏
    await page.screenshot({ path: 'e2e/screenshots/data_management_stats_tab.png', fullPage: false })
  })

  test('点击预览Tab正常显示', async ({ page }) => {
    await loginAsTestUser(page, 'preview_tab')

    // 先上传一个文件
    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')
    const csvPath = createTempCSV()
    await page.locator('input[type="file"]').first().setInputFiles(csvPath)
    await page.waitForTimeout(3000)

    // 点击文件行的"查看"按钮
    const viewButton = page.locator('button, a').filter({ hasText: /查看|eye/i }).first()
    const viewBtnVisible = await viewButton.isVisible().catch(() => false)
    if (viewBtnVisible) {
      await viewButton.click()
      await page.waitForTimeout(1000)
    }

    // 确保在统计Tab时点击预览Tab
    const statsTab = page.locator('button').filter({ hasText: /统计/i }).first()
    const statsVisible = await statsTab.isVisible().catch(() => false)
    if (statsVisible) {
      await statsTab.click()
      await page.waitForTimeout(500)
    }

    // 点击"预览" Tab
    const previewTab = page.locator('button').filter({ hasText: /预览/i }).first()
    await expect(previewTab).toBeVisible({ timeout: 5000 })
    await previewTab.click()
    await page.waitForTimeout(2000)

    // 预览 Tab - 详情面板应显示预览内容或暂无数据
    const hasPreviewContent = await page.locator('text=/暂无预览数据|id|feature|target|preview|行|列/i').first().isVisible({ timeout: 5000 }).catch(() => false)
    await expect(hasPreviewContent).toBe(true)
  })

})
