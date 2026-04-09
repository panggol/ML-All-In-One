# -*- coding: utf-8 -*-
"""
Encoder 测试
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np

from mlkit.preprocessing.encoder import LabelEncoder, OneHotEncoder, OrdinalEncoder


class TestLabelEncoder:
    """LabelEncoder 测试"""

    def test_fit(self):
        """测试 fit"""
        y = np.array(['cat', 'dog', 'cat', 'bird'])
        
        encoder = LabelEncoder()
        encoder.fit(y)
        
        assert encoder.is_fitted() is True
        assert len(encoder.classes_) == 3

    def test_transform(self):
        """测试 transform"""
        y = np.array(['cat', 'dog', 'cat'])
        
        encoder = LabelEncoder()
        encoder.fit(y)
        result = encoder.transform(y)
        
        expected = np.array([0, 1, 0])  # cat=0, dog=1
        np.testing.assert_array_equal(result, expected)

    def test_fit_transform(self):
        """测试 fit_transform"""
        y = np.array(['cat', 'dog', 'cat'])
        
        encoder = LabelEncoder()
        result = encoder.fit_transform(y)
        
        expected = np.array([0, 1, 0])
        np.testing.assert_array_equal(result, expected)

    def test_inverse_transform(self):
        """测试逆变换"""
        y = np.array(['cat', 'dog', 'cat'])
        
        encoder = LabelEncoder()
        encoder.fit(y)
        
        indices = np.array([0, 1, 0])
        result = encoder.inverse_transform(indices)
        
        np.testing.assert_array_equal(result, y)


class TestOneHotEncoder:
    """OneHotEncoder 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.array([['cat', 'small'], ['dog', 'medium'], ['cat', 'large']])
        
        encoder = OneHotEncoder()
        encoder.fit(X)
        
        assert encoder.is_fitted() is True
        assert len(encoder.categories_) == 2

    def test_transform(self):
        """测试 transform"""
        X = np.array([['cat', 'small'], ['dog', 'medium']])
        
        encoder = OneHotEncoder()
        encoder.fit(X)
        result = encoder.transform(X)
        
        # np.unique 排序后: ['cat', 'dog'], ['medium', 'small']
        # 列0: cat=1, 列1: dog=1, 列2: medium=1, 列3: small=1
        expected = np.array([
            [1, 0, 0, 1],  # cat=1, small=1
            [0, 1, 1, 0],  # dog=1, medium=1
        ])
        np.testing.assert_array_equal(result, expected)

    def test_fit_transform(self):
        """测试 fit_transform"""
        X = np.array([['cat', 'small'], ['dog', 'medium']])
        
        encoder = OneHotEncoder()
        result = encoder.fit_transform(X)
        
        expected = np.array([
            [1, 0, 0, 1],  # cat, small
            [0, 1, 1, 0],  # dog, medium
        ])
        np.testing.assert_array_equal(result, expected)


class TestOrdinalEncoder:
    """OrdinalEncoder 测试"""

    def test_fit(self):
        """测试 fit"""
        X = np.array([['low', 'small'], ['medium', 'medium'], ['high', 'large']])
        
        encoder = OrdinalEncoder()
        encoder.fit(X)
        
        assert encoder.is_fitted() is True
        assert len(encoder.categories_) == 2

    def test_transform(self):
        """测试 transform"""
        X = np.array([['low', 'small'], ['medium', 'medium'], ['high', 'large']])
        
        encoder = OrdinalEncoder()
        encoder.fit(X)
        result = encoder.transform(X)
        
        # np.unique 会排序：['high', 'low', 'medium'] -> 0,1,2
        # ['large', 'medium', 'small'] -> 0,1,2
        # 'low'=1, 'medium'=2, 'high'=0
        # 'small'=2, 'medium'=1, 'large'=0
        expected = np.array([
            [1, 2],  # low, small
            [2, 1],  # medium, medium
            [0, 0],  # high, large
        ])
        np.testing.assert_array_equal(result, expected)

    def test_fit_transform(self):
        """测试 fit_transform"""
        X = np.array([['low', 'small'], ['medium', 'medium']])
        
        encoder = OrdinalEncoder()
        result = encoder.fit_transform(X)
        
        # np.unique 排序后: ['low', 'medium'], ['medium', 'small']
        # low=0, medium=1
        # medium=0, small=1
        expected = np.array([
            [0, 1],  # low, medium
            [1, 0],  # medium, medium
        ])
        np.testing.assert_array_equal(result, expected)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
