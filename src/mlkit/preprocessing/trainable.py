# -*- coding: utf-8 -*-
"""
可训练预处理模块 - Trainable Preprocessing

支持：
- 确定性预处理 (不需要训练)
- 可训练预处理 (需要和主模型一起训练)
- Pipeline 混合模式
"""

from typing import Optional, List, Dict, Any, Callable
from abc import abstractmethod
import numpy as np

from mlkit.preprocessing.base import BaseTransformer


class TrainablePreprocessor(BaseTransformer):
    """
    可训练预处理器基类
    
    与普通预处理器不同，这类预处理器：
    1. 有可训练的参数
    2. 需要参与梯度反向传播
    3. 可能需要和主模型一起训练
    
    Example:
        - 词嵌入 (Word Embedding)
        - 可学习特征提取
        - 参数化数据增强
    """
    
    order = 0  # 默认最高优先级（最先执行）
    
    def __init__(self):
        super().__init__()
        self._is_fitted = False
        self._requires_training = True  # 是否需要训练
    
    @abstractmethod
    def forward(self, X):
        """
        前向传播（支持梯度）
        
        Args:
            X: 输入数据
            
        Returns:
            处理后的数据（支持梯度）
        """
        pass
    
    def fit(self, X, y=None):
        """
        训练预处理模型
        
        对于可训练预处理，通常不直接调用 fit，
        而是通过主模型的梯度反向传播来训练
        """
        self._is_fitted = True
        return self
    
    def transform(self, X):
        """转换（调用 forward）"""
        return self.forward(X)
    
    @property
    def requires_training(self) -> bool:
        """是否需要训练"""
        return self._requires_training
    
    @property
    def is_trainable(self) -> bool:
        """是否可训练"""
        return True


class EmbeddingPreprocessor(TrainablePreprocessor):
    """
    可训练的嵌入预处理器
    
    将离散特征转换为可训练的嵌入向量
    可以和主模型一起训练
    
    Example:
        categories = ['cat', 'dog', 'bird']
        embeddings = EmbeddingPreprocessor(num_embeddings=3, embedding_dim=8)
        # 训练时通过梯度反向传播更新嵌入
    """
    
    def __init__(self, num_embeddings: int, embedding_dim: int):
        """
        Args:
            num_embeddings: 嵌入数量（类别数）
            embedding_dim: 嵌入维度
        """
        super().__init__()
        self.num_embeddings = num_embeddings
        self.embedding_dim = embedding_dim
        # 实际实现需要 PyTorch 等框架
        self._embeddings = None
    
    def forward(self, X):
        """前向传播（支持梯度）"""
        # 返回嵌入向量
        # 实际实现中使用 torch.nn.Embedding
        pass
    
    def fit(self, X, y=None):
        """初始化嵌入表"""
        # 可以用预训练嵌入初始化
        self._is_fitted = True
        return self


class LearnedTokenizer(TrainablePreprocessor):
    """
    可学习的分词器
    
    不同于传统分词器，这是可训练的子词嵌入
    可以和主模型一起学习最优的分词策略
    
    Example:
        tokenizer = LearnedTokenizer(vocab_size=10000, char_dim=32)
        # 通过 BPE 或学习式分词实现
    """
    
    def __init__(self, vocab_size: int, char_dim: int = 32):
        super().__init__()
        self.vocab_size = vocab_size
        self.char_dim = char_dim
    
    def forward(self, X):
        """返回词索引或嵌入"""
        pass


class ParameterizedAugmentation(TrainablePreprocessor):
    """
    参数化数据增强
    
    数据增强可以是可学习的，比如：
    - 可学习的颜色变换
    - 可学习的几何变换
    - AutoAugment 风格策略
    
    Example:
        aug = ParameterizedAugmentation(
            rotation_range=15,
            brightness_range=0.2,
            learnable=True  # 可学习参数
        )
    """
    
    def __init__(self, learnable: bool = True, **kwargs):
        super().__init__()
        self.learnable = learnable
        self.augmentation_params = kwargs
        self._requires_training = learnable
    
    def forward(self, X):
        """应用增强"""
        pass


class FeatureLearner(TrainablePreprocessor):
    """
    可学习的特征提取器
    
    从原始数据学习特征表示，比如：
    - PCA（经典）/ AutoEncoder（深度学习版本）
    - 特征交叉学习
    - 领域自适应特征
    
    Example:
        feature_extractor = FeatureLearner(
            input_dim=100,
            hidden_dims=[64, 32],
            output_dim=16
        )
        # 输出可学习的低维特征
    """
    
    def __init__(self, input_dim: int, output_dim: int, hidden_dims: List[int] = None):
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dims = hidden_dims or [64, 32]
    
    def forward(self, X):
        """返回学习到的特征"""
        pass


class HybridPipeline:
    """
    混合管道 - 支持可训练和确定性预处理
    
    特点：
    1. 区分 fit 模式和 train 模式
    2. 确定性预处理只 fit 一次
    3. 可训练预处理在主模型训练时一起训练
    
    Example:
        pipeline = HybridPipeline([
            ('tokenizer', LearnedTokenizer(vocab_size=5000)),
            ('embedding', EmbeddingPreprocessor(5000, 64)),
            ('encoder', LSTMEncoder(64, 128)),
            ('classifier', LinearClassifier(128, 10)),
        ])
        
        # 训练模式 1：分步训练
        pipeline.fit_preprocessors(X_train, y_train)  # 确定性预处理
        pipeline.train_preprocessors(X_train, y_train)  # 可训练预处理 + 主模型
        
        # 训练模式 2：端到端训练（推荐）
        model = pipeline.to_model()
        model.fit(X_train, y_train)  # 一起训练
    """
    
    def __init__(self, stages: List[tuple]):
        """
        Args:
            stages: [(name, transformer), ...]
        """
        self.stages = stages
        self._preprocessors = []  # 确定性预处理
        self._trainables = []     # 可训练预处理
        self._classifier = None   # 主模型
        
        self._classify_stages()
    
    def _classify_stages(self):
        """分类各阶段"""
        for name, stage in self.stages:
            if isinstance(stage, TrainablePreprocessor):
                self._trainables.append((name, stage))
            else:
                self._preprocessors.append((name, stage))
    
    def fit(self, X, y=None):
        """
        拟合确定性预处理
        
        只对确定性预处理调用 fit_transform，
        可训练预处理保持原样
        """
        for name, stage in self._preprocessors:
            if hasattr(stage, 'fit_transform'):
                X = stage.fit_transform(X, y)
            elif hasattr(stage, 'fit'):
                stage.fit(X, y)
        return self
    
    def transform(self, X):
        """转换数据"""
        for name, stage in self.stages:
            if hasattr(stage, 'transform'):
                X = stage.transform(X)
        return X
    
    def fit_transform(self, X, y=None):
        """一次性拟合和转换（确定性）"""
        return self.fit(X, y).transform(X)
    
    def to_model(self):
        """
        转换为可训练的 PyTorch 模型
        
        返回一个 nn.Module，可以端到端训练
        """
        # 构建可训练的 pipeline 模型
        # 将各阶段组合为 nn.Sequential
        pass
    
    def get_trainable_params(self):
        """获取可训练参数"""
        params = []
        for name, stage in self._trainables:
            if hasattr(stage, 'parameters'):
                params.extend(stage.parameters())
        return params
    
    def freeze_preprocessors(self):
        """冻结确定性预处理（训练时使用）"""
        for name, stage in self._preprocessors:
            if hasattr(stage, 'eval'):
                stage.eval()
            # 冻结参数（如有）
    
    def unfreeze_preprocessors(self):
        """解冻预处理（微调时使用）"""
        for name, stage in self._prepreprocessors:
            if hasattr(stage, 'train'):
                stage.train()


# 工厂函数：创建端到端预处理管道
def create_end_to_end_pipeline(
    preprocessors: List[BaseTransformer],
    model: Any,
    trainable: bool = True
) -> HybridPipeline:
    """
    创建端到端管道
    
    Args:
        preprocessors: 预处理列表
        model: 主模型
        trainable: 是否可训练
        
    Returns:
        HybridPipeline
    """
    stages = []
    for p in preprocessors:
        stages.append((p.__class__.__name__.lower(), p))
    stages.append(('model', model))
    return HybridPipeline(stages)
