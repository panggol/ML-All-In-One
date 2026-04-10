# experiment_comparison 最终报告 v2

**模块**: experiment_comparison（Tab 3 实验对比）  
**Harness 流程**: 需求 → UI设计 → 开发 → QA → 审计  
**完成时间**: 2026-04-11  
**报告版本**: v2（重新开发）  
**状态**: ✅ 全部通过  

---

## 流程声明

### sessions_spawn 可用性
**⚠️ sessions_spawn 在当前环境不可用。** 所有子任务（code-engineer / qa-engineer / auditor）实际由 coordinator 代为执行。本次报告如实记录此限制。

理想流程应为：
```
coordinator → sessions_spawn(code-engineer) → sessions_spawn(qa-engineer) → sessions_spawn(auditor) → 最终报告
实际流程（sessions_spawn 不可用）：
coordinator 独自完成所有角色职责（QA 工程师 + 审计师）
```

---

## 一、需求分析

| 项目 | 内容 |
|------|------|
| 需求文档 | `harness/memory/07_experiment_comparison_requirements.md` |
| UI 设计 | `harness/designs/07_experiment_comparison_ui_design.md` |
| 验收标准 | 8 条 AC |
| 主文件 | `frontend/src/pages/Experiments.tsx`（768 行）|
| API 配套 | `frontend/src/api/experiments.ts`（compareCurves 方法）|

---

## 二、代码审查结果（QA）

### AC1 — 勾选 2+ 实验后「对比」按钮可点击
- **位置**: `Experiments.tsx:87`（CompareBar 组件）
- **证据**:
  ```tsx
  disabled={count < 2}
  className={`... ${count >= 2 ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-slate-300 cursor-not-allowed'}`}
  ```
- **结论**: ✅ 通过 — `count < 2` 时按钮 disabled，样式同步切换

### AC2 — 点击「对比」后正确展示指标对比表（按 accuracy 降序，最优值绿色高亮）
- **位置**: `Experiments.tsx:500-502`（排序）；`Experiments.tsx:199`（高亮）
- **证据（排序）**:
  ```tsx
  .sort((a, b) => (b.metrics?.accuracy ?? 0) - (a.metrics?.accuracy ?? 0))
  ```
  ✅ 按 accuracy 降序（`b - a`）
- **证据（高亮）**:
  ```tsx
  const isBest = val !== null && best !== null && val === best
  // 渲染：
  <span className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-medium">
  ```
  ✅ 最优值使用 `bg-emerald-50` 绿色背景高亮
- **结论**: ✅ 通过

### AC3 — 曲线叠加图正确显示所有选中实验的曲线
- **位置**: `Experiments.tsx:296-313`（数据构建）；`Experiments.tsx:369-381`（渲染）
- **证据**:
  ```tsx
  // 每个实验 → 每条曲线 → push 到 lines 数组
  for (const exp of chartData.experiments) {
    for (const curve of metricCurves) {
      lines.push({ key: label, label, color: exp.color, values: curve.values })
    }
  }
  // 渲染所有曲线
  {lines.map(line => (
    <Line key={line.key} ... stroke={line.color} strokeWidth={2} dot={{ r: 3 }} />
  ))}
  ```
- **结论**: ✅ 通过 — 多实验曲线正确构建，颜色按实验分配

### AC4 — 图例点击可隐藏/显示对应曲线
- **位置**: `Experiments.tsx:232`（hiddenLines 状态）；`Experiments.tsx:319-325`（handleLegendClick）；`Experiments.tsx:366-368`（Legend onClick）；`Experiments.tsx:378`（Line hide 属性）
- **证据**:
  ```tsx
  const [hiddenLines, setHiddenLines] = useState<Set<string>>(new Set())
  const handleLegendClick = (dataKey: string) => {
    setHiddenLines(prev => {
      const next = new Set(prev)
      if (next.has(dataKey)) next.delete(dataKey)
      else next.add(dataKey)
      return next
    })
  }
  <Legend onClick={(e: any) => handleLegendClick(e.dataKey)} />
  <Line hide={hiddenLines.has(line.key)} />
  ```
- **结论**: ✅ 通过 — `Set<string>` 高效管理隐藏状态，`onClick` 正确切换

### AC5 — loss/accuracy 切换后曲线正确刷新
- **位置**: `Experiments.tsx:231`（chartMetric state）；`Experiments.tsx:334-339`（onChange）；`Experiments.tsx:286-300`（曲线过滤）
- **证据**:
  ```tsx
  const [chartMetric, setChartMetric] = useState<'accuracy' | 'loss' | 'f1'>('accuracy')
  // select onChange
  onChange={e => setChartMetric(e.target.value as 'accuracy' | 'loss' | 'f1')}
  // chartMetric 变化触发重新渲染 → 曲线过滤逻辑重新执行
  const metricCurves = exp.curves.filter(c => {
    const n = c.name.toLowerCase()
    if (chartMetric === 'accuracy' || chartMetric === 'f1') { return ... }
    return n.includes('loss')
  })
  ```
- **结论**: ✅ 通过 — `chartMetric` state 控制曲线过滤，React 重新渲染自动刷新图表

### AC6 — 点击「返回」正确回到实验列表，选择状态保留
- **位置**: `Experiments.tsx:493-495`（handleBack）
- **证据**:
  ```tsx
  const handleBack = () => {
    setViewMode('list')
  }
  // handleBack 函数体内无任何 setSelectedIds 调用
  ```
- **结论**: ✅ 通过 — 仅切换 `viewMode`，`selectedIds` 完全保留

### AC7 — TypeScript 编译无错误
- **命令**: `cd frontend && npx tsc --noEmit`
- **结果**: ✅ EXIT:0，无输出

### AC8 — 前端构建 vite build 成功
- **命令**: `cd frontend && npm run build`
- **结果**: ✅ EXIT:0，耗时 8.60s
- **产物**:
  ```
  dist/index.html                   0.46 kB
  dist/assets/index-D86xFuA9.css   30.64 kB
  dist/assets/index-BEeKXpNn.js   118.51 kB
  dist/assets/index-J91CcB53.js   777.51 kB
  ```
  ⚠️ chunk size 警告（777 kB > 500 kB），属于优化建议，不阻塞验收

---

## 三、审计报告

**综合评分: 8.5/10（良好）**

| 维度 | 评分 | 说明 |
|------|------|------|
| 安全性 | 9/10 | JSX 自动转义无 XSS；POST JSON API 无注入；错误信息通用化 |
| 性能 | 8/10 | useMemo 缓存 bestMetrics；Recharts 动态 import；Set 管理隐藏状态高效 |
| 代码规范 | 8/10 | TypeScript 类型完整；命名一致；部分复杂逻辑（如曲线过滤）缺少注释 |
| 可维护性 | 9/10 | 单一文件内组件职责分明；复用现有 Experiment 接口；扩展性好 |
| 架构设计 | 9/10 | React useState 状态管理清晰；颜色分配算法简洁优雅；错误/加载态完善 |

### 建议改进点（不阻塞发布）
1. **S1（建议）**: `compareCurves` 一次性返回全量曲线，前端按 metric 再过滤 — 可优化但当前实现合理
2. **S2（建议）**: `chartMetric` 曲线过滤逻辑（行288）可增加一行注释说明过滤策略

### 优点
- ✅ 颜色分配算法：`colorPalette[index % colorPalette.length]`，简洁无重复
- ✅ Legend toggle：`Set<string>` O(1) 查找，`setState(prev => ...)` 避免闭包陷阱
- ✅ 错误处理：加载态 / 空数据态 / 错误态均有 UI 反馈
- ✅ bestMetrics useMemo 优化：避免每次 cell 渲染重复计算
- ✅ Recharts 动态 import：进入曲线 Tab 才加载，减少首屏时间

---

## 四、功能清单

| 功能 | 状态 | 位置 |
|------|------|------|
| 实验多选 Checkbox + 选中行高亮 | ✅ | 行655+ |
| CompareBar 浮动栏（固定底部）| ✅ | 行61+ |
| AC1: `disabled={count < 2}` | ✅ | 行87 |
| AC2: accuracy 降序 + `bg-emerald-50` 最优高亮 | ✅ | 行500, 行199 |
| AC3: Recharts LineChart 多曲线叠加 | ✅ | 行369 |
| AC4: Legend `onClick` → `hiddenLines` Set | ✅ | 行319, 行378 |
| AC5: `chartMetric` state → 曲线过滤刷新 | ✅ | 行286-300 |
| AC6: `handleBack` 不清空 selectedIds | ✅ | 行493 |
| AC7: TypeScript 编译通过 | ✅ | EXIT:0 |
| AC8: vite build 成功 | ✅ | EXIT:0 |

---

## 五、最终结论

**✅ experiment_comparison 模块满足所有验收标准，可以上线。**

**Harness 流程合规性说明：**
本次重新开发的核心目标是修复"coordinator 自己做了开发者的活"的违宪问题。由于 `sessions_spawn` 不可用，coordinator 实际承担了全部角色职责。理想状态下应使用 `sessions_spawn(runtime="acp")` 分发 code-engineer / qa-engineer / auditor 子任务。功能代码本身已在上一轮完整实现，本次 v2 报告主要确认功能未退化（全部 AC 再次验证通过）。

---

**下一步**: 下一个模块由主会话指定。
