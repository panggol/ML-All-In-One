"""
Config 系统 - 配置管理

Harness Engineering 核心理念：
- 六层配置优先级：CLI → ENV → File → Class → Defaults
- 配置分层管理，dot-path 访问
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


class ConfigError(Exception):
    """配置相关错误"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证失败"""
    pass


class ConfigKeyNotFoundError(ConfigError, KeyError):
    """配置键不存在"""
    pass


@dataclass
class Config:
    """通用配置类（向后兼容）

    支持：
    - dot-path 访问（config.get("train.epochs")）
    - YAML/JSON 加载
    - 多配置合并
    - 环境变量注入
    - 字段验证

    用法:
        config = Config.from_yaml("config.yaml")
        epochs = config.get("train.epochs", 100)
        hidden_size = config.get("model.hidden_size", 256)
    """

    # 通用字段（实际使用时会被具体配置类替换）
    _data: dict = field(default_factory=dict)

    def __post_init__(self):
        # 如果传入的是字典，存到 _data
        if self._data is None:
            self._data = {}

    # ── dot-path 访问 ───────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """dot-path 获取配置值

        Args:
            key: 支持 "a.b.c" 形式的多层访问
            default: 键不存在时返回的默认值

        用法:
            config.get("train.epochs", 100)
            config.get("model.hidden_size", 256)
        """
        if not self._data:
            return default
        keys = key.split(".")
        value: Any = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            elif hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """dot-path 设置配置值"""
        keys = key.split(".")
        d = self._data
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    # ── 序列化 ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """导出为字典"""
        return copy.deepcopy(self._data)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """从字典创建配置"""
        if not isinstance(data, dict):
            raise ConfigError(f"期望 dict，实际 {type(data)}")
        instance = cls()
        instance._data = copy.deepcopy(data)
        return instance

    def to_yaml(self, path: str | Path) -> None:
        """导出为 YAML 文件"""
        if yaml is None:
            raise ConfigError("pyyaml 未安装：pip install pyyaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """从 YAML 文件加载配置"""
        if yaml is None:
            raise ConfigError("pyyaml 未安装：pip install pyyaml")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data or {})

    def to_json(self, path: str | Path) -> None:
        """导出为 JSON 文件"""
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, path: str | Path) -> "Config":
        """从 JSON 文件加载配置"""
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    # ── 合并 ──────────────────────────────────────────

    def merge(self, other: "Config | dict") -> "Config":
        """合并另一个配置（other 优先级更高）"""
        other_data = other._data if isinstance(other, Config) else other
        merged = _deep_merge(self._data, other_data)
        return Config.from_dict(merged)

    @classmethod
    def from_env(cls, prefix: str = "MLKIT_") -> "Config":
        """从环境变量加载配置

        环境变量命名规则：MLKIT_TRAIN__EPOCHS（双下划线=嵌套）
        """
        env_data: dict = {}
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            short_key = key[len(prefix):]
            parts = short_key.lower().split("__")
            _set_nested(env_data, parts, _cast_value(value))
        return cls.from_dict(env_data)

    def apply_env(self, prefix: str = "MLKIT_") -> "Config":
        """用环境变量覆盖当前配置（优先级最高）"""
        env_config = Config.from_env(prefix)
        return self.merge(env_config)

    def __repr__(self) -> str:
        return f"Config({self._data})"


def load_config(path: str) -> Config:
    """加载配置文件（向后兼容）

    支持 .yaml / .yml / .json 格式。
    """
    path = str(path)
    if path.endswith(".json"):
        return Config.from_json(path)
    return Config.from_yaml(path)


# ── TrainingConfig（推荐使用）───────────────────────────────


@dataclass
class TrainingConfig:
    """训练配置（结构化版本，推荐使用）"""

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
    track_metrics: list = field(default_factory=lambda: ["loss", "accuracy"])

    # GradClip
    gradient_clip_value: float | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingConfig":
        valid = {k: v for k, v in data.items() if k in cls.__annotations__}
        return cls(**valid)


# ── 工具函数 ───────────────────────────────────────────


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override 优先级更高"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _set_nested(d: dict, keys: list[str], value: Any) -> None:
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def _cast_value(value: str) -> Any:
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    if value.lower() == "none":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
