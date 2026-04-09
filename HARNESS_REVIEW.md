# ML All In One — Harness Engineering 视角评审

**Review Date:** 2026-04-08
**Reviewer:** 龙虾小秘 🦞
**方法论:** 基于 Harness Engineering 四大理念（Prompt Assembly / Memory / Hook / Continuous Learning）
**参考项目:** learn-claude-code, everything-claude-code, Archon, claude-code-book

---

## 一、当前架构总览

```
┌─────────────────────────────────────────────────────┐
│                      Runner                          │
│            （核心编排器，生命周期管理）                   │
├──────────┬──────────┬──────────┬──────────────────┤
│  Config  │ Registry  │  Model   │  Data            │
│  (配置)  │  (注册)   │ (模型基类) │ (数据加载)        │
├──────────┴──────────┴──────────┴──────────────────┤
│                     Hooks                          │
│  Logger│Checkpoint│EarlyStop│Eval│LR│IterTimer    │
├─────────────────────────────────────────────────────┤
│              Preprocessing Pipeline                  │
│  Encoder│Imputer│Scaler│PCA│LDA│Vectorizer│...    │
├─────────────────────────────────────────────────────┤
│           API │ Experiment │ Utils                  │
└─────────────────────────────────────────────────────┘
```

**代码规模：**
- 核心模块：`src/mlkit/` 下约 40 个 Python 文件
- 测试：9 个文件，105 个测试函数
- 示例：6 个示例脚本

---

## 二、设计状态评审（四大维度）

### 维度一：Hook System（已达标 ⭐⭐⭐⭐⭐）

**优点：**

项目已有完整的 Hook 生命周期体系，参照了 Claude Code 的设计：

```python
# 8 个生命周期事件
before_run → before_epoch → before_iter
after_run  → after_epoch  → after_iter
before_val → after_val
```

已实现的 Hook：
- `LoggerHook`：迭代日志记录 → JSON 文件
- `CheckpointHook`：定期保存 + 最佳模型保存 + 自动清理旧 checkpoint
- `EarlyStoppingHook`：patience 机制，monitor 任意指标
- `EvalHook`：验证钩子（目前较简单）
- `LearningRateHook`：学习率调度
- `IterTimerHook`：迭代计时

**对比 Claude Code 的 Hook System：**

| 维度 | Claude Code | ML All In One | 差距 |
|------|------------|--------------|------|
| 事件数量 | 26 个 | 8 个 | 中等 |
| Hook 类型 | Pre/Post 分离 | 混在一起 | 待改进 |
| 配置驱动 | YAML/JSON | 代码实例化 | 可改进 |
| 扩展方式 | 装饰器 | 子类继承 | 可并存 |

**待改进：**
- `Callback.trigger()` 方法里的 `method_name` 有 bug：`event.replace("_", "_")` 替换后没变，应该直接用原名
- EarlyStoppingHook 记录的是 `best_score`，但判断 improved 时比较方向写反了（`current < best_score - min_delta` 时才改善，但 mode=min 时越小越好）

---

### 维度二：Registry System（已达标 ⭐⭐⭐⭐）

**优点：**

装饰器注册 + 自动扫描机制，是 Harness 中 Plugin System 的雏形：

```python
@register_model(name="RandomForest")
class MyModel(SKLearnModel): ...

# 或自动扫描
MODEL_REGISTRY.scan(["mlkit.models"])
```

全局注册表：MODEL_REGISTRY / DATASET_REGISTRY / OPTIMIZER_REGISTRY / HOOK_REGISTRY / METRIC_REGISTRY / TRANSFORM_REGISTRY

**设计问题：**

1. `locations` 里声明的路径（如 `"mlkit.models"`）在代码库里不存在——config/、model/、experiment/ 目录几乎是空的，只有 `__init__.py`
2. 这意味着 Registry 的 scan 能力目前是空壳，无法真正实现"新增模块→自动发现"
3. 需要建立"插件约定"：每个插件放在哪个路径、注册哪个注册表

---

### 维度三：Prompt Assembly / Memory System（基本缺失 ❌）

**问题：**

Claude Code 的 Memory System 有四类记忆：用户偏好、纠正记录、项目约束、外部引用。ML All In One 目前完全没有这个系统。

**具体缺失：**

```
Claude Code Memory System          ML All In One 现状
─────────────────────────────────────────────────────
用户偏好 (prefer_pnpm.md)    →   没有记录
纠正记录 (ask_before_codegen) →   没有记录
项目约束 (incident_dashboard)  →   没有记录
外部引用                       →   没有记录
```

结果：**每次新会话，Agent 都从零开始**。如果 AI 助手在处理项目时遇到历史偏好（比如"之前这个数据集有特殊清洗逻辑"），完全没有记忆。

**Config 层的问题：**

`src/mlkit/config/` 是空的。CLAUDE.md 里写了六层配置优先级链，但实际没有 Config 系统实现。Runner 里的 config 是直接从 dict 取值，缺少 Schema 验证、类型安全、默认值注入。

---

### 维度四：Continuous Learning（待建立 ⚠️）

**问题：**

Claude Code 的 Continuous Learning 是：从每次 session 中提取模式，沉淀为可复用技能。ML All In One 没有这个机制。

**缺失的循环：**

```
训练结果 → 发现问题模式 → 更新 SKILL.md/CLAUDE.md → 下次避免
```

**Experiment 模块的问题：**

`src/mlkit/experiment/` 是空的。但 PROGRESS.md 里写了"实验追踪与对比"、"超参数搜索"已✅完成。这是一个设计与实现严重脱节的地方。

---

## 三、代码状态评审

### 优秀的地方 ✅

1. **BaseModel 抽象接口**：清晰定义 fit/predict/save/load，SKLearnModel 和未来 PyTorchModel 都可以一致调用
2. **Runner 编排逻辑**：build → train → val → test → predict 流程清晰，Hook 注入点合理
3. **Preprocessing 模块结构好**：base.py 有抽象类，tabular/ 和 root 下有实现，分层清晰
4. **测试覆盖率高**：105 个测试，覆盖 data / model / preprocessing 三大模块
5. **pyproject.toml 配置完整**：black + isort + ruff + mypy + pytest 全家桶

### 严重问题 ❌

1. **重复代码**：`src/mlkit/preprocessing/` 下有大量重复模块
   ```
   preprocessing/
   ├── encoder.py        ← 存在
   ├── tabular/
   │   └── encoder.py    ← 存在，内容几乎相同
   ├── imputer.py        ← 存在
   ├── tabular/
   │   └── imputer.py    ← 存在，内容几乎相同
   ├── scaler.py         ← 存在
   ├── tabular/
   │   └── scaler.py     ← 存在，内容几乎相同
   ```
   这是严重的设计问题——tabular/ 是冗余的还是计划迁移中？

2. **空目录**：
   ```
   config/       ← 空的
   model/        ← 空的（模型实现在哪里？）
   experiment/   ← 空的
   ```
   CLAUDE.md 和 PROGRESS.md 里写的模块，在代码里找不到实现。

3. **dimensionality_reduction.py**：同时存在 `dimensionality/` 目录（PCA/LDA）和独立的 `dimensionality_reduction.py`，功能重复。

4. **EarlyStoppingHook 的判断逻辑**：
   ```python
   # 当前代码
   improved = current < (self.best_score - self.min_delta)
   ```
   当 mode="min" 时，current 比 best 小才是改善，逻辑是对的。
   但 `best_score` 记录的是"最后一个最佳值"而非"监控指标本身"，
   注释说"检查是否改善"但没有记录当前指标值到 logs。

5. **Callback.trigger() bug**：
   ```python
   def trigger(self, event: str, *args, **kwargs):
       method_name = event.replace("_", "_")  # 替换前后一样！
       if hasattr(hook, method_name):
           getattr(hook, method_name)(*args, **kwargs)
   ```
   应该直接用 `event`，不需要 replace。

---

## 四、对比 Harness Engineering 核心理念

| 理念 | Claude Code 实现 | ML All In One 现状 | 建议 |
|------|----------------|-------------------|------|
| **Prompt Assembly Pipeline** | SOUL+SKILL+MEMORY分层 | CLAUDE.md 有雏形，但 SKILL.md 与代码脱节 | 重构 SKILL.md 按 Skill 粒度组织 |
| **Hook System** | 26个事件，Pre/Post分离 | 8个事件，Hook基类清晰但实现粗糙 | 修复bug，补全EarlyStopping |
| **Memory System** | 四类记忆，YAML frontmatter | **完全没有** | 新建 `.memory/` 目录 |
| **Continuous Learning** | 每次session提取模式 | **没有** | 建立"经验→SKILL"循环 |
| **Registry/Plugin** | 装饰器注册+自动扫描 | 有装饰器但scan路径是空的 | 填入实际路径或删除空声明 |
| **Permission/Safety** | 四阶段权限管线 | **没有**（训练任务无危险操作，可接受） | 风险操作前加确认 |
| **Context Management** | 四级压缩机制 | Runner无上下文上限保护 | 加训练数据量上限 |

---

## 五、未来开发规划

### P0 — 立即修复（不影响架构）

- [ ] 修复 `Callback.trigger()` 的 method_name bug
- [ ] 清理 `preprocessing/tabular/` 重复代码（确认是废弃还是迁移中）
- [ ] 删除空的 `config/`、`model/`、`experiment/` 目录，或填入实现
- [ ] 修复 `dimensionality_reduction.py` vs `dimensionality/` 的重复

### P1 — 核心能力补全（1-2周）

- [ ] **建立 Config 系统**：`src/mlkit/config/` 实现 YAML/JSON 加载、Schema 验证、优先级合并、dot-path 访问
- [ ] **建立 Memory 系统**：创建 `.memory/` 目录，按四类记忆组织（用户偏好 / 纠正记录 / 项目约束 / 外部引用）
- [ ] **建立 Experiment 系统**：`src/mlkit/experiment/` 实现训练历史记录、超参数追踪、实验对比功能
- [ ] **重构 SKILL.md**：将 SKILL.md 从"使用说明"改为"技能定义"，每个技能独立文件，支持按需加载

### P2 — 架构升级（1个月）

- [ ] **Hook System 增强**：
  - Pre/Post 分离（类似 Claude Code：PreToolUse vs PostToolUse）
  - 支持配置驱动注册（YAML/JSON 声明式配置，而不是代码实例化）
  - 支持 Hook 优先级

- [ ] **Continuous Learning 循环**：
  - 训练结束后自动记录"发现的问题模式"
  - 提取为 `.skills/` 下的新技能文件
  - 新的类似任务自动加载相关技能

- [ ] **Context Management**：
  - Runner 加训练数据量上限保护（防止 OOM）
  - 大数据集自动采样提示
  - 多 GPU/NPU 自动分配

### P3 — 高级功能（长期）

- [ ] **分布式训练支持**：Dask-ML 集成，K8s 调度
- [ ] **模型版本管理**：Model Registry + Lineage 追踪
- [ ] **AutoML**：自动化超参数搜索 + 早停
- [ ] **多 Agent 协作**：参考 Archon 思路，不同角色（数据工程师 / 算法工程师 / 评审员）协作

---

## 六、总结

| 维度 | 评分 | 说明 |
|------|------|------|
| Hook System | ⭐⭐⭐⭐ | 体系完整，但有 bug 且配置方式原始 |
| Registry/Plugin | ⭐⭐⭐ | 有装饰器体系，但 scan 路径是空的 |
| Memory System | ⭐ | **完全缺失**，需要新建 |
| Continuous Learning | ⭐ | **完全没有**，需要建立循环 |
| 代码质量 | ⭐⭐⭐⭐ | 测试覆盖高，但有重复代码和空模块 |
| 文档质量 | ⭐⭐⭐⭐ | CLAUDE.md/SKILL.md 有雏形，需与代码同步 |

**综合评分：⭐⭐⭐（3.2/5）**

**核心结论：** ML All In One 的 **Hook + Registry + Runner 铁三角** 设计优秀，是 Harness Engineering 理念的良好实践。但 Memory 和 Continuous Learning 两个高层理念缺失，导致系统无法"从经验中学习"。此外，设计文档（CLAUDE.md/PROGRESS.md）与实际代码存在脱节，部分模块"写在文档里，但代码是空的"。建议优先完成 P0 修复和 P1 核心补全，再进入架构升级阶段。

---

*评审方法：基于 Harness Engineering 四大维度（Hook/Memory/Registry/Continuous Learning），结合源码逐文件分析*
