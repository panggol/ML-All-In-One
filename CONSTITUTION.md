# ML All In One — Constitution

**Version**: 1.0.0
**Ratified**: 2026-04-11
**Last Amended**: 2026-04-11

## Core Principles

### I. 规划先行，接口第一
- 复杂功能必须先写设计文档（SPEC.md），再写代码
- 先定义接口契约（API/CLI），再实现内部逻辑
- 接口变更必须更新契约文档

### II. Library-First（库优先）
- 每个功能模块必须是一个独立的 Python 包（`src/mlkit/` 下）
- 包必须自包含、可独立测试、有清晰职责
- 不允许纯组织性质的"工具包"存在

### III. 接口标准化
- 所有核心功能同时暴露 **Python API** 和 **CLI 接口**
- CLI 遵循 Text in/out 协议：`stdin/args → stdout`，错误 → `stderr`
- API 支持 JSON 格式输出

### IV. 测试不可绕过（NON-NEGOTIABLE）
- 新增代码必须有单元测试（pytest）
- 涉及模块间交互的功能必须有集成测试
- 核心契约（API 端点、CLI 输出格式）必须有契约测试

### V. 集成测试重点区域
- 新模块的契约测试
- 模块间通信（API ↔ Database ↔ MLKit）
- 共享 Schema 变更

### VI. 可观测性
- 所有 API 路由必须结构化日志（JSON 格式）
- 日志包含：请求 ID、用户 ID、操作类型、耗时、状态码

### VII. 版本管理
- 采用语义化版本：`MAJOR.MINOR.BUILD`
- Breaking Changes 必须升级 MAJOR 版本并更新 CHANGELOG

### VIII. 简洁优先（YAGNI）
- 从简单开始，不提前过度设计
- 每次变更必须有明确价值
- 拒绝"未来可能有用"的代码

## Additional Constraints

### 技术栈约束
- **语言**: Python 3.10+
- **Web 框架**: FastAPI（API 层）
- **数据库**: SQLite（默认）/ PostgreSQL（生产）
- **前端**: React + TypeScript
- **测试**: pytest
- **ML 框架**: sklearn + PyTorch

### 大数据处理约束
- 50GB+ CSV 文件必须使用 pandas `chunksize` 或 Dask 分块读取
- 不支持流式训练的模型必须采样或使用 Dask-ML

### 样本不均衡处理
- 支持 class_weight 类别权重
- 支持 SMOTE/ADASYN 过采样
- 支持 RandomUnderSampler 欠采样

### 部署约束
- 必须支持 Docker 部署
- 必须支持 K8s 分布式（GPU/NPU）
- 配置通过环境变量注入，不硬编码

## Development Workflow

### 功能开发流程（强制）
1. **需求分析** → 输出 `specs/<feature>/spec.md`（spec-template 格式）
2. **Constitution 检查** → 验证是否符合本宪法
3. **设计** → 输出 `specs/<feature>/plan.md`（plan-template 格式）
4. **开发** → 按 plan.md 实现
5. **QA 验证** → 测试通过
6. **审计** → 代码质量 + 安全检查通过
7. **合并** → 进入主分支

### 代码审查要求
- 所有 PR 必须有测试
- 所有 PR 必须通过 CI（lint + test）
- 复杂度超标必须额外说明理由

## Governance

- **本宪法优先于所有其他实践规范**
- 修订需要：文档化 + 批准 + 迁移计划
- 所有代码审查必须验证合规性
- 复杂度超标必须使用 [GUIDANCE_FILE] 进行运行时开发指导

---

*Constitution 由 Coordinator subagent 创建 | 2026-04-11*
