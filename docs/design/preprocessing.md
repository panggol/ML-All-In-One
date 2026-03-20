# ML All In One - 预处理模块设计文档

## 1. 需求背景

ML 平台需要支持多模态数据预处理，当前 `data` 模块仅有基础功能，需要扩展完整的预处理能力。

## 2. 设计目标

- 支持表格、文本、图像、音频、视频等多种数据类型
- 支持多阶段预处理管道
- 支持 Hook 机制动态添加/删除阶段
- 支持约束管理（依赖、互斥、顺序）
- 支持预处理过程可视化

## 3. 模块结构

```
src/mlkit/preprocessing/
├── base/                   # 基础抽象
│   ├── base.py            # BaseTransformer 基类
│   └── mixins.py          # TransformerMixin
├── tabular/               # 表格数据
│   ├── scaler.py         # StandardScaler, MinMaxScaler, RobustScaler
│   ├── encoder.py         # OneHotEncoder, OrdinalEncoder
│   ├── imputer.py        # 缺失值填充
│   └── reducer.py        # PCA, Autoencoder
├── text/                  # 文本数据
│   ├── tokenizer.py       # 分词器
│   └── vectorizer.py     # TF-IDF
├── image/                 # 图像数据
│   ├── transforms.py      # 基本变换
│   └── augmentor.py       # 数据增强
├── audio/                 # 音频数据
│   └── extractor.py      # MFCC
├── pipeline/              # 管道系统
│   └── pipeline.py       # Pipeline + Hook
└── visualization/         # 可视化
    └── visualize.py       # 分布图、效果对比
```

## 4. 核心接口

### 4.1 BaseTransformer

```python
class BaseTransformer(ABC):
    depends_on: List[str] = []    # 依赖阶段
    conflicts_with: List[str] = [] # 互斥阶段
    mode: StageMode = SERIAL      # 串行/并行
    order: int = 0               # 执行顺序
    
    def fit(self, X, y=None):
        return self
    
    @abstractmethod
    def transform(self, X):
        pass
    
    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)
```

### 4.2 ProcessingPipeline

```python
class ProcessingPipeline:
    def add_stage(self, stage: ProcessingStage):
        """添加阶段，自动处理依赖和顺序"""
        
    def remove_stage(self, name: str):
        """删除阶段"""
        
    def transform(self, X):
        """执行管道"""
```

## 5. 约束规则

| 阶段 | 依赖 | 顺序 |
|------|------|------|
| Imputer | - | 0 |
| Encoder | Imputer | 1 |
| Scaler | Encoder, Imputer | 2 |
| DimReducer | Scaler | 3 |

## 6. 实现计划

| 阶段 | 任务 | 优先级 |
|------|------|--------|
| 1 | 基础架构 (base + pipeline) | P0 |
| 2 | 表格预处理 (scaler, encoder, imputer) | P0 |
| 3 | 可视化基础 | P1 |
| 4 | 文本预处理 | P2 |
| 5 | 图像预处理 | P2 |
| 6 | 音频/视频预处理 | P3 |

## 7. 待定问题

- [ ] 并行实现方式 (多进程/多线程)
- [ ] 配置格式 (YAML/JSON)
- [ ] 持久化方案

---

*创建时间: 2026-03-21*
*最后更新: 2026-03-21*
