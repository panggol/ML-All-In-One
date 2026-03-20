# -*- coding: utf-8 -*-
"""
sklearn 训练示例
"""

import sys
sys.path.insert(0, 'src/mlkit')

from mlkit import create_runner, Config, ImbalanceHandler, DataValidator
from sklearn.datasets import make_classification
import numpy as np


def main():
    # 1. 生成模拟数据
    print("=" * 50)
    print("1. 生成模拟数据")
    print("=" * 50)

    X, y = make_classification(
        n_samples=10000,
        n_features=20,
        n_informative=15,
        n_redundant=5,
        n_classes=2,
        weights=[0.9, 0.1],  # 不均衡数据
        random_state=42
    )

    print(f"数据形状: {X.shape}")
    print(f"类别分布: {np.bincount(y)}")

    # 2. 数据验证
    print("\n" + "=" * 50)
    print("2. 数据验证")
    print("=" * 50)

    from mlkit.data import DataValidator
    validation_result = DataValidator.validate(X, y)
    print(f"数据有效: {validation_result['valid']}")
    print(f"警告: {validation_result['warnings']}")

    # 3. 处理样本不均衡
    print("\n" + "=" * 50)
    print("3. 处理样本不均衡 - SMOTE")
    print("=" * 50)

    X_resampled, y_resampled = ImbalanceHandler.handle(
        X, y,
        method='smote',
        random_state=42
    )

    print(f"处理后数据形状: {X_resampled.shape}")
    print(f"处理后类别分布: {np.bincount(y_resampled)}")

    # 4. 创建配置文件
    print("\n" + "=" * 50)
    print("4. 创建训练配置")
    print("=" * 50)

    config_dict = {
        'model': {
            'type': 'sklearn',
            'task': 'classification',
            'model_class': 'RandomForestClassifier',
            'n_estimators': 100,
            'max_depth': 10,
            'random_state': 42
        },
        'train': {
            'epochs': 5,
        },
        'hooks': {
            'logger': True,
            'log_dir': './logs',
            'log_interval': 1,
            'checkpoint': True,
            'save_dir': './checkpoints',
            'save_best': True,
            'monitor': 'val_acc',
            'save_interval': 1,
        }
    }

    config = Config.from_dict(config_dict)
    print(config.to_yaml())

    # 5. 创建并运行 Runner
    print("\n" + "=" * 50)
    print("5. 开始训练")
    print("=" * 50)

    runner = create_runner(config)

    # 手动设置数据集
    from mlkit.data import Dataset
    runner.train_dataset = Dataset(X_resampled, y_resampled)

    # 创建验证集
    X_val, y_val = make_classification(
        n_samples=1000,
        n_features=20,
        n_informative=15,
        n_redundant=5,
        n_classes=2,
        weights=[0.9, 0.1],
        random_state=123
    )
    runner.val_dataset = Dataset(X_val, y_val)

    # 运行训练
    history = runner.train()

    print("\n训练完成!")
    print(f"训练历史: {history['train_history']}")
    print(f"验证历史: {history['val_history']}")

    # 6. 测试预测
    print("\n" + "=" * 50)
    print("6. 测试预测")
    print("=" * 50)

    X_test, y_test = make_classification(
        n_samples=100,
        n_features=20,
        random_state=999
    )

    predictions = runner.predict(X_test)
    accuracy = (predictions == y_test).mean()
    print(f"测试准确率: {accuracy:.4f}")

    # 7. 保存模型
    print("\n" + "=" * 50)
    print("7. 保存模型")
    print("=" * 50)

    runner.save_model('./checkpoints/final_model.pth')
    print("模型已保存到 ./checkpoints/final_model.pth")


if __name__ == '__main__':
    main()
