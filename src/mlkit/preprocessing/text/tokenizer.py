# -*- coding: utf-8 -*-
"""
文本分词器 - Tokenizer

支持：
- 空格分词
- 字符分词
- 自定义分词
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import re

from mlkit.preprocessing.base import BaseTransformer


class BaseTokenizer(BaseTransformer, ABC):
    """分词器基类"""
    
    order = 1
    
    def __init__(self):
        super().__init__()
        self.vocabulary_: Optional[dict] = None
    
    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        """分词方法"""
        pass
    
    def fit(self, texts, y=None):
        """构建词汇表"""
        self.vocabulary_ = {}
        for text in texts:
            tokens = self.tokenize(text)
            for token in tokens:
                if token not in self.vocabulary_:
                    self.vocabulary_[token] = len(self.vocabulary_)
        self._fitted = True
        return self
    
    def transform(self, texts):
        """转换为token索引"""
        if self.vocabulary_ is None:
            raise ValueError("Tokenizer not fitted")
        
        result = []
        for text in texts:
            tokens = self.tokenize(text)
            indices = [self.vocabulary_.get(t, -1) for t in tokens]
            result.append(indices)
        return result
    
    def fit_transform(self, texts, y=None):
        return self.fit(texts, y).transform(texts)


class WhitespaceTokenizer(BaseTokenizer):
    """空格分词器"""
    
    def tokenize(self, text: str) -> List[str]:
        return text.split()


class CharacterTokenizer(BaseTokenizer):
    """字符分词器"""
    
    def __init__(self, ngram_range: tuple = (1, 1)):
        super().__init__()
        self.ngram_range = ngram_range
    
    def tokenize(self, text: str) -> List[str]:
        text = text.replace(" ", "")  # 移除空格
        n_min, n_max = self.ngram_range
        tokens = []
        for n in range(n_min, n_max + 1):
            for i in range(len(text) - n + 1):
                tokens.append(text[i:i+n])
        return tokens


class RegexTokenizer(BaseTokenizer):
    """正则分词器"""
    
    def __init__(self, pattern: str = r'\w+'):
        super().__init__()
        self.pattern = re.compile(pattern)
    
    def tokenize(self, text: str) -> List[str]:
        return self.pattern.findall(text.lower())
