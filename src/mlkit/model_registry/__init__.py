"""
Model Registry — Library-First Python Package

提供模型版本管理的核心业务逻辑：
- 计算下一个版本号
- 计算数据集指纹（SHA256）
- 版本对比逻辑
- 标签状态机

同时暴露 Python API 和 CLI（Text in/out）。
"""
from .core import (
    compute_next_version,
    compute_dataset_hash,
    compare_versions,
    VALID_TAGS,
)
from .exceptions import (
    ModelRegistryError,
    VersionNotFoundError,
    InvalidTagError,
    RollbackNotAllowedError,
)

__all__ = [
    "compute_next_version",
    "compute_dataset_hash",
    "compare_versions",
    "VALID_TAGS",
    "ModelRegistryError",
    "VersionNotFoundError",
    "InvalidTagError",
    "RollbackNotAllowedError",
]
