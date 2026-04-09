# -*- coding: utf-8 -*-
"""
新增预处理功能测试 - TargetEncoder, QuantileTransformer, PowerTransformer, IterativeImputer
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np

from mlkit.preprocessing.tabular.encoder import TargetEncoder
from mlkit.preprocessing.tabular.scaler import QuantileTransformer, PowerTransformer
from mlkit.preprocessing.tabular.imputer import IterativeImputer


class TestTargetEncoder:
    """TargetEncoder 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.array([['cat'], ['dog'], ['cat'], ['mouse']])
        y = np.array([1, 0, 1, 0])
        
        encoder = TargetEncoder()
        encoder.fit(X, y)
        
        assert encoder.is_fitted() is True
        assert encoder.global_mean_ == 0.5

    def test_transform(self):
        """测试 transform"""
        X = np.array([['cat'], ['dog'], ['cat'], ['mouse']])
        y = np.array([1, 0, 1, 0])
        
        encoder = TargetEncoder()
        encoder.fit(X, y)
        result = encoder.transform(X)
        
        # cat: mean=1, count=2, global=0.5, smoothing=1
        # -> (2*1 + 1*0.5) / (2+1) = 2.5/3 ≈ 0.833
        # dog: mean=0, count=1 -> (1*0 + 1*0.5)/2 = 0.25
        # mouse: mean=0, count=1 -> 0.25
        assert result.shape == X.shape
        assert result[0, 0] > result[1, 0]  # cat > dog

    def test_fit_transform(self):
        """测试 fit_transform"""
        X = np.array([['cat'], ['dog'], ['cat'], ['mouse']])
        y = np.array([1, 0, 1, 0])
        
        encoder = TargetEncoder()
        result = encoder.fit_transform(X, y)
        
        assert result.shape == X.shape

    def test_smoothing(self):
        """测试平滑参数"""
        X = np.array([['cat'], ['dog'], ['cat'], ['mouse']])
        y = np.array([1, 0, 1, 0])
        
        # 高 smoothing 趋向于全局均值
        encoder_high = TargetEncoder(smoothing=100)
        encoder_high.fit(X, y)
        result_high = encoder_high.transform(X)
        
        # 低 smoothing 趋向于类别均值
        encoder_low = TargetEncoder(smoothing=0.01)
        encoder_low.fit(X, y)
        result_low = encoder_low.transform(X)
        
        # 高 smoothing 应该更接近 0.5
        assert abs(result_high[0, 0] - 0.5) < abs(result_low[0, 0] - 0.5)

    def test_multicolumn(self):
        """测试多列"""
        X = np.array([
            ['cat', 'A'],
            ['dog', 'B'],
            ['cat', 'A'],
            ['mouse', 'C']
        ])
        y = np.array([1, 0, 1, 0])
        
        encoder = TargetEncoder()
        result = encoder.fit_transform(X, y)
        
        assert result.shape == (4, 2)


class TestQuantileTransformer:
    """QuantileTransformer 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.random.randn(1000, 3)
        
        transformer = QuantileTransformer(n_quantiles=100)
        transformer.fit(X)
        
        assert transformer.is_fitted() is True
        assert transformer.quantiles_.shape[0] == 100

    def test_transform_uniform(self):
        """测试 uniform 分布变换"""
        X = np.random.randn(1000, 3)
        
        transformer = QuantileTransformer(
            n_quantiles=100, 
            output_distribution='uniform'
        )
        result = transformer.fit_transform(X)
        
        # uniform 分布应该在 [0, 1] 范围内
        assert result.min() >= 0
        assert result.max() <= 1

    def test_transform_normal(self):
        """测试 normal 分布变换"""
        X = np.random.randn(1000, 3)
        
        transformer = QuantileTransformer(
            n_quantiles=100, 
            output_distribution='normal'
        )
        result = transformer.fit_transform(X)
        
        # normal 分布均值接近 0，标准差接近 1
        assert abs(np.mean(result)) < 0.1
        assert abs(np.std(result) - 1) < 0.1

    def test_inverse_transform(self):
        """测试逆变换"""
        X = np.random.randn(1000, 3)
        
        transformer = QuantileTransformer(n_quantiles=100)
        X_transformed = transformer.fit_transform(X)
        X_inverse = transformer.inverse_transform(X_transformed)
        
        # 逆变换应该接近原始数据
        # 注意：由于分位数化的精度损失，不会完全相等
        np.testing.assert_allclose(X, X_inverse, rtol=0.5)

    def test_n_quantiles(self):
        """测试 n_quantiles 参数"""
        X = np.random.randn(100, 3)
        
        transformer = QuantileTransformer(n_quantiles=50)
        transformer.fit(X)
        
        assert transformer.quantiles_.shape[0] == 50


class TestPowerTransformer:
    """PowerTransformer 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.random.randn(100, 3) ** 2 + 1  # 确保为正
        
        transformer = PowerTransformer(method='yeo-johnson')
        transformer.fit(X)
        
        assert transformer.is_fitted() is True
        assert transformer.lambdas_.shape == (3,)

    def test_fit_boxcox(self):
        """测试 Box-Cox fit"""
        X = np.random.randn(100, 3) ** 2 + 1  # 确保为正
        
        transformer = PowerTransformer(method='box-cox')
        transformer.fit(X)
        
        assert transformer.is_fitted() is True
        # Box-Cox 要求输入为正
        assert all(l > 0 for l in transformer.lambdas_)

    def test_transform_yeojohnson(self):
        """测试 Yeo-Johnson 变换"""
        X = np.random.randn(100, 3) ** 2 + 0.1  # 可以包含零
        
        transformer = PowerTransformer(method='yeo-johnson')
        result = transformer.fit_transform(X)
        
        # 变换后应该接近正态分布
        assert abs(np.mean(result)) < 0.2
        assert abs(np.std(result) - 1) < 0.2

    def test_inverse_transform(self):
        """测试逆变换"""
        X = np.random.randn(100, 3) ** 2 + 0.1
        
        transformer = PowerTransformer(method='yeo-johnson')
        X_transformed = transformer.fit_transform(X)
        X_inverse = transformer.inverse_transform(X_transformed)
        
        # 逆变换应该接近原始数据
        np.testing.assert_allclose(X, X_inverse, rtol=0.1)

    def test_standardize(self):
        """测试标准化参数"""
        X = np.random.randn(100, 3) ** 2 + 0.1
        
        # 带标准化
        transformer_std = PowerTransformer(method='yeo-johnson', standardize=True)
        result_std = transformer_std.fit_transform(X)
        
        # 不带标准化
        transformer_no_std = PowerTransformer(method='yeo-johnson', standardize=False)
        result_no_std = transformer_no_std.fit_transform(X)
        
        # 标准化后均值接近 0，标准差接近 1
        assert abs(np.mean(result_std)) < 0.1
        assert abs(np.std(result_std) - 1) < 0.1


class TestIterativeImputer:
    """IterativeImputer 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.random.randn(100, 3)
        X[::5, 0] = np.nan  # 引入缺失值
        
        imputer = IterativeImputer(max_iter=5)
        imputer.fit(X)
        
        assert imputer.is_fitted() is True

    def test_transform(self):
        """测试填充"""
        X = np.random.randn(100, 3)
        X[::5, 0] = np.nan
        X[::10, 1] = np.nan
        
        imputer = IterativeImputer(max_iter=5)
        result = imputer.fit_transform(X)
        
        # 填充后应该没有 NaN
        assert not np.any(np.isnan(result))

    def test_max_iter(self):
        """测试迭代次数"""
        X = np.random.randn(50, 3)
        X[::5, :] = np.nan
        
        imputer = IterativeImputer(max_iter=1)
        result = imputer.fit_transform(X)
        
        assert not np.any(np.isnan(result))

    def test_initial_strategy(self):
        """测试初始填充策略"""
        X = np.random.randn(50, 3)
        X[::5, :] = np.nan
        
        # median 策略
        imputer = IterativeImputer(initial_strategy='median', max_iter=3)
        result = imputer.fit_transform(X)
        
        assert not np.any(np.isnan(result))

    def test_convergence(self):
        """测试收敛"""
        np.random.seed(42)
        X = np.random.randn(100, 3)
        X[::5, :] = np.nan
        
        imputer_tight = IterativeImputer(tol=1e-6, max_iter=100)
        imputer_loose = IterativeImputer(tol=1, max_iter=5)
        
        # 两者都应该能收敛
        result_tight = imputer_tight.fit_transform(X)
        result_loose = imputer_loose.fit_transform(X)
        
        assert not np.any(np.isnan(result_tight))
        assert not np.any(np.isnan(result_loose))

    def test_preserve_values(self):
        """测试保留非缺失值"""
        X = np.array([
            [1.0, 2.0, np.nan],
            [3.0, np.nan, 6.0],
            [np.nan, 8.0, 9.0]
        ])
        
        imputer = IterativeImputer(max_iter=10)
        result = imputer.fit_transform(X)
        
        # 非缺失值应该被保留（近似）
        assert abs(result[0, 0] - 1.0) < 0.1
        assert abs(result[0, 1] - 2.0) < 0.1
        assert abs(result[1, 0] - 3.0) < 0.1
        assert abs(result[1, 2] - 6.0) < 0.1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
