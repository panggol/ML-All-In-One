"""
Hooks 机制 - Lifecycle Hooks

提供训练过程的扩展点：
- 日志记录
- 模型保存
- 评估
- 学习率调度
- 早停
"""

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, Optional


class Hook(ABC):
    """Hook 基类"""

    def __init__(self):
        self.runner = None

    def set_runner(self, runner):
        """绑定 Runner"""
        self.runner = runner

    def before_run(self, runner):
        """训练开始前调用"""
        pass

    def after_run(self, runner):
        """训练结束后调用"""
        pass

    def before_epoch(self, runner, epoch: int):
        """每个 epoch 开始前调用"""
        pass

    def after_epoch(self, runner, epoch: int, logs: dict):
        """每个 epoch 结束后调用"""
        pass

    def before_iter(self, runner, iter: int):
        """每次迭代开始前调用"""
        pass

    def after_iter(self, runner, iter: int, logs: dict):
        """每次迭代结束后调用"""
        pass

    def before_val(self, runner):
        """验证开始前调用"""
        pass

    def after_val(self, runner, logs: dict):
        """验证结束后调用"""
        pass


class LoggerHook(Hook):
    """日志记录 Hook"""

    def __init__(self, log_dir: str = "./logs", log_interval: int = 10):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_interval = log_interval
        self.logs = []

    def before_run(self, runner):
        """创建日志目录"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logs = []

    def after_iter(self, runner, iter: int, logs: dict):
        """记录迭代日志"""
        if iter % self.log_interval == 0:
            log_entry = {
                "iter": iter,
                "epoch": (
                    runner.current_epoch if hasattr(runner, "current_epoch") else 0
                ),
                "timestamp": time.time(),
                **logs,
            }
            self.logs.append(log_entry)

    def after_run(self, runner):
        """保存日志到文件"""
        if self.logs:
            log_file = self.log_dir / f"train_{int(time.time())}.json"
            with open(log_file, "w") as f:
                json.dump(self.logs, f, indent=2)


class CheckpointHook(Hook):
    """模型保存 Hook"""

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
        self.mode = mode  # 'min' or 'max'
        self.max_keep = max_keep

        self.best_score = float("inf") if mode == "min" else float("-inf")
        self.saved_checkpoints = []

    def before_run(self, runner):
        """创建保存目录"""
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def after_epoch(self, runner, epoch: int, logs: dict):
        """保存 checkpoint"""
        # 定期保存
        if epoch % self.save_interval == 0:
            self._save_checkpoint(runner, epoch, logs, is_best=False)

        # 保存最佳模型
        if self.save_best and self.monitor in logs:
            current_score = logs[self.monitor]
            is_best = (self.mode == "min" and current_score < self.best_score) or (
                self.mode == "max" and current_score > self.best_score
            )

            if is_best:
                self.best_score = current_score
                self._save_checkpoint(runner, epoch, logs, is_best=True)

    def _save_checkpoint(self, runner, epoch: int, logs: dict, is_best: bool = False):
        """保存检查点"""
        # 调用模型的 save 方法
        if hasattr(runner, "model"):
            if is_best:
                save_path = self.save_dir / "best_model.pth"
            else:
                save_path = self.save_dir / f"epoch_{epoch}.pth"

            if hasattr(runner.model, "save"):
                runner.model.save(save_path)

            self.saved_checkpoints.append(save_path)

            # 清理旧 checkpoint
            if len(self.saved_checkpoints) > self.max_keep:
                old_path = self.saved_checkpoints.pop(0)
                if old_path.exists() and "best" not in str(old_path):
                    old_path.unlink()


class EvalHook(Hook):
    """评估 Hook"""

    def __init__(self, val_data, interval: int = 1, metrics: list | None = None):
        super().__init__()
        self.val_data = val_data
        self.interval = interval
        self.metrics = metrics or ["accuracy"]

    def before_val(self, runner):
        """验证前准备"""
        pass

    def after_val(self, runner, logs: dict):
        """验证后记录结果"""
        pass


class EarlyStoppingHook(Hook):
    """早停 Hook"""

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
        self.mode = mode
        self.min_delta = min_delta
        self.verbose = verbose

        self.best_score = float("inf") if mode == "min" else float("-inf")
        self.wait = 0
        self.stopped_epoch = 0

    def after_epoch(self, runner, epoch: int, logs: dict):
        """检查是否需要早停"""
        if self.monitor not in logs:
            return

        current = logs[self.monitor]

        # 检查是否改善
        if self.mode == "min":
            improved = current < (self.best_score - self.min_delta)
        else:
            improved = current > (self.best_score + self.min_delta)

        if improved:
            self.best_score = current
            self.wait = 0
        else:
            self.wait += 1
            if self.wait >= self.patience:
                self.stopped_epoch = epoch
                if self.verbose:
                    print(f"Early stopping triggered at epoch {epoch}")
                runner.stop_training = True


class LearningRateHook(Hook):
    """学习率调度 Hook"""

    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler

    def after_epoch(self, runner, epoch: int, logs: dict):
        """更新学习率"""
        if self.scheduler:
            # 根据指标更新
            if hasattr(self.scheduler, "step"):
                if hasattr(self.scheduler, "metric") and self.scheduler.metric in logs:
                    self.scheduler.step(logs[self.scheduler.metric])
                else:
                    self.scheduler.step()


class IterTimerHook(Hook):
    """迭代计时 Hook"""

    def __init__(self):
        super().__init__()
        self.iter_times = []
        self.epoch_start_time = None

    def before_epoch(self, runner, epoch: int):
        """记录 epoch 开始时间"""
        self.epoch_start_time = time.time()

    def after_iter(self, runner, iter: int, logs: dict):
        """记录迭代时间"""
        if "time" not in logs:
            logs["iter_time"] = time.time() - (
                self.iter_times[-1] if self.iter_times else self.epoch_start_time
            )

        self.iter_times.append(time.time())

    def after_epoch(self, runner, epoch: int, logs: dict):
        """记录 epoch 耗时"""
        if self.epoch_start_time:
            logs["epoch_time"] = time.time() - self.epoch_start_time


class Callback:
    """回调函数容器"""

    def __init__(self):
        self.hooks: dict[str, list] = {
            "before_run": [],
            "after_run": [],
            "before_epoch": [],
            "after_epoch": [],
            "before_iter": [],
            "after_iter": [],
            "before_val": [],
            "after_val": [],
        }

    def register_hook(self, hook: Hook):
        """注册 Hook"""
        # 将 hook 注册到所有事件
        for event in self.hooks.keys():
            if hasattr(hook, event.replace("_", "_")):
                self.hooks[event].append(hook)

    def trigger(self, event: str, *args, **kwargs):
        """触发事件"""
        for hook in self.hooks.get(event, []):
            method_name = event.replace("_", "_")
            if hasattr(hook, method_name):
                getattr(hook, method_name)(*args, **kwargs)
