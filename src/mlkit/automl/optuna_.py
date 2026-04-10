"""
AutoML - Bayesian Optimization（optuna）
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from mlkit.model import create_model


# ─── Objective ───────────────────────────────────────────────────────────────────


class OptunaObjective:
    """Optuna 目标函数适配"""

    def __init__(
        self,
        task_type: Literal["classification", "regression"],
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        search_space: "SearchSpace",
        timeout_per_trial: float = 30.0,
    ):
        self.task_type = task_type
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.search_space = search_space
        self.timeout_per_trial = timeout_per_trial

    def __call__(self, trial) -> float:
        """optuna objective: return negative val_score (optuna minimizes)"""
        from sklearn.metrics import accuracy_score, r2_score

        start = time.time()
        params = {}
        for s in self.search_space.choices():
            name = s["name"]
            if s["type"] == "choice":
                params[name] = trial.suggest_categorical(name, s["values"])
            elif s["type"] == "int":
                params[name] = trial.suggest_int(name, s["low"], s["high"], step=s.get("step", 1))
            elif s["type"] == "float":
                if s.get("log"):
                    params[name] = trial.suggest_float(name, s["low"], s["high"], log=True)
                else:
                    params[name] = trial.suggest_float(name, s["low"], s["high"])

        model_type = params.get("model_type", "sklearn")
        n_estimators = params.get("n_estimators", 50)
        max_depth = params.get("max_depth", 5)
        learning_rate = params.get("learning_rate", 0.1)

        try:
            if model_type in ("random_forest",):
                model = create_model(
                    "sklearn",
                    model_class="RandomForestClassifier" if self.task_type == "classification" else "RandomForestRegressor",
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    random_state=42,
                )
            elif model_type in ("xgboost",):
                model = create_model(
                    "xgboost",
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    random_state=42,
                    objective="binary:logistic" if self.task_type == "classification" else "reg:squarederror",
                )
            elif model_type in ("lightgbm",):
                model = create_model(
                    "lightgbm",
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    random_state=42,
                )
            else:
                model = create_model(
                    "sklearn",
                    model_class="RandomForestClassifier" if self.task_type == "classification" else "RandomForestRegressor",
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    random_state=42,
                )

            if time.time() - start > self.timeout_per_trial:
                return 1.0  # timeout, return bad score

            model.fit(self.X_train, self.y_train)

            y_pred_val = model.predict(self.X_val)

            if self.task_type == "classification":
                val_score = accuracy_score(self.y_val, y_pred_val)
            else:
                val_score = r2_score(self.y_val, y_pred_val)

            return -val_score  # optuna minimizes
        except Exception as e:
            print(f"[Optuna] Trial failed: {e}")
            return 1.0
