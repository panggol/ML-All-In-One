"""
Experiment 集成 Hook

将 Hook System 和 Experiment System 连接的桥梁。
Harness Engineering 核心理念：Continuous Learning

每次训练的结果都值得记录，形成组织的"记忆"。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mlkit.experiment import Experiment
    from mlkit.runner import Runner


class ExperimentTrackHook:
    """实验追踪 Hook

    将每次 epoch 的指标自动记录到 Experiment 系统。

    这是 Continuous Learning 的核心基础设施：
    每次训练 → 历史实验数据 → 提取模式 → 指导未来实验

    用法:
        from mlkit.experiment import ExperimentManager, ExperimentTrackHook
        manager = ExperimentManager("./experiments")
        exp = manager.create_experiment("lr-sweep-v1", params={"lr": 0.001})

        hook = ExperimentTrackHook(exp, monitor_metric="val_loss")
        runner.register_hook(hook)

        # 训练结束后，实验数据已自动记录
        manager.save_experiment(exp)
    """

    one_shot = False  # 重要：告诉 Callback 这是持久 Hook

    def __init__(
        self,
        experiment: "Experiment",
        monitor_metric: str | None = None,
    ):
        """
        Args:
            experiment: Experiment 实例（由 ExperimentManager.create_experiment 创建）
            monitor_metric: 监控的指标名，用于追踪最佳值
        """
        self.experiment = experiment
        self.monitor_metric = monitor_metric
        self._runner: "Runner | None" = None

    def set_runner(self, runner: "Runner") -> None:
        """绑定 Runner 实例（Harness Engineering Hook 规范）"""
        self._runner = runner

    @property
    def runner(self) -> "Runner":
        if self._runner is None:
            raise RuntimeError("ExperimentTrackHook 未绑定 Runner，请先调用 register_hook")
        return self._runner

    def before_epoch(self, runner: "Runner", epoch: int) -> None:
        """每个 epoch 开始前调用"""
        pass

    def after_epoch(self, runner: "Runner", epoch: int, logs: dict) -> None:
        """每个 epoch 结束后，将所有指标记录到 Experiment

        Continuous Learning 的核心：每次训练结果都被持久化
        """
        for metric_name, value in logs.items():
            if isinstance(value, (int, float)):
                self.experiment.record_metric(metric_name, float(value), epoch)

        # 追踪最佳指标
        if self.monitor_metric and self.monitor_metric in logs:
            current = float(logs[self.monitor_metric])
            name = self.monitor_metric
            if name not in self.experiment.best_metrics:
                self.experiment.best_metrics[name] = current
            elif current < self.experiment.best_metrics[name]:
                self.experiment.best_metrics[name] = current

    def after_run(self, runner: "Runner") -> None:
        """训练结束后，更新最终指标并标记完成

        这是 Continuous Learning 的"学习"时刻：
        实验完成 → 数据沉淀 → 可供未来参考
        """
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

        status = (
            "completed"
            if not getattr(runner, "stop_training", False)
            else "interrupted"
        )
        self.experiment.finish(status=status)
