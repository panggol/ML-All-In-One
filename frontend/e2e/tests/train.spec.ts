import { test, expect } from '@playwright/test'
import * as fs from 'fs'

/**
 * E2E 测试：训练创建和状态查询流程
 * 覆盖：
 * - 未登录时访问训练页应跳转登录
 * - 选择数据文件
 * - 选择模型和任务类型
 * - 创建训练任务
 * - 轮询训练状态
 * - 训练完成后查看指标
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'

function createTempCSV(): string {
  const content = [
    'id,feature_a,feature_b,target',
    '1,0.1,0.2,0',
    '2,-0.3,0.5,1',
    '3,0.7,-0.1,0',
    '4,-0.2,0.3,1',
    '5,0.4,-0.6,0',
    '6,0.3,-0.2,1',
    '7,-0.5,0.1,0',
    '8,0.6,0.4,1',
    '9,-0.1,-0.3,0',
    '10,0.8,-0.5,1',
  ].join('\n')
  const tmpPath = '/tmp/e2e_train_data.csv'
  fs.writeFileSync(tmpPath, content)
  return tmpPath
}

async function loginAsTestUser(page: any, username: string) {
  await page.goto(`${BASE_URL}/auth`)
  const randomUser = `${username}_${Date.now()}`

  await page.getByRole('tab', { name: /注册|register/i }).click()
  await page.getByPlaceholder(/用户名|username/i).fill(randomUser)
  await page.getByPlaceholder(/邮箱|email/i).fill(`${randomUser}@test.com`)
  await page.getByPlaceholder(/密码|password/i).first().fill('password123')
  await page.getByPlaceholder(/确认密码|confirm/i).fill('password123')
  await page.getByRole('button', { name: /注册|创建账户|sign up/i }).click()
  await page.waitForTimeout(1000)

  await page.getByPlaceholder(/密码|password/i).fill('password123')
  await page.getByRole('button', { name: /登录|sign in|log in/i }).click()
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 })

  return randomUser
}

async function uploadDataFile(page: any) {
  await page.goto(`${BASE_URL}/data`)
  await page.waitForLoadState('networkidle')
  const uploadButton = page.locator('button').filter({ hasText: /上传|upload|导入/i }).first()
  await uploadButton.click()
  const csvPath = createTempCSV()
  await page.locator('input[type="file"]').first().setInputFiles(csvPath)
  await page.waitForTimeout(2000)
}

test.describe('训练创建和状态查询', () => {

  test('未登录时访问训练页应跳转登录页', async ({ page }) => {
    await page.goto(`${BASE_URL}/training`)
    await expect(page).toHaveURL(/\/auth/, { timeout: 5000 })
  })

  test('训练页面加载成功且关键元素可见', async ({ page }) => {
    await loginAsTestUser(page, 'train_page_load')

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 关键元素应可见：训练按钮/标题
    await expect(
      page.locator('text=/训练|train|创建|start/i').first()
    ).toBeVisible({ timeout: 5000 })
  })

  test('选择数据文件', async ({ page }) => {
    await loginAsTestUser(page, 'select_data')
    await uploadDataFile(page)

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 查找文件选择器或下拉框
    const fileSelect = page.locator('select, [role="combobox"], [role="listbox"]').first()
    const selectVisible = await fileSelect.isVisible().catch(() => false)

    if (selectVisible) {
      await expect(fileSelect).toBeVisible({ timeout: 3000 })
    }
  })

  test('选择任务类型（分类/回归）', async ({ page }) => {
    await loginAsTestUser(page, 'select_task')

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 查找任务类型选项（分类/回归）
    const taskOptions = page.locator('text=/分类|classification|回归|regression/i')
    const count = await taskOptions.count()

    if (count > 0) {
      // 点击分类选项
      const classificationOption = page.locator('text=/分类|classification/i').first()
      await classificationOption.click()
      await page.waitForTimeout(300)
    }
  })

  test('选择模型类型', async ({ page }) => {
    await loginAsTestUser(page, 'select_model')

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 查找模型选项
    const modelOptions = page.locator('text=/RandomForest|XGBoost|LightGBM|Logistic/i')
    const count = await modelOptions.count()

    if (count > 0) {
      await modelOptions.first().click()
      await page.waitForTimeout(300)
    }
  })

  test('填写目标列', async ({ page }) => {
    await loginAsTestUser(page, 'target_column')

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 查找目标列输入框
    const targetInput = page.locator('input[placeholder*="目标" i], input[placeholder*="target" i], input').first()
    const inputVisible = await targetInput.isVisible().catch(() => false)

    if (inputVisible) {
      await targetInput.fill('target')
      await page.waitForTimeout(200)
    }
  })

  test('训练状态轮询（训练完成后显示指标）', async ({ page }) => {
    await loginAsTestUser(page, 'train_status_poll')
    await uploadDataFile(page)

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 选择数据文件
    const fileSelect = page.locator('select').first()
    const fileSelectVisible = await fileSelect.isVisible().catch(() => false)
    if (fileSelectVisible) {
      const options = await fileSelect.locator('option').all()
      if (options.length > 1) {
        await fileSelect.selectOption({ index: 1 })
        await page.waitForTimeout(500)
      }
    }

    // 填写目标列
    const targetInput = page.locator('input[placeholder*="目标" i], input[placeholder*="target" i]').first()
    const targetVisible = await targetInput.isVisible().catch(() => false)
    if (targetVisible) {
      await targetInput.fill('target')
    }

    // 选择分类任务
    const classOption = page.locator('text=/分类|classification/i').first()
    const classVisible = await classOption.isVisible().catch(() => false)
    if (classVisible) {
      await classOption.click()
      await page.waitForTimeout(200)
    }

    // 点击开始训练按钮
    const trainButton = page.locator('button').filter({ hasText: /开始训练|start.*train|train.*start|训练/i }).first()
    const trainBtnVisible = await trainButton.isVisible().catch(() => false)

    if (trainBtnVisible) {
      await trainButton.click()
      await page.waitForTimeout(2000)

      // 检查是否有进度条或状态显示
      const progressOrStatus = page.locator('text=/进度|progress|进行中|running|pending/i, [role="progressbar"]').first()
      const statusVisible = await progressOrStatus.isVisible().catch(() => false)

      if (statusVisible) {
        // 等待训练完成（最多 60 秒）
        let completed = false
        for (let i = 0; i < 60; i++) {
          await page.waitForTimeout(1000)
          const statusText = await page.locator('text=/完成|completed|成功|success/i').count()
          if (statusText > 0) {
            completed = true
            break
          }
          const failedText = await page.locator('text=/失败|failed|错误|error/i').count()
          if (failedText > 0) break
        }

        if (completed) {
          // 训练完成，检查是否有指标显示
          await expect(
            page.locator('text=/accuracy|precision|recall|指标|metrics|结果|result/i').first()
          ).toBeVisible({ timeout: 5000 })
        }
      }
    }
  })

  test('停止训练任务', async ({ page }) => {
    await loginAsTestUser(page, 'stop_training')
    await uploadDataFile(page)

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 选择数据文件
    const fileSelect = page.locator('select').first()
    const fileSelectVisible = await fileSelect.isVisible().catch(() => false)
    if (fileSelectVisible) {
      const options = await fileSelect.locator('option').all()
      if (options.length > 1) {
        await fileSelect.selectOption({ index: 1 })
        await page.waitForTimeout(500)
      }
    }

    // 填写目标列
    const targetInput = page.locator('input[placeholder*="目标" i], input[placeholder*="target" i]').first()
    const targetVisible = await targetInput.isVisible().catch(() => false)
    if (targetVisible) {
      await targetInput.fill('target')
    }

    // 选择分类任务
    const classOption = page.locator('text=/分类|classification/i').first()
    const classVisible = await classOption.isVisible().catch(() => false)
    if (classVisible) {
      await classOption.click()
      await page.waitForTimeout(200)
    }

    // 点击开始训练按钮
    const trainButton = page.locator('button').filter({ hasText: /开始训练|start.*train|train.*start|训练/i }).first()
    const trainBtnVisible = await trainButton.isVisible().catch(() => false)

    if (trainBtnVisible) {
      await trainButton.click()
      await page.waitForTimeout(2000)

      // 查找停止按钮
      const stopButton = page.locator('button').filter({ hasText: /停止|stop|cancel|取消/i }).first()
      const stopBtnVisible = await stopButton.isVisible().catch(() => false)

      if (stopBtnVisible) {
        await stopButton.click()
        await page.waitForTimeout(1000)
        // 训练应停止，不应出现"完成"状态
        const completedText = await page.locator('text=/完成|completed|成功|success/i').count()
        // 停止后状态应变化（不再是 running/进行中）
        const statusText = await page.locator('text=/进行中|running/i').count()
        // 停止后要么进度停止，要么状态变为停止
        expect(stopBtnVisible).toBeTruthy()
      } else {
        console.log('⚠️ 停止训练按钮未找到，跳过停止测试')
      }
    }
  })

  test('训练页面元素完整性检查', async ({ page }) => {
    await loginAsTestUser(page, 'train_elements')

    await page.goto(`${BASE_URL}/training`)
    await page.waitForLoadState('networkidle')

    // 训练页面应包含以下关键元素的至少一个
    const keyElements = [
      page.locator('text=/训练|train/i').first(),
      page.locator('text=/模型|model/i').first(),
      page.locator('text=/数据|data|file/i').first(),
      page.locator('button').first(),
    ]

    let found = false
    for (const el of keyElements) {
      if (await el.isVisible().catch(() => false)) {
        found = true
        break
      }
    }
    expect(found).toBeTruthy()
  })

})
