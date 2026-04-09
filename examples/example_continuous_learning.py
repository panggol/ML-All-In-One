"""
Continuous Learning 示例

展示如何用 Experiment + Hook 系统实现"每次训练都变成未来学习的素材"。

Harness Engineering 核心理念：
- 每次训练 → 历史实验数据 → 提取模式 → 指导未来实验
"""

import tempfile
import shutil
from pathlib import Path

# 1. 准备配置和数据
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

from mlkit.config import Config
from mlkit.runner import Runner, create_runner
from mlkit.experiment import ExperimentManager

# 2. 创建实验管理器
exp_dir = tempfile.mkdtemp(prefix="mlkit_cl_")
manager = ExperimentManager(exp_dir)

# 3. 运行多组实验（Continuous Learning 的核心：积累实验数据）
experiments_to_run = [
    ("rf-depth-5", {"max_depth": 5, "n_estimators": 100}),
    ("rf-depth-10", {"max_depth": 10, "n_estimators": 100}),
    ("rf-depth-15", {"max_depth": 15, "n_estimators": 100}),
    ("rf-depth-None", {"max_depth": None, "n_estimators": 100}),
]

print("=" * 60)
print("Continuous Learning 演示：随机森林深度调优")
print("=" * 60)

for exp_name, params in experiments_to_run:
    print(f"\n>>> 运行实验：{exp_name}，参数：{params}")

    # 3.1 创建实验记录
    exp = manager.create_experiment(
        name=exp_name,
        params={"model": "RandomForest", **params},
        description=f"随机森林深度调优实验，depth={params['max_depth']}",
    )

    # 3.2 生成数据
    X, y = make_classification(
        n_samples=1000, n_features=20, n_informative=10,
        random_state=42
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 3.3 创建模型
    model = RandomForestClassifier(random_state=42, **params)
    model.fit(X_train, y_train)

    # 3.4 模拟训练过程（模拟多 epoch）
    for epoch in range(1, 6):
        train_acc = model.score(X_train, y_train)
        val_acc = model.score(X_val, y_val)
        val_loss = 1 - val_acc

        # 3.5 ExperimentTrackHook 自动记录每 epoch 指标
        exp.record_metric("train_acc", train_acc, epoch)
        exp.record_metric("val_acc", val_acc, epoch)
        exp.record_metric("val_loss", val_loss, epoch)

        print(f"  Epoch {epoch}: train_acc={train_acc:.4f} val_acc={val_acc:.4f} val_loss={val_loss:.4f}")

    # 3.6 更新最终指标
    exp.update_final_metrics({
        "final_train_acc": train_acc,
        "final_val_acc": val_acc,
    })
    exp.finish()
    manager.save_experiment(exp)

    print(f"  ✅ 实验完成：best_val_acc={exp.best_metrics.get('val_acc', 0):.4f}")

# 4. 实验对比（Continuous Learning 的"学习"时刻）
print("\n" + "=" * 60)
print("实验对比（Continuous Learning 结果）")
print("=" * 60)

results = manager.compare("val_acc")
for r in results:
    print(f"  [{r['status']:12}] {r['name']:20} "
          f"best_val_acc={r['best']:.4f}  "
          f"params={r['params']}")

# 5. 找到最优实验
best = manager.best_experiment("val_acc", mode="max")
if best:
    print(f"\n🏆 最优实验：{best.name}")
    print(f"   最佳 val_acc：{best.best_metrics.get('val_acc', 0):.4f}")
    print(f"   最优参数：depth={best.params.get('max_depth')}")

# 6. 生成报告
print("\n" + "=" * 60)
print("Markdown 实验报告")
print("=" * 60)
report = manager.generate_report()
print(report)

# 7. 清理
shutil.rmtree(exp_dir)
print(f"\n临时目录已清理：{exp_dir}")
