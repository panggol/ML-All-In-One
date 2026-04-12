import { test, expect } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'

test.describe('数据可视化页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/auth`)
    await page.getByPlaceholder('请输入用户名或邮箱').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('admin123')
    await Promise.all([
      page.locator('form').getByRole('button', { name: '登录' }).click(),
      page.waitForURL(`${BASE_URL}/dashboard`, { timeout: 10000 })
    ])
  })

  test('数据可视化 - 页面加载和核心元素检查', async ({ page }) => {
    await page.goto(`${BASE_URL}/visualization`)
    await page.waitForTimeout(3000)
    
    // 验证页面标题存在（main 区域内）
    const title = page.getByRole('main').getByRole('heading', { name: '数据可视化' })
    await expect(title).toBeVisible()
    
    // 验证数据集选择器存在
    const dataSelect = page.getByLabel('数据集')
    await expect(dataSelect).toBeVisible()
    
    // 截图：页面加载
    await page.screenshot({ path: 'e2e/screenshots/data_visualization_page.png', fullPage: false })
  })

  test('数据可视化 - 图表类型切换（下拉框可见性）', async ({ page }) => {
    await page.goto(`${BASE_URL}/visualization`)
    await page.waitForTimeout(3000)
    
    // 截图：初始状态
    await page.screenshot({ path: 'e2e/screenshots/data_visualization_default.png', fullPage: false })
    
    // 图表类型选择器在 distribution tab 中，默认 tab 即为 distribution
    // 类型选择器可见（无需数据文件即可看到下拉框）
    const typeSelect = page.getByLabel('类型')
    await expect(typeSelect).toBeVisible()
    
    // 验证默认值为 histogram
    const selectedOption = await typeSelect.locator('option:checked').textContent()
    expect(selectedOption).toContain('直方图')
    
    // 截图：切换前
    await page.screenshot({ path: 'e2e/screenshots/data_visualization_before_switch.png', fullPage: false })
    
    // 切换到 boxplot
    await typeSelect.selectOption('boxplot')
    await page.waitForTimeout(1000)
    
    // 截图：切换到 boxplot 后
    await page.screenshot({ path: 'e2e/screenshots/data_visualization_boxplot.png', fullPage: false })
    
    // 验证值已切换
    const newSelectedOption = await typeSelect.locator('option:checked').textContent()
    expect(newSelectedOption).toContain('箱线图')
  })
})
