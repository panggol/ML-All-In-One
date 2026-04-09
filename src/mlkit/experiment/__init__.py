"""
Experiment 系统 - 实验追踪与对比

Harness Engineering 核心理念：
- 每个实验的结果都值得记录，形成组织的"记忆"
- Continuous Learning 的基础设施：历史实验 → 提取模式 → 指导未来实验

功能：
- 训练历史记录（metrics, params, artifacts）
- 超参数记录
- 实验对比（多实验横向对比）
- 自动生成实验报告
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ── 数据结构 ──────────────────────────────────────────────


@dataclass
class MetricRecord:
    """单条指标记录"""
    name: str
    value: float
    step: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class Experiment:
    """单次实验记录"""

    id: str
    name: str
    description: str = ""
    status: str = "running"  # running / completed / failed / interrupted
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    # 超参数
    params: dict[str, Any] = field(default_factory=dict)

    # 指标历史
    metrics: dict[str, list[MetricRecord]] = field(default_factory=dict)

    # 最佳指标
    best_metrics: dict[str, float] = field(default_factory=dict)

    # 最终指标（训练结束时的值）
    final_metrics: dict[str, float] = field(default_factory=dict)

    # artifacts 路径
    artifacts_dir: Path | None = None

    # 备注
    notes: str = ""

    # metadata
    git_commit: str | None = None
    duration: float | None = None  # 秒

    def record_metric(self, name: str, value: float, step: int) -> None:
        """记录一条指标"""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(MetricRecord(name=name, value=value, step=step))

        # 更新 best_metrics
        if name not in self.best_metrics:
            self.best_metrics[name] = value
        else:
            # 简单实现：假设 monitor 越小越好
            if value < self.best_metrics[name]:
                self.best_metrics[name] = value

    def update_final_metrics(self, metrics: dict[str, float]) -> None:
        """更新最终指标"""
        self.final_metrics.update(metrics)

    def finish(self, status: str = "completed") -> None:
        """标记实验结束"""
        self.status = status
        self.finished_at = time.time()
        if self.created_at:
            self.duration = self.finished_at - self.created_at

    def to_dict(self) -> dict:
        """序列化"""
        d = asdict(self)
        d["artifacts_dir"] = str(self.artifacts_dir) if self.artifacts_dir else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Experiment":
        """反序列化"""
        if data.get("artifacts_dir"):
            data["artifacts_dir"] = Path(data["artifacts_dir"])
        # 反序列化 MetricRecord
        if "metrics" in data:
            for name, records in data["metrics"].items():
                data["metrics"][name] = [
                    MetricRecord(**r) if isinstance(r, dict) else r
                    for r in records
                ]
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


# ── 实验管理器 ──────────────────────────────────────────────


class ExperimentManager:
    """实验管理器

    管理所有实验记录，支持：
    - 创建新实验
    - 记录指标
    - 查询历史
    - 横向对比

    用法:
        manager = ExperimentManager("./experiments")
        exp = manager.create_experiment("baseline-v1", params={"lr": 0.001})

        # 训练循环中
        exp.record_metric("train_loss", 0.5, step=1)
        exp.record_metric("val_loss", 0.6, step=1)

        # 训练结束后
        exp.update_final_metrics({"final_train_loss": 0.1, "final_val_loss": 0.15})
        exp.finish()
        manager.save_experiment(exp)
    """

    def __init__(self, base_dir: str | Path = "./experiments"):
        self.base_dir = Path(base_dir)
        self.experiments: dict[str, Experiment] = {}
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.base_dir / "index.json"

    def create_experiment(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        description: str = "",
        git_commit: str | None = None,
    ) -> Experiment:
        """创建新实验"""
        exp_id = f"{name}_{int(time.time())}"
        exp = Experiment(
            id=exp_id,
            name=name,
            description=description,
            params=params or {},
            git_commit=git_commit,
            artifacts_dir=self.base_dir / exp_id,
        )
        exp.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.experiments[exp_id] = exp
        return exp

    def save_experiment(self, exp: Experiment) -> None:
        """保存实验到文件"""
        exp_dir = self.base_dir / exp.id
        exp_dir.mkdir(parents=True, exist_ok=True)
        exp_file = exp_dir / "experiment.json"
        with open(exp_file, "w", encoding="utf-8") as f:
            json.dump(exp.to_dict(), f, indent=2, ensure_ascii=False)
        self._save_index()

    def load_experiment(self, exp_id: str) -> Experiment | None:
        """从文件加载实验"""
        if exp_id in self.experiments:
            return self.experiments[exp_id]
        exp_file = self.base_dir / exp_id / "experiment.json"
        if not exp_file.exists():
            return None
        with open(exp_file, encoding="utf-8") as f:
            data = json.load(f)
        exp = Experiment.from_dict(data)
        self.experiments[exp_id] = exp
        return exp

    def load_all(self) -> dict[str, Experiment]:
        """加载所有实验"""
        if not self._index_file.exists():
            return {}
        with open(self._index_file, encoding="utf-8") as f:
            index = json.load(f)
        for exp_id in index.get("experiments", []):
            self.load_experiment(exp_id)
        return self.experiments

    def _save_index(self) -> None:
        """保存索引文件"""
        index = {
            "experiments": list(self.experiments.keys()),
            "last_updated": time.time(),
        }
        with open(self._index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)

    def compare(
        self,
        metric: str,
        filter_fn=None,
    ) -> list[dict]:
        """横向对比实验中的某个指标

        Args:
            metric: 指标名（如 "val_loss"）
            filter_fn: 可选的过滤函数 (Experiment → bool)

        Returns:
            按指标排序的实验列表
        """
        results = []
        for exp_id, exp in self.experiments.items():
            if filter_fn and not filter_fn(exp):
                continue
            best = exp.best_metrics.get(metric)
            final = exp.final_metrics.get(metric)
            results.append({
                "exp_id": exp_id,
                "name": exp.name,
                "best": best,
                "final": final,
                "status": exp.status,
                "duration": exp.duration,
                "params": exp.params,
            })
        return sorted(results, key=lambda x: x["best"] or float("inf"))

    def best_experiment(self, metric: str, mode: str = "min") -> Experiment | None:
        """找到某指标最优的实验"""
        if not self.experiments:
            self.load_all()
        best: Experiment | None = None
        best_score: float | None = None
        for exp in self.experiments.values():
            if exp.status != "completed":
                continue
            score = exp.best_metrics.get(metric)
            if score is None:
                continue
            if best_score is None:
                best = exp
                best_score = score
            elif mode == "min" and score < best_score:
                best = exp
                best_score = score
            elif mode == "max" and score > best_score:
                best = exp
                best_score = score
        return best

    def generate_report(self, exp_ids: list[str] | None = None) -> str:
        """生成 Markdown 实验报告

        Args:
            exp_ids: 指定实验ID列表，None 表示所有实验
        """
        if exp_ids:
            exps = [self.experiments[eid] for eid in exp_ids if eid in self.experiments]
        else:
            exps = list(self.experiments.values())

        lines = ["# 实验报告", ""]
        lines.append(f"实验数量：{len(exps)}")
        lines.append("")

        for exp in sorted(exps, key=lambda e: e.created_at):
            lines.append(f"## {exp.name}")
            lines.append(f"**ID**: `{exp.id}`")
            lines.append(f"**状态**: {exp.status}")
            lines.append(f"**耗时**: {exp.duration:.1f}s" if exp.duration else "**耗时**: N/A")
            if exp.description:
                lines.append(f"**描述**: {exp.description}")
            lines.append("")

            if exp.params:
                lines.append("**超参数**：")
                for k, v in exp.params.items():
                    lines.append(f"- {k}: {v}")
                lines.append("")

            if exp.best_metrics:
                lines.append("**最佳指标**：")
                for k, v in exp.best_metrics.items():
                    lines.append(f"- {k}: {v:.4f}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def summary(self) -> dict:
        """返回实验统计摘要"""
        if not self.experiments:
            self.load_all()
        completed = [e for e in self.experiments.values() if e.status == "completed"]
        return {
            "total": len(self.experiments),
            "completed": len(completed),
            "running": sum(1 for e in self.experiments.values() if e.status == "running"),
            "failed": sum(1 for e in self.experiments.values() if e.status == "failed"),
        }


# ExperimentTrackHook 在 hooks 模块中定义为避免循环导入
# 使用时请从 mlkit.experiment 导入


# ExperimentTrackHook 在单独文件中避免循环导入
from mlkit.experiment.hook import ExperimentTrackHook

__all__ = ["Experiment", "ExperimentManager", "ExperimentTrackHook"]

