"""
Cron 表达式解析器
使用 croniter 计算下次执行时间、验证表达式合法性。
"""
from datetime import datetime, timezone as dt_tz
from typing import Optional
from croniter import croniter, CroniterError


class CronParseError(ValueError):
    """Cron 解析错误，包含具体错误信息"""
    pass


def validate_cron(cron_expr: str) -> bool:
    """
    验证 Cron 表达式是否合法（5段式：分 时 日 月 周）。
    返回 True 表示合法，抛出 CronParseError 表示非法。
    """
    try:
        croniter(cron_expr)
        return True
    except (CroniterError, ValueError) as e:
        raise CronParseError(f"无效的 Cron 表达式: {cron_expr}，错误: {str(e)}")


def get_next_run_time(cron_expr: str, base_time: Optional[datetime] = None) -> datetime:
    """
    计算 Cron 表达式的下次执行时间。

    Args:
        cron_expr: 5段式 Cron 表达式（如 "0 8 * * *"）
        base_time: 基准时间（默认当前时间）

    Returns:
        下次执行时间的 datetime（UTC，带时区信息）

    Raises:
        CronParseError: 表达式非法时
    """
    if base_time is None:
        base_time = datetime.now(dt_tz.utc)
    else:
        # 确保 base_time 带时区信息
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=dt_tz.utc)

    try:
        cron = croniter(cron_expr, base_time)
        return cron.get_next(datetime)
    except (CroniterError, ValueError) as e:
        raise CronParseError(f"Cron 表达式解析失败: {cron_expr}，错误: {str(e)}")


def get_prev_run_time(cron_expr: str, base_time: Optional[datetime] = None) -> datetime:
    """
    计算 Cron 表达式的上次执行时间。

    Args:
        cron_expr: 5段式 Cron 表达式
        base_time: 基准时间（默认当前时间）

    Returns:
        上次执行时间的 datetime（UTC，带时区信息）
    """
    if base_time is None:
        base_time = datetime.now(dt_tz.utc)
    else:
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=dt_tz.utc)

    try:
        cron = croniter(cron_expr, base_time)
        return cron.get_prev(datetime)
    except (CroniterError, ValueError) as e:
        raise CronParseError(f"Cron 表达式解析失败: {cron_expr}，错误: {str(e)}")


def describe_cron(cron_expr: str) -> str:
    """
    将 Cron 表达式翻译为人类可读描述。

    常见格式：
        0 8 * * *     → 每天早上 8:00
        0 * * * *     → 每小时整点
        0 0 * * 1     → 每周一 00:00
        */5 * * * *   → 每 5 分钟
    """
    try:
        croniter(cron_expr)  # 先验证合法性
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise CronParseError("Cron 表达式必须是5段式（分 时 日 月 周）")

        minute, hour, day, month, weekday = parts

        # 常见模式识别
        if minute == "*" and hour == "*":
            return "每分钟"
        if minute == "0" and hour == "*":
            return "每小时整点"
        if minute == "0" and hour == "0" and day == "*" and month == "*":
            if weekday == "*":
                return "每天 00:00"
            elif weekday == "1":
                return "每周一 00:00"
            else:
                return f"每周第{weekday}天 00:00"
        if "*/" in minute:
            interval = minute.replace("*/", "")
            return f"每隔 {interval} 分钟"
        if "*/" in hour:
            interval = hour.replace("*/", "")
            return f"每隔 {interval} 小时"

        return f"每天 {hour.zfill(2)}:{minute.zfill(2)}"

    except Exception:
        return cron_expr


# 常用 Cron 预设模板（前端快捷按钮用）
CRON_PRESETS = {
    "每天早上": "0 8 * * *",       # 每天 08:00
    "每小时": "0 * * * *",          # 每小时整点
    "每周一": "0 0 * * 1",         # 每周一 00:00
    "每天凌晨": "0 2 * * *",       # 每天 02:00
    "每30分钟": "*/30 * * * *",    # 每 30 分钟
    "每15分钟": "*/15 * * * *",    # 每 15 分钟
}
