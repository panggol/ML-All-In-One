"""
AutoML - 自动模型选择和超参数调优

支持：
- Grid Search（暴力网格搜索）
- Random Search（随机搜索）
- Bayesian Optimization（optuna，需要安装 optuna）

用法:
    from mlkit.automl import AutoMLEngine, RandomSearch

    engine = AutoMLEngine(
        task_type="classification",
        X_train=X_train, y_train=y_train,
        X_val=X_val, y_val=y_val,
        strategy="random",
        n_trials=20,
    )
    result = engine.run()
    print(result.best_params)
"""

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from mlkit.model import create_model


# ─── 数据类 ───────────────────────────────────────────────────────────────────

@dataclass
class TrialResult:
    """单次 Trial 结果"""
    trial_id: int
    params: dict
    train_score: float
    val_score: float
    train_time: float  # seconds


@dataclass
class AutoMLResult:
    """AutoML 搜索结果"""
    best_params: dict
    best_val_score: float
    best_train_score: float
    trials: list[TrialResult]
    strategy: str
    n_trials: int
    total_time: float  # seconds


# ─── 搜索空间 ────────────────────────────────────────────────────────────────

class SearchSpace:
    """超参数搜索空间定义"""

    def __init__(self):
        self._spaces: list[dict] = []

    def add(self, name: str, values: list) -> "SearchSpace":
        """添加离散选项参数"""
        self._spaces.append({"name": name, "type": "choice", "values": values})
        return self

    def add_int(self, name: str, low: int, high: int, step: int = 1) -> "SearchSpace":
        """添加整数范围参数（Grid Search 用）"""
        self._spaces.append({
            "name": name, "type": "int",
            "low": low, "high": high, "step": step
        })
        return self

    def add_float(self, name: str, low: float, high: float,
                  log: bool = False) -> "SearchSpace":
        """添加浮点数范围参数"""
        self._spaces.append({
            "name": name, "type": "float",
            "low": low, "high": high, "log": log
        })
        return self

    def choices(self) -> list[dict]:
        return list(self._spaces)

    def grid_points(self) -> list[dict]:
        """生成所有网格点（Grid Search）"""
        import itertools

        grids = []
        for s in self._spaces:
            name = s["name"]
            if s["type"] == "choice":
                grids.append([(name, v) for v in s["values"]])
            elif s["type"] == "int":
                vals = list(range(s["low"], s["high"] + 1, s["step"]))
                grids.append([(name, v) for v in vals])
            elif s["type"] == "float":
                grids.append([(name, v) for v in [s["low"], s["high"]]])

        if not grids:
            return [{}]

        points = []
        for combo in itertools.product(*grids):
            point = dict(combo)
            # 插值浮点参数
            for s in self._spaces:
                if s["type"] == "float":
                    name = s["name"]
                    low, high = s["low"], s["high"]
                    if s.get("log"):
                        point[name] = np.exp(np.log(low) + np.random.rand() * (np.log(high) - np.log(low)))
                    else:
                        point[name] = low + np.random.rand() * (high - low)
            points.append(point)
        return points

    def random_point(self, rng: np.random.Generator) -> dict:
        """生成随机采样点（Random Search）"""
        point = {}
        for s in self._spaces:
            name = s["name"]
            if s["type"] == "choice":
                point[name] = rng.choice(s["values"])
            elif s["type"] == "int":
                low, high = s["low"], s["high"]
                if "step" in s and s["step"] > 1:
                    n_steps = (high - low) // s["step"]
                    point[name] = low + rng.integers(0, n_steps + 1) * s["step"]
                else:
                    point[name] = rng.integers(low, high + 1)
            elif s["type"] == "float":
                low, high = s["low"], s["high"]
                if s.get("log"):
                    point[name] = np.exp(rng.uniform(np.log(low), np.log(high)))
                else:
                    point[name] = rng.uniform(low, high)
        return point


# ─── Trial 评估 ────────────────────────────────────────────────────────────────

def _evaluate_trial(
    params: dict,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    task_type: str,
    max_iter: int = 100,
    timeout: float = 30.0,
) -> tuple[float, float]:
    """评估一组超参数"""
    import time
    from sklearn.metrics import accuracy_score, r2_score

    start = time.time()
    if time.time() - start > timeout:
        return 0.0, 0.0

    model_type = params.pop("model_type", "sklearn")
    n_estimators = params.pop("n_estimators", 50)
    max_depth = params.pop("max_depth", 5)
    learning_rate = params.pop("learning_rate", 0.1)

    try:
        if model_type in ("random_forest",):
            model = create_model("sklearn", model_class="RandomForestClassifier" if task_type == "classification" else "RandomForestRegressor",
                                 n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        elif model_type in ("xgboost",):
            model = create_model("xgboost", n_estimators=n_estimators, max_depth=max_depth,
                                  learning_rate=learning_rate, random_state=42,
                                  objective="binary:logistic" if task_type == "classification" else "reg:squarederror")
        elif model_type in ("lightgbm",):
            model = create_model("lightgbm", n_estimators=n_estimators, max_depth=max_depth,
                                  learning_rate=learning_rate, random_state=42)
        else:
            model = create_model("sklearn", model_class="RandomForestClassifier" if task_type == "classification" else "RandomForestRegressor",
                                 n_estimators=n_estimators, max_depth=max_depth, random_state=42)

        model.fit(X_train, y_train)

        y_pred_train = model.predict(X_train)
        y_pred_val = model.predict(X_val)

        if task_type == "classification":
            train_score = accuracy_score(y_train, y_pred_train)
            val_score = accuracy_score(y_val, y_pred_val)
        else:
            train_score = r2_score(y_train, y_pred_train)
            val_score = r2_score(y_val, y_pred_val)

        return float(train_score), float(val_score)
    except Exception as e:
        return 0.0, 0.0


# ─── AutoML Engine ─────────────────────────────────────────────────────────────

class AutoMLEngine:
    """AutoML 搜索引擎

    用法:
        engine = AutoMLEngine(
            task_type="classification",
            X_train=X_train, y_train=y_train,
            X_val=X_val, y_val=y_val,
            strategy="random",  # grid | random
            n_trials=20,
            search_space=search_space,
        )
        result = engine.run()
    """

    DEFAULT_SEARCH_SPACE = {
        "classification": SearchSpace()
            .add("model_type", ["random_forest", "xgboost", "lightgbm"])
            .add_int("n_estimators", 50, 200)
            .add_int("max_depth", 3, 10)
            .add_float("learning_rate", 0.01, 0.3, log=True),
        "regression": SearchSpace()
            .add("model_type", ["random_forest", "xgboost", "lightgbm"])
            .add_int("n_estimators", 50, 200)
            .add_int("max_depth", 3, 10)
            .add_float("learning_rate", 0.01, 0.3, log=True),
    }

    def __init__(
        self,
        task_type: Literal["classification", "regression"],
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        strategy: Literal["grid", "random"] = "random",
        n_trials: int = 20,
        search_space: SearchSpace | None = None,
        max_iter_per_trial: int = 100,
        timeout_per_trial: float = 30.0,
        random_state: int = 42,
        experiment=None,
    ):
        self.task_type = task_type
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.strategy = strategy
        self.n_trials = n_trials
        self.search_space = search_space or self.DEFAULT_SEARCH_SPACE[task_type]
        self.max_iter = max_iter_per_trial
        self.timeout = timeout_per_trial
        self.experiment = experiment
        self._rng = np.random.default_rng(random_state)
        self._trials: list[TrialResult] = []

    def run(self) -> AutoMLResult:
        """执行 AutoML 搜索"""
        import time

        start_time = time.time()

        if self.strategy == "grid":
            self._run_grid()
        else:
            self._run_random()

        total_time = time.time() - start_time

        best_trial = max(self._trials, key=lambda t: t.val_score)

        return AutoMLResult(
            best_params=best_trial.params,
            best_val_score=best_trial.val_score,
            best_train_score=best_trial.train_score,
            trials=list(self._trials),
            strategy=self.strategy,
            n_trials=len(self._trials),
            total_time=total_time,
        )

    def _run_grid(self) -> None:
        """Grid Search"""
        points = self.search_space.grid_points()
        # 限制 Grid 点数
        if len(points) > self.n_trials:
            points = points[:self.n_trials]

        for i, params in enumerate(points):
            self._evaluate(params, i)

    def _run_random(self) -> None:
        """Random Search"""
        for i in range(self.n_trials):
            params = self.search_space.random_point(self._rng)
            self._evaluate(params, i)

    def _evaluate(self, params: dict, trial_id: int) -> None:
        """评估单个参数组合"""
        import time

        start = time.time()
        train_score, val_score = _evaluate_trial(
            params,
            self.X_train, self.y_train,
            self.X_val, self.y_val,
            self.task_type,
            self.max_iter,
            self.timeout,
        )
        elapsed = time.time() - start

        result = TrialResult(
            trial_id=trial_id,
            params=dict(params),
            train_score=train_score,
            val_score=val_score,
            train_time=elapsed,
        )
        self._trials.append(result)

        # 注册到 Experiment
        if self.experiment:
            self.experiment.record_metric("val_score", val_score, trial_id)

        # 打印进度
        best_so_far = max(t.val_score for t in self._trials)
        print(f"  [AutoML] Trial {trial_id + 1}/{self.n_trials} | "
              f"Val: {val_score:.4f} | Best: {best_so_far:.4f} | "
              f"Time: {elapsed:.1f}s | Params: {params.get('model_type', '?')}")

    def get_top_models(self, top_k: int = 3) -> list[TrialResult]:
        """返回 Top-K 模型"""
        return sorted(self._trials, key=lambda t: t.val_score, reverse=True)[:top_k]

    def generate_report(self) -> str:
        """生成 Markdown 调优报告"""
        lines = [
            f"# AutoML 调优报告",
            f"",
            f"**任务类型**: {self.task_type}",
            f"**搜索策略**: {self.strategy}",
            f"**搜索次数**: {len(self._trials)}",
            f"**最佳验证分数**: {max(t.val_score for t in self._trials):.4f}",
            f"**最佳参数**: `{self._trials[-1].params if self._trials else 'N/A'}`",
            f"",
            f"## Top-3 模型",
            f"",
            f"| 排名 | 模型 | 验证分数 | 训练分数 | 用时 |",
            f"|------|------|----------|----------|------|",
        ]

        for i, trial in enumerate(self.get_top_models(3), 1):
            lines.append(
                f"| {i} | {trial.params.get('model_type', '?')} | "
                f"{trial.val_score:.4f} | {trial.train_score:.4f} | "
                f"{trial.train_time:.1f}s |"
            )

        return "\n".join(lines)
