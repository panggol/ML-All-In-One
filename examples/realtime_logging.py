# -*- coding: utf-8 -*-
"""
实时日志示例 - WebSocket 推送训练过程
"""

import sys
sys.path.insert(0, 'src/mlkit')

import asyncio
from mlkit.utils import RealTimeLogger, TrainingLogger
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier


async def simulate_training(experiment_id: str = "exp_001"):
    """模拟训练过程，带实时日志"""

    # 创建实时日志器
    realtime_logger = RealTimeLogger(host="0.0.0.0", port=8765)
    logger = TrainingLogger(realtime_logger, experiment_id)

    # 启动 WebSocket 服务器
    server_task = asyncio.create_task(realtime_logger.start_server())

    await logger.log_system("=" * 50)
    await logger.log_system("训练任务开始")
    await logger.log_system(f"实验ID: {experiment_id}")
    await logger.log_system("=" * 50)

    # 生成模拟数据
    X, y = make_classification(n_samples=1000, n_features=10, random_state=42)
    model = RandomForestClassifier(n_estimators=10)

    # 模拟训练
    epochs = 5
    for epoch in range(epochs):
        await logger.log(f"开始第 {epoch + 1}/{epochs} 轮训练...")

        # 模拟训练步骤
        model.fit(X, y)
        train_score = model.score(X, y)

        # 模拟验证
        val_score = train_score - 0.05  # 模拟验证集略低

        # 记录指标
        await logger.log_metrics({
            "train_acc": train_score,
            "val_acc": val_score,
            "loss": 1 - train_score
        }, epoch=epoch, step=epoch)

        # 模拟进度
        await logger.log_progress(epoch + 1, epochs, f"Epoch {epoch + 1}/{epochs}")

        # 模拟延迟
        await asyncio.sleep(1)

    await logger.log_system("训练完成!")
    await logger.log(f"最终验证准确率: {val_score:.4f}")

    # 停止服务器
    server_task.cancel()

    try:
        await server_task
    except asyncio.CancelledError:
        pass


def main():
    print("=" * 60)
    print("实时日志示例")
    print("=" * 60)
    print("\n启动 WebSocket 服务器: ws://localhost:8765")
    print("使用 WebSocket 客户端连接后可接收实时日志\n")

    # 运行异步任务
    asyncio.run(simulate_training())


if __name__ == '__main__':
    main()
