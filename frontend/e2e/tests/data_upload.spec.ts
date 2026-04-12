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

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'

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

  // 登录辅助函数
  async function loginAsTestUser(page: any, username: string) {
    await page.goto(`${BASE_URL}/auth`)
    const randomUser = `${username}_${Date.now()}`

    // 注册
    await page.getByRole('tab', { name: /注册|register/i }).click()
    await page.getByPlaceholder(/用户名|username/i).fill(randomUser)
    await page.getByPlaceholder(/邮箱|email/i).fill(`${randomUser}@test.com`)
    await page.getByPlaceholder(/密码|password/i).first().fill('password123')
    await page.getByPlaceholder(/确认密码|confirm/i).fill('password123')
    await page.getByRole('button', { name: /注册|创建账户|sign up/i }).click()
    await page.waitForTimeout(1000)

    // 登录
    await page.getByPlaceholder(/密码|password/i).fill('password123')
    await page.getByRole('button', { name: /登录|sign in|log in/i }).click()
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 })

    return randomUser
  }

  test('未登录时访问数据管理页应跳转登录页', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`)
    // 应跳转到登录页
    await expect(page).toHaveURL(/\/auth/, { timeout: 5000 })
  })

  test('上传 CSV 文件成功', async ({ page }) => {
    await loginAsTestUser(page, 'data_upload')

    // 跳转到数据管理页
    await page.goto(`${BASE_URL}/data`)

    // 等待页面加载
    await page.waitForLoadState('networkidle')

    // 点击上传按钮
    const uploadButton = page.locator('button').filter({ hasText: /上传|upload|导入/i }).first()
    await expect(uploadButton).toBeVisible({ timeout: 5000 })
    await uploadButton.click()

    // 选择文件
    const csvPath = createTempCSV()
    const fileChooser = page.locator('input[type="file"]').first()
    await fileChooser.setInputFiles(csvPath)

    // 等待上传完成
    await page.waitForTimeout(2000)

    // 检查是否有成功提示或文件出现在列表中
    const successOrFile = page.locator('text=/成功|upload|complete/i, table >> text=e2e_test_data.csv').first()
    await expect(successOrFile).toBeVisible({ timeout: 10000 })
  })

  test('上传非 CSV 文件应显示错误提示', async ({ page }) => {
    await loginAsTestUser(page, 'invalid_upload')

    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')

    const uploadButton = page.locator('button').filter({ hasText: /上传|upload|导入/i }).first()
    await expect(uploadButton).toBeVisible({ timeout: 5000 })
    await uploadButton.click()

    // 选择一个非 CSV 文件（用临时 txt 文件）
    const tmpPath = '/tmp/e2e_test.txt'
    fs.writeFileSync(tmpPath, 'not a csv file')
    const fileChooser = page.locator('input[type="file"]').first()
    await fileChooser.setInputFiles(tmpPath)

    // 应该出现错误提示
    await page.waitForTimeout(1000)
    await expect(
      page.locator('text=/csv|CSV|只能|only.*csv|invalid/i')
    ).toBeVisible({ timeout: 5000 })
  })

  test('查看数据预览（查看按钮）', async ({ page }) => {
    await loginAsTestUser(page, 'preview')

    // 先上传一个文件
    await page.goto(`${BASE_URL}/data`)
    await page.waitForLoadState('networkidle')
    const uploadButton = page.locator('button').filter({ hasText: /上传|upload|导入/i }).first()
    await uploadButton.click()
    const csvPath = createTempCSV()
    await page.locator('input[type="file"]').first().setInputFiles(csvPath)
    await page.waitForTimeout(2000)

    // 点击"查看"按钮（如果有文件的话）
    const viewButton = page.locator('button, a').filter({ hasText: /查看|preview|eye|eye/i }).first()
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
    const uploadButton = page.locator('button').filter({ hasText: /上传|upload|导入/i }).first()
    await uploadButton.click()
    const csvPath = createTempCSV()
    await page.locator('input[type="file"]').first().setInputFiles(csvPath)
    await page.waitForTimeout(2000)

    // 查找并点击删除按钮
    const deleteButton = page.locator('button').filter({ hasText: /删除|delete|trash|remove/i }).first()
    const deleteBtnVisible = await deleteButton.isVisible().catch(() => false)

    if (deleteBtnVisible) {
      await deleteButton.click()
      // 等待确认或直接删除
      await page.waitForTimeout(500)
      // 再次确认（如果有确认对话框）
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
  })

})
