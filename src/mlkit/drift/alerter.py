"""
飞书告警器
Library-First: WebHook 发送逻辑，重试机制
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 重试配置
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5  # 秒，指数退避


def _build_feishu_card(
    model_id: int,
    model_name: str,
    check_time: str,
    drift_level: str,
    psi_overall: float,
    threshold: float,
    drifted_features: list[str],
    report_url: Optional[str] = None,
) -> dict:
    """构建飞书卡片消息 JSON"""
    level_emoji = {
        "none": "✅",
        "mild": "⚠️",
        "moderate": "🚨",
        "severe": "🔴",
        "undefined": "❓",
    }
    emoji = level_emoji.get(drift_level, "🚨")
    level_text = {
        "none": "无漂移",
        "mild": "轻度漂移",
        "moderate": "中度漂移",
        "severe": "严重漂移",
        "undefined": "无法判定",
    }

    content_lines = [
        f"**模型 ID**: {model_id}",
        f"**检测时间**: {check_time}",
        f"**漂移等级**: {emoji} {level_text.get(drift_level, drift_level)}",
        "",
        f"**当前 PSI**: {psi_overall:.4f}（阈值: {threshold:.2f}）",
    ]

    if drifted_features:
        content_lines.append(f"**超过阈值的特征**: {', '.join(drifted_features)}")
    else:
        content_lines.append("**超过阈值的特征**: 无")

    action_block = []
    if report_url:
        action_block = [
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看完整报告"},
                        "type": "primary",
                        "url": report_url,
                    }
                ],
            }
        ]

    recommendation = _get_recommendation(drift_level, drifted_features)

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{emoji} 模型漂移告警"},
                "template": _get_template(drift_level),
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(content_lines)}},
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"💡 **建议动作**: {recommendation}",
                    },
                },
                *action_block,
            ],
        },
    }


def _get_template(drift_level: str) -> str:
    """根据漂移等级返回卡片模板颜色"""
    return {
        "none": "green",
        "mild": "yellow",
        "moderate": "orange",
        "severe": "red",
        "undefined": "grey",
    }.get(drift_level, "grey")


def _get_recommendation(drift_level: str, drifted_features: list[str]) -> str:
    """根据漂移等级给出建议"""
    if drift_level in ("none", "undefined"):
        return "数据分布稳定，继续监控"
    if drift_level == "mild":
        return f"注意观察，{', '.join(drifted_features[:2])} 略有偏移，建议 3 天后复检"
    if drift_level == "moderate":
        return f"{', '.join(drifted_features[:2])} 漂移明显，建议检查数据管道，考虑模型重训练"
    return f"{', '.join(drifted_features[:2])} 严重漂移，建议立即重新训练模型"


def send_feishu_alert(
    webhook_url: str,
    model_id: int,
    model_name: Optional[str] = None,
    check_time: Optional[str] = None,
    drift_level: str = "moderate",
    psi_overall: float = 0.0,
    threshold: float = 0.2,
    drifted_features: Optional[list[str]] = None,
    report_url: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    发送飞书告警

    重试策略：最多 3 次，指数退避（5s, 10s, 20s）
    最终失败不抛出异常，写入日志

    参数
    ----
    webhook_url    : str 飞书 WebHook URL
    model_id       : int 模型 ID
    model_name     : str 模型名称
    check_time     : str 检测时间
    drift_level    : str 漂移等级
    psi_overall    : float 整体 PSI
    threshold      : float 告警阈值
    drifted_features: list[str] 漂移特征列表
    report_url     : str 报告链接

    返回
    ----
    (success: bool, error_message: Optional[str])
    """
    if drifted_features is None:
        drifted_features = []

    card = _build_feishu_card(
        model_id=model_id,
        model_name=model_name or f"Model-{model_id}",
        check_time=check_time or "",
        drift_level=drift_level,
        psi_overall=psi_overall,
        threshold=threshold,
        drifted_features=drifted_features,
        report_url=report_url,
    )

    last_error: Optional[str] = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                webhook_url,
                json=card,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(
                    f"[DriftAlert] WebHook sent successfully (attempt {attempt + 1}), "
                    f"model_id={model_id}, psi={psi_overall:.4f}"
                )
                return True, None
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(
                    f"[DriftAlert] WebHook failed (attempt {attempt + 1}/{MAX_RETRIES}): {last_error}"
                )
        except requests.RequestException as e:
            last_error = str(e)[:200]
            logger.warning(
                f"[DriftAlert] WebHook exception (attempt {attempt + 1}/{MAX_RETRIES}): {last_error}"
            )

        # 指数退避
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            time.sleep(delay)

    # 最终失败
    # 脱敏：只记录是否失败，不记录 URL
    logger.error(
        f"[DriftAlert] WebHook failed after {MAX_RETRIES} attempts for model_id={model_id}"
    )
    return False, last_error
