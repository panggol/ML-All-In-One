"""
训练配置

@dataclass
class TrainingConfig(BaseConfig):
    # 训练参数
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    optimizer: str = "adam"          # adam / sgd / adamw
    scheduler: str | None = None      # step / cosine / none
    scheduler_params: dict = field(default_factory=dict)

    # 早停
    early_stopping: bool = True
    early_stopping_patience: int = 10
    early_stopping_monitor: str = "val_loss"
    early_stopping_mode: str = "min"
    early_stopping_min_delta: float = 0.0

    # 模型保存
    checkpoint_enabled: bool = True
    checkpoint_dir: str = "./checkpoints"
    checkpoint_save_interval: int = 1
    checkpoint_save_best: bool = True
    checkpoint_max_keep: int = 5

    # 数据
    num_workers: int = 4
    pin_memory: bool = True
    shuffle: bool = True

    # 随机种子
    seed: int = 42

    # 验证
    val_interval: int = 1
    log_interval: int = 10

    # 设备
    device: str = "auto"              # auto / cpu / cuda / mps

    # 实验追踪
    experiment_name: str = "default_exp"
    experiment_dir: str = "./experiments"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrainingConfig:
    """训练配置"""

    # 训练参数
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    optimizer: str = "adam"
    weight_decay: float = 0.0
    momentum: float = 0.9
    scheduler: str | None = None  # step / cosine / exponential / none
    scheduler_params: dict = field(default_factory=dict)

    # 早停
    early_stopping: bool = True
    early_stopping_patience: int = 10
    early_stopping_monitor: str = "val_loss"
    early_stopping_mode: str = "min"
    early_stopping_min_delta: float = 0.0

    # 模型保存
    checkpoint_enabled: bool = True
    checkpoint_dir: str = "./checkpoints"
    checkpoint_save_interval: int = 1
    checkpoint_save_best: bool = True
    checkpoint_max_keep: int = 5

    # 数据
    num_workers: int = 4
    pin_memory: bool = True
    shuffle_train: bool = True

    # 随机种子
    seed: int = 42

    # 验证
    val_interval: int = 1
    log_interval: int = 10

    # 设备
    device: str = "auto"

    # 实验追踪
    experiment_name: str = "default_exp"
    experiment_dir: str = "./experiments"
    track_metrics: list[str] = field(default_factory=lambda: ["loss", "accuracy"])

    # GradClip
    gradient_clip_value: float | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingConfig":
        valid = {k: v for k, v in data.items() if k in cls.__annotations__}
        return cls(**valid)
