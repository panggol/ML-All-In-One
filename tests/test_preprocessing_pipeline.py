# -*- coding: utf-8 -*-
"""
Pipeline 测试
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np

from mlkit.preprocessing.base import BaseTransformer, StageMode
from mlkit.preprocessing.pipeline import Pipeline


class AddTransformer(BaseTransformer):
    """加法转换器"""
    
    def __init__(self, value=1):
        super().__init__()
        self.value = value
    
    def transform(self, X):
        return X + self.value
    
    def get_params(self):
        return {'value': self.value}


class MultiplyTransformer(BaseTransformer):
    """乘法转换器"""
    
    order = 1  # 优先级更高
    
    def __init__(self, factor=2):
        super().__init__()
        self.factor = factor
    
    def transform(self, X):
        return X * self.factor
    
    def get_params(self):
        return {'factor': self.factor}


class TestPipeline:
    """Pipeline 测试"""

    def test_create_empty_pipeline(self):
        """测试创建空管道"""
        pipeline = Pipeline()
        assert len(pipeline) == 0

    def test_create_pipeline_with_steps(self):
        """测试创建带阶段的管道"""
        steps = [
            ('add', AddTransformer(1)),
            ('multiply', MultiplyTransformer(2)),
        ]
        pipeline = Pipeline(steps)
        assert len(pipeline) == 2

    def test_add_stage(self):
        """测试添加阶段"""
        pipeline = Pipeline()
        pipeline.add_stage('add', AddTransformer(1))
        
        assert len(pipeline) == 1
        assert pipeline.get_stage('add') is not None

    def test_remove_stage(self):
        """测试删除阶段"""
        steps = [
            ('add', AddTransformer(1)),
            ('multiply', MultiplyTransformer(2)),
        ]
        pipeline = Pipeline(steps)
        pipeline.remove_stage('add')
        
        assert len(pipeline) == 1

    def test_fit_transform(self):
        """测试拟合并转换"""
        X = np.array([[1, 2], [3, 4]])
        
        pipeline = Pipeline([
            ('add', AddTransformer(1)),
            ('multiply', MultiplyTransformer(2)),
        ])
        
        result = pipeline.fit_transform(X)
        
        # (1 + 1) * 2 = 4
        # (2 + 1) * 2 = 6
        expected = np.array([[4, 6], [8, 10]])
        np.testing.assert_array_equal(result, expected)

    def test_transform(self):
        """测试转换"""
        X = np.array([[1, 2], [3, 4]])
        
        pipeline = Pipeline([
            ('add', AddTransformer(1)),
            ('multiply', MultiplyTransformer(2)),
        ])
        pipeline.fit(X)
        
        result = pipeline.transform(X)
        
        expected = np.array([[4, 6], [8, 10]])
        np.testing.assert_array_equal(result, expected)

    def test_get_stage(self):
        """测试获取阶段"""
        transformer = AddTransformer(1)
        pipeline = Pipeline([('add', transformer)])
        
        assert pipeline.get_stage('add') is transformer

    def test_get_stage_not_found(self):
        """测试获取不存在的阶段"""
        pipeline = Pipeline()
        
        with pytest.raises(KeyError):
            pipeline.get_stage('not_exist')

    def test_get_config(self):
        """测试获取配置"""
        pipeline = Pipeline([
            ('add', AddTransformer(1)),
            ('multiply', MultiplyTransformer(2)),
        ])
        
        config = pipeline.get_config()
        
        assert 'stages' in config
        assert len(config['stages']) == 2

    def test_repr(self):
        """测试 __repr__"""
        pipeline = Pipeline([
            ('add', AddTransformer(1)),
            ('multiply', MultiplyTransformer(2)),
        ])
        
        assert 'add' in repr(pipeline)
        assert 'multiply' in repr(pipeline)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
