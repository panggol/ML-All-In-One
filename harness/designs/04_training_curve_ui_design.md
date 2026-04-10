# ML All In One - 训练曲线可视化 UI 设计

**项目：** ML All In One  
**模块：** 训练曲线可视化（Phase 4）  
**日期：** 2026-04-10  
**状态：** 设计完成

---

## 一、模块概述

训练曲线可视化模块展示模型训练过程中的指标变化，帮助用户判断模型收敛情况、过拟合/欠拟合状态，从而决定是否调整超参数或提前停止训练。

---

## 二、API 接口

### 获取训练曲线
```
GET /api/viz/experiments/{experiment_id}/training-curves

Response:
{
  "experiment_id": 1,
  "epochs": [1, 2, 3, ..., 100],
  "curves": [
    { "name": "train_loss", "values": [...] },
    { "name": "val_loss", "values": [...] },
    { "name": "train_accuracy", "values": [...] },
    { "name": "val_accuracy", "values": [...] }
  ]
}
```

### 获取图表 PNG
```
GET /api/viz/experiments/{experiment_id}/chart/loss_curve
→ PNG 图片
```

---

## 三、页面布局

```
┌─────────────────────────────────────────────────────────────┐
│ Page Header                                                  │
│ 「训练曲线」实验选择下拉 + 刷新按钮                            │
├─────────────────────────────────────────────────────────────┤
│ Metric Tabs: [Loss] [Accuracy] [All]                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Loss 曲线图表（Recharts LineChart）                        │
│   - train_loss（实线，#6366f1）                              │
│   - val_loss（虚线，#f59e0b）                               │
│   - 悬停显示：Epoch / 值 / 与上轮差值                         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Metric Summary Cards                                         │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│ │ 最终train_loss│ │ 最终val_loss │ │ Best val_loss │        │
│ │ 0.0234        │ │ 0.0312       │ │ 0.0289        │        │
│ └──────────────┘ └──────────────┘ └──────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、组件 Props

### TrainingCurvesChart Props
```typescript
interface TrainingCurvesChartProps {
  data: {
    epochs: number[];
    curves: Array<{ name: string; values: number[] }>;
  };
  metrics?: ('loss' | 'accuracy' | 'all')[];
  loading?: boolean;
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
}
```

### ChartCard Props（同前文复用）

---

## 五、颜色规范

| 曲线 | 颜色 | 样式 |
|------|------|------|
| train_loss | #6366f1（indigo-500） | 实线，2px |
| val_loss | #f59e0b（amber-500） | 虚线，2px |
| train_accuracy | #10b981（emerald-500） | 实线，2px |
| val_accuracy | #ec4899（pink-500） | 虚线，2px |

---

## 六、实现清单

- [ ] `TrainingCurvesChart` 组件（Recharts LineChart）
- [ ] Experiment 选择器 + 刷新
- [ ] Metric Tabs（Loss / Accuracy / All）
- [ ] Metric Summary Cards
- [ ] 接入 `/api/viz/experiments/{id}/training-curves`
- [ ] E2E 测试

---

*文档版本：v1.0.0 | 最后更新：2026-04-10*
