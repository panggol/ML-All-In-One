"""
时序频率自动检测器
Library-First: 纯算法实现，不依赖 API 层
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np


# 支持的频率枚举
FrequencyType = str  # "daily" | "weekly" | "monthly" | "quarterly" | "yearly" | "unknown"


def detect_frequency(timestamps: pd.Series) -> tuple[FrequencyType, float]:
    """
    自动检测时序数据的频率（daily / weekly / monthly / quarterly / yearly）

    原理：分析相邻时间戳的间隔分布，取众数作为频率。

    参数
    ----
    timestamps : pd.Series
        已解析为 datetime 的时间戳序列（不含 NaT）

    返回
    ----
    tuple[FrequencyType, float]
        - 检测到的频率类型
        - 置信度（众数占比，越高越可信）
    """
    if len(timestamps) < 2:
        return "unknown", 0.0

    # 计算相邻间隔（天数）
    diffs = timestamps.sort_values().diff().dropna().dt.total_seconds() / 86400.0
    diffs = diffs[diffs > 0]  # 过滤零间隔

    if len(diffs) == 0:
        return "unknown", 0.0

    # 按间隔分组统计
    candidates = {
        "daily":     (1.0,      0.5),    # (目标天数, 容差)
        "weekly":    (7.0,      1.5),
        "monthly":   (30.4375,  5.0),
        "quarterly": (91.3125,  10.0),
        "yearly":    (365.25,   30.0),
    }

    best_freq: FrequencyType = "unknown"
    best_count = 0
    total = len(diffs)

    for freq_name, (target, tolerance) in candidates.items():
        matched = diffs[
            (diffs >= target - tolerance) & (diffs <= target + tolerance)
        ]
        if len(matched) > best_count:
            best_count = len(matched)
            best_freq = freq_name

    confidence = best_count / total if total > 0 else 0.0

    # 置信度过低 → unknown
    if confidence < 0.7:
        return "unknown", round(confidence, 4)

    return best_freq, round(confidence, 4)


def infer_freq_str(freq: FrequencyType) -> str:
    """将频率枚举转为 pandas 频率字符串"""
    mapping = {
        "daily":     "D",
        "weekly":    "W",
        "monthly":   "MS",   # Month Start
        "quarterly": "QS",   # Quarter Start
        "yearly":    "YS",   # Year Start
    }
    return mapping.get(freq, "D")


def infer_period_for_seasonality(freq: FrequencyType) -> int:
    """为给定频率推断季节性周期（用于 ARIMA / STL 分解）"""
    mapping = {
        "daily":     7,       # 周季节性
        "weekly":    4,       # 月季节性（约 4 周）
        "monthly":   12,      # 年季节性
        "quarterly": 4,       # 年季节性
        "yearly":    1,       # 无季节性
    }
    return mapping.get(freq, 7)
