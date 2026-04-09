# ML All In One 前端 - 设计决策记录

**项目：** ML All In One 现代UI前端  
**日期：** 2026-04-09  
**状态：** 进行中

---

## 一、技术选型决策

### 1.1 React + TypeScript
**决策：** 使用 React 18 + TypeScript  
**原因：**
- 类型安全，减少运行时错误
- 社区生态丰富
- 团队熟悉度高

### 1.2 Vite
**决策：** 使用 Vite 作为构建工具  
**原因：**
- 快速的开发服务器启动
- HMR 热更新快
- 配置简单

### 1.3 TailwindCSS
**决策：** 使用 TailwindCSS 作为样式方案  
**原因：**
- 原子化 CSS，开发效率高
- 与设计规范配合良好
- 支持暗色主题扩展

### 1.4 组件库策略
**决策：** 自研基础组件，不使用第三方UI库  
**原因：**
- 完全可控的样式和交互
- 与设计系统无缝集成
- 学习曲线可控

---

## 二、设计系统

### 2.1 色彩系统
```css
/* 主色调 */
Primary: #0ea5e9 (Sky-500)
Primary-hover: #0284c7 (Sky-600)

/* 功能色 */
Success: #10b981 (Emerald-500)
Warning: #f59e0b (Amber-500)
Error: #ef4444 (Red-500)

/* 中性色 */
Background: #f8fafc (Slate-50)
Card: #ffffff
Border: #e2e8f0 (Slate-200)
Text: #0f172a (Slate-900)
Text-secondary: #64748b (Slate-500)
```

### 2.2 间距系统
- 页面边距：`px-6 py-8`
- 卡片间距：`gap-6` (24px)
- 元素间距：`gap-3 gap-4` (12-16px)

### 2.3 圆角系统
- 卡片：`rounded-xl` (12px)
- 按钮/输入框：`rounded-lg` (8px)
- 大按钮：`rounded-2xl` (16px)

### 2.4 阴影系统
```css
shadow-card: 多层阴影组合
shadow-soft: hover状态加深
```

---

## 三、目录结构

```
frontend/
├── src/
│   ├── components/       # 可复用组件
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Badge.tsx
│   │   ├── Input.tsx
│   │   ├── Select.tsx
│   │   ├── ProgressBar.tsx
│   │   ├── StatCard.tsx
│   │   └── index.ts
│   ├── pages/            # 页面组件
│   │   ├── Dashboard.tsx
│   │   ├── Training.tsx
│   │   └── Experiments.tsx
│   ├── api/              # API 调用（后续）
│   ├── hooks/            # 自定义 Hooks（后续）
│   ├── App.tsx
│   └── main.tsx
```

---

## 四、组件设计

### 4.1 Button
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | 'primary' \| 'secondary' \| 'stop' | 'primary' | 按钮变体 |
| size | 'sm' \| 'md' \| 'lg' | 'md' | 按钮尺寸 |
| children | ReactNode | - | 内容 |

### 4.2 Card
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| hover | boolean | true | 是否启用hover效果 |

### 4.3 Badge
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | 'success' \| 'warning' \| 'error' \| 'info' \| 'default' | 'default' | 标签变体 |
| icon | ReactNode | - | 可选图标 |

### 4.4 Select
使用原生 `<select>` + 自定义样式 + ChevronDown 图标

### 4.5 ProgressBar
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| value | number | - | 当前值 |
| max | number | 100 | 最大值 |
| showLabel | boolean | true | 是否显示百分比标签 |
| size | 'sm' \| 'md' | 'md' | 进度条高度 |

---

## 五、页面设计

### 5.1 Dashboard
- 统计卡片网格（4列 → 2列 → 1列响应式）
- 快速入口列表
- 最近模型列表
- 系统状态面板

### 5.2 Training
- 文件上传拖拽区域
- 任务配置表单
- 模型选择网格
- 训练控制按钮
- 实时进度展示

### 5.3 Experiments
- 表格布局
- 状态徽章
- 详情展开面板

---

## 六、后续计划

### 阶段2：API集成
- [ ] FastAPI 后端开发
- [ ] API 客户端封装
- [ ] 状态管理集成

### 阶段3：高级功能
- [ ] 数据可视化（Recharts）
- [ ] 实时训练进度（WebSocket）
- [ ] 实验对比功能

### 阶段4：优化
- [ ] 加载骨架屏
- [ ] 错误边界
- [ ] 性能优化

---

## 七、已知问题

| 问题 | 严重度 | 状态 | 备注 |
|------|--------|------|------|
| 训练模拟数据 | 低 | 待修复 | 使用setTimeout模拟，需替换真实API |
| 响应式适配 | 中 | 部分完成 | 1024px以上屏幕优化 |
| 无暗色主题 | 低 | 待规划 | 可作为后续功能 |

---

*本文件随项目迭代持续更新*
