# -*- coding: utf-8 -*-
"""
推理服务示例
"""

import sys
sys.path.insert(0, 'src/mlkit')

from mlkit import serve_model
from mlkit.api import ModelRegistry, run_inference_server
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
import numpy as np


def train_and_serve():
    """训练模型并启动推理服务"""

    # 1. 生成训练数据
    print("生成训练数据...")
    X, y = make_classification(
        n_samples=5000,
        n_features=5,
        n_classes=3,
        n_informative=3,
        random_state=42
    )

    # 2. 训练模型
    print("训练模型...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    # 3. 启动推理服务
    print("启动推理服务...")
    serve_model(
        model=model,
        model_name="RandomForest_Classifier",
        model_type="sklearn",
        task_type="classification",
        input_features=["feature_0", "feature_1", "feature_2", "feature_3", "feature_4"],
        output_classes=["class_0", "class_1", "class_2"],
        model_dir="./models",
        host="0.0.0.0",
        port=8000
    )


def use_existing_model():
    """使用已存在的模型启动服务"""

    # 加载已训练的模型
    import joblib
    model = joblib.load("./checkpoints/final_model.pth")

    # 启动服务
    serve_model(
        model=model,
        model_name="My_Model",
        model_type="sklearn",
        task_type="classification",
        input_features=["feature_0", "feature_1", "feature_2", "feature_3", "feature_4"],
        model_dir="./models",
        port=8001
    )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="推理服务示例")
    parser.add_argument('--mode', choices=['train', 'serve'], default='train',
                       help='模式: train=训练并启动, serve=使用已有模型')
    args = parser.parse_args()

    if args.mode == 'train':
        train_and_serve()
    else:
        use_existing_model()
