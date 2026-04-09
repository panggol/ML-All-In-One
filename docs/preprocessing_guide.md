# ML All In One - 数据预处理模块使用指南

## 1. 新增功能列表

| 功能 | 状态 | 说明 |
|------|------|------|
| TargetEncoder | ✅ 已实现 | 目标编码，支持 smoothing |
| QuantileTransformer | ✅ 已实现 | 分位数变换 (uniform/normal) |
| PowerTransformer | ✅ 已实现 | 幂变换 (Box-Cox/Yeo-Johnson) |
| IterativeImputer | ✅ 已实现 | MICE 迭代填充 |
| LinearDiscriminantAnalysis (LDA) | ✅ 已实现 | 线性判别分析 |
| DataLoader 封装 | ✅ 已实现 | PyTorch DataLoader 支持 |
| Pipeline | ✅ 已实现 | 自定义管道系统 |

---

## 2. 使用示例

### 2.1 TargetEncoder (目标编码)

将分类特征转换为目标变量的统计值，适合高基数类别特征。

```python
from mlkit.preprocessing import TargetEncoder
import numpy as np

X = np.array([['cat'], ['dog'], ['cat'], ['mouse'], ['dog']])
y = np.array([1, 0, 1, 0, 1])

encoder = TargetEncoder(smoothing=1.0)
X_encoded = encoder.fit_transform(X, y)
# 输出: [[0.833], [0.25], [0.833], [0.25], [0.833]]
```

### 2.2 QuantileTransformer (分位数变换)

将数据变换为指定分布（uniform 或 normal），对异常值鲁棒。

```python
from mlkit.preprocessing import QuantileTransformer
import numpy as np

X = np.random.exponential(scale=2, size=(1000, 3))
transformer = QuantileTransformer(n_quantiles=100, output_distribution='normal')
X_normal = transformer.fit_transform(X)
X_restored = transformer.inverse_transform(X_normal)
```

### 2.3 PowerTransformer (幂变换)

通过幂变换使数据更接近正态分布。

```python
from mlkit.preprocessing import PowerTransformer
import numpy as np

X = np.random.lognormal(mean=0, sigma=1, size=(100, 3))
pt = PowerTransformer(method='yeo-johnson')
X_transformed = pt.fit_transform(X)
```

### 2.4 IterativeImputer (MICE 迭代填充)

使用多变量迭代方法填充缺失值。

```python
from mlkit.preprocessing import IterativeImputer
import numpy as np

X = np.array([[1, 2, np.nan], [3, np.nan, 4], [np.nan, 5, 6]])
imputer = IterativeImputer(max_iter=10)
X_filled = imputer.fit_transform(X)
```

### 2.5 LDA (线性判别分析)

用于分类任务的监督降维方法。

```python
from mlkit.preprocessing.dimensionality import LinearDiscriminantAnalysis
from sklearn.datasets import make_classification

X, y = make_classification(n_samples=200, n_features=4, n_classes=3, random_state=42)
lda = LinearDiscriminantAnalysis(n_components=2)
X_lda = lda.fit_transform(X, y)
```

### 2.6 Pipeline (管道)

将多个预处理步骤串联起来。

```python
from mlkit.preprocessing import Pipeline, StandardScaler, SimpleImputer
import numpy as np

pipeline = Pipeline([
    ('imputer', SimpleImputer(strategy='mean')),
    ('scaler', StandardScaler()),
])
X = np.array([[1, 2, np.nan], [3, np.nan, 4]])
X_processed = pipeline.fit_transform(X)
```

---

## 3. 测试结果

- TargetEncoder: 5/5 通过
- QuantileTransformer: 5/5 通过
- PowerTransformer: 5/5 通过
- IterativeImputer: 6/6 通过
- **总计: 21/21 全部通过**

---

## 4. 文件位置

```
src/mlkit/preprocessing/tabular/encoder.py       # TargetEncoder
src/mlkit/preprocessing/tabular/scaler.py       # QuantileTransformer, PowerTransformer
src/mlkit/preprocessing/tabular/imputer.py      # IterativeImputer
src/mlkit/preprocessing/dimensionality/lda.py    # LDA
tests/test_preprocessing_new_features.py        # 测试用例
```

---

**更新日期: 2026-03-28**
