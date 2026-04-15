"""
Model Registry exceptions.
"""


class ModelRegistryError(Exception):
    """基础异常"""
    pass


class VersionNotFoundError(ModelRegistryError):
    """版本不存在"""
    pass


class InvalidTagError(ModelRegistryError):
    """非法标签值"""
    pass


class RollbackNotAllowedError(ModelRegistryError):
    """不允许回滚（如目标为 archived）"""
    pass
