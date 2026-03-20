"""
配置系统 - Configuration System

支持 YAML/JSON/Python 配置格式，提供配置继承、验证等功能
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml


class Config:
    """配置管理类"""

    def __init__(self, config_dict: dict | None = None):
        self._config = config_dict or {}
        self._base_config: Config | None = None

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> "Config":
        """从 YAML 文件加载配置"""
        with open(file_path, encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)
        return cls(config_dict)

    @classmethod
    def from_json(cls, file_path: str | Path) -> "Config":
        """从 JSON 文件加载配置"""
        with open(file_path, encoding="utf-8") as f:
            config_dict = json.load(f)
        return cls(config_dict)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "Config":
        """从字典创建配置"""
        return cls(deepcopy(config_dict))

    def merge(self, base_config: "Config") -> "Config":
        """配置继承合并"""
        merged = deepcopy(self)
        merged._base_config = base_config
        merged._config = self._merge_dict(base_config._config, self._config)
        return merged

    def _merge_dict(self, base: dict, override: dict) -> dict:
        """递归合并字典"""
        result = deepcopy(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_dict(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号访问"""
        keys = key.split(".")
        value = self._config

        # 先查找当前配置
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    # 如果找不到，尝试从 base_config 查找
                    if self._base_config is not None:
                        return self._base_config.get(key, default)
                    return default
            else:
                if self._base_config is not None:
                    return self._base_config.get(key, default)
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def __getitem__(self, key: str) -> Any:
        """支持 config['key'] 访问"""
        value = self.get(key)
        if value is None:
            raise KeyError(f"Config key '{key}' not found")
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """支持 'key' in config"""
        return self.get(key) is not None

    def to_dict(self) -> dict:
        """转换为字典"""
        return deepcopy(self._config)

    def to_yaml(self) -> str:
        """转换为 YAML 字符串"""
        return yaml.dump(self._config, allow_unicode=True, default_flow_style=False)

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self._config, ensure_ascii=False, indent=2)

    def save_yaml(self, file_path: str | Path) -> None:
        """保存为 YAML 文件"""
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)

    def save_json(self, file_path: str | Path) -> None:
        """保存为 JSON 文件"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def validate(self, schema: dict) -> bool:
        """配置验证（简化版）"""
        for key, expected_type in schema.items():
            value = self.get(key)
            if value is not None and not isinstance(value, expected_type):
                raise ValueError(
                    f"Config key '{key}' expected type {expected_type}, got {type(value)}"
                )
        return True

    def __repr__(self) -> str:
        return f"Config({self._config})"


# 便捷函数
def load_config(file_path: str | Path) -> Config:
    """加载配置文件（自动识别格式）"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in [".yaml", ".yml"]:
        return Config.from_yaml(file_path)
    elif suffix == ".json":
        return Config.from_json(file_path)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")
