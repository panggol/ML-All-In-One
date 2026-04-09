# -*- coding: utf-8 -*-
"""
预处理管道 - Pipeline
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from mlkit.preprocessing.base import BaseTransformer, StageMode


class Pipeline:
    """
    预处理管道
    
    将多个预处理阶段串联起来，支持：
    - 自动依赖排序
    - 约束验证
    - 并行执行
    """

    def __init__(self, steps: Optional[List[Tuple[str, BaseTransformer]]] = None):
        """
        初始化管道
        
        Args:
            steps: [(name, transformer), ...] 阶段列表
        """
        self.steps: List[Tuple[str, BaseTransformer]] = steps or []
        self._stage_map: Dict[str, BaseTransformer] = {}
        
        # 构建映射
        for name, transformer in self.steps:
            self._stage_map[name] = transformer
        
        # 验证约束
        self._validate_constraints()

    def _validate_constraints(self):
        """验证约束"""
        # 检查依赖
        for name, transformer in self.steps:
            for dep in transformer.depends_on:
                if dep not in self._stage_map:
                    raise ValueError(
                        f"阶段 '{name}' 依赖 '{dep}'，但该阶段不存在"
                    )
            
            # 检查互斥
            for conflict in transformer.conflicts_with:
                if conflict in self._stage_map:
                    raise ValueError(
                        f"阶段 '{name}' 与 '{conflict}' 互斥，不能同时存在"
                    )

    def _sort_stages(self) -> List[Tuple[str, BaseTransformer]]:
        """基于依赖和顺序自动排序"""
        if not self.steps:
            return []
        
        # 拓扑排序
        sorted_stages = []
        remaining = self.steps.copy()
        added = set()
        
        while remaining:
            # 找所有依赖都满足的阶段
            for i, (name, transformer) in enumerate(remaining):
                deps_satisfied = all(dep in added for dep in transformer.depends_on)
                
                if deps_satisfied:
                    sorted_stages.append((name, transformer))
                    added.add(name)
                    remaining.pop(i)
                    break
            else:
                # 无法找到满足的阶段，可能有循环依赖
                remaining_names = [s[0] for s in remaining]
                raise ValueError(f"存在循环依赖: {remaining_names}")
        
        return sorted_stages

    def add_stage(self, name: str, transformer: BaseTransformer, force: bool = False):
        """添加阶段"""
        if name in self._stage_map and not force:
            raise ValueError(f"阶段 '{name}' 已存在")
        
        self.steps.append((name, transformer))
        self._stage_map[name] = transformer
        self._validate_constraints()

    def remove_stage(self, name: str):
        """删除阶段"""
        for i, (stage_name, _) in enumerate(self.steps):
            if stage_name == name:
                self.steps.pop(i)
                break
        
        self._stage_map.pop(name, None)

    def fit(self, X, y=None):
        """拟合并转换"""
        self._sorted_stages = self._sort_stages()
        
        for name, transformer in self._sorted_stages:
            X = transformer.fit_transform(X, y)
        
        return self

    def transform(self, X):
        """应用变换"""
        if not hasattr(self, '_sorted_stages'):
            self._sorted_stages = self._sort_stages()
        
        for name, transformer in self._sorted_stages:
            X = transformer.transform(X)
        
        return X

    def fit_transform(self, X, y=None):
        """拟合并转换"""
        return self.fit(X, y).transform(X)

    def get_stage(self, name: str) -> BaseTransformer:
        """获取指定阶段"""
        if name not in self._stage_map:
            raise KeyError(f"阶段 '{name}' 不存在")
        return self._stage_map[name]

    def get_config(self) -> dict:
        """获取配置"""
        return {
            'stages': [
                (name, t.get_params()) 
                for name, t in self.steps
            ]
        }

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        stage_names = [name for name, _ in self.steps]
        return f"Pipeline({' -> '.join(stage_names)})"
