"""
注册机制 - Registry System

提供模块化注册功能，支持自动发现和装饰器注册
"""

import builtins
import importlib
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


class Registry:
    """注册表基类"""

    def __init__(self, name: str, locations: list[str] | None = None):
        """
        初始化注册表

        Args:
            name: 注册表名称
            locations: 模块搜索路径列表
        """
        self.name = name
        self.locations = locations or []
        self._registry: dict[str, type] = {}
        self._functions: dict[str, Callable] = {}

    def register(self, name: str | None = None, force: bool = False):
        """
        装饰器：注册类或函数

        Args:
            name: 注册名称，默认使用类名/函数名
            force: 是否强制覆盖已存在的注册
        """

        def decorator(cls_or_func):
            key = name or cls_or_func.__name__

            if key in self._registry and not force:
                raise ValueError(
                    f"Cannot register '{key}' in {self.name}: already exists"
                )

            # 判断是类还是函数
            if inspect.isclass(cls_or_func):
                self._registry[key] = cls_or_func
            else:
                self._functions[key] = cls_or_func

            return cls_or_func

        return decorator

    def register_class(self, name: str | None = None):
        """装饰器：注册类（别名）"""
        return self.register(name)

    def register_function(self, name: str | None = None):
        """装饰器：注册函数（别名）"""
        return self.register(name)

    def get(self, name: str) -> Any:
        """获取注册的类或函数"""
        if name in self._registry:
            return self._registry[name]
        if name in self._functions:
            return self._functions[name]
        raise KeyError(f"'{name}' not found in {self.name}")

    def get_class(self, name: str) -> type:
        """获取注册的类"""
        if name not in self._registry:
            raise KeyError(f"Class '{name}' not found in {self.name}")
        return self._registry[name]

    def get_function(self, name: str) -> Callable:
        """获取注册的函数"""
        if name not in self._functions:
            raise KeyError(f"Function '{name}' not found in {self.name}")
        return self._functions[name]

    def exists(self, name: str) -> bool:
        """检查是否已注册"""
        return name in self._registry or name in self._functions

    def list(self) -> list[str]:
        """列出所有注册的名称"""
        return list(self._registry.keys()) + list(self._functions.keys())

    def scan(self, locations: builtins.list[str] | None = None) -> None:
        """扫描并自动发现注册"""
        locations = locations or self.locations

        for location in locations:
            self._scan_module(location)

    def _scan_module(self, module_path: str) -> None:
        """扫描单个模块"""
        try:
            module = importlib.import_module(module_path)

            # 扫描模块中的类和函数
            for name, obj in inspect.getmembers(module):
                # 跳过私有成员和已注册的
                if name.startswith("_"):
                    continue

                # 检查是否有注册标记
                if hasattr(obj, "_registered_in_" + self.name):
                    self.register(name)(obj)

        except ImportError:
            pass

    def __repr__(self) -> str:
        return f"Registry(name='{self.name}', items={len(self.list())})"


# 全局注册表
DATASET_REGISTRY = Registry("dataset", locations=["mlkit.data.datasets"])
MODEL_REGISTRY = Registry("model", locations=["mlkit.models"])
OPTIMIZER_REGISTRY = Registry("optimizer", locations=["mlkit.optimizers"])
HOOK_REGISTRY = Registry("hook", locations=["mlkit.hooks"])
METRIC_REGISTRY = Registry("metric", locations=["mlkit.metrics"])
TRANSFORM_REGISTRY = Registry("transform", locations=["mlkit.data.transforms"])


# 便捷装饰器
def register_model(name: str | None = None):
    """注册模型的装饰器"""
    return MODEL_REGISTRY.register(name)


def register_dataset(name: str | None = None):
    """注册数据集的装饰器"""
    return DATASET_REGISTRY.register(name)


def register_hook(name: str | None = None):
    """注册 Hook 的装饰器"""
    return HOOK_REGISTRY.register(name)


def register_metric(name: str | None = None):
    """注册指标的装饰器"""
    return METRIC_REGISTRY.register(name)


def register_optimizer(name: str | None = None):
    """注册优化器的装饰器"""
    return OPTIMIZER_REGISTRY.register(name)
