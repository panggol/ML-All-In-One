"""
mlkit - ML All In One

机器学习和深度学习模型训练全流程平台。
"""

from mlkit.config import Config, load_config
from mlkit.hooks import Hook
from mlkit.model import BaseModel, SKLearnModel, create_model
from mlkit.registry import (
    DATASET_REGISTRY,
    HOOK_REGISTRY,
    METRIC_REGISTRY,
    MODEL_REGISTRY,
    OPTIMIZER_REGISTRY,
    Registry,
    register_dataset,
    register_hook,
    register_metric,
    register_model,
)
from mlkit.runner import Runner, create_runner
from mlkit.experiment import Experiment, ExperimentManager, ExperimentTrackHook
from mlkit.auth import (
    AuthService,
    User,
    TokenData,
    get_auth_service,
    login_required,
    admin_required,
    get_current_user,
)

__version__ = "0.2.0"

__all__ = [
    # Config
    "Config",
    "load_config",
    # Registry
    "Registry",
    "MODEL_REGISTRY",
    "DATASET_REGISTRY",
    "HOOK_REGISTRY",
    "METRIC_REGISTRY",
    "OPTIMIZER_REGISTRY",
    "register_model",
    "register_dataset",
    "register_hook",
    "register_metric",
    # Model
    "BaseModel",
    "SKLearnModel",
    "create_model",
    # Hooks
    "Hook",
    # Runner
    "Runner",
    "create_runner",
    # Experiment
    "Experiment",
    "ExperimentManager",
    "ExperimentTrackHook",
    # Auth
    "AuthService",
    "User",
    "TokenData",
    "get_auth_service",
    "login_required",
    "admin_required",
    "get_current_user",
]
