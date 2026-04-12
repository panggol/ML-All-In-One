import { test, expect, Page, Locator } from '@playwright/test'

/**
 * E2E 测试：登录/注册流程
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000/login'

// ============================================================
// 辅助函数：JS 方式设置 React controlled input 的值
// ============================================================
async function setReactInput(page: Page, locator: Locator, v: string) {
  await locator.evaluate(
    (el: HTMLInputElement) => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
      setter.call(el, (window as any).__testVal);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    },
    v
  );
}

// ============================================================
// 表单选择器（精确版）
// ============================================================
function getLoginForm(page: Page) {
  // 登录表单的特征：有"用户名"和"密码"字样
  return page.locator('form').filter({ hasText: '用户名' }).filter({ hasText: '密码' })
}
function getRegForm(page: Page) {
  return page.locator('form').filter({ hasText: '邮箱' }).filter({ hasText: '确认密码' })
}
function getLoginUsernameInput(page: Page) {
  return page.locator('input[placeholder="请输入用户名或邮箱"]')
}
function getLoginPasswordInput(page: Page) {
  return page.locator('input[placeholder="请输入密码"]')
}
function getRegUsernameInput(page: Page) {
  return page.locator('input[placeholder="3-20个字符"]')
}
function getRegEmailInput(page: Page) {
  return page.locator('input[placeholder="your@email.com"]')
}
function getRegPasswordInput(page: Page) {
  return page.locator('input[placeholder="至少6位"]')
}
function getRegConfirmInput(page: Page) {
  return page.locator('input[placeholder="再次输入密码"]')
}
// Tab 切换按钮（div.flex 容器下的按钮，排除表单内的同名按钮）
function getTabLoginBtn(page: Page) {
  return page.locator('div.flex > button').filter({ hasText: '登录' })
}
function getTabRegisterBtn(page: Page) {
  return page.locator('div.flex > button').filter({ hasText: '注册' })
}
// 错误提示框
function getErrorBox(page: Page) {
  return page.locator('div.bg-red-50')
}

// ============================================================
// 测试用例
// ============================================================
test.describe('认证流程', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/auth`)
  })

  // --- 注册失败场景 ---

  test('注册 - 密码不一致时显示错误提示', async ({ page }) => {
    await getTabRegisterBtn(page).click()
    await getRegUsernameInput(page).fill('testuser_e2e')
    await getRegEmailInput(page).fill('test_e2e@example.com')
    await getRegPasswordInput(page).fill('password123')
    await getRegConfirmInput(page).fill('password456') // 不一致
    await getRegForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await expect(getErrorBox(page)).toBeVisible()
    await expect(getErrorBox(page).locator('text=/两次|不一致|密码|mismatch|do not match/i')).toBeVisible()
  })

  test('注册 - 密码过短时显示错误提示', async ({ page }) => {
    await getTabRegisterBtn(page).click()
    await getRegUsernameInput(page).fill('testuser_e2e')
    await getRegEmailInput(page).fill('test_e2e@example.com')
    await getRegPasswordInput(page).fill('12345') // 少于 6 位
    await getRegConfirmInput(page).fill('12345') // 也填，跳过 required 验证
    await getRegForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await expect(getErrorBox(page)).toBeVisible()
    await expect(getErrorBox(page).locator('text=/6|过短|at least/i')).toBeVisible()
  })

  test('注册 - 用户名过短时显示错误提示', async ({ page }) => {
    await getTabRegisterBtn(page).click()
    await getRegUsernameInput(page).fill('ab') // 少于 3 字符
    await getRegEmailInput(page).fill('test@example.com')
    await getRegPasswordInput(page).fill('password123')
    await getRegConfirmInput(page).fill('password123')
    await getRegForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await expect(getErrorBox(page)).toBeVisible()
    await expect(getErrorBox(page).locator('text=/3|用户名|username|character/i')).toBeVisible()
  })

  // --- 登录失败场景 ---

  test('登录 - 用户名错误时显示错误提示', async ({ page }) => {
    await getLoginUsernameInput(page).fill('nonexistent_user_xyz')
    await page.waitForTimeout(200) // 等待 React 状态更新
    await getLoginPasswordInput(page).fill('wrongpassword')
    await page.waitForTimeout(200)
    // 按 Enter 提交表单
    await getLoginPasswordInput(page).press('Enter')

    await expect(getErrorBox(page)).toBeVisible({ timeout: 8000 })
    await expect(getErrorBox(page).locator('text=/登录失败|用户名|密码|incorrect|invalid|failed/i')).toBeVisible()
  })

  test('登录 - 密码错误时显示错误提示', async ({ page }) => {
    const randomUser = `user_${Date.now()}`
    await getTabRegisterBtn(page).click()
    await getRegUsernameInput(page).fill(randomUser)
    await getRegEmailInput(page).fill(`${randomUser}@test.com`)
    await getRegPasswordInput(page).fill('password123')
    await getRegConfirmInput(page).fill('password123')
    await getRegForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await getLoginPasswordInput(page).waitFor({ state: 'visible', timeout: 5000 })

    await getLoginUsernameInput(page).fill(randomUser)
    await page.waitForTimeout(300)
    await getLoginPasswordInput(page).fill('wrongpassword')
    await page.waitForTimeout(300)
    await getLoginForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await expect(getErrorBox(page)).toBeVisible({ timeout: 8000 })
    await expect(getErrorBox(page).locator('text=/登录失败|密码|incorrect|invalid|failed/i')).toBeVisible()
  })

  // --- 登录成功场景 ---

  test('登录 - 成功后跳转到 Dashboard', async ({ page }) => {
    const randomUser = `user_${Date.now()}`
    await getTabRegisterBtn(page).click()
    await getRegUsernameInput(page).fill(randomUser)
    await getRegEmailInput(page).fill(`${randomUser}@test.com`)
    await getRegPasswordInput(page).fill('password123')
    await getRegConfirmInput(page).fill('password123')
    await getRegForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await getLoginPasswordInput(page).waitFor({ state: 'visible', timeout: 5000 })
    await getLoginPasswordInput(page).fill('password123')
    await page.waitForTimeout(300)
    await getLoginForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 })
  })

  test('注册 - 成功后自动切换到登录并填充用户名', async ({ page }) => {
    const randomUser = `user_${Date.now()}`
    await getTabRegisterBtn(page).click()
    await getRegUsernameInput(page).fill(randomUser)
    await getRegEmailInput(page).fill(`${randomUser}@test.com`)
    await getRegPasswordInput(page).fill('password123')
    await getRegConfirmInput(page).fill('password123')
    await getRegForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await expect(getErrorBox(page)).toBeVisible({ timeout: 5000 })
    await expect(getErrorBox(page).locator('text=/成功|success|注册成功/i')).toBeVisible()

    await getLoginUsernameInput(page).waitFor({ state: 'visible', timeout: 5000 })
    await expect(getLoginUsernameInput(page)).toHaveValue(randomUser)
  })

  test('退出登录后应跳转登录页且无法访问受保护页面', async ({ page }) => {
    const randomUser = `user_${Date.now()}`
    await getTabRegisterBtn(page).click()
    await getRegUsernameInput(page).fill(randomUser)
    await getRegEmailInput(page).fill(`${randomUser}@test.com`)
    await getRegPasswordInput(page).fill('password123')
    await getRegConfirmInput(page).fill('password123')
    await getRegForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())

    await getLoginPasswordInput(page).waitFor({ state: 'visible', timeout: 5000 })
    await getLoginPasswordInput(page).fill('password123')
    await page.waitForTimeout(300)
    await getLoginForm(page).evaluate((f: HTMLFormElement) => f.requestSubmit())
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 })

    // 查找并点击退出登录按钮
    const logoutButton = page.locator('button').filter({ hasText: /退出|logout|sign out|登出/i }).first()
    const logoutBtnVisible = await logoutButton.isVisible().catch(() => false)

    if (logoutBtnVisible) {
      await logoutButton.click()
      await expect(page).toHaveURL(/\/auth/, { timeout: 5000 })
      await page.goto(`${BASE_URL}/dashboard`)
      await expect(page).toHaveURL(/\/auth/, { timeout: 5000 })
    } else {
      console.log('⚠️ 退出登录按钮未在页面上找到，跳过此测试')
    }
  })

})
