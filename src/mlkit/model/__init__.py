"""
模型基类 - Model Base Classes

统一 sklearn 和 PyTorch 的训练接口
支持：
- 传统 ML: sklearn, XGBoost, LightGBM
- 深度学习: PyTorch
- 大数据: 流式训练、增量学习
"""

import pickle
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, Optional, Union

import joblib
import numpy as np


class BaseModel(ABC):
    """模型基类 - 抽象接口"""

    @abstractmethod
    def fit(self, X, y, **kwargs):
        """
        训练模型

        Args:
            X: 训练数据
            y: 标签
            **kwargs: 其他训练参数
        """
        pass

    @abstractmethod
    def predict(self, X):
        """
        预测

        Args:
            X: 输入数据

        Returns:
            预测结果
        """
        pass

    @abstractmethod
    def save(self, path: str | Path) -> None:
        """保存模型"""
        pass

    @abstractmethod
    def load(self, path: str | Path) -> None:
        """加载模型"""
        pass

    def predict_proba(self, X):
        """
        预测概率（分类模型）

        Args:
            X: 输入数据

        Returns:
            预测概率
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support predict_proba"
        )

    def predict_log_proba(self, X):
        """
        预测对数概率（分类模型）

        Args:
            X: 输入数据

        Returns:
            预测对数概率
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support predict_log_proba"
        )

    def score(self, X, y, **kwargs):
        """
        评估模型

        Args:
            X: 测试数据
            y: 真实标签

        Returns:
            评估分数
        """
        from sklearn.metrics import accuracy_score

        y_pred = self.predict(X)
        return accuracy_score(y, y_pred)

    def get_params(self) -> dict:
        """获取模型参数"""
        return {}

    def set_params(self, **params):
        """设置模型参数"""
        return self


class SKLearnModel(BaseModel):
    """sklearn 模型包装器"""

    def __init__(self, model, task_type: str = "classification"):
        """
        初始化 sklearn 模型包装器

        Args:
            model: sklearn 模型实例
            task_type: 任务类型 ('classification' / 'regression')
        """
        self.model = model
        self.task_type = task_type

    def fit(self, X, y, **kwargs):
        """训练模型"""
        # 支持增量学习的模型
        if hasattr(self.model, "partial_fit"):
            # 流式训练模式
            if "batch_size" in kwargs:
                batch_size = kwargs.pop("batch_size")
                n_samples = X.shape[0]

                for i in range(0, n_samples, batch_size):
                    X_batch = X[i : i + batch_size]
                    y_batch = y[i : i + batch_size]

                    # 对于分类问题，需要传入所有类别
                    if self.task_type == "classification" and not hasattr(
                        self.model, "classes_"
                    ):
                        self.model.partial_fit(X_batch, y_batch, classes=np.unique(y))
                    else:
                        self.model.partial_fit(X_batch, y_batch)
            else:
                self.model.fit(X, y)
        else:
            self.model.fit(X, y)

        return self

    def predict(self, X):
        """预测"""
        return self.model.predict(X)

    def predict_proba(self, X):
        """预测概率"""
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        return super().predict_proba(X)

    def predict_log_proba(self, X):
        """预测对数概率"""
        if hasattr(self.model, "predict_log_proba"):
            return self.model.predict_log_proba(X)
        return super().predict_log_proba(X)

    def score(self, X, y, **kwargs):
        """评估模型"""
        return self.model.score(X, y)

    def save(self, path: str | Path) -> None:
        """保存模型"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)

    def load(self, path: str | Path) -> None:
        """加载模型"""
        self.model = joblib.load(path)

    def get_params(self) -> dict:
        """获取模型参数"""
        return self.model.get_params()

    def set_params(self, **params):
        """设置模型参数"""
        self.model.set_params(**params)
        return self


class XGBoostModel(SKLearnModel):
    """XGBoost 模型包装器"""

    def __init__(self, **kwargs):
        from xgboost import XGBClassifier, XGBRegressor

        # 根据任务类型选择模型
        if kwargs.get("objective", "binary:logistic").startswith(
            "binary:"
        ) or kwargs.get("objective", "multi:softmax").startswith("multi:"):
            model = XGBClassifier(**kwargs)
        else:
            model = XGBRegressor(**kwargs)

        super().__init__(
            model,
            task_type=(
                "classification"
                if "Classifier" in type(model).__name__
                else "regression"
            ),
        )


class LightGBMModel(SKLearnModel):
    """LightGBM 模型包装器"""

    def __init__(self, **kwargs):
        from lightgbm import LGBMClassifier, LGBMRegressor

        # 根据任务类型选择模型
        if kwargs.get("objective", "binary").startswith("binary") or kwargs.get(
            "objective", "multiclass"
        ).startswith("multiclass"):
            model = LGBMClassifier(**kwargs)
        else:
            model = LGBMRegressor(**kwargs)

        super().__init__(
            model,
            task_type=(
                "classification"
                if "Classifier" in type(model).__name__
                else "regression"
            ),
        )


class PyTorchModel(BaseModel):
    """PyTorch 模型包装器"""

    def __init__(self, model, criterion=None, optimizer=None, device: str = "cpu"):
        """
        初始化 PyTorch 模型包装器

        Args:
            model: PyTorch 模型 (nn.Module)
            criterion: 损失函数
            optimizer: 优化器
            device: 设备 ('cpu' / 'cuda' / 'npu')
        """
        import torch.nn as nn

        self.model = model
        self.criterion = criterion or nn.CrossEntropyLoss()
        self.optimizer = optimizer
        self.device = device
        self.model.to(self.device)

        # 自动推断任务类型
        if isinstance(self.model, nn.Module):
            # 默认假设是分类
            self.task_type = "classification"
        else:
            self.task_type = "regression"

    def fit(self, X, y, **kwargs):
        """
        训练模型

        Args:
            X: 训练数据 (Tensor 或 numpy array)
            y: 标签 (Tensor 或 numpy array)
            epochs: 训练轮数
            batch_size: 批次大小
            val_data: 验证数据 (X_val, y_val)
            callbacks: 回调函数列表
        """
        import torch
        from torch.utils.data import DataLoader, TensorDataset

        # 转换为 Tensor
        if isinstance(X, np.ndarray):
            X = torch.from_numpy(X).float()
        if isinstance(y, np.ndarray):
            y = torch.from_numpy(y)

        # 确定标签类型
        if self.task_type == "classification" and y.dtype in [torch.int64, torch.int32]:
            # 分类任务
            pass
        else:
            # 回归任务
            y = y.float()

        # 创建 DataLoader
        batch_size = kwargs.get("batch_size", 32)
        dataset = TensorDataset(X, y)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        epochs = kwargs.get("epochs", 10)
        callbacks = kwargs.get("callbacks", [])

        # 训练循环
        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_X, batch_y in dataloader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)

                # 前向传播
                outputs = self.model(batch_X)

                # 处理不同的损失函数要求
                if self.task_type == "classification":
                    if batch_y.dim() > 1 and batch_y.shape[1] > 1:
                        # one-hot 编码
                        loss = self.criterion(outputs, batch_y.argmax(dim=1))
                    else:
                        loss = self.criterion(outputs, batch_y)
                else:
                    loss = self.criterion(outputs, batch_y)

                # 反向传播
                if self.optimizer:
                    self.optimizer.zero_grad()
                loss.backward()
                if self.optimizer:
                    self.optimizer.step()

                epoch_loss += loss.item()

            # 执行回调
            for callback in callbacks:
                callback(epoch, epoch_loss / len(dataloader))

        return self

    def predict(self, X):
        """预测"""
        import torch

        self.model.eval()

        # 转换为 Tensor
        if isinstance(X, np.ndarray):
            X = torch.from_numpy(X).float()

        X = X.to(self.device)

        with torch.no_grad():
            outputs = self.model(X)

        if self.task_type == "classification":
            # 返回预测类别
            if hasattr(outputs, "argmax"):
                return outputs.argmax(dim=1).cpu().numpy()
            return (outputs > 0.5).cpu().numpy()
        else:
            return outputs.cpu().numpy()

    def predict_proba(self, X):
        """预测概率"""
        import torch

        self.model.eval()

        if isinstance(X, np.ndarray):
            X = torch.from_numpy(X).float()

        X = X.to(self.device)

        with torch.no_grad():
            outputs = self.model(X)

        # softmax 转换为概率
        if hasattr(outputs, "softmax"):
            return outputs.softmax(dim=1).cpu().numpy()
        elif hasattr(torch, "softmax"):
            import torch.nn.functional as F

            return F.softmax(outputs, dim=1).cpu().numpy()

        return outputs.cpu().numpy()

    def save(self, path: str | Path) -> None:
        """保存模型"""
        import torch

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": (
                    self.optimizer.state_dict() if self.optimizer else None
                ),
            },
            path,
        )

    def load(self, path: str | Path) -> None:
        """加载模型"""
        import torch

        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])

        if self.optimizer and checkpoint.get("optimizer_state_dict"):
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

    def get_params(self) -> dict:
        """获取模型参数"""
        return dict(self.model.named_parameters())


def create_model(model_type: str, **kwargs) -> BaseModel:
    """
    工厂函数：创建模型

    Args:
        model_type: 模型类型 ('sklearn', 'xgboost', 'lightgbm', 'pytorch')
        **kwargs: 模型参数

    Returns:
        BaseModel 实例
    """
    if model_type == "sklearn":
        from sklearn.ensemble import (
            GradientBoostingClassifier,
            RandomForestClassifier,
            RandomForestRegressor,
        )
        from sklearn.linear_model import LinearRegression, LogisticRegression
        from sklearn.svm import SVC, SVR

        task = kwargs.pop("task", "classification")

        # 支持字符串到类的映射
        sklearn_models = {
            "RandomForestClassifier": RandomForestClassifier,
            "RandomForestRegressor": RandomForestRegressor,
            "GradientBoostingClassifier": GradientBoostingClassifier,
            "LogisticRegression": LogisticRegression,
            "LinearRegression": LinearRegression,
            "SVC": SVC,
            "SVR": SVR,
        }

        model_class_name = kwargs.pop(
            "model_class",
            (
                "RandomForestClassifier"
                if task == "classification"
                else "RandomForestRegressor"
            ),
        )

        if isinstance(model_class_name, str):
            if model_class_name not in sklearn_models:
                raise ValueError(
                    f"Unknown sklearn model: {model_class_name}. Available: {list(sklearn_models.keys())}"
                )
            model_class = sklearn_models[model_class_name]
        else:
            model_class = model_class_name

        return SKLearnModel(model_class(**kwargs), task_type=task)

    elif model_type == "xgboost":
        return XGBoostModel(**kwargs)

    elif model_type == "lightgbm":
        return LightGBMModel(**kwargs)

    elif model_type == "pytorch":
        import torch.nn as nn

        model = kwargs.pop("model", None)
        if model is None:
            # 创建默认的全连接网络
            input_dim = kwargs.pop("input_dim", 10)
            hidden_dim = kwargs.pop("hidden_dim", 64)
            output_dim = kwargs.pop("output_dim", 2)
            num_layers = kwargs.pop("num_layers", 3)

            layers = []
            dims = [input_dim] + [hidden_dim] * (num_layers - 1) + [output_dim]

            for i in range(len(dims) - 1):
                layers.append(nn.Linear(dims[i], dims[i + 1]))
                if i < len(dims) - 2:
                    layers.append(nn.ReLU())

            model = nn.Sequential(*layers)

        criterion = kwargs.pop("criterion", None)
        optimizer = kwargs.pop("optimizer", None)
        device = kwargs.pop("device", "cpu")

        # 如果没有指定优化器，创建一个默认的
        if optimizer is None:
            optimizer = torch.optim.Adam(model.parameters(), lr=kwargs.get("lr", 0.001))

        return PyTorchModel(
            model, criterion=criterion, optimizer=optimizer, device=device
        )

    else:
        raise ValueError(f"Unknown model type: {model_type}")
