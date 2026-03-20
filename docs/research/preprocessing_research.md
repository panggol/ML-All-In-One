# 数据预处理模块调研报告

## 1. 现有框架调研

### 1.1 sklearn.preprocessing (表格数据)

**核心类列表：**

| 类别 | 类名 | 功能 |
|------|------|------|
| 缩放 | StandardScaler | 标准化 (均值0,方差1) |
| | MinMaxScaler | 归一化 (0-1范围) |
| | MaxAbsScaler | 最大绝对值归一化 |
| | RobustScaler | 鲁棒缩放 (中位数/四分位) |
| 编码 | OneHotEncoder | 独热编码 |
| | OrdinalEncoder | 序数编码 |
| | LabelEncoder | 标签编码 |
| | TargetEncoder | 目标编码 |
| 离散化 | KBinsDiscretizer | 分箱 |
| | Binarizer | 二值化 |
| 多项式 | PolynomialFeatures | 多项式特征 |
| | SplineTransformer | B样条特征 |
| 变换 | PowerTransformer | 幂变换 (Box-Cox, Yeo-Johnson) |
| | QuantileTransformer | 分位数变换 |
| | FunctionTransformer | 自定义函数变换 |

**设计模式：**
- fit() / transform() / fit_transform() 分离
- TransformerMixin 提供 fit_transform()
- BaseEstimator 提供 get_params()/set_params()

### 1.2 sklearn.pipeline (管道)

**核心类：**

| 类名 | 功能 |
|------|------|
| Pipeline | 线性管道 (transform1 -> transform2 -> model) |
| FeatureUnion | 并行管道 (transform1 + transform2) |
| ColumnTransformer | 列选择变换 |
| TransformedTargetRegressor | 目标变量变换 |

**使用示例：**
```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('classifier', RandomForestClassifier())
])
```

### 1.3 torchvision.transforms (图像数据增强)

**常用变换：**

| 类别 | 变换名 | 功能 |
|------|--------|------|
| 调整大小 | Resize | 调整尺寸 |
| | CenterCrop | 中心裁剪 |
| | RandomCrop | 随机裁剪 |
| | RandomResizedCrop | 随机裁剪并resize |
| 几何变换 | RandomHorizontalFlip | 水平翻转 |
| | RandomVerticalFlip | 垂直翻转 |
| | RandomRotation | 随机旋转 |
| | RandomAffine | 随机仿射 |
| 颜色变换 | ColorJitter | 颜色抖动 |
| | RandomGrayscale | 随机灰度 |
| | RandomInvert | 随机反色 |
| 图像增强 | RandomAutocontrast | 自动对比度 |
| | RandomEqualize | 直方图均衡化 |
| 转换为Tensor | ToTensor | 转为Tensor |
| | Normalize | 归一化 |

**设计模式：**
- Compose 组合多个变换
- Lambda 支持自定义变换
- 随机变换使用 Random* 前缀

### 1.4 文本预处理

**常用工具：**

| 库 | 功能 |
|----|------|
| nltk | 分词、词干、词性标注 |
| spacy | 工业级NLP |
| jieba | 中文分词 |
| transformers | BERT等预训练模型 |

**标准流程：**
```
文本 -> 分词 -> 去停用词 -> 词干/词形还原 -> 向量化 -> 特征
```

**向量化方法：**
- Bag of Words (CountVectorizer)
- TF-IDF (TfidfVectorizer)
- 词嵌入 (Word2Vec, GloVe)
- 上下文嵌入 (BERT, RoBERTa)

### 1.5 音频预处理

**常用特征：**

| 特征 | 说明 | 库 |
|------|------|-----|
| MFCC | 梅尔频率倒谱系数 | librosa |
| Mel Spectrogram | 梅尔频谱 | librosa |
| Chroma | 色度特征 | librosa |
| Spectral Contrast | 频谱对比度 | librosa |
| Zero Crossing Rate | 过零率 | librosa |

**常用操作：**
- 重采样 (librosa.resample)
- 预加重 (librosa.effects.preemphasis)
- 分帧 (librosa.frame)
- 窗函数 (librosa.stft)

### 1.6 视频预处理

**常用操作：**

| 操作 | 说明 |
|------|------|
| 帧提取 | cv2.VideoCapture, decord |
| 光流 | cv2.calcOpticalFlow |
| 关键帧提取 | 基于场景切换检测 |
| 时序采样 | 均匀采样, 随机采样 |

---

## 2. 可视化设计

### 2.1 数据分布可视化

```python
# 特征分布
可视化.plot_distribution(data, feature_names)

# 箱线图
可视化.plot_boxplot(data, feature_names)

# 相关性热力图
可视化.plot_correlation(data)

# PCA 降维可视化
可视化.plot_pca_2d(data, labels)
```

### 2.2 预处理过程可视化

```python
# 管道可视化
pipeline.plot()  # 显示管道结构
pipeline.visualize()  # 图形化展示

# 预处理效果对比
可视化.plot_before_after(original, transformed)

# 图像增强可视化
可视化.plot_augmentations(image, transforms, n_samples=8)
```

### 2.3 特征重要性可视化

```python
# 特征重要性
可视化.plot_feature_importance(model, feature_names)

# 降维可视化 (t-SNE, UMAP)
可视化.plot_embedding_2d(embeddings, labels)
```

---

## 3. 多模态预处理设计

### 3.1 联合管道设计

```python
from mlkit.preprocessing import Pipeline, MultimodalPipeline

# 单模态管道
text_pipeline = Pipeline([
    ('tokenize', Tokenizer()),
    ('vectorize', TfidfVectorizer())
])

image_pipeline = Pipeline([
    ('resize', Resize(224)),
    ('normalize', ImageNormalize())
])

# 多模态联合
multi_pipeline = MultimodalPipeline(
    pipelines={
        'text': text_pipeline,
        'image': image_pipeline,
        'tabular': StandardScaler()
    },
    fusion='concatenate'  # concat/attention/late_fusion
)
```

### 3.2 数据对齐

```python
# 不同模态数据对齐
aligner = TemporalAligner(
    modalities=['audio', 'video'],
    method='linear'  # linear/interpolation
)
aligned_data = aligner.fit_transform(multimodal_data)
```

---

## 4. 模块结构设计

```
src/mlkit/preprocessing/
├── __init__.py
│
├── base/                      # 基础抽象
│   ├── __init__.py
│   ├── base.py               # BaseTransformer 抽象类
│   ├── mixins.py            # TransformerMixin, FitMixin
│   └── config.py             # 预处理配置
│
├── tabular/                  # 表格数据
│   ├── __init__.py
│   ├── scaler.py            # StandardScaler, MinMaxScaler, RobustScaler
│   ├── encoder.py           # OneHotEncoder, OrdinalEncoder, TargetEncoder
│   ├── discretizer.py       # KBinsDiscretizer, Binarizer
│   ├── transformer.py       # PowerTransformer, QuantileTransformer
│   ├── imputer.py           # 缺失值填充
│   └── feature_selector.py  # 特征选择
│
├── text/                     # 文本数据
│   ├── __init__.py
│   ├── cleaner.py           # 文本清洗
│   ├── tokenizer.py         # 分词器
│   ├── normalizer.py        # 文本规范化
│   ├── stemmer.py           # 词干提取
│   ├── vectorizer.py        # TF-IDF, CountVectorizer
│   └── embedding.py         # 词嵌入
│
├── image/                    # 图像数据
│   ├── __init__.py
│   ├── transforms.py        # 基本变换
│   ├── augmentor.py         # 数据增强
│   ├── normalizer.py        # 图像归一化
│   └── extractor.py          # 特征提取
│
├── audio/                    # 音频数据
│   ├── __init__.py
│   ├── transforms.py        # 基本变换
│   ├── extractor.py         # 特征提取 (MFCC, Mel)
│   ├── segmenter.py        # 音频分割
│   └── augmentor.py         # 音频增强
│
├── video/                    # 视频数据
│   ├── __init__.py
│   ├── extractor.py        # 关键帧提取
│   ├── sampler.py          # 时序采样
│   └── optical_flow.py     # 光流计算
│
├── multimodal/              # 多模态
│   ├── __init__.py
│   ├── aligner.py         # 时空对齐
│   ├── fusion.py          # 特征融合
│   └── pipeline.py         # 多模态管道
│
├── pipeline/                # 管道系统
│   ├── __init__.py
│   ├── pipeline.py         # Pipeline
│   ├── feature_union.py    # FeatureUnion
│   └── composer.py         # 管道构建器
│
└── visualization/          # 可视化
    ├── __init__.py
    ├── distribution.py    # 分布可视化
    ├── pipeline.py        # 管道可视化
    ├── augmentation.py   # 增强效果可视化
    └── embedding.py       # 降维可视化
```

---

## 5. 核心接口设计

### 5.1 BaseTransformer

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
import numpy as np

class BaseTransformer(ABC):
    """所有预处理器基类"""
    
    def fit(self, X, y=None):
        """学习变换参数"""
        return self
    
    @abstractmethod
    def transform(self, X):
        """应用变换"""
        pass
    
    def fit_transform(self, X, y=None):
        """拟合并转换"""
        return self.fit(X, y).transform(X)
    
    def inverse_transform(self, X):
        """逆变换"""
        raise NotImplementedError
    
    def get_params(self) -> dict:
        """获取参数"""
        return {}
    
    def set_params(self, **params):
        """设置参数"""
        return self
    
    def plot(self):
        """可视化"""
        raise NotImplementedError
```

### 5.2 可视化接口

```python
class VisualizableMixin:
    """可视化Mixin"""
    
    def plot_distribution(self, X, feature_names=None):
        """绘制特征分布"""
        pass
    
    def plot_before_after(self, X_original, X_transformed):
        """变换前后对比"""
        pass
    
    def plot_augmentations(self, X, n_samples=8):
        """展示数据增强效果"""
        pass
```

### 5.3 Pipeline

```python
class Pipeline:
    """预处理管道"""
    
    def __init__(self, steps):
        """
        Args:
            steps: list of (name, transformer) tuples
        """
        self.steps = steps
        self._validate_steps()
    
    def fit(self, X, y=None):
        for name, transformer in self.steps:
            X = transformer.fit_transform(X, y)
        return self
    
    def transform(self, X):
        for name, transformer in self.steps:
            X = transformer.transform(X)
        return X
    
    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)
    
    def plot(self):
        """可视化管道结构"""
        pass
    
    def get_config(self) -> dict:
        """获取完整配置"""
        return {
            'steps': [(name, t.get_params()) for name, t in self.steps]
        }
```

---

## 6. 使用示例

### 6.1 表格数据预处理

```python
from mlkit.preprocessing import (
    Pipeline, StandardScaler, OneHotEncoder,
    KBestSelector, PCA
)

# 构建管道
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('pca', PCA(n_components=10)),
    ('selector', KBestSelector(k=5)),
])

# 训练和转换
X_train_processed = pipeline.fit_transform(X_train)
X_test_processed = pipeline.transform(X_test)

# 可视化
pipeline.plot()
```

### 6.2 图像数据增强

```python
from mlkit.preprocessing.image import (
    Compose, RandomHorizontalFlip, 
    RandomRotation, ColorJitter, Normalize
)

transforms = Compose([
    RandomHorizontalFlip(p=0.5),
    RandomRotation(degrees=15),
    ColorJitter(brightness=0.2, contrast=0.2),
    Normalize(mean=[0.485, 0.456, 0.406], 
              std=[0.229, 0.224, 0.225])
])

# 可视化增强效果
transforms.plot_augmentations(image, n_samples=8)
```

### 6.3 多模态预处理

```python
from mlkit.preprocessing import MultimodalPipeline
from mlkit.preprocessing.text import Tokenizer, TfidfVectorizer
from mlkit.preprocessing.image import Resize, Normalize
from mlkit.preprocessing.tabular import StandardScaler

pipeline = MultimodalPipeline(
    pipelines={
        'text': Pipeline([
            ('tokenize', Tokenizer()),
            ('vectorize', TfidfVectorizer())
        ]),
        'image': Pipeline([
            ('resize', Resize(224)),
            ('normalize', Normalize())
        ]),
        'tabular': StandardScaler()
    },
    fusion='concatenate'
)

# 输入: {'text': [...], 'image': [...], 'tabular': [...]}
features = pipeline.fit_transform(data_dict)
```

---

## 7. 总结

### 设计原则

1. **一致性**: 所有预处理器遵循 fit/transform 模式
2. **可组合性**: 通过 Pipeline 灵活组合
3. **可可视化**: 每个预处理器支持可视化
4. **可配置**: 支持配置化管理
5. **可扩展**: 容易添加新的预处理器

### 优先级

| 优先级 | 模块 | 说明 |
|--------|------|------|
| P0 | tabular 基础 | Scaler, Encoder, Imputer |
| P0 | Pipeline | 管道系统 |
| P0 | 可视化基础 | 分布、对比可视化 |
| P1 | 图像增强 | torchvision 风格 |
| P1 | 文本处理 | 分词、向量化 |
| P2 | 音频处理 | MFCC 等特征 |
| P2 | 视频处理 | 帧提取、光流 |
| P3 | 多模态 | 特征融合、对齐 |

---

*调研完成时间: 2026-03-21*
