# -*- coding: utf-8 -*-
"""
PyTorch DataLoader 封装

支持：
- Map-style Dataset
- Iterable-style Dataset
- 分布式采样器
- 数据增强
"""

from typing import Any, Callable, Iterator, List, Optional, Sequence
import numpy as np

# 尝试导入 PyTorch
try:
    import torch
    from torch.utils.data import (
        DataLoader as TorchDataLoader,
        Dataset as TorchDataset,
        IterableDataset as TorchIterableDataset,
        Sampler,
    )
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    TorchDataset = object
    TorchIterableDataset = object
    Sampler = object


class BaseDataset:
    """
    数据集基类
    
    提供统一的接口用于 PyTorch DataLoader。
    """

    def __init__(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
    ):
        """
        Args:
            X: 特征数据，形状为 (n_samples, n_features)
            y: 标签数据，形状为 (n_samples,)
            transform: 特征变换函数
            target_transform: 标签变换函数
        """
        self.X = np.array(X)
        self.y = np.array(y) if y is not None else None
        self.transform = transform
        self.target_transform = target_transform

    def __len__(self) -> int:
        """返回样本数量"""
        return len(self.X)

    def __getitem__(self, idx: int) -> tuple:
        """获取单个样本"""
        X = self.X[idx]
        
        if self.transform is not None:
            X = self.transform(X)
        
        if self.y is not None:
            y = self.y[idx]
            if self.target_transform is not None:
                y = self.target_transform(y)
            return X, y
        
        return X


class MapDataset(BaseDataset):
    """
    Map-style 数据集
    
    支持通过索引访问样本，适用于大多数场景。
    
    Example:
        dataset = MapDataset(X_train, y_train)
        dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
        
        for batch_x, batch_y in dataloader:
            # 训练代码
            pass
    """

    def __init__(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
    ):
        """
        Args:
            X: 特征数据
            y: 标签数据
            transform: 特征变换
            target_transform: 标签变换
        """
        super().__init__(X, y, transform, target_transform)
        
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for MapDataset")

    def __getitem__(self, idx: int) -> tuple:
        """获取样本对 (X[idx], y[idx])"""
        X = torch.from_numpy(self.X[idx]).float()
        
        if self.transform is not None:
            X = self.transform(X)
        
        if self.y is not None:
            y = torch.tensor(self.y[idx])
            if self.target_transform is not None:
                y = self.target_transform(y)
            return X, y
        
        return X


class IterableMapDataset(BaseDataset):
    """
    Iterable-style 数据集
    
    支持流式数据处理，适用于大数据集。
    
    Example:
        def data_generator():
            for i in range(10000):
                yield X[i], y[i]
        
        dataset = IterableMapDataset(data_generator)
        dataloader = DataLoader(dataset, batch_size=32)
    """

    def __init__(
        self,
        data: Iterator | Sequence,
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
    ):
        """
        Args:
            data: 数据迭代器或序列
            transform: 特征变换
            target_transform: 标签变换
        """
        self.data = data
        self.transform = transform
        self.target_transform = target_transform
        
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for IterableMapDataset")

    def __iter__(self):
        """迭代返回样本"""
        for item in self.data:
            if isinstance(item, tuple) and len(item) == 2:
                X, y = item
                if self.transform is not None:
                    X = self.transform(X)
                if self.target_transform is not None:
                    y = self.target_transform(y)
                yield X, y
            else:
                X = item
                if self.transform is not None:
                    X = self.transform(X)
                yield X

    def __len__(self):
        """返回长度（如果可用）"""
        if hasattr(self.data, '__len__'):
            return len(self.data)
        raise TypeError("len() not available for IterableDataset")


class DataLoader:
    """
    PyTorch DataLoader 封装
    
    提供简化的接口来创建 PyTorch DataLoader。
    
    支持：
    - 批处理
    - 打乱
    - 多进程加载
    - 自定义采样器
    
    Example:
        # 基本用法
        loader = DataLoader(
            X=X_train,
            y=y_train,
            batch_size=32,
            shuffle=True,
            num_workers=4
        )
        
        for batch_x, batch_y in loader:
            # 训练
            pass
        
        # 使用分布式采样器
        loader = DataLoader(
            X=X_train,
            y=y_train,
            batch_size=32,
            distributed=True,
            rank=0,
            world_size=4
        )
    """

    def __init__(
        self,
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        dataset: Optional[TorchDataset] = None,
        batch_size: int = 32,
        shuffle: bool = False,
        num_workers: int = 0,
        pin_memory: bool = True,
        drop_last: bool = False,
        sampler: Optional[Sampler] = None,
        batch_sampler: Optional[Callable] = None,
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
        distributed: bool = False,
        rank: int = 0,
        world_size: int = 1,
        seed: Optional[int] = None,
    ):
        """
        Args:
            X: 特征数据（如果不提供 dataset）
            y: 标签数据
            dataset: PyTorch Dataset（可选）
            batch_size: 批大小
            shuffle: 是否打乱
            num_workers: 数据加载进程数
            pin_memory: 是否固定内存
            drop_last: 是否丢弃最后一个不完整批
            sampler: 自定义采样器
            batch_sampler: 自定义批采样器
            transform: 特征变换
            target_transform: 标签变换
            distributed: 是否使用分布式训练
            rank: 当前进程 rank
            world_size: 总进程数
            seed: 随机种子
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for DataLoader")
        
        import torch
        if seed is not None:
            torch.manual_seed(seed)
        
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.num_workers = num_workers
        self.pin_memory = pin_memory
        self.drop_last = drop_last
        
        # 创建或使用 dataset
        if dataset is not None:
            self.dataset = dataset
        elif X is not None:
            self.dataset = MapDataset(X, y, transform, target_transform)
        else:
            raise ValueError("Either X/y or dataset must be provided")
        
        # 设置采样器
        if distributed and sampler is None:
            self.sampler = self._create_distributed_sampler(rank, world_size, seed)
        else:
            self.sampler = sampler
        
        self.batch_sampler = batch_sampler
        
        # 创建随机数生成器并设置种子
        generator = None
        if seed is not None:
            torch.manual_seed(seed)
            generator = torch.Generator()
            generator.manual_seed(seed)
        
        # 创建 PyTorch DataLoader
        self._loader = TorchDataLoader(
            self.dataset,
            batch_size=batch_size,
            shuffle=shuffle if sampler is None else False,
            num_workers=num_workers,
            pin_memory=pin_memory,
            drop_last=drop_last,
            sampler=self.sampler,
            batch_sampler=batch_sampler,
            collate_fn=self._collate_fn,
            generator=generator,
        )

    def _create_distributed_sampler(
        self, rank: int, world_size: int, seed: Optional[int] = None
    ) -> Sampler:
        """创建分布式采样器"""
        from torch.utils.data.distributed import DistributedSampler
        
        sampler = DistributedSampler(
            self.dataset,
            num_replicas=world_size,
            rank=rank,
            shuffle=self.shuffle,
            seed=seed or 0,
        )
        return sampler

    def _collate_fn(self, batch):
        """自定义批处理整理函数"""
        if isinstance(batch[0], tuple):
            # (X, y) 对
            X_batch = torch.stack([item[0] for item in batch])
            y_batch = torch.stack([item[1] for item in batch])
            return X_batch, y_batch
        else:
            return torch.stack(batch)

    def __iter__(self):
        """迭代返回批次"""
        return iter(self._loader)

    def __len__(self) -> int:
        """返回批次数"""
        return len(self._loader)

    @property
    def sampler(self):
        """返回采样器"""
        return self._sampler

    @sampler.setter
    def sampler(self, value):
        self._sampler = value

    def set_epoch(self, epoch: int):
        """设置 epoch（用于分布式训练）"""
        if hasattr(self._sampler, 'set_epoch'):
            self._sampler.set_epoch(epoch)


class WeightedRandomSampler:
    """
    加权随机采样器
    
    根据样本权重进行有放回或无放回抽样。
    
    Example:
        # 处理类别不均衡
        class_counts = np.bincount(y_train)
        weights = 1.0 / class_counts[y_train]
        
        sampler = WeightedRandomSampler(weights, num_samples=len(weights))
        loader = DataLoader(X, y, sampler=sampler)
    """

    def __init__(
        self,
        weights: Sequence[float],
        num_samples: Optional[int] = None,
        replacement: bool = True,
        generator: Optional[torch.Generator] = None,
    ):
        """
        Args:
            weights: 每个样本的权重
            num_samples: 采样数量
            replacement: 是否为有放回抽样
            generator: 随机数生成器
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for WeightedRandomSampler")
        
        self.weights = torch.tensor(weights, dtype=torch.double)
        self.num_samples = num_samples or len(weights)
        self.replacement = replacement
        self.generator = generator

    def __iter__(self) -> Iterator[int]:
        """返回样本索引"""
        # 使用 torch 的 multinomial 进行加权抽样
        indices = torch.multinomial(
            self.weights,
            self.num_samples,
            replacement=self.replacement,
            generator=self.generator,
        )
        return iter(indices.tolist())

    def __len__(self) -> int:
        return self.num_samples


class TensorDataset:
    """
    NumPy/Pandas 数据转 PyTorch Dataset
    
    便捷工具类，用于快速创建 PyTorch Dataset。
    
    Example:
        # 从 NumPy 数组创建
        dataset = TensorDataset(X_train, y_train)
        
        # 从 pandas DataFrame 创建
        dataset = TensorDataset(df.values, labels)
    """

    def __init__(
        self,
        X,
        y: Optional[Any] = None,
        tensor_type: str = 'float32',
    ):
        """
        Args:
            X: 输入数据 (NumPy array, pandas DataFrame, etc.)
            y: 标签数据（可选）
            tensor_type: PyTorch tensor 类型
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for TensorDataset")
        
        dtype_map = {
            'float32': torch.float32,
            'float64': torch.float64,
            'int32': torch.int32,
            'int64': torch.int64,
        }
        
        self.X = torch.tensor(X, dtype=dtype_map.get(tensor_type, torch.float32))
        
        if y is not None:
            self.y = torch.tensor(y, dtype=dtype_map.get(tensor_type, torch.float32))
        else:
            self.y = None

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int) -> tuple:
        if self.y is not None:
            return self.X[idx], self.y[idx]
        return self.X[idx]


def create_dataloader(
    X: np.ndarray,
    y: Optional[np.ndarray] = None,
    batch_size: int = 32,
    shuffle: bool = False,
    num_workers: int = 0,
    transform: Optional[Callable] = None,
    target_transform: Optional[Callable] = None,
    **kwargs,
) -> DataLoader:
    """
    快速创建 DataLoader 的便捷函数
    
    Args:
        X: 特征数据
        y: 标签数据
        batch_size: 批大小
        shuffle: 是否打乱
        num_workers: 工作进程数
        transform: 特征变换
        target_transform: 标签变换
        **kwargs: 其他 DataLoader 参数
        
    Returns:
        DataLoader 实例
    """
    return DataLoader(
        X=X,
        y=y,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        transform=transform,
        target_transform=target_transform,
        **kwargs,
    )


# 导出
__all__ = [
    'MapDataset',
    'IterableMapDataset',
    'DataLoader',
    'WeightedRandomSampler',
    'TensorDataset',
    'create_dataloader',
    'TORCH_AVAILABLE',
]
