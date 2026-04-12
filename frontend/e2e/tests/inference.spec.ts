import { test, expect, Page } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const ADMIN_USER = 'admin'
const ADMIN_PASS = 'admin123'
const MODEL_NAME = 'RandomForestRegressor_job_23'

// ============================================================
// 辅助函数：登录
// ============================================================
async function doLogin(page: Page) {
  await page.goto(`${BASE_URL}/auth`)
  await page.waitForLoadState('networkidle')

  const usernameInput = page.locator('input[placeholder="请输入用户名或邮箱"]')
  const passwordInput = page.locator('input[placeholder="请输入密码"]')

  await usernameInput.waitFor({ state: 'visible', timeout: 8000 })
  await usernameInput.fill(ADMIN_USER)
  await page.waitForTimeout(300)
  await passwordInput.fill(ADMIN_PASS)
  await page.waitForTimeout(300)

  // 找到登录表单并提交
  const loginForm = page.locator('form').filter({ hasText: '用户名' }).filter({ hasText: '密码' })
  await loginForm.evaluate((f: HTMLFormElement) => f.requestSubmit())

  await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 })
}

// ============================================================
// 辅助函数：导航到推理页面
// ============================================================
async function goToInference(page: Page) {
  await page.goto(`${BASE_URL}/inference`)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)
}

// ============================================================
// 辅助函数：截图并保存
// ============================================================
async function screenshot(page: Page, name: string) {
  await page.screenshot({ path: `e2e/screenshots/inference_${name}.png`, fullPage: false })
  console.log(`📸 Screenshot: e2e/screenshots/inference_${name}.png`)
}

// ============================================================
// 测试用例
// ============================================================
test.describe('推理模块 E2E', () => {

  test.beforeEach(async ({ page }) => {
    // 登录
    await doLogin(page)
    // 导航到推理页面
    await goToInference(page)
  })

  // --- 场景1：推理页面加载 + 模型选择 ---
  test('推理页面加载 + 模型选择', async ({ page }) => {
    await screenshot(page, 'page_loaded')

    // 验证页面标题
    await expect(page.locator('h1').filter({ hasText: '模型推理' })).toBeVisible()

    // 验证有模型可选（包含我们的测试模型）
    const modelCard = page.locator('text=' + MODEL_NAME).first()
    await expect(modelCard).toBeVisible({ timeout: 10000 })
    await screenshot(page, 'models_visible')

    // 点击选择模型
    await modelCard.click()
    await page.waitForTimeout(1000)
    await screenshot(page, 'model_selected')

    // 验证模型详情显示（已选择提示里有模型名）
    await expect(page.getByText(MODEL_NAME, { exact: true })).toBeVisible()
  })

  // --- 场景2：JSON 模式推理 ---
  test('JSON 模式推理成功', async ({ page }) => {
    // 选择模型
    const modelCard = page.locator('text=' + MODEL_NAME).first()
    await modelCard.waitFor({ state: 'visible', timeout: 10000 })
    await modelCard.click()
    await page.waitForTimeout(1000)
    await screenshot(page, 'json_mode_before')

    // 确认当前是 JSON 模式（默认模式）
    const jsonTab = page.locator('button', { hasText: 'JSON' }).first()
    await expect(jsonTab).toBeVisible()

    // 切换到 JSON 模式（如果当前不是）
    const currentMode = await jsonTab.getAttribute('class')
    const isActive = currentMode?.includes('border-primary')
    console.log('JSON tab active:', isActive)

    // 输入 JSON 数据（与训练数据特征一致：feature_a, feature_b, feature_c, feature_d）
    const jsonTextarea = page.locator('textarea').first()
    await jsonTextarea.waitFor({ state: 'visible', timeout: 5000 })
    await jsonTextarea.fill(
      `[
  {"feature_a": 1.0, "feature_b": 2.5, "feature_c": 3.0, "feature_d": 4.1},
  {"feature_a": 0.5, "feature_b": 3.1, "feature_c": 2.0, "feature_d": 5.2},
  {"feature_a": 2.3, "feature_b": 1.0, "feature_c": 1.5, "feature_d": 3.3}
]`
    )
    await page.waitForTimeout(500)
    await screenshot(page, 'json_input_filled')

    // 点击"开始推理"按钮
    const runBtn = page.locator('button', { hasText: '开始推理' }).first()
    await expect(runBtn).toBeEnabled()
    await runBtn.click()
    await page.waitForTimeout(3000) // 等待推理完成
    await screenshot(page, 'json_inference_done')

    // 验证结果区域出现
    const resultsHeader = page.locator('h2', { hasText: '推理结果' })
    await expect(resultsHeader).toBeVisible({ timeout: 10000 })

    // 验证有结果数据（表格行）
    const resultRows = page.locator('table tbody tr')
    const count = await resultRows.count()
    console.log('Result rows:', count)
    expect(count).toBeGreaterThan(0)

    await screenshot(page, 'json_results_table')
  })

  // --- 场景3：数据集模式推理 ---
  test('数据集模式推理', async ({ page }) => {
    // 选择模型
    const modelCard = page.locator('text=' + MODEL_NAME).first()
    await modelCard.waitFor({ state: 'visible', timeout: 10000 })
    await modelCard.click()
    await page.waitForTimeout(1000)

    // 切换到"数据集"模式
    const pathTab = page.locator('button', { hasText: '数据集' }).first()
    await pathTab.click()
    await page.waitForTimeout(1000)
    await screenshot(page, 'dataset_mode')

    // 选择第一个数据集
    const fileItem = page.locator('.space-y-2 > div').filter({ hasText: 'e2e_training_data.csv' }).first()
    const fileItemVisible = await fileItem.isVisible().catch(() => false)
    if (fileItemVisible) {
      await fileItem.click()
      await page.waitForTimeout(1000)
      await screenshot(page, 'dataset_selected')

      // 验证已选择提示（数据集已选，有2个已选择文本，取第一个即数据集那个）
      await expect(page.locator('text=已选择: e2e_training_data.csv')).toBeVisible()
    } else {
      console.log('⚠️ No dataset files visible, skipping dataset selection')
    }

    // 点击开始推理
    const runBtn = page.locator('button', { hasText: '开始推理' }).first()
    await expect(runBtn).toBeEnabled()
    await runBtn.click()
    await page.waitForTimeout(3000)
    await screenshot(page, 'dataset_inference_done')

    // 验证结果出现
    const resultsHeader = page.locator('h2', { hasText: '推理结果' })
    await expect(resultsHeader).toBeVisible({ timeout: 10000 })
    await screenshot(page, 'dataset_results')
  })

  // --- 场景4：无模型时的空状态 ---
  test('无模型时的空状态提示', async ({ page }) => {
    // 推理页面在没有登录时会自动跳转，所以先确认页面已加载
    await expect(page.locator('h1').filter({ hasText: '模型推理' })).toBeVisible({ timeout: 5000 })

    // 如果有"暂无训练好的模型"提示，则模型列表为空
    const emptyState = page.locator('text=暂无训练好的模型').first()
    const hasEmptyState = await emptyState.isVisible().catch(() => false)

    if (hasEmptyState) {
      await screenshot(page, 'no_models_empty_state')
      // 推理按钮应该不可用或不存在
      const runBtn = page.locator('button', { hasText: '开始推理' }).first()
      const btnVisible = await runBtn.isVisible().catch(() => false)
      if (btnVisible) {
        await expect(runBtn).toBeDisabled()
      }
    } else {
      // 有模型，正常选择
      const modelCard = page.locator('text=' + MODEL_NAME).first()
      await modelCard.click()
      await page.waitForTimeout(1000)
      await screenshot(page, 'has_models_state')
    }
  })

  // --- 场景5：JSON 输入格式错误 ---
  test('JSON 输入格式错误时显示错误提示', async ({ page }) => {
    // 选择模型
    const modelCard = page.locator('text=' + MODEL_NAME).first()
    await modelCard.waitFor({ state: 'visible', timeout: 10000 })
    await modelCard.click()
    await page.waitForTimeout(1000)

    // 输入错误的 JSON
    const jsonTextarea = page.locator('textarea').first()
    await jsonTextarea.waitFor({ state: 'visible', timeout: 5000 })
    await jsonTextarea.fill('{not valid json at all}')
    await page.waitForTimeout(500)
    await screenshot(page, 'json_error_before')

    // 点击推理按钮
    const runBtn = page.locator('button', { hasText: '开始推理' }).first()
    await runBtn.click()
    await page.waitForTimeout(1000)

    // 验证错误提示出现
    const errorMsg = page.locator('text=/JSON 解析错误|数据格式错误|解析错误/i').first()
    await expect(errorMsg).toBeVisible({ timeout: 5000 })
    await screenshot(page, 'json_error_shown')
  })

  // --- 场景6：下载结果 ---
  test('推理完成后可下载结果 CSV', async ({ page }) => {
    // 选择模型
    const modelCard = page.locator('text=' + MODEL_NAME).first()
    await modelCard.waitFor({ state: 'visible', timeout: 10000 })
    await modelCard.click()
    await page.waitForTimeout(1000)

    // 输入 JSON 数据
    const jsonTextarea = page.locator('textarea').first()
    await jsonTextarea.waitFor({ state: 'visible', timeout: 5000 })
    await jsonTextarea.fill(
      `[{"feature_a": 1.0, "feature_b": 2.5, "feature_c": 3.0, "feature_d": 4.1}]`
    )
    await page.waitForTimeout(300)

    // 执行推理
    const runBtn = page.locator('button', { hasText: '开始推理' }).first()
    await runBtn.click()
    await page.waitForTimeout(3000)

    // 验证结果出现
    const resultsHeader = page.locator('h2', { hasText: '推理结果' })
    await expect(resultsHeader).toBeVisible({ timeout: 10000 })
    await screenshot(page, 'download_ready')

    // 验证"下载结果 CSV"按钮出现
    const downloadBtn = page.locator('button', { hasText: '下载结果 CSV' }).first()
    await expect(downloadBtn).toBeVisible({ timeout: 5000 })
    await screenshot(page, 'download_button_visible')
  })

})
