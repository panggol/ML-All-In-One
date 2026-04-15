"""
Core business logic for Model Registry.
"""
import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple

# 有效标签枚举
VALID_TAGS = frozenset({"staging", "production", "archived"})


def compute_next_version(db_session, model_id: int) -> int:
    """
    计算给定模型的下一个版本号。

    Args:
        db_session: SQLAlchemy 数据库会话
        model_id: TrainedModel ID

    Returns:
        下一个版本号（整数，从 1 开始）

    Raises:
        ModelRegistryError: 查询失败时
    """
    from sqlalchemy import func, text

    result = db_session.execute(
        text("SELECT COALESCE(MAX(version), 0) FROM model_versions WHERE model_id = :model_id"),
        {"model_id": model_id}
    )
    row = result.fetchone()
    max_version = row[0] if row else 0
    return max_version + 1


def compute_dataset_hash(
    filepath: Optional[str] = None,
    filename: Optional[str] = None,
    size: Optional[int] = None,
    rows: Optional[int] = None,
    sample_bytes: int = 1024 * 10,
) -> str:
    """
    计算数据集指纹：SHA256(文件名 + 文件大小 + 行数 + 前 N 字节摘要)

    Args:
        filepath: 完整文件路径（优先使用，可直接读取）
        filename: 数据文件名（无 filepath 时使用）
        size: 文件大小（bytes）
        rows: 数据行数
        sample_bytes: 用于摘要的字节数（前 N 字节，默认 10KB）

    Returns:
        64 字符十六进制 SHA256 哈希
    """
    parts = []

    # 文件名
    name = os.path.basename(filepath) if filepath else (filename or "")
    parts.append(name.encode("utf-8"))

    # 文件大小
    if filepath and os.path.exists(filepath):
        stat = os.stat(filepath)
        size = stat.st_size
    parts.append(str(size or 0).encode("utf-8"))

    # 行数
    parts.append(str(rows or 0).encode("utf-8"))

    # 前 N 字节摘要
    if filepath and os.path.exists(filepath) and size and size > 0:
        try:
            with open(filepath, "rb") as f:
                sample = f.read(sample_bytes)
            sample_hash = hashlib.sha256(sample).hexdigest()
            parts.append(sample_hash.encode("utf-8"))
        except (IOError, OSError):
            parts.append(b"unavailable")
    else:
        parts.append(b"unavailable")

    # 合并计算
    combined = b"|".join(parts)
    return hashlib.sha256(combined).hexdigest()


def compare_versions(
    metrics_a: Dict[str, Any],
    metrics_b: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """
    对比两个版本的评估指标。

    Args:
        metrics_a: 版本 A 的指标字典
        metrics_b: 版本 B 的指标字典

    Returns:
        (comparison, unique_to_a, unique_to_b)
        - comparison: 交集指标对比列表
        - unique_to_a: 仅 A 有的指标名列表
        - unique_to_b: 仅 B 有的指标名列表
    """
    # 找出交集和差集
    keys_a = set(metrics_a.keys())
    keys_b = set(metrics_b.keys())
    common_keys = keys_a & keys_b
    unique_to_a = list(keys_a - keys_b)
    unique_to_b = list(keys_b - keys_a)

    comparison = []
    for key in sorted(common_keys):
        val_a = metrics_a[key]
        val_b = metrics_b[key]

        # 仅对数值类型计算 delta
        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            delta = round(val_b - val_a, 6)
            winner = "b" if delta > 0 else ("a" if delta < 0 else "tie")
            comparison.append({
                "metric": key,
                "value_a": val_a,
                "value_b": val_b,
                "delta": delta,
                "winner": winner,
            })
        else:
            # 非数值类型只记录原始值
            comparison.append({
                "metric": key,
                "value_a": val_a,
                "value_b": val_b,
                "delta": None,
                "winner": None,
            })

    return comparison, unique_to_a, unique_to_b
