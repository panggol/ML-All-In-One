# -*- coding: utf-8 -*-
"""
Scaler 测试
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np

from mlkit.preprocessing.scaler import StandardScaler, MinMaxScaler, RobustScaler


class TestStandardScaler:
    """StandardScaler 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.array([[1, 2], [3, 4], [5, 6]])
        
        scaler = StandardScaler()
        scaler.fit(X)
        
        assert scaler.is_fitted() is True
        np.testing.assert_array_almost_equal(scaler.mean_, [3, 4])
        np.testing.assert_array_almost_equal(scaler.std_, [1.632, 1.632], decimal=3)

    def test_transform(self):
        """测试 transform"""
        X = np.array([[1, 2], [3, 4], [5, 6]])
        
        scaler = StandardScaler()
        result = scaler.fit_transform(X)
        
        # 均值应接近0，标准差应接近1
        assert np.abs(result.mean(axis=0)).max() < 0.001
        assert np.abs(result.std(axis=0) - 1).max() < 0.001

    def test_inverse_transform(self):
        """测试逆变换"""
        X = np.array([[1, 2], [3, 4], [5, 6]])
        
        scaler = StandardScaler()
        scaler.fit(X)
        
        transformed = scaler.transform(X)
        restored = scaler.inverse_transform(transformed)
        
        np.testing.assert_array_almost_equal(restored, X)

    def test_with_mean_false(self):
        """测试不中心化"""
        X = np.array([[1, 2], [3, 4], [5, 6]])
        
        scaler = StandardScaler(with_mean=False, with_std=False)
        result = scaler.fit_transform(X)
        
        # with_mean=False, with_std=False 时应该等于原始数据
        np.testing.assert_array_almost_equal(result, X)


class TestMinMaxScaler:
    """MinMaxScaler 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.array([[1, 0], [2, 4], [3, 6]])
        
        scaler = MinMaxScaler()
        scaler.fit(X)
        
        assert scaler.is_fitted() is True
        np.testing.assert_array_equal(scaler.min_, [1, 0])
        np.testing.assert_array_equal(scaler.max_, [3, 6])

    def test_transform(self):
        """测试 transform 到 [0, 1]"""
        X = np.array([[1, 0], [2, 4], [3, 6]])
        
        scaler = MinMaxScaler()
        result = scaler.fit_transform(X)
        
        # 使用近似比较
        expected = np.array([[0, 0], [0.5, 0.66666667], [1, 1]])
        np.testing.assert_array_almost_equal(result, expected, decimal=3)

    def test_transform_custom_range(self):
        """测试自定义范围"""
        X = np.array([[1, 0], [2, 4], [3, 6]])
        
        scaler = MinMaxScaler(feature_range=(-1, 1))
        result = scaler.fit_transform(X)
        
        expected = np.array([[-1, -1], [0, 0.33333333], [1, 1]])
        np.testing.assert_array_almost_equal(result, expected, decimal=3)

    def test_inverse_transform(self):
        """测试逆变换"""
        X = np.array([[1, 0], [2, 4], [3, 6]])
        
        scaler = MinMaxScaler()
        scaler.fit(X)
        
        transformed = scaler.transform(X)
        restored = scaler.inverse_transform(transformed)
        
        np.testing.assert_array_almost_equal(restored, X)


class TestRobustScaler:
    """RobustScaler 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.array([[1, 2], [3, 4], [5, 6], [100, 100]])  # 有异常值
        
        scaler = RobustScaler()
        scaler.fit(X)
        
        assert scaler.is_fitted() is True
        # np.median([1,3,5,100]) = (3+5)/2 = 4
        # np.median([2,4,6,100]) = (4+6)/2 = 5
        np.testing.assert_array_almost_equal(scaler.center_, [4, 5])

    def test_transform(self):
        """测试 transform"""
        X = np.array([[0, 0], [2, 2], [4, 4], [6, 6]])
        
        scaler = RobustScaler()
        result = scaler.fit_transform(X)
        
        # 中位数应该在0附近
        assert np.abs(np.median(result)) < 0.1

    def test_inverse_transform(self):
        """测试逆变换"""
        X = np.array([[0, 0], [2, 2], [4, 4], [6, 6]])
        
        scaler = RobustScaler()
        scaler.fit(X)
        
        transformed = scaler.transform(X)
        restored = scaler.inverse_transform(transformed)
        
        np.testing.assert_array_almost_equal(restored, X)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
