"""
PyTorch MLP 模型封装
sklearn 风格的 MLP 接口，支持 fit/predict/predict_proba/save/load
"""
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn


class MLPClassifier:
    """
    PyTorch 实现的 MLP 分类器，封装为 sklearn 风格接口。

    支持：
    - fit() — 单轮训练（全数据前向+反向）
    - predict() — 预测类别
    - predict_proba() — 预测概率
    - save() / load() — joblib 持久化
    """

    def __init__(
        self,
        hidden_layer_sizes=(100,),
        activation="relu",
        solver="adam",
        alpha=0.0001,
        max_iter=200,
        random_state=None,
        task="classification",
        **kwargs,
    ):
        self.hidden_layer_sizes = hidden_layer_sizes
        self.activation = activation
        self.solver = solver
        self.alpha = alpha
        self.max_iter = max_iter
        self.random_state = random_state
        self.task = task
        self.model = None
        self._fitted = False

    def _build_model(self, n_features, n_classes):
        layers = []
        prev_size = n_features
        for size in self.hidden_layer_sizes:
            layers.append(nn.Linear(prev_size, size))
            if self.activation == "relu":
                layers.append(nn.ReLU())
            elif self.activation == "tanh":
                layers.append(nn.Tanh())
            prev_size = size
        layers.append(nn.Linear(prev_size, n_classes))
        self.model = nn.Sequential(*layers)

        if self.solver == "adam":
            self.optimizer = torch.optim.Adam(
                self.model.parameters(), lr=0.001, weight_decay=self.alpha
            )
        else:
            self.optimizer = torch.optim.SGD(
                self.model.parameters(), lr=0.01, weight_decay=self.alpha
            )

        if self.task == "classification":
            self.criterion = nn.CrossEntropyLoss()
        else:
            self.criterion = nn.MSELoss()

    def fit(self, X, y):
        if self.random_state is not None:
            torch.manual_seed(self.random_state)
            np.random.seed(self.random_state)

        X_t = torch.FloatTensor(X.values if isinstance(X, pd.DataFrame) else X)
        y_t = (
            torch.LongTensor(y.values if isinstance(y, (pd.DataFrame, pd.Series)) else y)
            if self.task == "classification"
            else torch.FloatTensor(y.values if isinstance(y, (pd.DataFrame, pd.Series)) else y)
        )

        if self.model is None:
            n_features = X.shape[1]
            n_classes = (
                len(np.unique(y)) if self.task == "classification" else 1
            )
            self._build_model(n_features, n_classes)

        self.model.train()
        self.optimizer.zero_grad()
        output = self.model(X_t)
        loss = self.criterion(output, y_t)
        loss.backward()
        self.optimizer.step()
        self._fitted = True
        return self

    def predict(self, X):
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X.values if isinstance(X, pd.DataFrame) else X)
            output = self.model(X_t)
            if self.task == "classification":
                return torch.argmax(output, dim=1).numpy()
            else:
                return output.numpy().flatten()

    def predict_proba(self, X):
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X.values if isinstance(X, pd.DataFrame) else X)
            output = self.model(X_t)
            probs = torch.softmax(output, dim=1)
            return probs.numpy()

    def save(self, path):
        joblib.dump(self, path)

    @classmethod
    def load(cls, path):
        return joblib.load(path)
