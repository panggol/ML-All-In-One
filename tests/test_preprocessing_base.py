# -*- coding: utf-8 -*-
"""
预处理模块基础类测试
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np
from sklearn.datasets import make_classification

from mlkit.preprocessing.base import BaseTransformer, StageMode


class DummyTransformer(BaseTransformer):
    """测试用虚拟转换器"""
    
    def __init__(self, multiply=2.0):
        super().__init__()
        self.multiply = multiply
    
    def transform(self, X):
        return X * self.multiply
    
    def get_params(self):
        return {'multiply': self.multiply}


class TestBaseTransformer:
    """BaseTransformer 测试"""

    def test_fit(self):
        """测试 fit 方法"""
        X = np.array([[1, 2], [3, 4], [5, 6]])
        
        transformer = DummyTransformer()
        result = transformer.fit(X)
        
        assert result is transformer
        assert transformer.is_fitted() is True
        assert transformer._n_features_in == 2

    def test_transform(self):
        """测试 transform 方法"""
        X = np.array([[1, 2], [3, 4]])
        
        transformer = DummyTransformer(multiply=2)
        transformer.fit(X)
        result = transformer.transform(X)
        
        expected = np.array([[2, 4], [6, 8]])
        np.testing.assert_array_equal(result, expected)

    def test_fit_transform(self):
        """测试 fit_transform 方法"""
        X = np.array([[1, 2], [3, 4]])
        
        transformer = DummyTransformer(multiply=3)
        result = transformer.fit_transform(X)
        
        expected = np.array([[3, 6], [9, 12]])
        np.testing.assert_array_equal(result, expected)
        assert transformer.is_fitted() is True

    def test_get_params(self):
        """测试 get_params 方法"""
        transformer = DummyTransformer(multiply=5.0)
        params = transformer.get_params()
        
        assert params['multiply'] == 5.0

    def test_set_params(self):
        """测试 set_params 方法"""
        transformer = DummyTransformer()
        transformer.set_params(multiply=10.0)
        
        assert transformer.multiply == 10.0

    def test_stage_mode(self):
        """测试 StageMode 枚举"""
        assert StageMode.SERIAL.value == "serial"
        assert StageMode.PARALLEL.value == "parallel"

    def test_depends_on(self):
        """测试依赖阶段"""
        class DependentTransformer(BaseTransformer):
            depends_on = ['scaler', 'encoder']
            
            def transform(self, X):
                return X
        
        transformer = DependentTransformer()
        assert transformer.depends_on == ['scaler', 'encoder']

    def test_repr(self):
        """测试 __repr__"""
        transformer = DummyTransformer()
        assert repr(transformer) == "DummyTransformer()"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
