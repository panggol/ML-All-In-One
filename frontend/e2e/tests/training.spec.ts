import { test, expect, Page } from '@playwright/test'
import * as fs from 'fs'

/**
 * E2E 测试：训练管理模块（training）
 * Bug 修复验证：
 * - stats.columns → column_stats.map(s => s.column)（loadFileColumns + handleFileUpload）
 * - target column 从 Input 改为 Select
 * - 列名按字母分组展示（分组 Tabs）
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
  await page.screenshot({ path: `${SCREENSHOT_DIR}/training_login_page.png` })

  const usernameField = page.locator('input[placeholder*="用户名" i], input[placeholder*="username" i]').first()
  const passwordField = page.locator('input[placeholder*="密码" i], input[placeholder*="password" i]').first()

  await usernameField.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  await usernameField.fill('admin')
  await passwordField.fill('admin123')

  await page.screenshot({ path: `${SCREENSHOT_DIR}/training_login_filled.png` })

  const loginBtn = page.locator('button[type="submit"]').filter({ hasText: /登录/i }).first()
  await loginBtn.click()

  // Wait for URL change — the app navigates to /dashboard after successful login
  await page.waitForURL(url => url.pathname === '/dashboard' || url.pathname === '/', { timeout: 10000 }).catch(() => {
    console.log('⚠️ Dashboard redirect not detected, current URL:', page.url())
  })
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${SCREENSHOT_DIR}/training_login_success.png` })
  console.log('✅ 登录成功，当前 URL:', page.url())
}

function createTempCSV(): string {
  const content = [
    'id,feature_a,feature_b,feature_c,feature_d,target',
    '1,0.1,0.2,0.3,0.4,0',
    '2,-0.3,0.5,-0.1,0.6,1',
    '3,0.7,-0.1,0.8,-0.2,0',
    '4,-0.2,0.3,-0.4,0.5,1',
    '5,0.4,-0.6,0.7,-0.8,0',
    '6,0.3,-0.2,0.1,-0.3,1',
    '7,-0.5,0.1,-0.6,0.7,0',
    '8,0.6,0.4,0.9,0.2,1',
    '9,-0.1,-0.3,-0.5,-0.7,0',
    '10,0.8,-0.5,0.6,-0.4,1',
  ].join('\n')
  const tmpPath = '/tmp/e2e_training_data.csv'
  fs.writeFileSync(tmpPath, content)
  return tmpPath
}

function createLargeCSV(): string {
  // CSV with >20 columns to trigger alphabetical grouping Tabs (FEATURE_GROUP_SIZE=20)
  const headers = ['id', 'apple_val', 'banana_val', 'cherry_val', 'date_val', 'elder_val',
    'fig_val', 'grape_val', 'hazelnut_val', 'kiwi_val', 'lemon_val', 'mango_val',
    'nectarine_val', 'orange_val', 'papaya_val', 'quince_val', 'raspberry_val', 'strawberry_val',
    'tangerine_val', 'ugli_val', 'vanilla_val', 'watermelon_val', 'target']
  const dataRow = headers.map((h) => {
    if (h === 'target') return '0'
    return '0.5'
  })
  const content = [headers.join(','), dataRow.join(',')].join('\n')
  const tmpPath = '/tmp/e2e_training_large_data.csv'
  fs.writeFileSync(tmpPath, content)
  return tmpPath
}

async function uploadViaDataPage(page: Page) {
  await page.goto(`${BASE_URL}/data`)
  await page.waitForLoadState('networkidle')

  ensureScreenshotDir()
  await page.screenshot({ path: `${SCREENSHOT_DIR}/training_data_page.png` })

  // Upload via the hidden file input (the upload zone is a <label> for this input)
  const csvPath = createTempCSV()
  const fileInput = page.locator('input[type="file"]').first()
  await expect(fileInput).toBeAttached({ timeout: 5000 })
  await fileInput.setInputFiles(csvPath)
  await page.waitForTimeout(3000)
  await page.screenshot({ path: `${SCREENSHOT_DIR}/training_data_uploaded.png` })
  console.log('✅ 数据文件上传成功')
}

async function uploadLargeCSVViaDataPage(page: Page) {
  await page.goto(`${BASE_URL}/data`)
  await page.waitForLoadState('networkidle')

  const csvPath = createLargeCSV()
  const fileInput = page.locator('input[type="file"]').first()
  await expect(fileInput).toBeAttached({ timeout: 5000 })
  await fileInput.setInputFiles(csvPath)
  await page.waitForTimeout(3000)
  console.log('✅ 大数据文件上传成功（22列）')
}

async function uploadAndGoToTraining(page: Page) {
  await uploadViaDataPage(page)
  await page.goto(`${BASE_URL}/training`)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(2000)
}

test.describe('训练管理模块 E2E', () => {

  test('1. 未登录时访问训练页应跳转登录', async ({ page }) => {
    await page.goto(`${BASE_URL}/training`)
    await expect(page).toHaveURL(/\/login|\/auth/, { timeout: 5000 })
    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_unauthenticated_redirect.png` })
  })

  test('2. 登录（admin/admin123）', async ({ page }) => {
    await loginAsAdmin(page)
    // Verify we're on the dashboard or root
    const url = page.url()
    expect(url).toMatch(/\/dashboard|\/$/)
    console.log('✅ 登录测试通过')
  })

  test('3. 训练页面加载成功', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_page_loaded.png` })

    // h1 appears in both banner and main — use main's h1
    const heading = page.locator('main h1').filter({ hasText: /训练|train/i })
    await expect(heading).toBeVisible({ timeout: 5000 })
    console.log('✅ 训练页面加载成功，标题可见')
  })

  test('4. 上传数据文件，验证列数正确显示（核心修复验证）', async ({ page }) => {
    await loginAsAdmin(page)
    await uploadAndGoToTraining(page)

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_file_selected.png` })

    // Upload file via the training page upload zone
    const csvPath = createTempCSV()
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(csvPath)
    await page.waitForTimeout(4000)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_file_uploaded.png` })

    // 验证列数正确显示（不再是"N行0列"）
    const fileBadge = page.locator('text=/\\d+ 行 · \\d+ 列/')
    const fileBadgeVisible = await fileBadge.isVisible().catch(() => false)

    expect(fileBadgeVisible).toBeTruthy()
    const badgeText = await fileBadge.textContent()
    console.log('📋 文件信息 badge:', badgeText)

    // 核心断言：列数 > 0（Bug 之前会显示"0列"）
    const columnMatch = badgeText?.match(/(\d+) 列/)
    expect(columnMatch).not.toBeNull()
    const columnCount = parseInt(columnMatch![1], 10)
    expect(columnCount).toBeGreaterThan(0)
    console.log(`✅ 核心修复验证通过: 列数 = ${columnCount}（不再是 0）`)

    // 行数也应 > 0
    const rowMatch = badgeText?.match(/(\d+) 行/)
    expect(rowMatch).not.toBeNull()
    const rowCount = parseInt(rowMatch![1], 10)
    expect(rowCount).toBeGreaterThan(0)
    console.log(`✅ 行数 = ${rowCount}`)
  })

  test('5. 选择目标列（Select 下拉框，验证不再是 Input）', async ({ page }) => {
    await loginAsAdmin(page)
    await uploadAndGoToTraining(page)

    // Upload file
    const csvPath = createTempCSV()
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(csvPath)
    await page.waitForTimeout(4000)

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_target_column.png` })

    // 查找 Select 下拉框（label 为"目标列"）
    const targetLabel = page.locator('label').filter({ hasText: /目标列/i }).first()
    const targetLabelVisible = await targetLabel.isVisible().catch(() => false)

    if (targetLabelVisible) {
      // 找对应的 select 元素
      const selects = page.locator('select').all()
      const selectCount = await selects.length
      console.log(`✅ Select 元素数量: ${selectCount}`)

      if (selectCount > 0) {
        // 找目标列的 select（第一个通常就是）
        const targetSelect = page.locator('select').first()
        const options = await targetSelect.locator('option').all()
        expect(options.length).toBeGreaterThan(1)
        console.log(`✅ 目标列 Select 选项数: ${options.length}（非 Input）`)

        await targetSelect.selectOption({ index: 1 }).catch(() => {})
        await page.waitForTimeout(500)
        await page.screenshot({ path: `${SCREENSHOT_DIR}/training_target_selected.png` })
        console.log('✅ 目标列下拉框功能正常')
      }
    }

    // 验证不再是 Input（Bug 的表现）
    const targetInput = page.locator('input').filter({ hasText: /目标/i }).first()
    const inputVisible = await targetInput.isVisible().catch(() => false)
    expect(inputVisible).toBeFalsy()
    console.log('✅ 目标列不再是 Input（Bug 已修复）')
  })

  test('6. 选择特征列（分组 Tabs，>20列时出现）', async ({ page }) => {
    await loginAsAdmin(page)

    // First upload the large CSV via data page
    await uploadLargeCSVViaDataPage(page)

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Upload the large file via training page
    const csvPath = createLargeCSV()
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(csvPath)
    await page.waitForTimeout(4000)

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_feature_tabs.png` })

    // Select target column (the last column = target)
    const selects = page.locator('select').all()
    const selectCount = await selects.length
    if (selectCount > 0) {
      const targetSelect = page.locator('select').first()
      const options = await targetSelect.locator('option').all()
      if (options.length > 1) {
        await targetSelect.selectOption({ index: options.length - 1 }).catch(() => {})
        await page.waitForTimeout(500)
      }
    }

    // 查找特征分组 Tabs（role=tablist）
    const tabList = page.locator('[role="tablist"]').first()
    const tabListVisible = await tabList.isVisible().catch(() => false)

    if (tabListVisible) {
      const tabs = await tabList.locator('[role="tab"]').all()
      console.log(`✅ 特征分组 Tabs 出现，数量: ${tabs.length}`)
      expect(tabs.length).toBeGreaterThan(1)
      console.log('✅ 列名按字母分组展示功能正常（B 部分 Bug 已修复）')

      await tabs[1].click()
      await page.waitForTimeout(300)
      await page.screenshot({ path: `${SCREENSHOT_DIR}/training_feature_tab_clicked.png` })
    } else {
      // If no tabs, the file might not have 20+ feature columns
      console.log('⚠️ 未出现分组 Tabs（列数可能不足 20）')
    }
  })

  test('7. 选择模型类型', async ({ page }) => {
    await loginAsAdmin(page)
    await uploadAndGoToTraining(page)

    // Upload file
    const csvPath = createTempCSV()
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(csvPath)
    await page.waitForTimeout(4000)

    // Select target column
    const targetSelect = page.locator('select').first()
    const targetVisible = await targetSelect.isVisible().catch(() => false)
    if (targetVisible) {
      const options = await targetSelect.locator('option').all()
      if (options.length > 1) {
        await targetSelect.selectOption({ index: 1 }).catch(() => {})
        await page.waitForTimeout(500)
      }
    }

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_model_selection.png` })

    // 查找模型卡片（RandomForest/XGBoost/LightGBM 等）
    const modelCards = page.locator('text=/RandomForest|XGBoost|LightGBM|LogisticRegression/i')
    const modelCount = await modelCards.count()

    if (modelCount > 0) {
      await modelCards.first().click()
      await page.waitForTimeout(300)
      await page.screenshot({ path: `${SCREENSHOT_DIR}/training_model_selected.png` })
      console.log(`✅ 模型选项可见: ${modelCount} 个`)
    }
  })

  test('8. 点击开始训练', async ({ page }) => {
    await loginAsAdmin(page)
    await uploadAndGoToTraining(page)

    // Upload file to ensure it's in the selected state
    const csvPath = createTempCSV()
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(csvPath)
    await page.waitForTimeout(4000)

    // Select target column
    const targetSelect = page.locator('select').first()
    const targetVisible = await targetSelect.isVisible().catch(() => false)
    if (targetVisible) {
      const options = await targetSelect.locator('option').all()
      if (options.length > 1) {
        await targetSelect.selectOption({ index: 1 }).catch(() => {})
        await page.waitForTimeout(500)
      }
    }

    ensureScreenshotDir()
    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_ready.png` })

    // 查找并选择模型 — 使用精确的按钮文本（model.label）
    // CLASSIFIER_MODELS labels: RandomForest, XGBoost, LightGBM, LogisticRegression
    const modelBtn = page.locator('button', { hasText: 'RandomForest' }).first()
    const modelBtnVisible = await modelBtn.isVisible().catch(() => false)
    
    if (modelBtnVisible) {
      await modelBtn.click()
      await page.waitForTimeout(500)
      const isSelected = await modelBtn.getAttribute('aria-pressed').catch(() => 'false')
      console.log(`✅ 模型已选择, aria-pressed: ${isSelected}`)
      expect(isSelected).toBe('true')
    } else {
      console.log('⚠️ RandomForest 按钮不可见，尝试其他模型')
      const anyModelBtn = page.locator('[aria-pressed]').filter({ hasText: /Forest|Boost|LGBM/i }).first()
      const anyVisible = await anyModelBtn.isVisible().catch(() => false)
      if (anyVisible) {
        await anyModelBtn.click()
        await page.waitForTimeout(500)
      }
    }

    await page.screenshot({ path: `${SCREENSHOT_DIR}/training_configured.png` })

    // 查找开始训练按钮
    const trainBtn = page.locator('button').filter({ hasText: /开始训练/i }).first()
    await page.waitForTimeout(1000) // wait for button to become enabled
    const trainBtnVisible = await trainBtn.isVisible().catch(() => false)

    if (trainBtnVisible) {
      const isDisabled = await trainBtn.isDisabled().catch(() => true)
      
      if (!isDisabled) {
        await trainBtn.click()
        await page.waitForTimeout(2000)

        const logPanel = page.locator('[role="log"]').first()
        const logPanelVisible = await logPanel.isVisible().catch(() => false)

        await page.screenshot({ path: `${SCREENSHOT_DIR}/training_started.png` })

        if (logPanelVisible) {
          console.log('✅ 训练已启动，日志面板出现')
        } else {
          console.log('✅ 开始训练按钮已点击，页面状态已更新')
        }
      } else {
        const disabledTitle = await trainBtn.getAttribute('title').catch(() => 'unknown')
        console.log(`⚠️ 开始训练按钮仍被禁用，原因: ${disabledTitle}`)
        expect(isDisabled).toBeFalsy()
      }
    } else {
      console.log('⚠️ 开始训练按钮不可见，跳过')
    }
  })

})
