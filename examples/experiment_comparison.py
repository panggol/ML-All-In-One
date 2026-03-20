# -*- coding: utf-8 -*-
"""
实验对比示例
"""

import sys
sys.path.insert(0, 'src/mlkit')

from mlkit.experiment import ExperimentTracker, ExperimentComparator
from sklearn.datasets import make_classification
import numpy as np


def run_experiment(
    experiment_name: str,
    n_estimators: int,
    max_depth: int,
    experiment_dir: str = "./experiments"
):
    """运行单个实验"""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, f1_score

    # 创建实验追踪器
    tracker = ExperimentTracker(
        experiment_dir=experiment_dir,
        experiment_name=experiment_name,
        description=f"RandomForest n_estimators={n_estimators}, max_depth={max_depth}",
        params={
            'model': 'RandomForest',
            'n_estimators': n_estimators,
            'max_depth': max_depth,
            'random_state': 42
        },
        tags=['sklearn', 'random_forest']
    )

    # 生成数据
    X, y = make_classification(
        n_samples=5000,
        n_features=20,
        n_informative=15,
        n_redundant=5,
        n_classes=2,
        random_state=42
    )

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 训练模型
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42
    )
    model.fit(X_train, y_train)

    # 评估
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='weighted')

    # 记录指标
    tracker.log_metric('train_acc', 1.0)
    tracker.log_metric('val_acc', acc)
    tracker.log_metric('val_f1', f1)

    # 记录结果
    tracker.finish(results={
        'test_acc': acc,
        'test_f1': f1
    })

    print(f"✓ {experiment_name}: acc={acc:.4f}, f1={f1:.4f}")

    return tracker.experiment_id


def main():
    experiment_dir = "./experiments"

    print("=" * 60)
    print("实验对比示例")
    print("=" * 60)

    # 运行多个实验
    print("\n1. 运行实验...")
    experiment_ids = []

    # 实验1: n_estimators=50, max_depth=5
    exp_id = run_experiment(
        "RF_baseline",
        n_estimators=50,
        max_depth=5,
        experiment_dir=experiment_dir
    )
    experiment_ids.append(exp_id)

    # 实验2: n_estimators=100, max_depth=10
    exp_id = run_experiment(
        "RF_deeper",
        n_estimators=100,
        max_depth=10,
        experiment_dir=experiment_dir
    )
    experiment_ids.append(exp_id)

    # 实验3: n_estimators=200, max_depth=15
    exp_id = run_experiment(
        "RF_deepest",
        n_estimators=200,
        max_depth=15,
        experiment_dir=experiment_dir
    )
    experiment_ids.append(exp_id)

    # 实验对比
    print("\n2. 实验对比...")
    comparator = ExperimentComparator(experiment_dir)

    comparison_df = comparator.compare(
        experiment_ids=experiment_ids,
        metrics=['val_acc', 'val_f1'],
        params=['n_estimators', 'max_depth']
    )

    print("\n对比结果:")
    print(comparison_df[['name', 'n_estimators', 'max_depth', 'val_acc_final', 'val_f1_final']].to_string(index=False))

    # 最佳实验
    print("\n3. 最佳实验...")
    best_df = comparator.compare_best(metric='val_acc', mode='max', top_k=3)
    print("\nTop 3:")
    print(best_df[['name', 'best_score']].to_string(index=False))


if __name__ == '__main__':
    main()
