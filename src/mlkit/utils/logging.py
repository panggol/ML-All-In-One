"""
实时日志服务 - Real-time Logging

支持 WebSocket 推送训练日志和指标
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol


@dataclass
class LogMessage:
    """日志消息"""

    type: str  # log, metric, progress, error, system
    content: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    experiment_id: str | None = None
    epoch: int | None = None
    iter: int | None = None


class RealTimeLogger:
    """
    实时日志推送器

    使用 WebSocket 推送训练日志到前端
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: set[WebSocketServerProtocol] = set()
        self.server = None

    async def connect(self, websocket: WebSocketServerProtocol):
        """客户端连接"""
        self.clients.add(websocket)
        print(f"Client connected. Total clients: {len(self.clients)}")

    async def disconnect(self, websocket: WebSocketServerProtocol):
        """客户端断开"""
        self.clients.discard(websocket)
        print(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message: LogMessage):
        """广播消息到所有客户端"""
        if not self.clients:
            return

        message_json = json.dumps(message.__dict__, ensure_ascii=False, default=str)

        # 复制客户端集合，避免迭代时修改
        clients_snapshot = self.clients.copy()

        # 异步发送到所有客户端
        await asyncio.gather(
            *[self._send(ws, message_json) for ws in clients_snapshot],
            return_exceptions=True,
        )

    async def _send(self, websocket: WebSocketServerProtocol, message: str):
        """发送消息到单个客户端"""
        try:
            await websocket.send(message)
        except Exception as e:
            print(f"Error sending message: {e}")
            self.clients.discard(websocket)

    async def log(self, content: str, experiment_id: str | None = None):
        """推送日志"""
        await self.broadcast(
            LogMessage(type="log", content=content, experiment_id=experiment_id)
        )

    async def metric(
        self,
        name: str,
        value: float,
        step: int | None = None,
        experiment_id: str | None = None,
        epoch: int | None = None,
    ):
        """推送指标"""
        await self.broadcast(
            LogMessage(
                type="metric",
                content={"name": name, "value": value, "step": step},
                experiment_id=experiment_id,
                epoch=epoch,
                iter=step,
            )
        )

    async def metrics(
        self,
        metrics: dict[str, float],
        step: int | None = None,
        experiment_id: str | None = None,
        epoch: int | None = None,
    ):
        """批量推送指标"""
        for name, value in metrics.items():
            await self.metric(name, value, step, experiment_id, epoch)

    async def progress(
        self,
        current: int,
        total: int,
        message: str = "",
        experiment_id: str | None = None,
    ):
        """推送进度"""
        progress_pct = (current / total * 100) if total > 0 else 0
        await self.broadcast(
            LogMessage(
                type="progress",
                content={
                    "current": current,
                    "total": total,
                    "percent": round(progress_pct, 1),
                    "message": message,
                },
                experiment_id=experiment_id,
            )
        )

    async def error(self, error: str, experiment_id: str | None = None):
        """推送错误"""
        await self.broadcast(
            LogMessage(type="error", content=error, experiment_id=experiment_id)
        )

    async def system(self, message: str, experiment_id: str | None = None):
        """推送系统消息"""
        await self.broadcast(
            LogMessage(type="system", content=message, experiment_id=experiment_id)
        )

    async def start_server(self):
        """启动 WebSocket 服务器"""
        async with websockets.serve(self.handle_client, self.host, self.port):
            print(f"WebSocket server started at ws://{self.host}:{self.port}")
            await asyncio.Future()  # 永久运行

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        await self.connect(websocket)
        try:
            async for message in websocket:
                # 处理客户端消息
                try:
                    data = json.loads(message)
                    # 可以处理客户端的订阅/取消订阅等请求
                except json.JSONDecodeError:
                    pass
        finally:
            await self.disconnect(websocket)


class TrainingLogger:
    """
    训练日志包装器

    将训练过程中的日志同时输出到控制台和 WebSocket
    """

    def __init__(
        self,
        realtime_logger: RealTimeLogger | None = None,
        experiment_id: str | None = None,
    ):
        self.realtime_logger = realtime_logger
        self.experiment_id = experiment_id

    async def log(self, message: str):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

        if self.realtime_logger:
            await self.realtime_logger.log(message, self.experiment_id)

    async def log_metrics(
        self, metrics: dict[str, float], epoch: int = 0, step: int = 0
    ):
        """输出指标"""
        metrics_str = ", ".join([f"{k}={v:.4f}" for k, v in metrics.items()])
        print(f"Epoch {epoch} | Step {step} | {metrics_str}")

        if self.realtime_logger:
            await self.realtime_logger.metrics(metrics, step, self.experiment_id, epoch)

    async def log_progress(self, current: int, total: int, message: str = ""):
        """输出进度"""
        progress = (current / total * 100) if total > 0 else 0
        print(f"Progress: {progress:.1f}% {message}")

        if self.realtime_logger:
            await self.realtime_logger.progress(
                current, total, message, self.experiment_id
            )

    async def log_error(self, error: str):
        """输出错误"""
        print(f"ERROR: {error}")

        if self.realtime_logger:
            await self.realtime_logger.error(error, self.experiment_id)

    async def log_system(self, message: str):
        """输出系统消息"""
        print(f"SYSTEM: {message}")

        if self.realtime_logger:
            await self.realtime_logger.system(message, self.experiment_id)


# 全局实例
_global_logger: RealTimeLogger | None = None


def get_logger() -> RealTimeLogger:
    """获取全局日志实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = RealTimeLogger()
    return _global_logger


def set_logger(logger: RealTimeLogger):
    """设置全局日志实例"""
    global _global_logger
    _global_logger = logger
