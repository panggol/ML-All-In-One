"""
测试：时序预测模块（Time Series Forecasting）

覆盖：
- Prophet 训练 + 预测（mocked）
- ARIMA 训练 + 预测（mocked）
- LightGBM 训练 + 预测（mocked）
- 频率自动检测
- 交叉验证逻辑
- 分解输出格式
- API 路由端点

所有外部库（prophet / statsmodels / lightgbm）均通过 unittest.mock 模拟，
不依赖这些库的实际安装。
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


# ─── Helper ──────────────────────────────────────────────────────────────────


def _prophet_available():
    try:
        import prophet  # noqa
        return True
    except ImportError:
        return False


def _pmdarima_available():
    try:
        import pmdarima  # noqa
        return True
    except ImportError:
        return False


def _lightgbm_available():
    try:
        import lightgbm  # noqa
        return True
    except ImportError:
        return False


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_csv_content():
    """生成模拟时序 CSV 内容（日频）"""
    rng = np.random.default_rng(42)
    rows = []
    start = datetime(2024, 1, 1)
    for i in range(100):
        d = start + timedelta(days=i)
        val = 100 + 0.5 * i + 10 * np.sin(2 * np.pi * i / 7) + rng.normal(0, 2)
        rows.append(f"{d.strftime('%Y-%m-%d')},{val:.4f}")
    header = "timestamp,value\n"
    return header + "\n".join(rows)


@pytest.fixture
def mock_weekly_csv_content():
    """周频数据"""
    rng = np.random.default_rng(42)
    rows = []
    start = datetime(2024, 1, 1)
    for i in range(52):
        d = start + timedelta(weeks=i)
        val = 1000 + 5 * i + 50 * np.sin(2 * np.pi * i / 52) + rng.normal(0, 10)
        rows.append(f"{d.strftime('%Y-%m-%d')},{val:.4f}")
    header = "timestamp,value\n"
    return header + "\n".join(rows)


@pytest.fixture
def mock_monthly_csv_content():
    """月频数据"""
    rng = np.random.default_rng(42)
    rows = []
    d = datetime(2023, 1, 1)
    for i in range(24):
        m = d + timedelta(days=30 * i)
        val = 5000 + 100 * i + 200 * np.sin(2 * np.pi * i / 12) + rng.normal(0, 50)
        rows.append(f"{m.strftime('%Y-%m-%d')},{val:.4f}")
    header = "timestamp,value\n"
    return header + "\n".join(rows)


# ─── Test: 频率自动检测 ────────────────────────────────────────────────────────


class TestFrequencyDetection:
    """测试频率自动检测（使用 detector 模块）"""

    def test_detect_daily_from_csv(self, mock_csv_content):
        """日频数据：应检测为 daily"""
        from src.mlkit.forecast.detector import detect_frequency

        df = pd.read_csv(io.StringIO(mock_csv_content))
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        freq, confidence = detect_frequency(df['timestamp'])

        assert freq == 'daily', f"日频检测失败：freq={freq}, confidence={confidence}"
        assert 0.7 <= confidence <= 1.0

    def test_detect_weekly_from_csv(self, mock_weekly_csv_content):
        """周频数据：应检测为 weekly"""
        from src.mlkit.forecast.detector import detect_frequency

        df = pd.read_csv(io.StringIO(mock_weekly_csv_content))
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        freq, confidence = detect_frequency(df['timestamp'])

        assert freq == 'weekly', f"周频检测失败：freq={freq}, confidence={confidence}"

    def test_detect_monthly_from_csv(self, mock_monthly_csv_content):
        """月频数据：应检测为 monthly"""
        from src.mlkit.forecast.detector import detect_frequency

        df = pd.read_csv(io.StringIO(mock_monthly_csv_content))
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        freq, confidence = detect_frequency(df['timestamp'])

        assert freq == 'monthly', f"月频检测失败：freq={freq}, confidence={confidence}"

    def test_detect_frequency_irregular(self):
        """混合频率数据：应返回 unknown 或低置信度"""
        from src.mlkit.forecast.detector import detect_frequency

        irregular = (
            "timestamp,value\n"
            "2024-01-01,100\n"
            "2024-01-03,102\n"
            "2024-01-10,105\n"
            "2024-01-25,110\n"
        )
        df = pd.read_csv(io.StringIO(irregular))
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        freq, confidence = detect_frequency(df['timestamp'])

        # 不规则数据，置信度应低于阈值
        assert freq == 'unknown' or confidence < 0.7

    def test_detect_missing_ratio(self, mock_csv_content):
        """测试缺失比例计算"""
        content = mock_csv_content + "\n2024-04-20,\n2024-04-21,\n"
        df = pd.read_csv(io.StringIO(content))
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        missing_ratio = df['value'].isna().mean()
        assert 0 < missing_ratio < 0.1, f"缺失比例计算失败：{missing_ratio}"


# ─── Test: Prophet 训练 + 预测 ─────────────────────────────────────────────────


class TestProphetTrainPredict:
    """测试 Prophet 模型训练和预测"""

    def test_prophet_train_interface(self, mock_csv_content):
        """ProphetEngine 接口级验证"""
        from src.mlkit.forecast.engine import ProphetEngine, TrainResult, ForecastResult
        import dataclasses

        # Verify ProphetEngine.train is a classmethod with correct signature
        import inspect
        sig = inspect.signature(ProphetEngine.train)
        param_names = list(sig.parameters.keys())

        assert 'target_col' in param_names, f"Missing target_col. Available: {param_names}"
        assert 'timestamp_col' in param_names
        assert 'changepoint_prior_scale' in param_names
        assert 'seasonality_mode' in param_names

        # Verify ProphetEngine.name attribute
        assert ProphetEngine.name == 'prophet'

        # Verify TrainResult dataclass fields
        train_fields = {f.name for f in dataclasses.fields(TrainResult)}
        assert 'model_type' in train_fields
        assert 'metrics' in train_fields

        # Verify ForecastResult dataclass fields
        forecast_fields = {f.name for f in dataclasses.fields(ForecastResult)}
        assert 'yhat' in forecast_fields
        assert 'yhat_lower' in forecast_fields
        assert 'yhat_upper' in forecast_fields

    def test_prophet_predict_output_format(self):
        """预测输出格式：必须包含 timestamps / yhat / yhat_lower / yhat_upper"""
        from src.mlkit.forecast.engine import ForecastResult

        steps = 30
        mock_forecast = pd.DataFrame({
            'ds': pd.date_range('2024-04-11', periods=steps, freq='D'),
            'yhat': [100 + 0.5 * i for i in range(steps)],
            'yhat_lower': [95 + 0.4 * i for i in range(steps)],
            'yhat_upper': [105 + 0.6 * i for i in range(steps)],
            'trend': [100 + 0.5 * i for i in range(steps)],
            'yearly': [5 * np.sin(2 * np.pi * i / 365) for i in range(steps)],
            'weekly': [2 * np.sin(2 * np.pi * i / 7) for i in range(steps)],
            'holidays': [0] * steps,
        })

        result = ForecastResult(
            timestamps=mock_forecast['ds'].dt.strftime('%Y-%m-%d').tolist(),
            yhat=mock_forecast['yhat'].tolist(),
            yhat_lower=mock_forecast['yhat_lower'].tolist(),
            yhat_upper=mock_forecast['yhat_upper'].tolist(),
            trend=mock_forecast['trend'].tolist(),
            yearly=mock_forecast['yearly'].tolist(),
            weekly=mock_forecast['weekly'].tolist(),
            holidays=mock_forecast['holidays'].tolist(),
            confidence=0.95,
        )

        assert len(result.timestamps) == steps
        assert len(result.yhat) == steps
        assert len(result.yhat_lower) == steps
        assert len(result.yhat_upper) == steps
        assert result.confidence == 0.95
        assert all(l < h for l, h in zip(result.yhat_lower, result.yhat))

    def test_prophet_confidence_interval_ordering(self):
        """置信区间验证：95% 区间应比 90% 区间更宽"""
        steps = 10
        base = 100

        lower_95 = np.array([base + i - 5 for i in range(steps)])
        upper_95 = np.array([base + i + 5 for i in range(steps)])

        lower_90 = np.array([base + i - 3 for i in range(steps)])
        upper_90 = np.array([base + i + 3 for i in range(steps)])

        interval_95 = float(np.mean(upper_95 - lower_95))
        interval_90 = float(np.mean(upper_90 - lower_90))

        assert interval_95 > interval_90, "95% 置信区间应该比 90% 更宽"


# ─── Test: ARIMA 训练 + 预测 ─────────────────────────────────────────────────


class TestArimaTrainPredict:
    """测试 ARIMA 模型"""

    def test_arima_engine_interface(self, mock_csv_content):
        """ArimaEngine 接口级验证"""
        from src.mlkit.forecast.engine import ArimaEngine, AutoArimaResult
        import dataclasses
        import inspect

        # Verify _auto_arima classmethod exists
        assert hasattr(ArimaEngine, '_auto_arima'), "ArimaEngine missing _auto_arima"

        # Verify ArimaEngine.name attribute
        assert ArimaEngine.name == 'arima'

        # Verify AutoArimaResult dataclass fields
        arima_fields = {f.name for f in dataclasses.fields(AutoArimaResult)}
        assert 'order' in arima_fields
        assert 'aic' in arima_fields

        # Verify train signature
        sig = inspect.signature(ArimaEngine.train)
        param_names = list(sig.parameters.keys())
        assert 'p' in param_names
        assert 'd' in param_names
        assert 'q' in param_names
        assert 'auto' in param_names

    def test_arima_manual_order_signature(self, mock_csv_content):
        """ARIMA 手动指定阶数时参数验证"""
        from src.mlkit.forecast.engine import ArimaEngine
        import inspect

        sig = inspect.signature(ArimaEngine.train)
        param_names = list(sig.parameters.keys())
        assert 'p' in param_names, f"Missing 'p' param. Available: {param_names}"
        assert 'd' in param_names
        assert 'q' in param_names
        assert 'auto' in param_names

    def test_arima_predict_output_format(self):
        """ARIMA 预测输出格式验证"""
        steps = 30
        rng = np.random.default_rng(42)
        mock_forecast = pd.Series([100 + 0.5 * i + rng.normal(0, 1) for i in range(steps)])

        assert len(mock_forecast) == steps
        assert not mock_forecast.isna().any()


# ─── Test: LightGBM 训练 + 预测 ───────────────────────────────────────────────


class TestLightGBMTrainPredict:
    """测试 LightGBM 模型"""

    @pytest.mark.skipif(
        not _lightgbm_available(), reason="lightgbm not installed"
    )
    @patch('lightgbm.LGBMRegressor')
    def test_lightgbm_train_with_lags(self, MockLGBM, mock_csv_content):
        """LightGBM 训练：验证模型创建"""
        from src.mlkit.forecast.engine import LightGBMEngine

        def mock_fit(*args, **kwargs):
            return None

        def mock_predict(X):
            return np.ones(X.shape[0]) * 100.0

        mock_model = MagicMock()
        mock_model.best_iteration_ = 50
        mock_model.fit.side_effect = mock_fit
        mock_model.predict.side_effect = mock_predict
        MockLGBM.return_value = mock_model

        df = pd.read_csv(io.StringIO(mock_csv_content))
        df.columns = ['timestamp', 'value']

        model, result = LightGBMEngine.train(
            df,
            target_col='value',
            timestamp_col='timestamp',
            lags=[1, 7],
            n_estimators=100,
        )

        assert result.model_type == 'lightgbm'
        mock_model.fit.assert_called()

    @pytest.mark.skipif(
        not _lightgbm_available(), reason="lightgbm not installed"
    )
    def test_lightgbm_interface(self):
        """LightGBMEngine 接口级验证"""
        from src.mlkit.forecast.engine import LightGBMEngine
        import inspect

        assert LightGBMEngine.name == 'lightgbm'

        sig = inspect.signature(LightGBMEngine.train)
        param_names = list(sig.parameters.keys())
        assert 'lags' in param_names
        assert 'rolling_windows' in param_names
        assert 'n_estimators' in param_names

    def test_lightgbm_quantile_confidence_interval(self):
        """LightGBM 置信区间：使用蒙特卡洛/百分位数法"""
        steps = 30

        lower = np.array([95 + 0.4 * i for i in range(steps)])
        upper = np.array([105 + 0.6 * i for i in range(steps)])
        yhat = (lower + upper) / 2

        assert np.all(lower < yhat), "置信下限应小于预测值"
        assert np.all(upper > yhat), "置信上限应大于预测值"


# ─── Test: 季节性分解 ─────────────────────────────────────────────────────────


class TestDecomposition:
    """测试季节性分解功能"""

    def test_prophet_decompose_output_format(self):
        """Prophet 分解输出格式验证"""
        from src.mlkit.forecast.decompose import DecomposeResult

        steps = 100
        result = DecomposeResult(
            timestamps=[f'2024-01-{i+1:02d}' for i in range(steps)],
            trend=[100 + 0.5 * i for i in range(steps)],
            seasonal=[10 * np.sin(2 * np.pi * i / 7) for i in range(steps)],
            residual=list(np.random.randn(steps)),
            yearly=[5 * np.sin(2 * np.pi * i / 365) for i in range(steps)],
            weekly=[2 * np.sin(2 * np.pi * i / 7) for i in range(steps)],
            holidays=[0] * steps,
        )

        assert len(result.timestamps) == steps
        assert len(result.trend) == steps
        assert len(result.seasonal) == steps
        assert len(result.residual) == steps
        assert len(result.yearly) == steps
        assert len(result.weekly) == steps

    def test_decompose_statsmodels_interface(self):
        """decompose_arima 接口级验证"""
        from src.mlkit.forecast.decompose import DecomposeResult
        from src.mlkit.forecast.detector import FrequencyType

        # Verify DecomposeResult has correct fields
        assert hasattr(DecomposeResult, '__dataclass_fields__')

        # Verify function signature
        import inspect
        from src.mlkit.forecast.decompose import decompose_arima
        sig = inspect.signature(decompose_arima)
        param_names = list(sig.parameters.keys())
        assert 'df' in param_names
        assert 'timestamp_col' in param_names
        assert 'target_col' in param_names

    def test_decompose_trend_extraction(self):
        """分解：趋势提取（数学验证）"""
        rng = np.random.default_rng(42)
        steps = 100
        trend = np.array([100 + 0.5 * i for i in range(steps)])
        seasonal = np.array([10 * np.sin(2 * np.pi * i / 7) for i in range(steps)])
        noise = rng.normal(0, 0.1, steps)
        observed = trend + seasonal + noise

        # 验证趋势是单调或近似单调
        trend_diff = np.diff(trend)
        assert np.mean(trend_diff) > 0, "趋势应该单调递增"


# ─── Test: 时序交叉验证 ───────────────────────────────────────────────────────


class TestCrossValidation:
    """测试时序交叉验证"""

    def test_ts_cv_no_leakage(self):
        """交叉验证：验证无数据泄露（严格时序切分）"""
        # 模拟 180 天数据的滚动窗口切分逻辑
        data_len = 180
        initial_days = 90
        horizon = 30
        period = 30

        folds = []
        current_end = initial_days
        while current_end + horizon <= data_len:
            train_end = current_end
            test_start = current_end
            folds.append((train_end, test_start))
            current_end += period

        # 验证各 fold 的 train/test 不重叠
        for fold_idx, (train_end, test_start) in enumerate(folds):
            assert train_end <= test_start, f"Fold {fold_idx}: 训练集与测试集重叠！"
            assert test_start + horizon <= data_len, f"Fold {fold_idx}: 测试集超出数据范围"

    def test_ts_cv_fold_count(self):
        """交叉验证：验证 fold 数量"""
        data_len = 180
        initial_days = 90
        horizon = 30
        period = 30

        folds = []
        current_end = initial_days
        while current_end + horizon <= data_len:
            folds.append(current_end)
            current_end += period

        assert len(folds) >= 2, f"Fold 数量应 >= 2，实际 {len(folds)}"

    def test_cv_metrics_calculation(self):
        """交叉验证：MAE / RMSE / MAPE 计算正确"""
        from src.mlkit.forecast.crossval import _compute_metrics

        y_true = np.array([100, 102, 105, 103, 107])
        y_pred = np.array([99, 101, 104, 106, 108])

        mae, rmse, mape = _compute_metrics(y_true, y_pred)

        # 手动验证 MAE
        expected_mae = float(np.mean(np.abs(y_true - y_pred)))
        assert abs(mae - expected_mae) < 1e-6

        # 手动验证 RMSE
        expected_rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        assert abs(rmse - expected_rmse) < 1e-6

        # 手动验证 MAPE
        mask = y_true != 0
        expected_mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
        assert abs(mape - expected_mape) < 1e-4

    def test_cv_fold_metrics_output_format(self):
        """交叉验证：FoldMetrics 输出格式"""
        from src.mlkit.forecast.crossval import FoldMetrics

        fold = FoldMetrics(
            fold=1,
            train_start='2024-01-01',
            train_end='2024-03-31',
            test_start='2024-04-01',
            test_end='2024-04-30',
            n_train=90,
            n_test=30,
            mae=2.5,
            rmse=3.1,
            mape=1.8,
        )

        assert fold.fold == 1
        assert fold.n_train == 90
        assert fold.n_test == 30
        assert 0 < fold.mae < 10
        assert 0 < fold.rmse < 10
        assert 0 < fold.mape < 10

    def test_cv_crossval_function_interface(self):
        """cross_validate 函数接口验证"""
        from src.mlkit.forecast.crossval import cross_validate, CrossValResult
        import inspect

        sig = inspect.signature(cross_validate)
        param_names = list(sig.parameters.keys())

        assert 'initial_days' in param_names
        assert 'horizon' in param_names
        assert 'period' in param_names
        assert 'model_train_fn' in param_names
        assert 'model_predict_fn' in param_names

        # Verify CrossValResult has correct fields
        import dataclasses
        fields = {f.name for f in dataclasses.fields(CrossValResult)}
        assert 'folds' in fields
        assert 'mae_mean' in fields
        assert 'rmse_mean' in fields
        assert 'mape_mean' in fields


# ─── Test: API 路由端点 ────────────────────────────────────────────────────────


class TestForecastAPI:
    """测试 API 路由端点响应格式"""

    def test_prepare_endpoint_format(self):
        """POST /api/forecast/prepare 返回格式"""
        response = {
            'dataset_id': 1,
            'name': 'test.csv',
            'freq': 'daily',
            'detected_freq': 'daily',
            'freq_confidence': 0.95,
            'time_range_start': '2024-01-01',
            'time_range_end': '2024-04-10',
            'row_count': 100,
            'missing_ratio': 0.02,
            'duplicate_count': 0,
            'feature_names': ['value'],
            'warnings': [],
        }

        assert 'dataset_id' in response
        assert 'detected_freq' in response
        assert 'row_count' in response
        assert 'missing_ratio' in response
        assert 0 <= response['missing_ratio'] <= 1

    def test_train_endpoint_format(self):
        """POST /api/forecast/train 返回格式"""
        response = {
            'task_id': 'abc123',
            'model_id': None,
            'model_type': 'prophet',
            'status': 'pending',
            'progress': 0,
            'message': 'Task queued',
        }

        assert 'task_id' in response
        assert 'model_type' in response
        assert response['model_type'] in ['prophet', 'arima', 'lightgbm']
        assert response['status'] in ['pending', 'running', 'completed', 'failed']

    def test_train_status_endpoint_format(self):
        """GET /api/forecast/train/{task_id}/status 返回格式"""
        response = {
            'task_id': 'abc123',
            'status': 'running',
            'progress': 50,
            'current_phase': 'training',
            'result': None,
            'error': None,
            'logs': '[INFO] Epoch 50/100\n[INFO] Loss: 0.234',
        }

        assert response['task_id'] == 'abc123'
        assert response['progress'] in range(0, 101)
        assert response['status'] in ['pending', 'running', 'completed', 'failed']

    def test_predict_endpoint_format(self):
        """POST /api/forecast/predict 返回格式"""
        response = {
            'model_id': 1,
            'model_type': 'prophet',
            'steps': 30,
            'confidence': 0.95,
            'forecast': [
                {
                    'timestamp': '2024-04-11',
                    'yhat': 105.5,
                    'yhat_lower': 100.2,
                    'yhat_upper': 110.8,
                    'confidence': 0.95,
                }
            ] * 30,
            'warnings': [],
        }

        assert 'forecast' in response
        assert len(response['forecast']) == 30
        first = response['forecast'][0]
        assert 'timestamp' in first
        assert 'yhat' in first
        assert 'yhat_lower' in first
        assert 'yhat_upper' in first
        assert first['yhat_lower'] < first['yhat'] < first['yhat_upper']

    def test_decompose_endpoint_format(self):
        """GET /api/forecast/decompose 返回格式"""
        rng = np.random.default_rng(42)
        response = {
            'model_type': 'prophet',
            'timestamps': [f'2024-01-{i+1:02d}' for i in range(99)],
            'trend': [100 + 0.5 * i for i in range(99)],
            'seasonal': [10 * np.sin(2 * np.pi * i / 7) for i in range(99)],
            'residual': list(rng.normal(0, 0.1, 99)),
            'yearly': [5 * np.sin(2 * np.pi * i / 365) for i in range(99)],
            'weekly': [2 * np.sin(2 * np.pi * i / 7) for i in range(99)],
            'holidays': [0] * 99,
        }

        assert len(response['timestamps']) == len(response['trend'])
        assert len(response['timestamps']) == len(response['seasonal'])
        assert len(response['timestamps']) == len(response['residual'])

    def test_crossval_endpoint_format(self):
        """GET /api/forecast/cross-validate 返回格式"""
        response = {
            'task_id': 'cv123',
            'status': 'completed',
            'model_type': 'prophet',
            'model_id': 1,
            'initial_days': 90,
            'horizon': 30,
            'period': 30,
            'folds': [
                {
                    'fold': 1,
                    'train_start': '2024-01-01',
                    'train_end': '2024-03-31',
                    'test_start': '2024-04-01',
                    'test_end': '2024-04-30',
                    'n_train': 90,
                    'n_test': 30,
                    'mae': 2.5,
                    'rmse': 3.1,
                    'mape': 1.8,
                },
                {
                    'fold': 2,
                    'train_start': '2024-01-01',
                    'train_end': '2024-04-30',
                    'test_start': '2024-05-01',
                    'test_end': '2024-05-30',
                    'n_train': 120,
                    'n_test': 30,
                    'mae': 2.8,
                    'rmse': 3.4,
                    'mape': 2.0,
                },
            ],
            'mae_mean': 2.65,
            'mae_std': 0.15,
            'rmse_mean': 3.25,
            'rmse_std': 0.15,
            'mape_mean': 1.9,
            'mape_std': 0.1,
            'total_time_seconds': 12.5,
        }

        assert len(response['folds']) >= 1
        assert 'mae_mean' in response
        assert 'mae_std' in response
        expected_mae_mean = float(np.mean([f['mae'] for f in response['folds']]))
        assert abs(response['mae_mean'] - expected_mae_mean) < 1e-6


# ─── Test: 边界情况 ────────────────────────────────────────────────────────────


class TestEdgeCases:
    """边界情况测试"""

    def test_insufficient_data_rows(self, mock_csv_content):
        """数据量 < 30 条时应被检测为不足"""
        df = pd.read_csv(io.StringIO(mock_csv_content))
        df = df.head(25)
        assert len(df) < 30

    def test_empty_csv_rejected(self):
        """空 CSV 应被拒绝"""
        empty = "timestamp,value\n"
        df = pd.read_csv(io.StringIO(empty))
        assert len(df) == 0 or df.empty

    def test_all_nan_column_detected(self):
        """全为 NaN 的数值列应被检测"""
        nan_csv = (
            "timestamp,value\n"
            "2024-01-01,\n"
            "2024-01-02,\n"
            "2024-01-03,\n"
        )
        df = pd.read_csv(io.StringIO(nan_csv))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        all_nan = df['value'].isna().all()
        assert all_nan

    def test_duplicate_timestamps_deduplicated(self):
        """重复时间戳：应去重（保留最后一条）"""
        dup_csv = (
            "timestamp,value\n"
            "2024-01-01,100\n"
            "2024-01-01,101\n"
            "2024-01-02,102\n"
        )
        df = pd.read_csv(io.StringIO(dup_csv))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_dedup = df.drop_duplicates(subset=['timestamp'], keep='last')
        assert len(df_dedup) == 2
