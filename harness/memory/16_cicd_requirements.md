# ML All In One — CI/CD 需求文档

_Version: 1.0_
_Date: 2026-04-10_
_Author: 需求分析 Agent_

---

## 1. 概述

ML All In One 项目已具备基础 CI/CD 流程（test.yml / docker.yml），但缺少 lint、类型检查、前端构建验证等环节。本文档定义 CI/CD 的完整需求。

---

## 2. 现有 CI/CD 状态

| Workflow | 状态 | 说明 |
|----------|------|------|
| test.yml | ⚠️ 基础 | Python pytest（已存在，未验证可用性） |
| docker.yml | ⚠️ 基础 | Docker 构建（已存在） |
| minimal-test.yml | 🔧 手动 | 依赖调试（手动触发） |
| test-debug.yml | 🔧 手动 | 测试调试（手动触发） |

---

## 3. 需求缺口

### 3.1 必须有（MVP）
- [ ] **Lint 检查**：Black + Ruff 代码风格
- [ ] **类型检查**：mypy 静态类型验证
- [ ] **前端构建验证**：TypeScript 编译 + Vite 构建
- [ ] **CI 失败通知**：推送失败自动通知（暂用 commit status）

### 3.2 应该有（标准）
- [ ] **依赖安全扫描**：pip-audit / safety
- [ ] **pytest-cov 覆盖率报告**
- [ ] **PR review 前置检查清单**
- [ ] **Docker 镜像推送（带版本标签）**

### 3.3 最好有（增强）
- [ ] **并行 Job 加速**：lint + test 并行
- [ ] **缓存优化**：pip / node_modules 缓存
- [ ] **Docker layer 缓存**
- [ ] **nightly 构建**

---

## 4. 触发条件

| Event | 行为 |
|-------|------|
| push to master | 全量 CI + 推送 Docker 镜像 |
| pull_request | lint + test + frontend build |
| workflow_dispatch | 手动全量构建 |
| tag v*.*.* | 发布构建 + Docker push |

---

## 5. 验收标准

- [ ] push master 后 10 分钟内完成全量 CI
- [ ] lint / test / build 失败时 PR 不能合并
- [ ] 每次 master 构建生成 Docker 镜像并推送
- [ ] 前端构建产物自动部署到测试环境（Codespace）

---

## 6. 技术栈

- GitHub Actions（CI runner）
- Docker Buildx（多平台构建）
- npm / Vite（前端）
- Black + Ruff + mypy（Python 代码质量）

---

*文档版本：v1.0.0 | 最后更新：2026-04-10*
