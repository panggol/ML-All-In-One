"""
实验管理模块 - Experiment Tracking

功能：
- 实验参数记录
- 训练指标记录
- 实验对比分析
- 超参数搜索
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd


@dataclass
class Experiment:
    """实验记录"""

    id: str
    name: str
    description: str = ""

    # 参数
    params: dict[str, Any] = field(default_factory=dict)

    # 指标
    metrics: dict[str, list[float]] = field(default_factory=dict)

    # 结果
    results: dict[str, Any] = field(default_factory=dict)

    # 状态
    status: str = "pending"  # pending, running, completed, failed

    # 时间
    start_time: str | None = None
    end_time: str | None = None

    # 路径
    checkpoint_path: str | None = None
    log_path: str | None = None

    # 标签
    tags: list[str] = field(default_factory=list)

    # 父实验（用于对比）
    parent_id: str | None = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Experiment":
        """从字典创建"""
        return cls(**data)


class ExperimentTracker:
    """
    实验追踪器

    记录和管理实验，支持：
    - 参数记录
    - 指标记录
    - 实验对比
    - 超参数搜索
    """

    def __init__(
        self,
        experiment_dir: str = "./experiments",
        experiment_name: str | None = None,
        description: str = "",
        params: dict | None = None,
        tags: list[str] | None = None,
    ):
        """
        初始化实验追踪器

        Args:
            experiment_dir: 实验存储目录
            experiment_name: 实验名称
            description: 实验描述
            params: 实验参数
            tags: 实验标签
        """
        self.experiment_dir = Path(experiment_dir)
        self.experiment_dir.mkdir(parents=True, exist_ok=True)

        # 创建实验
        self.experiment = self._create_experiment(
            name=experiment_name, description=description, params=params, tags=tags
        )

        # 当前实验 ID
        self.experiment_id = self.experiment.id

    def _create_experiment(
        self,
        name: str | None,
        description: str,
        params: dict | None,
        tags: list[str] | None,
    ) -> Experiment:
        """创建实验记录"""
        # 生成唯一 ID
        timestamp = int(time.time() * 1000)
        exp_id = hashlib.md5(f"{timestamp}".encode()).hexdigest()[:8]

        # 默认名称
        if not name:
            name = f"exp_{exp_id}"

        experiment = Experiment(
            id=exp_id,
            name=name,
            description=description,
            params=params or {},
            tags=tags or [],
            start_time=datetime.now().isoformat(),
            status="running",
        )

        # 保存到文件
        self._save_experiment(experiment)

        return experiment

    def _save_experiment(self, experiment: Experiment) -> None:
        """保存实验记录"""
        exp_dir = self.experiment_dir / experiment.id
        exp_dir.mkdir(parents=True, exist_ok=True)

        exp_file = exp_dir / "experiment.json"
        with open(exp_file, "w", encoding="utf-8") as f:
            json.dump(experiment.to_dict(), f, ensure_ascii=False, indent=2)

    def log_params(self, params: dict[str, Any]) -> None:
        """记录参数"""
        self.experiment.params.update(params)
        self._save_experiment(self.experiment)

    def log_metric(self, name: str, value: float, step: int | None = None) -> None:
        """
        记录指标

        Args:
            name: 指标名称
            value: 指标值
            step: 步数（可选）
        """
        if name not in self.experiment.metrics:
            self.experiment.metrics[name] = []

        self.experiment.metrics[name].append(value)
        self._save_experiment(self.experiment)

    def log_metrics(
        self, metrics: dict[str, float], step: int | None = None
    ) -> None:
        """批量记录指标"""
        for name, value in metrics.items():
            self.log_metric(name, value, step)

    def log_results(self, results: dict[str, Any]) -> None:
        """记录最终结果"""
        self.experiment.results.update(results)
        self._save_experiment(self.experiment)

    def set_status(self, status: str) -> None:
        """设置实验状态"""
        self.experiment.status = status

        if status in ["completed", "failed"]:
            self.experiment.end_time = datetime.now().isoformat()

        self._save_experiment(self.experiment)

    def finish(self, results: dict | None = None) -> None:
        """结束实验"""
        if results:
            self.log_results(results)

        self.set_status("completed")

    def fail(self, error: str | None = None) -> None:
        """标记实验失败"""
        self.experiment.results["error"] = error
        self.set_status("failed")

    def add_tag(self, tag: str) -> None:
        """添加标签"""
        if tag not in self.experiment.tags:
            self.experiment.tags.append(tag)
            self._save_experiment(self.experiment)

    def get_experiment(self) -> Experiment:
        """获取当前实验"""
        return self.experiment

    @staticmethod
    def load_experiment(experiment_dir: str, experiment_id: str) -> Experiment:
        """加载实验"""
        exp_file = Path(experiment_dir) / experiment_id / "experiment.json"
        with open(exp_file, encoding="utf-8") as f:
            data = json.load(f)
        return Experiment.from_dict(data)

    @staticmethod
    def list_experiments(
        experiment_dir: str,
        tags: list[str] | None = None,
        status: str | None = None,
        sort_by: str = "start_time",
        ascending: bool = False,
    ) -> pd.DataFrame:
        """
        列出实验

        Args:
            experiment_dir: 实验目录
            tags: 过滤标签
            status: 过滤状态
            sort_by: 排序字段
            ascending: 升序

        Returns:
            实验列表 DataFrame
        """
        exp_dir = Path(experiment_dir)
        experiments = []

        for exp_path in exp_dir.iterdir():
            if not exp_path.is_dir():
                continue

            exp_file = exp_path / "experiment.json"
            if not exp_file.exists():
                continue

            with open(exp_file, encoding="utf-8") as f:
                exp_data = json.load(f)

            # 过滤
            if tags and not any(t in exp_data.get("tags", []) for t in tags):
                continue
            if status and exp_data.get("status") != status:
                continue

            experiments.append(exp_data)

        # 转换为 DataFrame
        df = pd.DataFrame(experiments)

        if not df.empty and sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending)

        return df


class ExperimentComparator:
    """实验对比器"""

    def __init__(self, experiment_dir: str):
        self.experiment_dir = Path(experiment_dir)

    def compare(
        self,
        experiment_ids: list[str],
        metrics: list[str] | None = None,
        params: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        对比多个实验

        Args:
            experiment_ids: 实验 ID 列表
            metrics: 要对比的指标
            params: 要对比的参数

        Returns:
            对比结果 DataFrame
        """
        rows = []

        for exp_id in experiment_ids:
            exp = ExperimentTracker.load_experiment(self.experiment_dir, exp_id)

            row = {
                "id": exp.id,
                "name": exp.name,
                "status": exp.status,
                "start_time": exp.start_time,
                "end_time": exp.end_time,
            }

            # 添加参数
            if params:
                for p in params:
                    row[p] = exp.params.get(p)

            # 添加指标（取最后一个值）
            if metrics:
                for m in metrics:
                    metric_values = exp.metrics.get(m, [])
                    row[f"{m}_final"] = metric_values[-1] if metric_values else None
                    row[f"{m}_best"] = max(metric_values) if metric_values else None

            # 添加结果
            for k, v in exp.results.items():
                row[k] = v

            rows.append(row)

        return pd.DataFrame(rows)

    def compare_best(
        self, metric: str, mode: str = "max", top_k: int = 10
    ) -> pd.DataFrame:
        """
        获取最佳实验

        Args:
            metric: 比较指标
            mode: 'max' 或 'min'
            top_k: 返回前 k 个

        Returns:
            最佳实验列表
        """
        df = ExperimentTracker.list_experiments(str(self.experiment_dir))

        if df.empty:
            return df

        # 计算最佳值
        if "metrics" in df.columns:

            def get_best(metrics_dict):
                if isinstance(metrics_dict, dict) and metric in metrics_dict:
                    values = metrics_dict[metric]
                    if mode == "max":
                        return max(values)
                    else:
                        return min(values)
                return None

            df["best_score"] = df["metrics"].apply(get_best)
            df = df.sort_values("best_score", ascending=(mode == "min"))

        return df.head(top_k)

    def get_metric_curve(self, experiment_id: str, metric: str) -> list[float]:
        """获取指标曲线"""
        exp = ExperimentTracker.load_experiment(self.experiment_dir, experiment_id)
        return exp.metrics.get(metric, [])


class HyperparameterSearcher:
    """超参数搜索器"""

    def __init__(
        self, experiment_dir: str, search_method: str = "grid"  # grid, random, bayesian
    ):
        self.experiment_dir = experiment_dir
        self.search_method = search_method

    def grid_search(
        self,
        param_grid: dict[str, list[Any]],
        base_params: dict | None = None,
        metric: str = "val_acc",
        mode: str = "max",
    ) -> dict[str, Any]:
        """
        网格搜索

        Args:
            param_grid: 参数网格
            base_params: 基础参数
            metric: 优化指标
            mode: 'max' 或 'min'

        Returns:
            最佳参数
        """
        from itertools import product

        base_params = base_params or {}
        best_score = float("-inf") if mode == "max" else float("inf")
        best_params = None

        # 生成所有参数组合
        keys = list(param_grid.keys())
        values = list(param_grid.values())

        for combo in product(*values):
            params = {**base_params, **dict(zip(keys, combo))}

            # 创建实验
            tracker = ExperimentTracker(
                experiment_dir=self.experiment_dir, params=params
            )

            yield params, tracker

    def random_search(
        self,
        param_distributions: dict[str, Any],
        base_params: dict | None = None,
        n_trials: int = 10,
        metric: str = "val_acc",
        mode: str = "max",
    ) -> dict[str, Any]:
        """
        随机搜索

        Args:
            param_distributions: 参数分布
            base_params: 基础参数
            n_trials: 试验次数
            metric: 优化指标
            mode: 'max' 或 'min'

        Returns:
            最佳参数
        """
        import random

        base_params = base_params or {}
        best_score = float("-inf") if mode == "max" else float("inf")
        best_params = None

        for _ in range(n_trials):
            params = {}
            for key, dist in param_distributions.items():
                if isinstance(dist, list):
                    params[key] = random.choice(dist)
                elif isinstance(dist, tuple) and len(dist) == 2:
                    # 数值范围
                    min_val, max_val = dist
                    params[key] = random.uniform(min_val, max_val)
                else:
                    params[key] = dist

            params = {**base_params, **params}

            tracker = ExperimentTracker(
                experiment_dir=self.experiment_dir, params=params
            )

            yield params, tracker
