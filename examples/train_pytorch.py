# -*- coding: utf-8 -*-
"""
PyTorch 训练示例
"""

import sys
sys.path.insert(0, 'src/mlkit')

import torch
import torch.nn as nn
import numpy as np
from mlkit import create_runner, Config
from mlkit.data import Dataset
from sklearn.datasets import make_classification


class SimpleNN(nn.Module):
    """简单的神经网络"""

    def __init__(self, input_dim, hidden_dim=64, output_dim=2):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x):
        return self.network(x)


def main():
    # 1. 生成模拟数据
    print("=" * 50)
    print("1. 生成模拟数据")
    print("=" * 50)

    X, y = make_classification(
        n_samples=5000,
        n_features=20,
        n_informative=15,
        n_redundant=5,
        n_classes=2,
        random_state=42
    )

    # 转换为 PyTorch 格式
    X = X.astype(np.float32)
    y = y.astype(np.int64)  # PyTorch 分类需要 long 类型

    print(f"数据形状: {X.shape}")
    print(f"类别分布: {np.bincount(y)}")

    # 2. 划分训练集和验证集
    from sklearn.model_selection import train_test_split
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 3. 创建 PyTorch 模型
    print("\n" + "=" * 50)
    print("2. 创建 PyTorch 模型")
    print("=" * 50)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"使用设备: {device}")

    model = SimpleNN(input_dim=20, hidden_dim=64, output_dim=2)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # 4. 创建配置文件
    print("\n" + "=" * 50)
    print("3. 创建训练配置")
    print("=" * 50)

    config_dict = {
        'model': {
            'type': 'pytorch',
            'task': 'classification',
        },
        'train': {
            'epochs': 10,
            'batch_size': 64,
        },
        'hooks': {
            'logger': True,
            'log_dir': './logs',
            'log_interval': 10,
            'checkpoint': True,
            'save_dir': './checkpoints',
            'save_best': True,
            'monitor': 'val_acc',
            'save_interval': 2,
        }
    }

    config = Config.from_dict(config_dict)

    # 5. 创建 Runner
    print("\n" + "=" * 50)
    print("4. 开始训练")
    print("=" * 50)

    # 使用自定义模型
    from mlkit.model import PyTorchModel
    pytorch_model = PyTorchModel(
        model=model,
        criterion=criterion,
        optimizer=optimizer,
        device=device
    )

    runner = create_runner(config)
    runner.model = pytorch_model

    # 设置数据集
    runner.train_dataset = Dataset(X_train, y_train)
    runner.val_dataset = Dataset(X_val, y_val)

    # 运行训练
    history = runner.train()

    print("\n训练完成!")
    print(f"最终训练准确率: {history['train_history'][-1].get('train_acc', 'N/A')}")
    print(f"最终验证准确率: {history['val_history'][-1].get('val_acc', 'N/A')}")

    # 6. 测试预测
    print("\n" + "=" * 50)
    print("5. 测试预测")
    print("=" * 50)

    X_test, y_test = make_classification(
        n_samples=100,
        n_features=20,
        random_state=999
    )
    X_test = X_test.astype(np.float32)

    predictions = runner.predict(X_test)
    accuracy = (predictions == y_test).mean()
    print(f"测试准确率: {accuracy:.4f}")

    # 7. 保存模型
    print("\n" + "=" * 50)
    print("6. 保存模型")
    print("=" * 50)

    runner.save_model('./checkpoints/pytorch_model.pth')
    print("模型已保存")


if __name__ == '__main__':
    main()
