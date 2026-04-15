"""
飞书 WebHook 告警模块
任务执行失败时发送飞书卡片消息。
支持告警冷却机制（同一 Job 5 分钟内不重复告警）。
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone as dt_tz
from typing import Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .models import Job, Execution

logger = logging.getLogger("platform.scheduler")

# 环境变量配置
DEFAULT_WEBHOOK_URL = os.getenv("MLKIT_SCHEDULER_WEBHOOK_DEFAULT", "")
ALERT_COOLDOWN_SECONDS = int(os.getenv("MLKIT_SCHEDULER_ALERT_COOLDOWN", "300"))  # 5 分钟


class AlertCooldownTracker:
    """
    告警冷却追踪器（内存中，按 Job ID 记录最近一次告警时间）。
    线程安全，支持清理过期记录。
    """

    def __init__(self, cooldown_seconds: int = ALERT_COOLDOWN_SECONDS):
        self._cooldown = cooldown_seconds
        self._lock = threading.RLock()
        self._last_alert: dict[str, float] = {}  # job_id -> timestamp

    def can_alert(self, job_id: str) -> bool:
        """判断某个 Job 是否在冷却期内（True=可以发送，False=在冷却期）"""
        with self._lock:
            now = time.time()
            last = self._last_alert.get(job_id, 0)
            if now - last < self._cooldown:
                return False
            self._last_alert[job_id] = now
            return True

    def cleanup(self):
        """清理过期的记录（节省内存）"""
        with self._lock:
            now = time.time()
            expired = [jid for jid, ts in self._last_alert.items() if now - ts > self._cooldown * 2]
            for jid in expired:
                self._last_alert.pop(jid, None)


# 全局冷却追踪器实例
_cooldown_tracker = AlertCooldownTracker()


def build_failure_card(job_name: str, job_id: str, executed_at: str, error_message: str, job_type: str, target_id: Optional[int] = None) -> dict:
    """
    构建飞书卡片消息 payload。

    Args:
        job_name: 任务名称
        job_id: 任务 ID
        executed_at: 执行时间（格式化字符串）
        error_message: 错误信息
        job_type: 任务类型
        target_id: 关联任务 ID

    Returns:
        飞书卡片 JSON payload dict
    """
    elements = [
        {"tag": "hr"},
        {
            "tag": "element",
            "element": {
                "tag": "column_set",
                "flex_mode": "none",
                "horizontal_spacing": "l",
                "children": [
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "vertical_align": "top",
                        "children": [
                            {"tag": "markdown", "content": f"**任务名称**\n{job_name}"},
                        ],
                    },
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "vertical_align": "top",
                        "children": [
                            {"tag": "markdown", "content": f"**任务类型**\n{job_type}"},
                        ],
                    },
                ],
            },
        },
        {
            "tag": "element",
            "element": {
                "tag": "column_set",
                "flex_mode": "none",
                "horizontal_spacing": "l",
                "children": [
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "vertical_align": "top",
                        "children": [
                            {"tag": "markdown", "content": f"**执行时间**\n{executed_at}"},
                        ],
                    },
                    {
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "vertical_align": "top",
                        "children": [
                            {"tag": "markdown", "content": f"**关联ID**\n{target_id or '—'}"},
                        ],
                    },
                ],
            },
        },
        {"tag": "hr"},
        {
            "tag": "markdown",
            "content": f"**错误信息**\n```\n{error_message[:500]}\n```",
        },
    ]

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ 调度任务执行失败"},
                "template": "red",
            },
            "elements": elements,
        },
    }


async def send_feishu_alert(
    job: "Job",
    execution: "Execution",
    error_message: str,
) -> bool:
    """
    发送飞书 WebHook 告警（失败时）。

    告警规则：
    - 如果 Job 没有配置 webhook_url，使用默认 WebHook URL（MLKIT_SCHEDULER_WEBHOOK_DEFAULT）
    - 同一 Job 5 分钟内最多发送 1 次告警（防止告警风暴）
    - 仅当状态为 FAILED 时发送告警

    Args:
        job: Job 实例
        execution: Execution 实例
        error_message: 错误信息

    Returns:
        True 表示发送成功（或被冷却拦截），False 表示发送失败
    """
    # 检查冷却机制
    if not _cooldown_tracker.can_alert(job.id):
        logger.debug(f"[AlertCooldown] Job {job.id} 在冷却期内，跳过告警")
        return True

    # 确定 WebHook URL
    webhook_url = job.webhook_url or DEFAULT_WEBHOOK_URL
    if not webhook_url:
        logger.warning(f"[AlertCooldown] Job {job.id} 未配置 WebHook URL，跳过告警")
        return False

    # 构建告警卡片
    executed_at = execution.started_at.strftime("%Y-%m-%d %H:%M:%S") if execution.started_at else "未知"
    payload = build_failure_card(
        job_name=job.name,
        job_id=job.id,
        executed_at=executed_at,
        error_message=error_message,
        job_type=job.job_type.value if hasattr(job.job_type, 'value') else str(job.job_type),
        target_id=job.target_id,
    )

    # 发送 HTTP POST
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code == 200:
                logger.info(f"[Alert] 飞书告警发送成功，Job={job.id}, execution={execution.id}")
                return True
            else:
                logger.warning(f"[Alert] 飞书告警发送失败，status={response.status_code}, body={response.text[:200]}")
                return False
    except httpx.RequestError as e:
        logger.error(f"[Alert] 飞书告警发送失败（网络错误），Job={job.id}: {e}")
        return False
    except Exception as e:
        logger.error(f"[Alert] 飞书告警发送失败（未知错误），Job={job.id}: {e}")
        return False


def cleanup_alert_cooldown():
    """定期清理过期的告警冷却记录（调度器后台线程调用）"""
    _cooldown_tracker.cleanup()
