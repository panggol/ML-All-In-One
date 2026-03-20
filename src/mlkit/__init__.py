"""
ML All In One - 机器学习全流程训练平台

核心模块：
- config: 配置系统
- registry: 注册机制
- model: 模型基类
- data: 数据处理
- hooks: 生命周期钩子
- runner: 训练运行器
"""

from mlkit.api.inference import (
    InferenceEngine,
    ModelRegistry,
    create_inference_app,
    run_inference_server,
    serve_model,
)
from mlkit.config import Config, load_config
from mlkit.data import (
    DataLoader,
    Dataset,
    DataValidator,
    ImbalanceHandler,
)
from mlkit.experiment import (
    Experiment,
    ExperimentComparator,
    ExperimentTracker,
    HyperparameterSearcher,
)
from mlkit.hooks import Hook
from mlkit.model import (
    BaseModel,
    PyTorchModel,
    SKLearnModel,
    create_model,
)
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
from mlkit.utils import (
    RealTimeLogger,
    TrainingLogger,
    get_logger,
)

__version__ = "0.1.0"

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
    "PyTorchModel",
    "create_model",
    # Data
    "Dataset",
    "DataLoader",
    "ImbalanceHandler",
    "DataValidator",
    # Hooks
    "Hook",
    # Runner
    "Runner",
    "create_runner",
    # Experiment
    "Experiment",
    "ExperimentTracker",
    "ExperimentComparator",
    "HyperparameterSearcher",
    # Utils
    "RealTimeLogger",
    "TrainingLogger",
    "get_logger",
    # API
    "ModelRegistry",
    "InferenceEngine",
    "create_inference_app",
    "run_inference_server",
    "serve_model",
]
