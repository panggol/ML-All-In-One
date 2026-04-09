# ML All In One - React Frontend

简约现代风格的机器学习平台前端界面。

## 技术栈

- **框架：** React 18 + TypeScript
- **构建工具：** Vite
- **样式：** TailwindCSS
- **图表：** Recharts
- **图标：** Lucide React
- **HTTP：** Axios + TanStack Query

## 快速开始

```bash
# 安装依赖
cd frontend
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

## 项目结构

```
frontend/
├── src/
│   ├── components/       # UI组件
│   │   ├── Button.tsx     # 按钮
│   │   ├── Card.tsx       # 卡片
│   │   ├── Badge.tsx      # 状态标签
│   │   ├── Input.tsx      # 输入框
│   │   ├── Select.tsx     # 下拉选择
│   │   ├── ProgressBar.tsx # 进度条
│   │   └── StatCard.tsx   # 统计卡片
│   ├── pages/             # 页面
│   │   ├── Dashboard.tsx  # 仪表盘
│   │   ├── Training.tsx   # 训练页面
│   │   └── Experiments.tsx # 实验记录
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## 页面说明

### 仪表盘 (Dashboard)
- 系统统计（训练次数、活跃实验、运行时长、最优模型）
- 快速入口（上传数据、自动ML、模型预测）
- 最近模型列表
- 系统状态监控

### 模型训练 (Training)
- CSV文件上传（拖拽支持）
- 任务配置（分类/回归、目标列、模型选择）
- 训练控制（开始/停止）
- 实时进度展示

### 实验记录 (Experiments)
- 实验列表表格
- 状态标签（完成/失败/运行中）
- 实验详情查看

## 设计规范

### 色彩
- 主色：Primary (#0ea5e9)
- 成功：Emerald (#10b981)
- 警告：Amber (#f59e0b)
- 错误：Red (#ef4444)

### 圆角
- 卡片：12px (rounded-xl)
- 按钮/输入框：8px (rounded-lg)
- 大按钮：16px (rounded-2xl)

## 开发说明

### API代理
开发环境下，Vite 配置了 `/api` 代理到 `http://localhost:8000`。

### 添加新组件
1. 在 `src/components/` 创建组件文件
2. 导出到 `src/components/index.ts`
3. 在页面中导入使用

## License

MIT
