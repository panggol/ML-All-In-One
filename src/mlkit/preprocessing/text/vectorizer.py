# -*- coding: utf-8 -*-
"""
文本向量化器 - Vectorizer

支持：
- 词袋模型 (CountVectorizer)
- TF-IDF (TFIDFVectorizer)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import numpy as np
from collections import Counter
import math

from mlkit.preprocessing.base import BaseTransformer


class BaseVectorizer(BaseTransformer, ABC):
    """向量化器基类"""
    
    order = 2
    
    def __init__(self):
        super().__init__()
        self.vocabulary_: Optional[Dict] = None


class CountVectorizer(BaseVectorizer):
    """
    词频向量化器
    
    将文本转换为词频向量
    """
    
    def __init__(self, max_features: Optional[int] = None):
        super().__init__()
        self.max_features = max_features
    
    def fit(self, texts, y=None):
        """构建词汇表（按词频排序）"""
        word_counts = Counter()
        for text in texts:
            if isinstance(text, str):
                words = text.split()
            else:
                words = text
            word_counts.update(words)
        
        # 按词频排序，取前 max_features
        if self.max_features:
            vocab_words = [w for w, _ in word_counts.most_common(self.max_features)]
        else:
            vocab_words = list(word_counts.keys())
        
        self.vocabulary_ = {w: i for i, w in enumerate(vocab_words)}
        self._fitted = True
        return self
    
    def transform(self, texts):
        """转换为词频向量"""
        if self.vocabulary_ is None:
            raise ValueError("Vectorizer not fitted")
        
        n_vocab = len(self.vocabulary_)
        result = np.zeros((len(texts), n_vocab))
        
        for i, text in enumerate(texts):
            if isinstance(text, str):
                words = text.split()
            else:
                words = text
            
            for word in words:
                if word in self.vocabulary_:
                    result[i, self.vocabulary_[word]] += 1
        
        return result
    
    def fit_transform(self, texts, y=None):
        return self.fit(texts, y).transform(texts)


class TFIDFVectorizer(BaseVectorizer):
    """
    TF-IDF 向量化器
    
    Term Frequency - Inverse Document Frequency
    """
    
    def __init__(self, max_features: Optional[int] = None):
        super().__init__()
        self.max_features = max_features
        self.idf_: Optional[np.ndarray] = None
    
    def fit(self, texts, y=None):
        """计算 IDF"""
        # 构建词汇表
        count_vec = CountVectorizer(max_features=self.max_features)
        count_vec.fit(texts)
        self.vocabulary_ = count_vec.vocabulary_
        
        # 计算 IDF
        n_docs = len(texts)
        doc_freq = np.zeros(len(self.vocabulary_))
        
        for text in texts:
            if isinstance(text, str):
                words = set(text.split())
            else:
                words = set(text)
            
            for word in words:
                if word in self.vocabulary_:
                    doc_freq[self.vocabulary_[word]] += 1
        
        # IDF = log(n / (1 + df)) + 1
        self.idf_ = np.log(n_docs / (1 + doc_freq)) + 1
        
        self._fitted = True
        return self
    
    def transform(self, texts):
        """转换为 TF-IDF 向量"""
        if self.vocabulary_ is None or self.idf_ is None:
            raise ValueError("Vectorizer not fitted")
        
        # 先获取词频
        count_vec = CountVectorizer()
        count_vec.vocabulary_ = self.vocabulary_
        tf = count_vec.transform(texts)
        
        # TF-IDF = TF * IDF
        return tf * self.idf_
    
    def fit_transform(self, texts, y=None):
        return self.fit(texts, y).transform(texts)
