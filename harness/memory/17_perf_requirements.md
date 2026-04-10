# ML All In One — 性能监控模块需求文档

_Version: 1.0_
_Date: 2026-04-10_
_Author: 需求分析 Agent_

---

## 1. 概述

ML All In One 缺乏系统级性能监控能力，用户无法感知训练过程中的资源消耗和效率变化。性能监控模块在训练运行时实时采集系统资源指标，帮助用户：
- 判断是否 GPU 绑颈 / 内存不足
- 评估训练效率（样本/秒、epoch/秒）
- 预估剩余训练时间
- 为环境扩容和超参数调优提供数据依据

---

## 2. 功能需求

### 2.1 资源指标采集

#### 2.1.1 CPU 监控
- CPU 使用率（总览 + 每核）
- 采样频率：每 5 秒一次
- 展示格式：百分比 + 折线图

#### 2.1.2 内存监控
- 已用内存 / 总内存
- 内存使用增长率
- 采样频率：每 5 秒一次
- 展示格式：MB/GB + 折线图

#### 2.1.3 GPU 监控（条件触发）
- 仅在 `CUDA_VISIBLE_DEVICES` 存在时采集
- GPU 使用率 / 显存使用量
- 采样频率：每 5 秒一次
- 展示格式：百分比 + 折线图

#### 2.1.4 训练速度
- 样本/秒（samples/sec）
- Epoch/秒
- 预估剩余时间（ETA）
- 基于最近 10 次迭代滚动平均

### 2.2 性能指标记录

- 训练开始/结束时间，总耗时
- 每个 epoch 的平均 speed（samples/sec）
- 峰值内存使用量
- 峰值 CPU/GPU 使用率
- 所有指标存入 experiment metrics

### 2.3 Hook 集成

- `PerformanceMonitorHook`：自动注册到 Runner，跟踪整个训练过程
- 使用 `psutil` 采集系统指标
- 使用 `torch.cuda` 采集 GPU 指标（如可用）
- 指标通过 LoggerHook 实时输出到训练日志

---

## 3. 非功能需求

- 监控开销 < 1% CPU 时间（异步采集，不阻塞训练）
- 内存占用稳定，不随训练时长累积
- GPU 不可用时不报错，降级为 CPU-only 模式
- 支持 fork/multiprocessing 安全（训练子进程内采集）

---

## 4. 接口设计

```python
from mlkit.hooks import PerformanceMonitorHook

# 使用方式
hook = PerformanceMonitorHook(
    interval=5,        # 采样间隔（秒）
    log_to_stdout=True,  # 是否输出到 stdout
    record_to_experiment=True  # 是否记录到 Experiment
)
runner.register_hook(hook, priority=5)
```

### 输出格式示例

```
[Performance] Epoch 3 | CPU: 78% | Mem: 4.2/16.0 GB (26%) | GPU: 65% | Speed: 1420 samples/s | ETA: 4m 23s
```

---

## 5. 指标存储

| 字段 | 类型 | 说明 |
|------|------|------|
| cpu_avg | float | 平均 CPU 使用率 |
| cpu_peak | float | 峰值 CPU 使用率 |
| memory_peak_gb | float | 峰值内存（GB） |
| gpu_avg | float | 平均 GPU 使用率 |
| gpu_peak | float | 峰值 GPU 使用率 |
| speed_avg | float | 平均训练速度（samples/s） |
| total_time_s | float | 总训练时长（秒） |

---

## 6. 技术选型

- `psutil`（跨平台系统指标）
- `torch.cuda`（GPU 指标，可选）
- 异步线程采集（不阻塞训练循环）

---

*文档版本：v1.0.0 | 最后更新： 2026-04-10*
