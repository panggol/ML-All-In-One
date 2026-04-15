"""
src.mlkit.forecast - 时序预测模块
Library-First: 核心 ML 逻辑封装，不依赖 API 层

主要子模块
--------
detector  : 频率自动检测
engine    : Prophet / ARIMA / LightGBM 训练和预测引擎
decompose : 季节性分解
crossval  : 时序交叉验证

CLI 使用示例
-----------
>>> from src.mlkit.forecast import prepare_data, train_model, predict
>>> df, meta = prepare_data("data.csv", timestamp_col="date", value_col="sales")
>>> model = train_model(df, model_type="prophet")
>>> result = predict(model, steps=30)
"""
from src.mlkit.forecast.detector import (
    detect_frequency,
    FrequencyType,
    infer_freq_str,
    infer_period_for_seasonality,
)
from src.mlkit.forecast.engine import (
    ForecastEngine,
    ForecastResult,
    TrainResult,
    create_lag_features,
    save_model,
    load_model,
    ProphetEngine,
    ArimaEngine,
    LightGBMEngine,
)
from src.mlkit.forecast.decompose import (
    decompose_prophet,
    decompose_arima,
    decompose_lightgbm,
    DecomposeResult,
)
from src.mlkit.forecast.crossval import (
    cross_validate,
    CrossValResult,
    FoldMetrics,
)

__all__ = [
    # detector
    "detect_frequency",
    "FrequencyType",
    "infer_freq_str",
    "infer_period_for_seasonality",
    # engine
    "ForecastEngine",
    "ForecastResult",
    "TrainResult",
    "create_lag_features",
    "save_model",
    "load_model",
    "ProphetEngine",
    "ArimaEngine",
    "LightGBMEngine",
    # decompose
    "decompose_prophet",
    "decompose_arima",
    "decompose_lightgbm",
    "DecomposeResult",
    # crossval
    "cross_validate",
    "CrossValResult",
    "FoldMetrics",
]
