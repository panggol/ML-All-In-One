"""
API 路由汇总
"""
from api.routes import auth, data, train, experiments, models, viz, automl, preprocessing, monitor, logs, platform_logs, admin, drift, explain, scheduler, forecast, model_registry

__all__ = ["auth", "data", "train", "experiments", "models", "viz", "automl", "preprocessing", "monitor", "logs", "platform_logs", "admin", "drift", "explain", "scheduler", "forecast", "model_registry"]
