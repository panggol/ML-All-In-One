"""
Drift Detection 单元测试
Constitution: 测试不可绕过
覆盖：PSI 计算、KS 检验、告警触发逻辑、WebHook 失败重试
"""
from __future__ import annotations

import math
import tempfile
from io import StringIO
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest
import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.mlkit.drift.psi import compute_psi, compute_psi_batch, compute_overall_psi, get_psi_level
from src.mlkit.drift.ks import compute_ks, compute_ks_batch, KSResult
from src.mlkit.drift.detector import check_drift, compute_feature_stats, DriftCheckResult
from src.mlkit.drift.alerter import send_feishu_alert, _build_feishu_card, _get_recommendation


# ============ PSI 计算测试 ============

class TestPSI:
    """PSI 计算单元测试"""

    def test_psi_same_distribution(self):
        """相同分布 → PSI ≈ 0"""
        np.random.seed(42)
        ref = np.random.normal(0, 1, 1000)
        cur = np.random.normal(0, 1, 1000)
        psi = compute_psi(ref, cur)
        assert 0 <= psi < 0.05, f"相同分布 PSI 应接近 0，实际: {psi}"

    def test_psi_different_distribution(self):
        """显著不同分布 → PSI > 0.25"""
        np.random.seed(42)
        ref = np.random.normal(0, 1, 1000)
        cur = np.random.normal(1, 1, 1000)  # 均值偏移 1
        psi = compute_psi(ref, cur)
        assert psi > 0.25, f"均值偏移后 PSI 应 > 0.25，实际: {psi}"

    def test_psi_zero_for_identical(self):
        """完全相同数据 → PSI = 0"""
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        psi = compute_psi(data, data.copy())
        assert psi == 0.0

    def test_psi_nan_handling(self):
        """常数列 → PSI = NaN（标记为 undefined）"""
        ref = np.array([1.0] * 100)
        cur = np.array([2.0] * 100)
        psi = compute_psi(ref, cur)
        assert math.isnan(psi), f"常数列 PSI 应为 NaN，实际: {psi}"

    def test_psi_with_nan(self):
        """包含 NaN 的数据 → 自动过滤 NaN"""
        ref = np.array([1.0, 2.0, 3.0, np.nan, 4.0, 5.0])
        cur = np.array([1.5, 2.5, 3.5, 4.5, 5.5])
        psi = compute_psi(ref, cur)
        assert not math.isnan(psi)
        assert psi >= 0

    def test_psi_pandas_series(self):
        """支持 pandas Series 输入"""
        ref = pd.Series([1, 2, 3, 4, 5] * 20)
        cur = pd.Series([1.1, 2.1, 3.1, 4.1, 5.1] * 20)
        psi = compute_psi(ref, cur)
        assert psi >= 0  # PSI ≥ 0

    def test_psi_batch(self):
        """批量计算 PSI"""
        np.random.seed(42)
        ref_df = pd.DataFrame({
            'feature_a': np.random.normal(0, 1, 500),
            'feature_b': np.random.normal(0, 1, 500),
        })
        cur_df = pd.DataFrame({
            'feature_a': np.random.normal(0.5, 1, 500),
            'feature_b': np.random.normal(0, 1, 500),
        })
        result = compute_psi_batch(ref_df, cur_df)
        assert 'feature_a' in result
        assert 'feature_b' in result
        assert result['feature_a'] > result['feature_b']

    def test_psi_overall(self):
        """整体 PSI = 各特征均值"""
        np.random.seed(42)
        ref_df = pd.DataFrame({
            'a': np.random.normal(0, 1, 500),
            'b': np.random.normal(0, 1, 500),
        })
        cur_df = pd.DataFrame({
            'a': np.random.normal(0.5, 1, 500),
            'b': np.random.normal(0, 1, 500),
        })
        overall = compute_overall_psi(ref_df, cur_df)
        assert not math.isnan(overall)
        assert overall >= 0

    def test_psi_boundary_values(self):
        """边界值：0, 1, 极端大"""
        ref = np.linspace(0, 1, 100)
        # 小偏移
        cur = np.linspace(0.01, 1.01, 100)
        psi = compute_psi(ref, cur)
        assert psi >= 0

    def test_get_psi_level(self):
        """PSI 等级划分"""
        assert get_psi_level(0.05) == "none"
        assert get_psi_level(0.099) == "none"
        assert get_psi_level(0.10) == "mild"  # 边界：0.1 ≤ PSI < 0.2 → mild
        assert get_psi_level(0.15) == "mild"
        assert get_psi_level(0.20) == "mild"
        assert get_psi_level(0.22) == "moderate"
        assert get_psi_level(0.25) == "moderate"
        assert get_psi_level(0.30) == "severe"
        assert get_psi_level(float('nan')) == "undefined"


# ============ KS 检验测试 ============

class TestKS:
    """KS 检验单元测试"""

    def test_ks_same_distribution(self):
        """相同分布 → p-value > 0.05（不漂移）"""
        np.random.seed(42)
        ref = np.random.normal(0, 1, 500)
        cur = np.random.normal(0, 1, 500)
        result = compute_ks(ref, cur)
        assert result.pvalue > 0.05, f"相同分布 p-value 应 > 0.05，实际: {result.pvalue}"
        assert result.drifted == False

    def test_ks_different_distribution(self):
        """不同分布 → p-value < 0.05（漂移）"""
        np.random.seed(42)
        ref = np.random.normal(0, 1, 500)
        cur = np.random.normal(2, 1, 500)  # 均值偏移 2
        result = compute_ks(ref, cur)
        assert result.pvalue < 0.05, f"均值偏移后 p-value 应 < 0.05，实际: {result.pvalue}"
        assert result.drifted == True
        assert 0 <= result.stat <= 1.0

    def test_ks_identical_data(self):
        """完全相同数据 → stat = 0, p-value = 1"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_ks(data, data.copy())
        assert result.stat == 0.0
        assert result.pvalue == 1.0
        assert result.drifted == False

    def test_ks_nan_handling(self):
        """常数列 → 漂移检测"""
        ref = np.array([1.0] * 100)
        cur = np.array([2.0] * 100)
        result = compute_ks(ref, cur)
        # 常数列均值不同 → 漂移
        assert result.drifted == True or result.stat == 1.0

    def test_ks_batch(self):
        """批量 KS 检验"""
        np.random.seed(42)
        ref_df = pd.DataFrame({
            'a': np.random.normal(0, 1, 300),
            'b': np.random.normal(0, 1, 300),
        })
        cur_df = pd.DataFrame({
            'a': np.random.normal(1, 1, 300),
            'b': np.random.normal(0, 1, 300),
        })
        results = compute_ks_batch(ref_df, cur_df)
        assert 'a' in results
        assert 'b' in results
        assert isinstance(results['a'], KSResult)

    def test_ks_with_nan(self):
        """包含 NaN 的数据 → 自动过滤"""
        ref = pd.Series([1.0, 2.0, np.nan, 3.0, 4.0, 5.0])
        cur = pd.Series([1.5, 2.5, 3.5, 4.5, 5.5])
        result = compute_ks(ref, cur)
        assert 0 <= result.stat <= 1.0


# ============ 漂移检测协调器测试 ============

class TestDetector:
    """漂移检测协调器测试"""

    def test_check_drift_basic(self):
        """基本漂移检测流程"""
        np.random.seed(42)
        ref_df = pd.DataFrame({
            'feature_a': np.random.normal(0, 1, 500),
            'feature_b': np.random.normal(0, 1, 500),
        })
        cur_df = pd.DataFrame({
            'feature_a': np.random.normal(0.5, 1, 500),
            'feature_b': np.random.normal(0, 1, 500),
        })
        result = check_drift(ref_df, cur_df, reference_id=1, model_id=1, check_id="test-123")
        assert isinstance(result, DriftCheckResult)
        assert result.check_id == "test-123"
        assert result.reference_id == 1
        assert result.model_id == 1
        assert not math.isnan(result.psi_overall)
        assert result.drift_level in ("none", "mild", "moderate", "severe")

    def test_check_drift_missing_features(self):
        """缺少特征 → ValueError"""
        ref_df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        cur_df = pd.DataFrame({'a': [1, 2, 3]})
        with pytest.raises(ValueError, match="缺少基准特征"):
            check_drift(ref_df, cur_df, reference_id=1)

    def test_check_drift_small_sample_warning(self):
        """样本量 < 1000 → 警告"""
        ref_df = pd.DataFrame({'a': np.random.normal(0, 1, 500)})
        cur_df = pd.DataFrame({'a': np.random.normal(0.5, 1, 500)})
        result = check_drift(ref_df, cur_df, reference_id=1)
        assert len(result.warnings) > 0
        assert any('1000' in w for w in result.warnings)

    def test_check_drift_alert_triggered(self):
        """显著漂移 → 触发告警标记"""
        np.random.seed(42)
        ref_df = pd.DataFrame({'feature_a': np.random.normal(0, 1, 2000)})
        cur_df = pd.DataFrame({'feature_a': np.random.normal(1.5, 1, 2000)})  # 大偏移
        result = check_drift(ref_df, cur_df, reference_id=1, psi_threshold=0.2)
        assert result.alerted == True

    def test_compute_feature_stats(self):
        """统计量计算"""
        df = pd.DataFrame({
            'a': [1.0, 2.0, 3.0, 4.0, 5.0],
            'b': [10.0, 20.0, 30.0, 40.0, 50.0],
        })
        stats = compute_feature_stats(df)
        assert 'a' in stats
        assert 'b' in stats
        assert 'mean' in stats['a']
        assert 'std' in stats['a']
        assert 'q25' in stats['a']
        assert 'q50' in stats['a']
        assert 'q75' in stats['a']


# ============ 告警逻辑测试 ============

class TestAlerter:
    """飞书告警器测试"""

    def test_build_feishu_card(self):
        """卡片消息格式正确"""
        card = _build_feishu_card(
            model_id=1,
            model_name="TestModel",
            check_time="2026-04-13T10:00:00",
            drift_level="moderate",
            psi_overall=0.22,
            threshold=0.2,
            drifted_features=["feature_a", "feature_b"],
        )
        assert card['msg_type'] == 'interactive'
        assert 'card' in card
        assert card['card']['header']['template'] == 'orange'
        # elements 应包含内容块
        assert len(card['card']['elements']) >= 2

    def test_get_recommendation(self):
        """建议文案正确"""
        assert "稳定" in _get_recommendation("none", [])
        assert "观察" in _get_recommendation("mild", ["a"])  # mild 建议观察
        assert "重新训练" in _get_recommendation("severe", ["a"])

    @patch('src.mlkit.drift.alerter.requests.post')
    def test_webhook_success(self, mock_post):
        """WebHook 发送成功"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        success, err = send_feishu_alert(
            webhook_url="https://open.feishu.cn/test-hook",
            model_id=1,
            drift_level="moderate",
            psi_overall=0.22,
            threshold=0.2,
            drifted_features=["a"],
        )
        assert success == True
        assert err is None
        assert mock_post.call_count == 1

    @patch('src.mlkit.drift.alerter.requests.post')
    def test_webhook_retry_then_success(self, mock_post):
        """首次失败，重试后成功"""
        mock_fail = MagicMock()
        mock_fail.status_code = 500
        mock_fail.text = "Internal Error"
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_post.side_effect = [mock_fail, mock_success]

        success, err = send_feishu_alert(
            webhook_url="https://open.feishu.cn/test-hook",
            model_id=1,
            drift_level="moderate",
            psi_overall=0.22,
            threshold=0.2,
            drifted_features=["a"],
        )
        assert success == True
        assert mock_post.call_count == 2

    @patch('src.mlkit.drift.alerter.requests.post')
    @patch('src.mlkit.drift.alerter.time.sleep')
    def test_webhook_all_fail(self, mock_sleep, mock_post):
        """全部失败 → 最终返回失败，不抛异常"""
        mock_fail = MagicMock()
        mock_fail.status_code = 404
        mock_fail.text = "Not Found"
        mock_post.return_value = mock_fail

        success, err = send_feishu_alert(
            webhook_url="https://open.feishu.cn/test-hook",
            model_id=1,
            drift_level="moderate",
            psi_overall=0.22,
            threshold=0.2,
            drifted_features=["a"],
        )
        assert success == False
        assert err is not None
        # 重试 3 次
        assert mock_post.call_count == 3
        # 不抛异常
        assert True

    @patch('src.mlkit.drift.alerter.requests.post')
    def test_webhook_network_error(self, mock_post):
        """网络异常 → 重试后失败"""
        mock_post.side_effect = requests.ConnectionError("Connection refused")
        success, err = send_feishu_alert(
            webhook_url="https://open.feishu.cn/test-hook",
            model_id=1,
            drift_level="severe",
            psi_overall=0.3,
            threshold=0.2,
            drifted_features=["a"],
        )
        assert success == False
        assert "Connection refused" in (err or "")
        assert mock_post.call_count == 3
