"""
src/mlkit/drift — 模型漂移检测与告警 Python 包
Library-First: 可独立测试 + 暴露 Python API + CLI 接口
"""
from src.mlkit.drift.psi import compute_psi, compute_psi_batch, compute_overall_psi, get_psi_level
from src.mlkit.drift.ks import compute_ks, compute_ks_batch, KSResult
from src.mlkit.drift.detector import check_drift, compute_feature_stats, DriftCheckResult, FeatureDriftResult
from src.mlkit.drift.alerter import send_feishu_alert

__version__ = "1.0.0"

__all__ = [
    # PSI
    "compute_psi",
    "compute_psi_batch",
    "compute_overall_psi",
    "get_psi_level",
    # KS
    "compute_ks",
    "compute_ks_batch",
    "KSResult",
    # Detector
    "check_drift",
    "compute_feature_stats",
    "DriftCheckResult",
    "FeatureDriftResult",
    # Alerter
    "send_feishu_alert",
]
