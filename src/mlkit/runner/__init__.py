"""
训练运行器 - Runner

统一训练流程：
- 数据准备
- 模型构建
- 训练循环
- 验证测试
- 日志与回调
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from mlkit.config import Config
from mlkit.data import DataLoader, Dataset
from mlkit.hooks import CheckpointHook, EarlyStoppingHook, Hook, LoggerHook
from mlkit.model import BaseModel, create_model


class Runner:
    """
    统一训练运行器

    管理训练全流程：
    - 构建环境
    - 训练循环
    - 验证测试
    - 回调执行
    """

    def __init__(self, config: Config, experiment: "Experiment | None" = None):
        """
        初始化 Runner

        Args:
            config: 配置对象
        """
        self.config = config
        self.model: BaseModel | None = None
        self.train_dataset: Dataset | None = None
        self.val_dataset: Dataset | None = None
        self.test_dataset: Dataset | None = None

        self.hooks: list[Hook] = []
        self.stop_training = False
        self.experiment: "Experiment | None" = experiment

        self.current_epoch = 0
        self.global_iter = 0

        # 训练历史
        self.train_history: list[dict] = []
        self.val_history: list[dict] = []

    def build(self):
        """构建训练环境"""
        # 1. 构建数据集
        self._build_datasets()

        # 2. 构建模型
        self._build_model()

        # 3. 注册默认 Hooks
        self._register_default_hooks()
        self._register_experiment_hook()

    def _build_datasets(self):
        """构建数据集"""
        # 从配置加载训练数据
        train_path = self.config.get("data.train_path")
        if train_path:
            loader = DataLoader(train_path)
            self.train_dataset = loader.load(
                target_column=self.config.get("data.target_column")
            )

        # 验证数据
        val_path = self.config.get("data.val_path")
        if val_path:
            loader = DataLoader(val_path)
            self.val_dataset = loader.load(
                target_column=self.config.get("data.target_column")
            )

        # 测试数据
        test_path = self.config.get("data.test_path")
        if test_path:
            loader = DataLoader(test_path)
            self.test_dataset = loader.load(
                target_column=self.config.get("data.target_column")
            )

    def _build_model(self):
        """构建模型"""
        model_type = self.config.get("model.type", "sklearn")

        model_kwargs = self.config.get("model", {}).copy()
        model_kwargs.pop("type", None)

        self.model = create_model(model_type, **model_kwargs)

    def _register_default_hooks(self):
        """注册默认 Hooks"""
        # 日志 Hook
        if self.config.get("hooks.logger", True):
            self.register_hook(
                LoggerHook(
                    log_dir=self.config.get("hooks.log_dir", "./logs"),
                    log_interval=self.config.get("hooks.log_interval", 10),
                )
            )

        # Checkpoint Hook
        if self.config.get("hooks.checkpoint", True):
            self.register_hook(
                CheckpointHook(
                    save_dir=self.config.get("hooks.save_dir", "./checkpoints"),
                    save_interval=self.config.get("hooks.save_interval", 1),
                    save_best=self.config.get("hooks.save_best", True),
                    monitor=self.config.get("hooks.monitor", "val_loss"),
                )
            )

        # Early Stopping Hook
        if self.config.get("hooks.early_stopping", False):
            self.register_hook(
                EarlyStoppingHook(
                    monitor=self.config.get("hooks.early_stopping_monitor", "val_loss"),
                    patience=self.config.get("hooks.early_stopping_patience", 10),
                    verbose=True,
                )
            )

    def _register_experiment_hook(self) -> None:
        """注册 Experiment 追踪 Hook（Continuous Learning 核心）

        当 Runner 初始化时传入了 Experiment 实例，自动注册 ExperimentTrackHook。
        """
        if self.experiment is None:
            return
        from mlkit.experiment.hook import ExperimentTrackHook
        monitor_metric = self.config.get("hooks.monitor", "val_loss")
        exp_hook = ExperimentTrackHook(self.experiment, monitor_metric=monitor_metric)
        self.register_hook(exp_hook)


    def register_hook(self, hook: Hook):
        """注册 Hook"""
        hook.set_runner(self)
        self.hooks.append(hook)

    def train(self) -> dict:
        """
        执行训练

        Returns:
            训练历史
        """
        # 触发 before_run
        for hook in self.hooks:
            hook.before_run(self)

        # 获取训练配置
        epochs = self.config.get("train.epochs", 10)
        batch_size = self.config.get("train.batch_size", None)
        val_interval = self.config.get("train.val_interval", 1)

        # 开始训练循环
        for epoch in range(epochs):
            if self.stop_training:
                break

            self.current_epoch = epoch

            # 触发 before_epoch
            for hook in self.hooks:
                hook.before_epoch(self, epoch)

            # 训练一个 epoch
            train_logs = self._train_epoch(epoch, batch_size)
            self.train_history.append(train_logs)

            # 验证
            if (
                val_interval > 0
                and (epoch + 1) % val_interval == 0
                and self.val_dataset
            ):
                val_logs = self._validate()
                self.val_history.append(val_logs)
                train_logs.update(val_logs)

            # 触发 after_epoch
            for hook in self.hooks:
                hook.after_epoch(self, epoch, train_logs)

        # 触发 after_run
        for hook in self.hooks:
            hook.after_run(self)

        return {"train_history": self.train_history, "val_history": self.val_history}

    def _train_epoch(self, epoch: int, batch_size: int | None = None) -> dict:
        """训练一个 epoch"""
        if not self.train_dataset:
            raise ValueError("Train dataset not found")

        X = self.train_dataset.X
        y = self.train_dataset.y

        logs = {"epoch": epoch}

        # 检查模型是否支持流式训练
        if batch_size and hasattr(self.model.model, "partial_fit"):
            # 流式训练
            from sklearn.utils import shuffle

            X, y = shuffle(X, y, random_state=epoch)

            n_samples = X.shape[0]
            classes = np.unique(y)

            for i in range(0, n_samples, batch_size):
                X_batch = X[i : i + batch_size]
                y_batch = y[i : i + batch_size]

                self.model.model.partial_fit(X_batch, y_batch, classes=classes)

                self.global_iter += 1

                # 触发 after_iter
                iter_logs = {"iter": self.global_iter, "epoch": epoch}
                for hook in self.hooks:
                    hook.after_iter(self, self.global_iter, iter_logs)
        else:
            # 常规训练
            self.model.fit(X, y)

            # 计算训练指标
            if hasattr(self.model, "score"):
                train_score = self.model.score(X, y)
                logs["train_loss"] = 1 - train_score
                logs["train_acc"] = train_score

        return logs

    def _validate(self) -> dict:
        """执行验证"""
        if not self.val_dataset:
            return {}

        # 触发 before_val
        for hook in self.hooks:
            hook.before_val(self)

        X_val = self.val_dataset.X
        y_val = self.val_dataset.y

        # 预测
        y_pred = self.model.predict(X_val)

        # 计算指标
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            precision_score,
            recall_score,
        )

        logs = {}

        # 分类指标
        if len(np.unique(y_val)) <= 10:  # 假设是分类
            logs["val_acc"] = accuracy_score(y_val, y_pred)
            logs["val_f1"] = f1_score(y_val, y_pred, average="weighted")
            logs["val_precision"] = precision_score(
                y_val, y_pred, average="weighted", zero_division=0
            )
            logs["val_recall"] = recall_score(
                y_val, y_pred, average="weighted", zero_division=0
            )
        else:
            # 回归指标
            from sklearn.metrics import (
                mean_absolute_error,
                mean_squared_error,
                r2_score,
            )

            logs["val_mse"] = mean_squared_error(y_val, y_pred)
            logs["val_mae"] = mean_absolute_error(y_val, y_pred)
            logs["val_r2"] = r2_score(y_val, y_pred)

        # 触发 after_val
        for hook in self.hooks:
            hook.after_val(self, logs)

        return logs

    def test(self) -> dict:
        """执行测试"""
        if not self.test_dataset:
            return {}

        X_test = self.test_dataset.X
        y_test = self.test_dataset.y

        y_pred = self.model.predict(X_test)

        # 计算指标
        from sklearn.metrics import accuracy_score, classification_report, f1_score

        results = {
            "test_acc": accuracy_score(y_test, y_pred),
            "test_f1": f1_score(y_test, y_pred, average="weighted"),
        }

        results["classification_report"] = classification_report(y_test, y_pred)

        return results

    def predict(self, X) -> np.ndarray:
        """使用训练好的模型进行预测"""
        if not self.model:
            raise ValueError("Model not trained yet")

        return self.model.predict(X)

    def predict_proba(self, X) -> np.ndarray:
        """预测概率"""
        if not self.model:
            raise ValueError("Model not trained yet")

        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        else:
            raise NotImplementedError("Model does not support predict_proba")

    def save_model(self, path: str | Path) -> None:
        """保存模型"""
        if not self.model:
            raise ValueError("Model not built")

        self.model.save(path)

    def load_model(self, path: str | Path) -> None:
        """加载模型"""
        if not self.model:
            self._build_model()

        self.model.load(path)

    def get_best_model(self) -> BaseModel:
        """获取最佳模型"""
        # 从 checkpoint 加载最佳模型
        save_dir = self.config.get("hooks.save_dir", "./checkpoints")
        best_path = Path(save_dir) / "best_model.pth"

        if best_path.exists():
            self.load_model(best_path)

        return self.model


def create_runner(config: Config | dict | str, experiment=None) -> Runner:
    """
    工厂函数：创建 Runner

    Args:
        config: Config 对象、字典或配置文件路径

    Returns:
        Runner 实例
    """
    if isinstance(config, str):
        # 从文件加载
        from mlkit.config import load_config

        config = load_config(config)
    elif isinstance(config, dict):
        config = Config.from_dict(config)

    if not isinstance(config, Config):
        raise ValueError(f"Invalid config type: {type(config)}")

    runner = Runner(config, experiment=experiment)
    runner.build()

    return runner
