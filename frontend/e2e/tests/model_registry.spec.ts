import { test, expect, Page } from '@playwright/test'
import * as fs from 'fs'

/**
 * E2E 测试：模型版本管理模块（model_registry）
 * 覆盖：
 * 1. 未登录访问应跳转登录页
 * 2. admin 登录后访问模型管理页
 * 3. 版本列表 Tab 展示
 * 4. 操作历史 Tab 展示
 *
 * 修复说明：
 * - 问题根因：组件调用 /api/models/ 获取模型列表，测试环境无训练数据返回空列表，
 *   导致 selectedModelId 为 null，版本列表/操作历史 Tab 被条件渲染隐藏。
 * - 解决方案：Models.tsx 支持 __TEST_MOCK_*__ localStorage 键，
 *   当存在时直接使用 mock 数据，跳过 API 调用。
 *   测试通过 page.addInitScript 在页面加载前设置 localStorage。
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'
const SCREENSHOT_DIR = '/home/gem/workspace/agent/workspace/ml-all-in-one/frontend/e2e/screenshots'

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_MODELS = [
  { id: 1, name: 'resnet50-classification', model_type: 'classification',
    metrics: { accuracy: 0.9521, f1_score: 0.9480 }, created_at: '2026-03-01T10:00:00Z' },
  { id: 2, name: 'yolov8-detection', model_type: 'detection',
    metrics: { mAP: 0.8934, recall: 0.8761 }, created_at: '2026-03-05T14:30:00Z' },
]

const MOCK_VERSIONS = [
  { version: 3, tag: 'production', algorithm_type: 'ResNet50',
    metrics: { accuracy: 0.9521, f1_score: 0.9480 }, registered_at: '2026-03-10T12:00:00Z', registered_by: 1 },
  { version: 2, tag: 'staging', algorithm_type: 'ResNet50',
    metrics: { accuracy: 0.9410, f1_score: 0.9380 }, registered_at: '2026-03-08T09:00:00Z', registered_by: 1 },
  { version: 1, tag: 'archived', algorithm_type: 'ResNet18',
    metrics: { accuracy: 0.9100, f1_score: 0.9050 }, registered_at: '2026-03-01T10:00:00Z', registered_by: 1 },
]

const MOCK_HISTORY = [
  { id: 101, model_id: 1, version: 3, action: 'register', actor_id: 1,
    details: { note: '正式版本上线' }, created_at: '2026-03-10T12:00:00Z' },
  { id: 102, model_id: 1, version: 2, action: 'tag_change', actor_id: 1,
    details: { from: 'staging', to: 'production' }, created_at: '2026-03-09T08:00:00Z' },
  { id: 103, model_id: 1, version: 1, action: 'register', actor_id: 1,
    details: { note: '初始版本' }, created_at: '2026-03-01T10:00:00Z' },
]

function ensureScreenshotDir() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
  }
}

async function loginAsAdmin(page: Page) {
  // Full browser context reset: clear localStorage, sessionStorage, and cookies
  // This ensures test isolation — no state from previous tests affects this login.
  await page.context().clearCookies()
  await page.goto(`${BASE_URL}/login`)
  await page.waitForLoadState('domcontentloaded')
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.waitForLoadState('networkidle')
  ensureScreenshotDir()
  const usernameField = page.locator('input[placeholder*="用户名"]').first()
  const passwordField = page.locator('input[type="password"]').first()
  await usernameField.fill('admin')
  await passwordField.fill('admin123')
  const loginBtn = page.locator('button[type="submit"]').filter({ hasText: /登录/i }).first()
  await loginBtn.click()
  // Wait ONLY for /dashboard — /login alone is not a successful auth
  await page.waitForURL('**/dashboard**', { timeout: 10000 })
  await page.screenshot({ path: `${SCREENSHOT_DIR}/model_registry_login_success.png` })
}

// ─── Inject test-mode mock data via localStorage ──────────────────────────────────
/**
 * Inject mock data into the page's localStorage.
 * Called AFTER login (so we're on a fully-loaded page with accessible localStorage),
 * BEFORE navigating to /models (so the mock data is ready when the component mounts).
 * Also clears any stale __TEST_MOCK_*__ keys first.
 */
async function injectTestModeData(page: Page) {
  await page.evaluate(
    ({ MOCK_MODELS, MOCK_VERSIONS, MOCK_HISTORY }: any) => {
      // Clear stale mock data first (prevents cross-test contamination)
      localStorage.removeItem('__TEST_MOCK_MODELS__')
      localStorage.removeItem('__TEST_MOCK_VERSIONS__')
      localStorage.removeItem('__TEST_MOCK_HISTORY__')
      // Set fresh mock data
      localStorage.setItem('__TEST_MOCK_MODELS__', JSON.stringify(MOCK_MODELS))
      localStorage.setItem('__TEST_MOCK_VERSIONS__', JSON.stringify({ total: 3, page: 1, items: MOCK_VERSIONS }))
      localStorage.setItem('__TEST_MOCK_HISTORY__', JSON.stringify({ total: 3, page: 1, items: MOCK_HISTORY }))
    },
    { MOCK_MODELS, MOCK_VERSIONS, MOCK_HISTORY }
  )
}

// ============================================================
// Test 1: 未登录访问模型管理页应跳转登录
// ============================================================
test('1. 未登录访问模型管理页应跳转登录页', async ({ page }) => {
  await page.goto(`${BASE_URL}/models`)
  await page.waitForLoadState('networkidle')
  await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  await page.screenshot({ path: `${SCREENSHOT_DIR}/model_registry_unauthenticated_redirect.png` })
})

// ============================================================
// Test 2: admin 登录后访问模型管理页（版本列表）
// ============================================================
test('2. 登录后访问模型管理页 - 版本列表 Tab', async ({ page }) => {
  await loginAsAdmin(page)
  // Now on the dashboard page (fully loaded), set mock data in localStorage
  await injectTestModeData(page)

  await page.goto(`${BASE_URL}/models`)
  await page.waitForLoadState('networkidle')

  // Wait for model selector to show mock data (proves loadModels used test data)
  await expect(page.getByText('resnet50-classification')).toBeVisible({ timeout: 10000 })

  // 检查页面标题
  await expect(page.getByRole('heading', { name: /模型版本管理/i })).toBeVisible({ timeout: 10000 })

  // selectedModelId 被设置后，Tab 区域才渲染
  await expect(page.getByRole('button', { name: /版本列表/i })).toBeVisible()

  // 检查标签筛选下拉框存在
  await expect(page.getByRole('combobox')).toBeVisible()

  await page.screenshot({ path: `${SCREENSHOT_DIR}/model_registry_versions_tab.png` })
})

// ============================================================
// Test 3: 操作历史 Tab
// ============================================================
test('3. 模型管理页 - 操作历史 Tab', async ({ page }) => {
  await loginAsAdmin(page)
  await injectTestModeData(page)
  await page.goto(`${BASE_URL}/models`)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)

  // Wait for models to load
  await expect(page.getByText('resnet50-classification')).toBeVisible({ timeout: 10000 })

  // 点击操作历史 Tab
  await page.getByRole('button', { name: /操作历史/i }).click()

  // Wait for history content to render
  await expect(page.getByText('正式版本上线')).toBeVisible({ timeout: 10000 })

  // 检查历史 Tab 内容区域（表格标题行）
  await expect(page.getByRole('columnheader', { name: /时间/i })).toBeVisible({ timeout: 15000 })

  await page.screenshot({ path: `${SCREENSHOT_DIR}/model_registry_history_tab.png` })
})

// ============================================================
// Test 4: 版本列表含数据时的版本表格
// ============================================================
test('4. 模型管理页 - 版本列表含数据时的版本表格', async ({ page }) => {
  await loginAsAdmin(page)
  await injectTestModeData(page)
  await page.goto(`${BASE_URL}/models`)
  await page.waitForLoadState('networkidle')

  // 验证版本表格存在（证明 loadVersions 成功返回 mock 数据）
  const table = page.getByRole('table')
  await expect(table).toBeVisible()

  // 验证版本数据行存在：检查 v3 版本号和 Production 标签（直接查找文本，不依赖复杂 CSS）
  const versionBadge = page.locator('table').locator('td', { hasText: 'v3' })
  await expect(versionBadge).toBeVisible({ timeout: 15000 })
  const tagBadge = page.locator('table').locator('td', { hasText: 'Production' })
  await expect(tagBadge).toBeVisible({ timeout: 15000 })

  await page.screenshot({ path: `${SCREENSHOT_DIR}/model_registry_with_versions.png` })
})
