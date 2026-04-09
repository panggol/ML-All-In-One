# ML All In One 前端 - UI设计方案

**基于需求文档版本：** v1.0  
**设计日期：** 2026-04-09

---

## 1. 设计规范

### 1.1 设计风格
- **风格定位**：简约现代 (Modern Minimal)
- **设计理念**：清晰、克制、功能优先
- **参考案例**：Linear、Notion、Vercel Dashboard

### 1.2 色彩系统

```
主色调 (Primary):
- Primary-50:  #f0f9ff  (浅蓝背景)
- Primary-100:  #e0f2fe
- Primary-200:  #bae6fd
- Primary-300:  #7dd3fc
- Primary-400:  #38bdf8
- Primary-500:  #0ea5e9  (主色)
- Primary-600:  #0284c7  (hover)
- Primary-700:  #0369a1
- Primary-800:  #075985
- Primary-900:  #0c4a6e

中性色 (Neutral):
- Slate-50:   #f8fafc  (页面背景)
- Slate-100:  #f1f5f9  (卡片背景 hover)
- Slate-200:  #e2e8f0  (边框)
- Slate-400:  #94a3b8  (placeholder)
- Slate-500:  #64748b  (次要文字)
- Slate-700:  #334155  (正文)
- Slate-900:  #0f172a  (标题)

功能色:
- Emerald-500:  #10b981  (成功)
- Amber-500:    #f59e0b  (警告/运行中)
- Red-500:      #ef4444  (错误/停止)
- Violet-500:   #8b5cf6  (特殊强调)
```

### 1.3 字体系统
- **主字体**：Inter（Google Fonts）
- **等宽字体**：JetBrains Mono（代码展示）
- **字号层级**：
  - 页面标题：2xl (24px), font-weight: 600
  - 卡片标题：lg (18px), font-weight: 600
  - 正文：sm-base (14-16px), font-weight: 400
  - 辅助文字：sm (14px), text-slate-500

### 1.4 间距系统
- **页面内边距**：max-w-7xl mx-auto px-6 py-8
- **卡片间距**：gap-6 (24px)
- **卡片内边距**：p-6 (24px)
- **元素间距**：gap-3 gap-4 (12-16px)

### 1.5 圆角系统
- **卡片**：rounded-xl (12px)
- **按钮**：rounded-lg (8px)
- **输入框**：rounded-lg (8px)
- **大按钮**：rounded-2xl (16px)

### 1.6 阴影系统
```
shadow-card: 
  0 0 0 1px rgba(0, 0, 0, 0.03),
  0 2px 4px rgba(0, 0, 0, 0.05),
  0 12px 24px rgba(0, 0, 0, 0.05)

shadow-soft:
  0 2px 15px -3px rgba(0, 0, 0, 0.07),
  0 10px 20px -2px rgba(0, 0, 0, 0.04)
```

---

## 2. 页面结构

### 2.1 整体布局
```
┌─────────────────────────────────────────────────┐
│  Header (sticky, h-16)                          │
│  ┌─────────────────────────────────────────┐    │
│  │ Logo    │   Tabs (Dashboard/Training/..)│    │
│  └─────────────────────────────────────────┘    │
├─────────────────────────────────────────────────┤
│  Main Content (max-w-7xl mx-auto px-6 py-8)     │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │                                         │    │
│  │   Page Content                          │    │
│  │                                         │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 2.2 导航结构
- **Header**：固定顶部，高度 64px，白色背景，底部边框
- **Logo**：左侧，图标 + "ML All In One" 文字
- **Tab导航**：居中，3个主Tab

---

## 3. 页面设计

### 3.1 仪表盘 (Dashboard)

**布局：两栏网格**

```
┌──────────────────┐  ┌──────────────────┐
│  统计数据卡片1    │  │  统计数据卡片2    │
└──────────────────┘  └──────────────────┘
┌──────────────────┐  ┌──────────────────┐
│  统计数据卡片3    │  │  统计数据卡片4    │
└──────────────────┘  └──────────────────┘

┌────────────────────────┐  ┌────────────────────────┐
│     快速开始            │  │     最近模型            │
│  ┌──────────────────┐  │  │  ┌──────────────────┐  │
│  │ 上传数据集       │  │  │  │ Model 1  94.2%  │  │
│  └──────────────────┘  │  │  │ Model 2  87.5%  │  │
│  ┌──────────────────┐  │  │  │ Model 3  91.8%  │  │
│  │ 自动机器学习     │  │  │  └──────────────────┘  │
│  └──────────────────┘  │  │                        │
│  ┌──────────────────┐  │  │                        │
│  │ 模型预测         │  │  │                        │
│  └──────────────────┘  │  │                        │
└────────────────────────┘  └────────────────────────┘
```

**统计卡片组件：**
- 左侧：圆形色块图标（48x48）
- 右侧：标签文字 + 数值（2xl semibold）
- Hover：阴影加深 shadow-soft

**快速开始卡片：**
- 背景：slate-50
- Hover：slate-100
- 标题：font-medium
- 描述：text-sm text-slate-500

**最近模型列表：**
- 每项：上边框分隔
- 左侧：模型名称 + 数据集+时间
- 右侧：准确率（primary色，粗体）

---

### 3.2 训练页面 (Training)

**布局：垂直堆叠**

```
┌─────────────────────────────────────────────┐
│  数据上传卡片                                │
│  ┌─────────────────────────────────────┐    │
│  │     虚线边框拖拽区域                 │    │
│  │     📤 图标 + 文字                   │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  已上传文件显示（上传后）                    │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  任务配置卡片                                │
│  ┌──────────────┐  ┌──────────────┐         │
│  │ 任务类型 ▼   │  │ 目标列       │         │
│  └──────────────┘  └──────────────┘         │
│                                             │
│  选择模型                                   │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐               │
│  │RF  │ │XGB │ │LGBM│ │LogR│               │
│  └────┘ └────┘ └────┘ └────┘               │
└─────────────────────────────────────────────┘

           ┌─────────────────┐
           │   ▶ 开始训练    │  (主按钮，蓝色)
           └─────────────────┘

┌─────────────────────────────────────────────┐
│  训练进度卡片（训练中显示）                   │
│  ━━━━━━━━━━━━━━━━━░░░░░░░  67%              │
│                                             │
│     67      │    0.892     │    12s          │
│   当前迭代  │   准确率     │   已用时间       │
└─────────────────────────────────────────────┘
```

**文件上传区：**
- 边框：2px dashed border-slate-200
- Hover：border-primary-300
- 居中：Upload图标 + 文字
- 点击：触发文件选择

**下拉选择框：**
- 右侧 ChevronDown 图标
- appearance-none 移除默认样式

**模型选择按钮：**
- 默认：border-slate-200
- Hover：border-primary-500 + bg-primary-50

**开始训练按钮：**
- 尺寸：px-8 py-4 (大按钮)
- 圆角：rounded-2xl
- 停止状态：红色 bg-red-500

**进度条：**
- 高度：h-2
- 背景：bg-slate-100
- 填充：bg-primary-500，动画过渡

---

### 3.3 实验记录 (Experiments)

**布局：列表 + 详情**

```
┌─────────────────────────────────────────────┐
│  实验记录                          [🔄刷新] │
├─────────────────────────────────────────────┤
│  表格                                       │
│  ┌──────┬────┬──────┬──────┬────┬──────┐    │
│  │名称  │状态│准确率│F1分数│耗时│ 时间 │    │
│  ├──────┼────┼──────┼──────┼────┼──────┤    │
│  │Exp1  │✅  │94.2% │93.8% │45s │2小时 │    │
│  │Exp2  │🔄  │ —    │ —    │—   │运行中│    │
│  │Exp3  │❌  │ —    │ —    │—   │昨天  │    │
│  └──────┴────┴──────┴──────┴────┴──────┘    │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  实验详情（选中后显示）                       │
│  ┌─────────────────────────────────────┐    │
│  │ Experiment: RF-iris-baseline        │    │
│  │ Status: completed                    │    │
│  │ Model: RandomForestClassifier        │    │
│  │ Parameters:                          │    │
│  │   - n_estimators: 100               │    │
│  │   - max_depth: 10                   │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

**状态标签：**
```
完成: bg-emerald-50 text-emerald-700  ✅
失败: bg-red-50 text-red-700           ❌
运行中: bg-amber-50 text-amber-700     🔄
```

**表格行：**
- Hover：bg-slate-50
- 选中：bg-primary-50
- 光标：pointer

---

## 4. 组件规范

### 4.1 按钮 (Button)

```tsx
// Primary
<button className="bg-primary-600 text-white px-4 py-2 rounded-lg 
                   font-medium hover:bg-primary-700 active:bg-primary-800
                   disabled:opacity-50 disabled:cursor-not-allowed">

// Secondary
<button className="bg-slate-100 text-slate-700 px-4 py-2 rounded-lg
                   font-medium hover:bg-slate-200">

// Stop variant
<button className="bg-red-500 text-white px-8 py-4 rounded-2xl
                   font-semibold text-lg hover:bg-red-600">
```

### 4.2 输入框 (Input)

```tsx
<input className="w-full px-4 py-2.5 rounded-lg border border-slate-200 
                 focus:border-primary-500 focus:ring-2 focus:ring-primary-100
                 outline-none transition-all duration-150">
```

### 4.3 卡片 (Card)

```tsx
<div className="bg-white rounded-xl shadow-card p-6 
                hover:shadow-soft transition-all duration-200">
```

### 4.4 标签 (Badge)

```tsx
<span className="inline-flex items-center gap-1 px-2.5 py-1 
                rounded-full text-xs font-medium 
                bg-emerald-50 text-emerald-700">
```

---

## 5. 交互动效

### 5.1 过渡时长
- 快速交互：duration-150 (150ms)
- 标准过渡：duration-200 (200ms)
- 加载动画：duration-500 (500ms)

### 5.2 Hover效果
- 卡片：shadow-soft
- 按钮：背景色加深
- 表格行：bg-slate-50

### 5.3 加载状态
- 按钮禁用：opacity-50
- 进度条：rounded-full + 动画宽度变化
- 骨架屏：【后续阶段】

---

## 6. 技术实现要点

### 6.1 目录结构
```
frontend/
├── src/
│   ├── components/       # 可复用组件
│   │   ├── Card.tsx
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   └── Badge.tsx
│   ├── pages/            # 页面组件
│   │   ├── Dashboard.tsx
│   │   ├── Training.tsx
│   │   └── Experiments.tsx
│   ├── api/              # API 调用
│   │   └── index.ts
│   ├── hooks/            # 自定义 Hooks
│   │   └── useTraining.ts
│   ├── App.tsx
│   └── main.tsx
```

### 6.2 API 代理配置
```ts
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

### 6.3 状态管理
- 组件级状态：React useState
- 服务器状态：TanStack Query
- 表单状态：受控组件

---

*本设计方案为初版，后续可根据实际开发反馈调整*
