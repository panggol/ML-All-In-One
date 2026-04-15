/**
 * Playwright 全局 Setup — E2E 测试数据准备
 *
 * 在所有测试运行之前执行：
 * 1. 调用 seed_e2e_inference_data.py 脚本准备测试数据
 * 2. 等待后端 API 服务就绪（可选，依赖 webServer 配置）
 *
 * 用法：在 playwright.config.ts 中配置 globalSetup 指向本文件。
 */

import { defineConfig } from "@playwright/test";
import { execSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * 运行 Python seeding 脚本
 */
function runSeedScript(): void {
  // 项目根目录（playwright.config.ts 所在目录的父目录）
  const projectRoot = path.resolve(__dirname, "..");

  const scriptPath = path.join(projectRoot, "scripts", "seed_e2e_inference_data.py");

  if (!fs.existsSync(scriptPath)) {
    console.warn(
      `[global-setup] ⚠️  Seeding script not found: ${scriptPath}`
    );
    console.warn(`[global-setup] Skipping E2E data seeding. Inference tests may fail.`);
    return;
  }

  console.log(`[global-setup] 🌱 Running E2E inference data seed script...`);

  try {
    // 使用当前 Python 环境运行脚本
    execSync(`python3 "${scriptPath}"`, {
      cwd: projectRoot,
      stdio: "inherit",
      env: {
        ...process.env,
        // 确保脚本能找到正确的数据库
        DATABASE_PATH: path.join(projectRoot, "ml_all_in_one.db"),
        MODELS_DIR: path.join(projectRoot, "models"),
        UPLOAD_DIR: path.join(projectRoot, "uploads"),
      },
    });

    console.log(`[global-setup] ✅ E2E data seeding complete.`);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[global-setup] ❌ Seeding script failed: ${message}`);
    // 不 throw，避免在 CI 环境中因 seeding 失败而阻断测试
    // inference.spec.ts 仍会运行，QA 报告会显示失败原因
    console.warn(`[global-setup] Continuing anyway — tests may fail due to missing data.`);
  }
}

/**
 * 等待后端 API 就绪
 */
async function waitForBackend(url: string, timeout: number = 30000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const response = await fetch(url, { method: "HEAD" });
      if (response.ok) {
        console.log(`[global-setup] ✅ Backend API is ready: ${url}`);
        return;
      }
    } catch {
      // ignore and retry
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Backend API not ready after ${timeout}ms: ${url}`);
}

export default async function globalSetup(): Promise<void> {
  console.log(`[global-setup] Starting E2E global setup...`);

  // 步骤 1：准备测试数据
  runSeedScript();

  // 步骤 2：等待后端 API 就绪
  const backendUrl = process.env.E2E_API_URL || "http://localhost:8000/api/auth/me";
  try {
    await waitForBackend(backendUrl, 30_000);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`[global-setup] ⚠️  Backend API check skipped: ${message}`);
  }

  console.log(`[global-setup] ✅ Global setup complete.`);
}
