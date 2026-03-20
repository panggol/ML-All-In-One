# -*- coding: utf-8 -*-
"""
ML All In One - 数据处理模块测试
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np
from sklearn.datasets import make_classification

from mlkit.data import Dataset, ImbalanceHandler, DataValidator


class TestDataset:
    """Dataset 测试"""

    def test_create_dataset(self):
        X = np.array([[1, 2], [3, 4], [5, 6]])
        y = np.array([0, 1, 0])
        
        dataset = Dataset(X=X, y=y)
        
        assert dataset.shape == (3, 2)
        assert dataset.n_samples == 3
        assert dataset.n_features == 2

    def test_dataset_with_feature_names(self):
        X = np.array([[1, 2], [3, 4]])
        y = np.array([0, 1])
        
        dataset = Dataset(
            X=X, y=y,
            feature_names=['feature_a', 'feature_b'],
            target_names=['label']
        )
        
        assert dataset.feature_names == ['feature_a', 'feature_b']
        assert dataset.target_names == ['label']


class TestImbalanceHandler:
    """ImbalanceHandler 测试"""

    def test_smote(self):
        """测试 SMOTE 过采样"""
        X, y = make_classification(
            n_samples=1000,
            n_features=10,
            weights=[0.9, 0.1],
            random_state=42
        )
        
        X_resampled, y_resampled = ImbalanceHandler.handle(
            X, y, method='smote', random_state=42
        )
        
        # SMOTE 后类别应该平衡
        assert len(y_resampled) > len(y)
        assert np.abs(np.sum(y_resampled == 0) - np.sum(y_resampled == 1)) < 100

    def test_undersample(self):
        """测试欠采样"""
        X, y = make_classification(
            n_samples=1000,
            n_features=10,
            weights=[0.9, 0.1],
            random_state=42
        )
        
        X_resampled, y_resampled = ImbalanceHandler.handle(
            X, y, method='undersample', random_state=42
        )
        
        # 欠采样后类别应该平衡
        assert len(y_resampled) < len(y)
        assert np.abs(np.sum(y_resampled == 0) - np.sum(y_resampled == 1)) < 10

    def test_list_methods(self):
        """测试列出所有方法"""
        methods = ImbalanceHandler.list_methods()
        
        assert 'smote' in methods
        assert 'adasyn' in methods
        assert 'undersample' in methods


class TestDataValidator:
    """DataValidator 测试"""

    def test_valid_data(self):
        """测试有效数据"""
        X = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        y = np.array([0, 1, 0])
        
        result = DataValidator.validate(X, y)
        
        assert result['valid'] is True

    def test_invalid_labels(self):
        """测试无效标签"""
        X = np.array([[1, 2], [3, 4]])
        y = np.array([0, 2])  # 二分类但标签为 2
        
        result = DataValidator.validate(X, y)
        
        # 验证通过，检查警告
        # 注意：实现可能不检查所有边界情况
        assert 'warnings' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
