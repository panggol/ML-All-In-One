# -*- coding: utf-8 -*-
"""
Imputer 测试
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np

from mlkit.preprocessing.imputer import SimpleImputer, KNNImputer


class TestSimpleImputer:
    """SimpleImputer 测试"""

    def test_fit_mean(self):
        """测试 fit 均值策略"""
        X = np.array([[1, 2], [3, np.nan], [5, 6]])
        
        imputer = SimpleImputer(strategy='mean')
        imputer.fit(X)
        
        # 第二列均值 = (2 + 6) / 2 = 4
        assert imputer.statistics_[1] == 4

    def test_transform_mean(self):
        """测试均值填充"""
        X = np.array([[1, 2], [3, np.nan], [5, 6]])
        
        imputer = SimpleImputer(strategy='mean')
        result = imputer.fit_transform(X)
        
        expected = np.array([[1, 2], [3, 4], [5, 6]])
        np.testing.assert_array_almost_equal(result, expected)

    def test_transform_median(self):
        """测试中位数填充"""
        X = np.array([[1, 2], [3, np.nan], [5, 10]])
        
        imputer = SimpleImputer(strategy='median')
        result = imputer.fit_transform(X)
        
        # 中位数 = (2 + 10) / 2 = 6
        expected = np.array([[1, 2], [3, 6], [5, 10]])
        np.testing.assert_array_almost_equal(result, expected)

    def test_transform_most_frequent(self):
        """测试众数填充"""
        X = np.array([[1, 1], [np.nan, 2], [1, 3]], dtype=float)
        
        imputer = SimpleImputer(strategy='most_frequent')
        result = imputer.fit_transform(X)
        
        # 众数是 1
        expected = np.array([[1, 1], [1, 2], [1, 3]])
        np.testing.assert_array_almost_equal(result, expected)

    def test_transform_constant(self):
        """测试常量填充"""
        X = np.array([[1, np.nan], [3, 4]])
        
        imputer = SimpleImputer(strategy='constant', fill_value=-999)
        result = imputer.fit_transform(X)
        
        expected = np.array([[1, -999], [3, 4]])
        np.testing.assert_array_equal(result, expected)


class TestKNNImputer:
    """KNNImputer 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
        
        imputer = KNNImputer(n_neighbors=2)
        imputer.fit(X)
        
        assert imputer.is_fitted() is True

    def test_transform_no_missing(self):
        """测试无缺失值"""
        X = np.array([[1, 2], [3, 4], [5, 6]])
        
        imputer = KNNImputer(n_neighbors=2)
        result = imputer.fit_transform(X)
        
        np.testing.assert_array_equal(result, X)

    def test_transform_with_missing(self):
        """测试有缺失值"""
        # 训练数据无缺失
        X_train = np.array([[1, 2], [3, 4], [5, 6], [7, 8]], dtype=float)
        # 测试数据有缺失
        X_test = np.array([[3, np.nan], [5, 6]], dtype=float)
        
        imputer = KNNImputer(n_neighbors=2)
        imputer.fit(X_train)
        result = imputer.transform(X_test)
        
        # 验证没有 NaN
        assert not np.any(np.isnan(result))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
