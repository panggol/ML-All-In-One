"""
Hooks 机制 - Lifecycle Hooks

提供训练过程的扩展点：
- 日志记录
- 模型保存
- 评估
- 学习率调度
- 早停

Harness Engineering 理念：
- Hook 是核心循环的外部扩展点，不改核心逻辑
- 支持 Pre/Post 分离配置
- 配置驱动注册
"""

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Protocol


class Hook(ABC):
    """Hook 基类

    所有 Hook 都通过继承此类实现。
    每个方法对应一个生命周期事件。
    子类可以只重写需要关注的事件，其他方法留空。
    """

    # 设置为 True 时，该 Hook 会在触发后从队列中移除（一次性 Hook）
    one_shot: bool = False

    def set_runner(self, runner: "Runner") -> None:
        """绑定 Runner 实例"""
        self.runner = runner

    # ── Run 生命周期 ──────────────────────────────────────────

    def before_run(self, runner: "Runner") -> None:
        """训练开始前调用"""
        pass

    def after_run(self, runner: "Runner") -> None:
        """训练结束后调用"""
        pass

    # ── Epoch 生命周期 ────────────────────────────────────────

    def before_epoch(self, runner: "Runner", epoch: int) -> None:
        """每个 epoch 开始前调用"""
        pass

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        """每个 epoch 结束后调用"""
        pass

    # ── Iteration 生命周期 ──────────────────────────────────

    def before_iter(self, runner: "Runner", iter: int) -> None:
        """每次迭代开始前调用"""
        pass

    def after_iter(self, runner: "Runner", iter: int, logs: dict) -> None:
        """每次迭代结束后调用"""
        pass

    # ── Validation 生命周期 ─────────────────────────────────

    def before_val(self, runner: "Runner") -> None:
        """验证开始前调用"""
        pass

    def after_val(self, runner: "Runner", logs: dict) -> None:
        """验证结束后调用"""
        pass


# ── 预置 Hook 实现 ──────────────────────────────────────────


class LoggerHook(Hook):
    """日志记录 Hook

    在每个迭代结束后记录关键指标到 JSON 文件。

    用法:
        hook = LoggerHook(log_dir="./logs", log_interval=10)
        runner.register_hook(hook)
    """

    def __init__(
        self,
        log_dir: str = "./logs",
        log_interval: int = 10,
        metrics: list[str] | None = None,
    ):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_interval = log_interval
        self.metrics = metrics  # None 表示记录所有指标
        self.logs: list[dict] = []
        self._run_count = 0

    def before_run(self, runner: "Runner") -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logs = []
        self._run_count += 1

    def after_iter(self, runner: "Runner", iter: int, logs: dict) -> None:
        if iter % self.log_interval == 0:
            entry: dict[str, Any] = {
                "iter": iter,
                "run": self._run_count,
                "timestamp": time.time(),
            }
            # 按 metrics 过滤
            if self.metrics:
                entry.update({k: v for k, v in logs.items() if k in self.metrics})
            else:
                entry.update(logs)
            self.logs.append(entry)

    def after_run(self, runner: "Runner") -> None:
        if self.logs:
            log_file = self.log_dir / f"run_{self._run_count}_{int(time.time())}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, indent=2, ensure_ascii=False)


class CheckpointHook(Hook):
    """模型保存 Hook

    支持：
    - 定期保存（每 N 个 epoch）
    - 保存最佳模型（按监控指标）
    - 最多保留 N 个 checkpoint

    用法:
        hook = CheckpointHook(save_dir="./checkpoints", save_interval=1,
                              save_best=True, monitor="val_loss")
        runner.register_hook(hook)
    """

    def __init__(
        self,
        save_dir: str = "./checkpoints",
        save_interval: int = 1,
        save_best: bool = True,
        monitor: str = "val_loss",
        mode: str = "min",
        max_keep: int = 5,
    ):
        super().__init__()
        self.save_dir = Path(save_dir)
        self.save_interval = save_interval
        self.save_best = save_best
        self.monitor = monitor
        self.mode = mode  # 'min' 或 'max'
        self.max_keep = max_keep

        # 状态
        self.best_score: float | None = None
        self.saved_checkpoints: list[Path] = []

    def before_run(self, runner: "Runner") -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        if self.mode == "min":
            self.best_score = float("inf")
        else:
            self.best_score = float("-inf")

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        # 定期保存
        if epoch % self.save_interval == 0:
            self._save_checkpoint(runner, epoch, logs, is_best=False)

        # 保存最佳模型
        if self.save_best and self.monitor in logs:
            current = logs[self.monitor]
            is_best = self._is_improved(current)

            if is_best:
                if self.mode == "min":
                    self.best_score = min(self.best_score or float("inf"), current)
                else:
                    self.best_score = max(self.best_score or float("-inf"), current)
                self._save_checkpoint(runner, epoch, logs, is_best=True)

    def _is_improved(self, current: float) -> bool:
        if self.best_score is None:
            return True
        if self.mode == "min":
            return current < self.best_score
        return current > self.best_score

    def _save_checkpoint(
        self, runner: "Runner", epoch: int, logs: dict, *, is_best: bool
    ) -> None:
        if not hasattr(runner, "model") or runner.model is None:
            return

        model = runner.model
        save_path = self.save_dir / ("best_model.pth" if is_best else f"epoch_{epoch}.pth")

        if hasattr(model, "save"):
            model.save(save_path)

        if not is_best:
            self.saved_checkpoints.append(save_path)
            # 清理旧 checkpoint
            while len(self.saved_checkpoints) > self.max_keep:
                old = self.saved_checkpoints.pop(0)
                if old.exists() and "best" not in old.name:
                    old.unlink()


class EarlyStoppingHook(Hook):
    """早停 Hook

    监控指定指标，连续 N 个 epoch 没有改善则停止训练。

    用法:
        hook = EarlyStoppingHook(monitor="val_loss", patience=10,
                                mode="min", min_delta=0.001)
        runner.register_hook(hook)
    """

    def __init__(
        self,
        monitor: str = "val_loss",
        patience: int = 10,
        mode: str = "min",
        min_delta: float = 0.0,
        verbose: bool = True,
    ):
        super().__init__()
        self.monitor = monitor
        self.patience = patience
        self.mode = mode  # 'min' 或 'max'
        self.min_delta = min_delta
        self.verbose = verbose

        self.best_score: float | None = None
        self.best_epoch: int = 0
        self.wait: int = 0
        self.stopped_epoch: int = 0
        self.triggered: bool = False

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        if self.monitor not in logs:
            return

        current = logs[self.monitor]

        # 首次，记录初始值
        if self.best_score is None:
            self.best_score = current
            self.best_epoch = epoch
            return

        # 判断是否改善
        if self.mode == "min":
            improved = current < self.best_score - self.min_delta
        else:
            improved = current > self.best_score + self.min_delta

        if improved:
            self.best_score = current
            self.best_epoch = epoch
            self.wait = 0
        else:
            self.wait += 1
            if self.wait >= self.patience:
                self.stopped_epoch = epoch
                self.triggered = True
                if self.verbose:
                    print(
                        f"[EarlyStopping] 触发于 epoch {epoch}，"
                        f"最佳 epoch={self.best_epoch}，"
                        f"最佳 {self.monitor}={self.best_score:.4f}"
                    )
                if hasattr(runner, "stop_training"):
                    runner.stop_training = True

    def reset(self) -> None:
        """重置早停状态，用于新的训练周期"""
        self.best_score = None
        self.best_epoch = 0
        self.wait = 0
        self.stopped_epoch = 0
        self.triggered = False


class EvalHook(Hook):
    """评估 Hook

    在每个 epoch 后执行验证集评估。

    用法:
        hook = EvalHook(val_data=val_dataset, interval=1)
        runner.register_hook(hook)
    """

    def __init__(
        self,
        val_data: Any = None,
        interval: int = 1,
        metrics: list[str] | None = None,
    ):
        super().__init__()
        self.val_data = val_data
        self.interval = interval
        self.metrics = metrics or ["accuracy", "loss"]
        self.eval_results: list[dict] = []

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        if epoch % self.interval != 0:
            return

        if self.val_data is None and hasattr(runner, "val_data"):
            self.val_data = runner.val_data

        if self.val_data is None:
            return

        # 执行评估（具体实现由子类或外部注入）
        result = self._evaluate(runner, epoch)
        self.eval_results.append(result)
        logs.update({f"val_{k}": v for k, v in result.items()})

    def _evaluate(self, runner: "Runner", epoch: int) -> dict:
        """可被子类重写的评估逻辑"""
        return {"accuracy": 0.0, "loss": 0.0}


class LearningRateHook(Hook):
    """学习率调度 Hook

    在每个 epoch 后更新学习率。

    用法:
        from torch.optim.lr_scheduler import StepLR
        scheduler = StepLR(optimizer, step_size=10, gamma=0.1)
        hook = LearningRateHook(scheduler=scheduler, monitor="val_loss")
        runner.register_hook(hook)
    """

    def __init__(
        self,
        scheduler: Any = None,
        monitor: str | None = None,
        frequency: str = "epoch",
    ):
        super().__init__()
        self.scheduler = scheduler
        self.monitor = monitor
        self.frequency = frequency  # 'epoch' 或 'iter'

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        if self.scheduler is None:
            return

        if self.frequency != "epoch":
            return

        if self.monitor and self.monitor in logs:
            self.scheduler.step(logs[self.monitor])
        else:
            self.scheduler.step()

    def after_iter(self, runner: "Runner", iter: int, logs: dict) -> None:
        if self.scheduler is None or self.frequency != "iter":
            return

        if self.monitor and self.monitor in logs:
            self.scheduler.step(logs[self.monitor])
        else:
            self.scheduler.step()


class IterTimerHook(Hook):
    """迭代计时 Hook

    记录每个 epoch 和 iter 的耗时。
    """

    def __init__(self):
        super().__init__()
        self.epoch_start: float = 0.0
        self.iter_times: list[float] = []

    def before_epoch(self, runner: "Runner", epoch: int) -> None:
        self.epoch_start = time.time()
        self.iter_times = []

    def after_iter(self, runner: "Runner", iter: int, logs: dict) -> None:
        self.iter_times.append(time.time())
        if len(self.iter_times) >= 2:
            logs["iter_time"] = self.iter_times[-1] - self.iter_times[-2]

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        logs["epoch_time"] = time.time() - self.epoch_start


class ExperimentTrackHook(Hook):
    """实验追踪 Hook

    将每次 epoch 的指标自动记录到 Experiment 系统。
    这是 Continuous Learning 的基础设施：
    每次训练 → 历史数据 → 提取模式 → 指导未来实验

    用法:
        from mlkit.experiment import ExperimentManager
        manager = ExperimentManager("./experiments")
        exp = manager.create_experiment("lr-sweep-v1", params={"lr": 0.001})

        hook = ExperimentTrackHook(exp)
        runner.register_hook(hook)

        # 训练结束后，实验数据已自动记录
        manager.save_experiment(exp)
    """

    def __init__(self, experiment: "Experiment", monitor_metric: str | None = None):
        """
        Args:
            experiment: Experiment 实例
            monitor_metric: 要记录到 best_metrics 的指标名
        """
        super().__init__()
        self.experiment = experiment
        self.monitor_metric = monitor_metric
        self.current_epoch = 0

    def before_epoch(self, runner: "Runner", epoch: int) -> None:
        self.current_epoch = epoch

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        """每个 epoch 结束后，将所有指标记录到 Experiment"""
        for metric_name, value in logs.items():
            if isinstance(value, (int, float)):
                self.experiment.record_metric(metric_name, float(value), epoch)

        # 标记最佳指标
        if self.monitor_metric and self.monitor_metric in logs:
            current = float(logs[self.monitor_metric])
            name = self.monitor_metric
            if name not in self.experiment.best_metrics:
                self.experiment.best_metrics[name] = current
            elif current < self.experiment.best_metrics[name]:
                self.experiment.best_metrics[name] = current

    def after_run(self, runner: "Runner") -> None:
        """训练结束后，更新最终指标并标记完成"""
        # 从 Runner 的 train_history/val_history 取最终值
        if hasattr(runner, "train_history") and runner.train_history:
            last = runner.train_history[-1]
            for k, v in last.items():
                if isinstance(v, (int, float)):
                    self.experiment.final_metrics[k] = float(v)
        if hasattr(runner, "val_history") and runner.val_history:
            last = runner.val_history[-1]
            for k, v in last.items():
                if isinstance(v, (int, float)):
                    self.experiment.final_metrics[k] = float(v)
        self.experiment.finish(status="completed" if not getattr(runner, "stop_training", False) else "interrupted")


# ── Callback 管理器 ──────────────────────────────────────────


class Callback:
    """Hook 容器和管理器

    负责：
    - 注册 Hook
    - 按生命周期顺序触发事件
    - 支持 one-shot Hook 的自动移除

    Harness Engineering 核心理念：
    - 所有扩展通过 Hook 注入，不改核心循环
    - Hook 按优先级排序执行
    - one-shot Hook 执行后自动清理

    用法:
        callback = Callback()
        callback.register_hook(LoggerHook())
        callback.register_hook(CheckpointHook(), priority=10)

        callback.trigger("before_run", runner)
    """

    # 支持的生命周期事件（与 Hook 基类方法一一对应）
    EVENTS = [
        "before_run",
        "before_epoch",
        "before_iter",
        "before_val",
        "after_val",
        "after_iter",
        "after_epoch",
        "after_run",
    ]

    def __init__(self):
        # 每个事件对应一个 Hook 列表，按 priority 降序排列
        self._hooks: dict[str, list[tuple[int, Hook]]] = {e: [] for e in self.EVENTS}
        # 缓存已移除的 Hook（避免迭代中修改）
        self._to_remove: set[Hook] = set()

    def register_hook(self, hook: Hook, priority: int = 0) -> None:
        """注册一个 Hook

        Args:
            hook: Hook 实例
            priority: 优先级，数值越大越先执行（默认 0）
        """
        for event in self.EVENTS:
            # 只有 Hook 类或其子类实际定义了（非空）方法才注册
            if event in self._hook_methods(hook):
                self._hooks[event].append((priority, hook))
        # 按优先级降序排列
        for event in self.EVENTS:
            self._hooks[event].sort(key=lambda x: x[0], reverse=True)

    def _hook_methods(self, hook: Hook) -> set[str]:
        """返回 Hook 实例实际定义了方法的事件集合"""
        return {
            event
            for event in self.EVENTS
            if getattr(type(hook), event, None) is not getattr(Hook, event, None)
            or getattr(hook, event).__func__ is not getattr(Hook, event, None)
        }

    def trigger(self, event: str, *args: Any, **kwargs: Any) -> None:
        """触发指定生命周期事件

        Args:
            event: 事件名（如 "before_epoch"）
            *args, **kwargs: 传递给 Hook 方法的参数
        """
        if event not in self._hooks:
            return

        for _, hook in self._hooks[event]:
            if hook in self._to_remove:
                continue

            try:
                method = getattr(hook, event, None)
                if callable(method):
                    method(*args, **kwargs)

                    # one-shot Hook 执行后标记移除
                    if hook.one_shot:
                        self._to_remove.add(hook)
            except Exception as e:
                # Hook 执行出错不影响主流程，打印警告
                print(f"[Callback] Hook {hook.__class__.__name__}.{event} 错误: {e}")

        # 清理已标记的 Hook
        if self._to_remove:
            for event in self.EVENTS:
                self._hooks[event] = [
                    (p, h) for p, h in self._hooks[event] if h not in self._to_remove
                ]
            self._to_remove.clear()

    def remove_hook(self, hook: Hook) -> None:
        """移除指定 Hook"""
        for event in self.EVENTS:
            self._hooks[event] = [
                (p, h) for p, h in self._hooks[event] if h is not hook
            ]

    def clear(self) -> None:
        """清空所有 Hook"""
        for event in self.EVENTS:
            self._hooks[event].clear()

    def summary(self) -> dict[str, int]:
        """返回各事件注册的 Hook 数量"""
        return {event: len(hooks) for event, hooks in self._hooks.items()}
