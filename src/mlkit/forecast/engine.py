"""
时序预测模型引擎
Library-First: Prophet / ARIMA / LightGBM 三种模型的训练和预测
"""
from __future__ import annotations

import json
import math
import os
import pickle
import tempfile
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from src.mlkit.forecast.detector import detect_frequency, FrequencyType


# ============ 数据类 ============

@dataclass
class ForecastResult:
    """预测结果"""
    timestamps: list[str]
    yhat: list[float]
    yhat_lower: list[float]
    yhat_upper: list[float]
    trend: list[float] | None = None
    yearly: list[float] | None = None
    weekly: list[float] | None = None
    holidays: list[float] | None = None
    confidence: float = 0.95


@dataclass
class TrainResult:
    """训练结果"""
    model_id: int
    model_type: str
    params: dict
    train_time_seconds: float
    metrics: dict
    warnings: list[str] = field(default_factory=list)


@dataclass
class AutoArimaResult:
    """ARIMA 自动搜索结果"""
    order: tuple[int, int, int]
    aic: float
    bic: float


# ============ 特征工程（LightGBM 用）============

def create_lag_features(
    df: pd.DataFrame,
    target_col: str,
    lags: list[int] | None = None,
    rolling_windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    为 LightGBM 生成滞后特征和滚动统计特征

    参数
    ----
    df         : 原始时序 DataFrame，必须含 timestamp/datetime 索引或列
    target_col : 目标列名
    lags       : 滞后阶数列表，默认 [1, 7, 14, 30]
    rolling_windows : 滚动窗口列表，默认 [7, 30]

    返回
    ----
    添加了 lag_* / rolling_* / time_feature_* 列的 DataFrame
    """
    if lags is None:
        lags = [1, 7, 14, 30]
    if rolling_windows is None:
        rolling_windows = [7, 30]

    df = df.copy()

    # 确保时间索引
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.set_index("timestamp").sort_index()
    elif not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have a 'timestamp' column or DatetimeIndex")

    target = df[target_col]

    # 滞后特征
    for lag in lags:
        df[f"lag_{lag}"] = target.shift(lag)

    # 滚动统计特征
    for window in rolling_windows:
        df[f"rolling_mean_{window}"] = target.shift(1).rolling(window).mean()
        df[f"rolling_std_{window}"] = target.shift(1).rolling(window).std()

    # 时间特征
    df["dayofweek"] = df.index.dayofweek
    df["month"] = df.index.month
    df["quarter"] = df.index.quarter
    df["dayofyear"] = df.index.dayofyear

    # 丢弃含 NaN 的行（lag 产生）
    df = df.dropna()

    return df.reset_index()


# ============ Prophet 引擎 ============

class ProphetEngine:
    """Prophet 预测引擎"""

    name = "prophet"

    @classmethod
    def train(
        cls,
        df: pd.DataFrame,
        target_col: str,
        timestamp_col: str = "ds",
        value_col: str = "y",
        changepoint_prior_scale: float = 0.05,
        seasonality_mode: str = "additive",
        growth: str = "linear",
        holidays: list[str] | None = None,
        custom_holidays_df: pd.DataFrame | None = None,
        **kwargs,
    ) -> tuple[object, TrainResult]:
        """
        训练 Prophet 模型

        返回 (model, TrainResult)
        """
        from prophet import Prophet

        start = time.time()

        # 准备 Prophet 格式数据
        prophet_df = df[[timestamp_col, target_col]].copy()
        prophet_df.columns = ["ds", "y"]
        prophet_df["ds"] = pd.to_datetime(prophet_df["ds"], errors="coerce")
        prophet_df = prophet_df.dropna()

        if len(prophet_df) < 30:
            raise ValueError("训练数据不足 30 条，请补充更多数据")

        warnings_list: list[str] = []

        # 构建模型
        model = Prophet(
            changepoint_prior_scale=changepoint_prior_scale,
            seasonality_mode=seasonality_mode,
            growth=growth,
            **kwargs,
        )

        # 添加中国节假日
        try:
            model.add_country_holidays("CN")
            warnings_list.append("已加载中国节假日")
        except Exception:
            warnings_list.append("中国节假日加载失败，跳过")

        # 自定义节假日
        if custom_holidays_df is not None:
            model.add_regressor("holiday")
            prophet_df = prophet_df.merge(custom_holidays_df, on="ds", how="left")
            prophet_df["holiday"] = prophet_df["holiday"].fillna(0).astype(int)
            warnings_list.append(f"已加载 {len(custom_holidays_df)} 个自定义节假日")

        model.fit(prophet_df)

        train_time = time.time() - start

        result = TrainResult(
            model_id=0,   # ID 由 API 层分配
            model_type="prophet",
            params={
                "changepoint_prior_scale": changepoint_prior_scale,
                "seasonality_mode": seasonality_mode,
                "growth": growth,
            },
            train_time_seconds=round(train_time, 2),
            metrics={},
            warnings=warnings_list,
        )
        return model, result

    @classmethod
    def predict(
        cls,
        model: object,
        steps: int,
        freq: FrequencyType,
        confidence: float = 0.95,
        freq_str: str = "D",
    ) -> ForecastResult:
        """预测未来 N 步"""
        from prophet import Prophet

        m: Prophet = model
        future = m.make_future_dataframe(periods=steps, freq=freq_str)
        forecast = m.predict(future)

        n_hist = len(m.history)
        n_total = len(forecast)
        n_future = n_total - n_hist

        # 置信区间宽度因子
        z_score = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
        interval_half = (forecast["yhat_upper"] - forecast["yhat_lower"]) / 2 / z_score * 1.96

        if n_future > 0:
            future_forecast = forecast.tail(n_future)
            yhat = future_forecast["yhat"].tolist()
            base = future_forecast["yhat"].values
            lower = (base - interval_half.tail(n_future).values * z_score / 1.96).tolist()
            upper = (base + interval_half.tail(n_future).values * z_score / 1.96).tolist()
        else:
            yhat = forecast["yhat"].tolist()
            lower = (forecast["yhat"].values - interval_half.values).tolist()
            upper = (forecast["yhat"].values + interval_half.values).tolist()

        return ForecastResult(
            timestamps=[str(ts) for ts in future_forecast["ds"]],
            yhat=[round(float(v), 4) for v in yhat],
            yhat_lower=[round(float(v), 4) for v in lower],
            yhat_upper=[round(float(v), 4) for v in upper],
            trend=[round(float(v), 4) for v in future_forecast["trend"]],
            yearly=[round(float(v), 4) for v in future_forecast["yearly"]] if "yearly" in future_forecast.columns else None,
            weekly=[round(float(v), 4) for v in future_forecast["weekly"]] if "weekly" in future_forecast.columns else None,
            holidays=[round(float(v), 4) for v in future_forecast["holidays"]] if "holidays" in future_forecast.columns else None,
            confidence=confidence,
        )


# ============ ARIMA 引擎 ============

class ArimaEngine:
    """ARIMA 预测引擎"""

    name = "arima"

    @classmethod
    def _auto_arima(cls, y: np.ndarray, max_p: int = 5, max_d: int = 2, max_q: int = 5, timeout: int = 60) -> AutoArimaResult:
        """
        自动搜索最优 ARIMA 阶数
        使用 pmdarima.auto_arima 或 statsmodels auto_arima
        """
        try:
            import pmdarima as pm
            import signal

            def handler(signum, frame):
                raise TimeoutError("ARIMA search timed out")

            # 超时处理
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(timeout)

            try:
                model = pm.auto_arima(
                    y,
                    max_p=max_p, max_d=max_d, max_q=max_q,
                    seasonal=False,
                    stepwise=True,
                    suppress_warnings=True,
                    error_action="ignore",
                )
                order = tuple(int(x) for x in model.order)
                aic = float(model.aic())
                bic = float(model.bic()) if hasattr(model, "bic") else float(model.aic())
            finally:
                signal.alarm(0)

            return AutoArimaResult(order=order, aic=aic, bic=bic)

        except ImportError:
            # fallback: 使用 statsmodels ARIMA 默认参数
            from statsmodels.tsa.arima.model import ARIMA
            import warnings as sw
            with sw.simplefilter("ignore"):
                m = ARIMA(y, order=(1, 1, 1))
                f = m.fit()
                return AutoArimaResult(
                    order=(1, 1, 1),
                    aic=float(f.aic),
                    bic=float(f.bic),
                )

    @classmethod
    def train(
        cls,
        df: pd.DataFrame,
        target_col: str,
        timestamp_col: str = "timestamp",
        p: int | None = None,
        d: int | None = None,
        q: int | None = None,
        auto: bool = True,
        max_p: int = 5,
        max_d: int = 2,
        max_q: int = 5,
        search_timeout: int = 60,
        **kwargs,
    ) -> tuple[object, TrainResult]:
        """训练 ARIMA 模型"""
        from statsmodels.tsa.arima.model import ARIMA
        import warnings as sw

        start = time.time()
        warnings_list: list[str] = []

        # 准备数据
        ts_df = df[[timestamp_col, target_col]].copy()
        ts_df.columns = ["timestamp", "y"]
        ts_df["timestamp"] = pd.to_datetime(ts_df["timestamp"], errors="coerce")
        ts_df = ts_df.dropna().set_index("timestamp").sort_index()

        if len(ts_df) < 30:
            raise ValueError("训练数据不足 30 条")

        y = ts_df["y"].values.astype(float)

        # 自动搜索或手动指定
        if auto or p is None:
            arima_result = cls._auto_arima(y, max_p=max_p, max_d=max_d, max_q=max_q, timeout=search_timeout)
            order = arima_result.order
            warnings_list.append(f"自动搜索最优阶数: {order}, AIC={arima_result.aic:.2f}")
        else:
            order = (p, d or 1, q or 1)

        with sw.simplefilter("ignore"):
            model = ARIMA(y, order=order)
            fit = model.fit()

        train_time = time.time() - start

        result = TrainResult(
            model_id=0,
            model_type="arima",
            params={"order": order},
            train_time_seconds=round(train_time, 2),
            metrics={
                "aic": round(float(fit.aic), 4),
                "bic": round(float(fit.bic), 4),
            },
            warnings=warnings_list,
        )
        return fit, result

    @classmethod
    def predict(
        cls,
        model_fit: object,
        steps: int,
        confidence: float = 0.95,
    ) -> ForecastResult:
        """预测未来 N 步"""
        from statsmodels.tsa.arima.model import ARIMAResults

        fit: ARIMAResults = model_fit
        forecast = fit.get_forecast(steps=steps)
        mean = forecast.predicted_mean
        # statsmodels 提供 95% 置信区间
        conf_int = forecast.conf_int(alpha=1 - confidence)

        z_score = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)

        # 统一置信区间（支持任意 confidence）
        se = (conf_int.iloc[:, 1] - conf_int.iloc[:, 0]).values / (2 * z_score)
        lower = mean.values - z_score * se
        upper = mean.values + z_score * se

        last_date = pd.Timestamp(fit.data.dates[-1])
        index = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=steps, freq="D")
        timestamps = [str(ts) for ts in index]

        return ForecastResult(
            timestamps=timestamps,
            yhat=[round(float(v), 4) for v in mean.values],
            yhat_lower=[round(float(v), 4) for v in lower],
            yhat_upper=[round(float(v), 4) for v in upper],
            confidence=confidence,
        )


# ============ LightGBM 引擎 ============

class LightGBMEngine:
    """LightGBM 监督学习时序预测引擎"""

    name = "lightgbm"

    @classmethod
    def train(
        cls,
        df: pd.DataFrame,
        target_col: str,
        timestamp_col: str = "timestamp",
        value_col: str = "value",
        lags: list[int] | None = None,
        rolling_windows: list[int] | None = None,
        n_estimators: int = 100,
        early_stopping_rounds: int | None = None,
        **kwargs,
    ) -> tuple[object, TrainResult]:
        """训练 LightGBM 回归模型"""
        import lightgbm as lgb
        from sklearn.model_selection import train_test_split

        start = time.time()
        warnings_list: list[str] = []

        # 生成特征
        features_df = create_lag_features(
            df[[timestamp_col, value_col]].rename(columns={value_col: target_col}),
            target_col=target_col,
            lags=lags,
            rolling_windows=rolling_windows,
        )

        feature_cols = [c for c in features_df.columns if c not in ["timestamp", target_col]]

        X = features_df[feature_cols].values
        y = features_df[target_col].values

        if len(X) < 30:
            raise ValueError(f"特征工程后有效数据仅 {len(X)} 条（lag 导致），请补充数据")

        # 划分训练/验证集（时间顺序，不打乱）
        split = max(1, int(len(X) * 0.8))
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]

        params = {
            "objective": "regression",
            "metric": "mae",
            "verbosity": -1,
            "n_estimators": n_estimators,
        }
        params.update(kwargs)

        model = lgb.LGBMRegressor(**params)

        eval_set = [(X_val, y_val)] if len(X_val) > 0 and early_stopping_rounds else None
        model.fit(
            X_train, y_train,
            eval_set=eval_set,
            callbacks=[
                lgb.early_stopping(early_stopping_rounds or 999999),
                lgb.log_evaluation(0),
            ] if eval_set else [lgb.log_evaluation(0)],
        )

        # 计算训练集指标
        y_pred = model.predict(X_train)
        mae = float(np.mean(np.abs(y_train - y_pred)))
        rmse = float(np.sqrt(np.mean((y_train - y_pred) ** 2)))

        train_time = time.time() - start

        result = TrainResult(
            model_id=0,
            model_type="lightgbm",
            params={"lags": lags, "rolling_windows": rolling_windows, "n_estimators": n_estimators},
            train_time_seconds=round(train_time, 2),
            metrics={"train_mae": round(mae, 4), "train_rmse": round(rmse, 4)},
            warnings=warnings_list,
        )
        return (model, feature_cols), result

    @classmethod
    def predict(
        cls,
        model_and_features: tuple,
        last_df: pd.DataFrame,
        target_col: str,
        timestamp_col: str = "timestamp",
        value_col: str = "value",
        steps: int = 30,
        confidence: float = 0.95,
    ) -> ForecastResult:
        """滚动预测未来 N 步（每次用预测值更新特征）"""
        import lightgbm as lgb

        model, feature_cols = model_and_features
        last_df = last_df.copy()
        last_df["timestamp"] = pd.to_datetime(last_df["timestamp"], errors="coerce")
        last_df = last_df.sort_values("timestamp").reset_index(drop=True)

        all_timestamps = []
        all_yhat = []
        all_lower = []
        all_upper = []

        current_df = last_df.tail(200).copy()  # 保留最近数据用于滚动

        for step in range(steps):
            # 构造当前步特征
            feat_df = create_lag_features(
                current_df[[timestamp_col, value_col]].rename(columns={value_col: target_col}),
                target_col=target_col,
            )
            feat_row = feat_df[feature_cols].tail(1)

            if len(feat_row) == 0:
                break

            y_pred = model.predict(feat_row.values)[0]

            # 更新置信区间（用历史残差标准差估计）
            residuals = last_df[value_col].values[-min(100, len(last_df)):]
            if len(residuals) > 5:
                std_resid = float(np.std(last_df[value_col].values[-100:] - model.predict(
                    create_lag_features(
                        last_df[[timestamp_col, value_col]].rename(columns={value_col: target_col}),
                        target_col=target_col,
                    )[feature_cols].tail(len(last_df) - max(30, len(last_df)) + 100).values
                )[-min(50, len(residuals)):]))

                z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
                half_width = z * (std_resid if std_resid > 0 else abs(y_pred) * 0.1)
            else:
                half_width = abs(y_pred) * 0.05

            last_ts = pd.to_datetime(current_df[timestamp_col].iloc[-1])
            next_ts = last_ts + pd.Timedelta(days=1)

            all_timestamps.append(str(next_ts))
            all_yhat.append(round(float(y_pred), 4))
            all_lower.append(round(float(y_pred - half_width), 4))
            all_upper.append(round(float(y_pred + half_width), 4))

            # 追加预测值，继续滚动
            new_row = {timestamp_col: next_ts, value_col: y_pred}
            current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)

        return ForecastResult(
            timestamps=all_timestamps,
            yhat=all_yhat,
            yhat_lower=all_lower,
            yhat_upper=all_upper,
            confidence=confidence,
        )


# ============ 统一引擎接口 ============

class ForecastEngine:
    """统一调度入口"""

    ENGINES = {
        "prophet": ProphetEngine,
        "arima": ArimaEngine,
        "lightgbm": LightGBMEngine,
    }

    @classmethod
    def train(
        cls,
        model_type: str,
        df: pd.DataFrame,
        target_col: str,
        timestamp_col: str = "timestamp",
        value_col: str = "value",
        confidence: float = 0.95,
        **kwargs,
    ) -> tuple[object, TrainResult]:
        """
        训练时序预测模型

        参数
        ----
        model_type : str   "prophet" | "arima" | "lightgbm"
        df         : DataFrame，含 timestamp_col 和 value_col
        target_col : str   目标列名（Prophet 用 ds/y，ARIMA/LightGBM 用 target）
        timestamp_col : str  默认 "timestamp"
        value_col  : str   默认 "value"
        kwargs     : 模型特定参数

        返回
        ----
        (model_instance, TrainResult)
        """
        engine_cls = cls.ENGINES.get(model_type.lower())
        if engine_cls is None:
            raise ValueError(f"不支持的模型类型: {model_type}，可选: {list(cls.ENGINES.keys())}")

        return engine_cls.train(df, target_col, timestamp_col, value_col, **kwargs)

    @classmethod
    def predict(
        cls,
        model_type: str,
        model: object,
        df: pd.DataFrame | None,
        steps: int,
        freq: FrequencyType = "daily",
        confidence: float = 0.95,
        **kwargs,
    ) -> ForecastResult:
        """预测接口"""
        engine_cls = cls.ENGINES.get(model_type.lower())
        if engine_cls is None:
            raise ValueError(f"不支持的模型类型: {model_type}")

        freq_str = {
            "daily": "D", "weekly": "W", "monthly": "MS",
            "quarterly": "QS", "yearly": "YS",
        }.get(freq, "D")

        return engine_cls.predict(model, steps, confidence=confidence, freq_str=freq_str, **kwargs)


def save_model(model: object, model_type: str, path: str) -> None:
    """持久化模型到文件系统"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump((model_type, model), f)


def load_model(path: str) -> tuple[str, object]:
    """从文件系统加载模型"""
    with open(path, "rb") as f:
        model_type, model = pickle.load(f)
    return model_type, model
