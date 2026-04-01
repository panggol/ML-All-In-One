# -*- coding: utf-8 -*-
"""
新增功能测试 - DataLoader, LDA
"""

import sys
sys.path.insert(0, 'src')

import pytest
import numpy as np

# 检查 PyTorch 是否可用
try:
    import torch
    from mlkit.data.dataloader import (
        MapDataset,
        DataLoader,
        TensorDataset,
        create_dataloader,
        TORCH_AVAILABLE,
    )
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    pytest.skip("PyTorch not available", allow_module_level=True)

from mlkit.preprocessing.dimensionality import LinearDiscriminantAnalysis


class TestDataLoader:
    """DataLoader 测试"""

    def test_torch_available(self):
        """检查 PyTorch 是否可用"""
        assert TORCH_AVAILABLE is True

    def test_map_dataset(self):
        """测试 MapDataset"""
        X = np.random.randn(100, 4)
        y = np.random.randint(0, 2, 100)
        
        dataset = MapDataset(X, y)
        
        assert len(dataset) == 100
        
        x, label = dataset[0]
        assert x.shape == (4,)
        assert isinstance(label, torch.Tensor)

    def test_tensor_dataset(self):
        """测试 TensorDataset"""
        X = np.random.randn(100, 4)
        y = np.random.randint(0, 2, 100)
        
        dataset = TensorDataset(X, y)
        
        assert len(dataset) == 100
        
        x, label = dataset[0]
        assert x.shape == (4,)

    def test_dataloader_batch(self):
        """测试 DataLoader 批处理"""
        X = np.random.randn(100, 4)
        y = np.random.randint(0, 2, 100)
        
        loader = DataLoader(X, y, batch_size=32)
        
        # 获取一个批次
        batch_x, batch_y = next(iter(loader))
        
        assert batch_x.shape[0] == 32
        assert batch_y.shape[0] == 32

    def test_dataloader_iteration(self):
        """测试 DataLoader 迭代"""
        X = np.random.randn(100, 4)
        y = np.random.randint(0, 2, 100)
        
        loader = DataLoader(X, y, batch_size=32)
        
        total = 0
        for batch_x, batch_y in loader:
            total += len(batch_x)
        
        assert total == 100

    def test_dataloader_shuffle(self):
        """测试 DataLoader 打乱"""
        X = np.arange(100).reshape(-1, 1)
        y = np.arange(100)
        
        loader1 = DataLoader(X, y, batch_size=10, shuffle=True, seed=42)
        loader2 = DataLoader(X, y, batch_size=10, shuffle=True, seed=42)
        
        # 相同 seed 应该产生相同顺序
        result1 = [next(iter(loader1))[0][0].item() for _ in range(10)]
        result2 = [next(iter(loader2))[0][0].item() for _ in range(10)]
        
        assert result1 == result2

    def test_dataloader_num_workers(self):
        """测试多进程加载"""
        X = np.random.randn(100, 4)
        y = np.random.randint(0, 2, 100)
        
        loader = DataLoader(X, y, batch_size=32, num_workers=0)
        
        batch = next(iter(loader))
        assert batch[0].shape[0] == 32

    def test_create_dataloader(self):
        """测试便捷函数"""
        X = np.random.randn(100, 4)
        y = np.random.randint(0, 2, 100)
        
        loader = create_dataloader(X, y, batch_size=32)
        
        batch = next(iter(loader))
        assert batch[0].shape[0] == 32


class TestLDA:
    """LinearDiscriminantAnalysis 测试"""

    def test_fit(self):
        """测试 fit"""
        np.random.seed(42)
        X = np.random.randn(100, 4)
        y = np.array([0] * 50 + [1] * 50)
        
        lda = LinearDiscriminantAnalysis()
        lda.fit(X, y)
        
        assert lda.is_fitted() is True

    def test_n_components(self):
        """测试 n_components 参数"""
        np.random.seed(42)
        X = np.random.randn(100, 4)
        y = np.array([0] * 50 + [1] * 50)
        
        lda = LinearDiscriminantAnalysis(n_components=1)
        lda.fit(X, y)
        
        assert lda.n_components_ == 1

    def test_transform(self):
        """测试 transform"""
        np.random.seed(42)
        X = np.random.randn(100, 4)
        y = np.array([0] * 50 + [1] * 50)
        
        lda = LinearDiscriminantAnalysis()
        result = lda.fit_transform(X, y)
        
        # 最多可以降到 min(类别数-1, 特征数) = min(1, 4) = 1
        assert result.shape[1] == 1
        assert result.shape[0] == 100

    def test_predict(self):
        """测试预测"""
        np.random.seed(42)
        X = np.random.randn(100, 4)
        y = np.array([0] * 50 + [1] * 50)
        
        lda = LinearDiscriminantAnalysis()
        lda.fit(X, y)
        predictions = lda.predict(X)
        
        assert len(predictions) == 100
        assert set(predictions).issubset({0, 1})

    def test_predict_proba(self):
        """测试概率预测"""
        np.random.seed(42)
        X = np.random.randn(100, 4)
        y = np.array([0] * 50 + [1] * 50)
        
        lda = LinearDiscriminantAnalysis()
        lda.fit(X, y)
        proba = lda.predict_proba(X)
        
        assert proba.shape == (100, 2)
        # 概率和应该接近 1
        assert np.allclose(proba.sum(axis=1), 1, atol=0.1)

    def test_score(self):
        """测试 score"""
        np.random.seed(42)
        X = np.random.randn(100, 4)
        y = np.array([0] * 50 + [1] * 50)
        
        lda = LinearDiscriminantAnalysis()
        lda.fit(X, y)
        score = lda.score(X, y)
        
        # 对于随机数据，准确率应该在 0.4-0.6 之间
        assert 0.3 < score < 0.7

    def test_multiple_classes(self):
        """测试多类别"""
        np.random.seed(42)
        X = np.random.randn(150, 5)
        y = np.array([0] * 50 + [1] * 50 + [2] * 50)
        
        lda = LinearDiscriminantAnalysis()
        result = lda.fit_transform(X, y)
        
        # 最多可以降到 min(类别数-1, 特征数) = min(2, 5) = 2
        assert result.shape[1] == 2

    def test_solvers(self):
        """测试不同求解器"""
        np.random.seed(42)
        X = np.random.randn(100, 4)
        y = np.array([0] * 50 + [1] * 50)
        
        for solver in ['svd', 'eigen', 'lsqr']:
            lda = LinearDiscriminantAnalysis(solver=solver)
            result = lda.fit_transform(X, y)
            assert result.shape[1] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
