"""
Config 基类 - BaseConfig

提供配置的分层管理、dot-path 访问、验证和序列化。
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

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
class BaseConfig:
    """配置基类

    所有配置类都应该继承此类。
    提供：
    - dot-path 访问
    - 层级合并
    - 环境变量注入
    - YAML/JSON 序列化
    """

    def get(self, key: str, default: Any = None) -> Any:
        """dot-path 获取配置值（向后兼容）"""
        keys = key.split(".")
        value: Any = self
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
                if value is None:
                    return default
            elif hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
        return value

    def to_dict(self) -> dict:
        result: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, BaseConfig):
                result[f.name] = value.to_dict()
            else:
                result[f.name] = copy.deepcopy(value)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "BaseConfig":
        if not isinstance(data, dict):
            raise ConfigError(f"期望 dict，实际 {type(data)}")
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_yaml(self, path: str | Path) -> None:
        if yaml is None:
            raise ConfigError("pyyaml 未安装：pip install pyyaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BaseConfig":
        if yaml is None:
            raise ConfigError("pyyaml 未安装：pip install pyyaml")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data or {})

    def to_json(self, path: str | Path) -> None:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, path: str | Path) -> "BaseConfig":
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def merge(self, other: "BaseConfig | dict") -> "BaseConfig":
        self_dict = self.to_dict()
        other_dict = other.to_dict() if isinstance(other, BaseConfig) else other
        merged = _deep_merge(self_dict, other_dict)
        return self.from_dict(merged)

    @classmethod
    def from_env(cls, prefix: str = "MLKIT_") -> "BaseConfig":
        env_data: dict[str, Any] = {}
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            short_key = key[len(prefix):]
            parts = short_key.lower().split("__")
            _set_nested(env_data, parts, _cast_value(value))
        return cls.from_dict(env_data)

    def apply_env(self, prefix: str = "MLKIT_") -> "BaseConfig":
        env_config = self.__class__.from_env(prefix)
        return self.merge(env_data)


def _deep_merge(base: dict, override: dict) -> dict:
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
