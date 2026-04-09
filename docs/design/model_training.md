# ML All In One - 模型训练模块设计文档

## 1. 需求背景

ML 平台需要支持多框架模型训练，包括传统机器学习（sklearn、XGBoost、LightGBM）和深度学习（PyTorch），提供统一的训练接口、实验追踪、超参数搜索和模型管理能力。

## 2. 设计目标

- **多框架支持**: 统一 sklearn、PyTorch、XGBoost、LightGBM 的训练接口
- **实验追踪**: 记录训练指标、参数、配置，支持对比分析
- **超参数搜索**: 支持网格搜索、随机搜索、贝叶斯优化
- **模型管理**: 模型版本控制、保存加载、模型注册表
- **实时监控**: WebSocket 实时日志、训练进度可视化
- **扩展性**: 支持自定义模型、损失函数、优化器

## 3. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ML All In One - 模型训练模块                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│     数据输入层       │  │     配置管理层       │  │     日志/监控层     │
│                     │  │                     │  │                     │
│  • NumPy Array      │  │  • TrainConfig      │  │  • WebSocket       │
│  • PyTorch Tensor   │  │  • ModelConfig     │  │  • TensorBoard    │
│  • Pandas DataFrame │  │  • HPO Config      │  │  • 实时日志        │
│  • 分批加载          │  │  • Experiment      │  │  • 训练进度        │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              核心模型层                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         BaseModel (抽象基类)                         │   │
│  │  • fit()  • predict()  • save()  • load()  • predict_proba()      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                    │                    │                    │              │
│    ┌───────────────┴───────┐   ┌───────┴───────┐   ┌───────┴───────────┐ │
│    ▼                       ▼   ▼               ▼   ▼                   ▼   │
│ ┌────────┐            ┌──────────┐       ┌──────────┐           ┌────────┐ │
│ │sklearn │            │ XGBoost  │       │ LightGBM │           │ PyTorch│ │
│ │        │            │          │       │          │           │        │ │
│ │• RF   │            │• 分类    │       │• 分类    │           │• NN    │ │
│ │• LR   │            │• 回归    │       │• 回归    │           │• CNN   │ │
│ │• SVC  │            │          │       │          │           │• RNN   │ │
│ └────────┘            └──────────┘       └──────────┘           └────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│     训练器层         │  │    实验追踪层        │  │   超参数搜索层      │
│                     │  │                     │  │                     │
│  • sklearn_runner   │  │  • 参数记录          │  │  • GridSearch      │
│  • pytorch_runner  │  │  • 指标记录          │  │  • RandomSearch    │
│  • Callback 系统   │  │  • 产物保存          │  │  • Bayesian        │
│  • EarlyStopping  │  │  • 实验对比          │  │                     │
│  • ModelCheckpoint│  │                     │  │                     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              输出层                                           │
│                                                                             │
│  • 模型文件 (.joblib, .pkl, .pt, .json)                                    │
│  • 实验报告 (metrics, artifacts, logs)                                      │
│  • 最佳参数 (best_params)                                                   │
│  • 模型注册表 (Model Registry)                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4. 模块结构

```
src/mlkit/model/
├── __init__.py            # 统一出口，工厂函数 create_model()
├── base.py                # BaseModel 基类
├── sklearn.py             # SKLearnModel 包装器
├── xgboost.py            # XGBoostModel 包装器
├── lightgbm.py           # LightGBMModel 包装器
├── pytorch.py            # PyTorchModel 包装器
└── registry.py            # 模型注册表

src/mlkit/runner/
├── trainer.py            # 训练器基类
├── sklearn_runner.py    # sklearn 训练器
├── pytorch_runner.py    # PyTorch 训练器
└── callback.py          # 回调系统

src/mlkit/experiment/
├── tracker.py           # 实验追踪器
├── metrics.py           # 指标计算
└── comparison.py       # 实验对比

src/mlkit/hpo/
├── searcher.py         # 超参数搜索器
├── grid.py             # 网格搜索
├── random.py           # 随机搜索
└── bayesian.py         # 贝叶斯优化
```

## 5. 核心接口

### 5.1 BaseModel

```python
class BaseModel(ABC):
    """模型基类 - 统一接口"""
    
    @abstractmethod
    def fit(self, X, y, **kwargs):
        """训练模型"""
        pass
    
    @abstractmethod
    def predict(self, X):
        """预测"""
        pass
    
    @abstractmethod
    def save(self, path: str):
        """保存模型"""
        pass
    
    @abstractmethod
    def load(self, path: str):
        """加载模型"""
        pass
    
    def predict_proba(self, X):
        """预测概率（分类）"""
        raise NotImplementedError
    
    def score(self, X, y):
        """评估分数"""
        pass
```

### 5.2 工厂函数

```python
def create_model(model_type: str, **kwargs) -> BaseModel:
    """
    创建模型实例
    
    Args:
        model_type: 'sklearn' | 'xgboost' | 'lightgbm' | 'pytorch'
        **kwargs: 模型参数
    
    Returns:
        BaseModel 实例
    """
```

### 5.3 训练配置

```python
@dataclass
class TrainConfig:
    # 数据
    batch_size: int = 32
    val_split: float = 0.2
    
    # 训练
    epochs: int = 10
    early_stopping: bool = True
    patience: int = 5
    
    # 优化
    optimizer: str = 'adam'
    lr: float = 0.001
    weight_decay: float = 0.0
    
    # 回调
    callbacks: List[Callback] = field(default_factory=list)
    
    # 日志
    log_interval: int = 10
    save_interval: int = 100
```

## 6. 支持的模型

### 6.1 传统机器学习

| 框架 | 分类 | 回归 | 特点 |
|------|------|------|------|
| sklearn | ✅ | ✅ | RandomForest, LogisticRegression, SVC, etc. |
| XGBoost | ✅ | ✅ | 高效梯度提升 |
| LightGBM | ✅ | ✅ | 快速梯度提升 |

### 6.2 深度学习

| 框架 | 支持 | 特点 |
|------|------|------|
| PyTorch | ✅ | 自定义 nn.Module, GPU 加速 |
| 预期支持 | - | TensorFlow, Keras |

### 6.3 模型配置示例

```python
# sklearn
model = create_model('sklearn', model_class='RandomForestClassifier', n_estimators=100)

# XGBoost
model = create_model('xgboost', n_estimators=100, max_depth=5, learning_rate=0.1)

# LightGBM
model = create_model('lightgbm', n_estimators=100, num_leaves=31)

# PyTorch
model = create_model('pytorch', input_dim=784, hidden_dim=256, output_dim=10, lr=0.001)
```

## 7. 回调系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     Callback 系统                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │               Callback (抽象基类)                   │  │
│  │                                                    │  │
│  │  • on_train_begin / on_train_end                  │  │
│  │  • on_epoch_begin / on_epoch_end                  │  │
│  │  • on_batch_begin / on_batch_end                   │  │
│  └────────────────────────────────────────────────────┘  │
│                         │                                │
│         ┌──────────────┼──────────────┐                  │
│         ▼              ▼              ▼                  │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│   │EarlyStop │   │Checkpoint│   │ LRSched  │            │
│   │  早停   │   │  保存模型 │   │  学习率  │            │
│   └──────────┘   └──────────┘   └──────────┘            │
│         │              │              │                  │
│         ▼              ▼              ▼                  │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│   │ TensorBoard│  │  Metrics │   │WeChat钉钉 │            │
│   │   日志   │   │  记录器  │   │  通知    │            │
│   └──────────┘   └──────────┘   └──────────┘            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 8. 实验追踪流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  开始训练  │───▶│ 记录参数  │───▶│ 记录指标  │───▶│ 保存产物  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Experiment DB   │
                                    │                  │
                                    │ • params.json    │
                                    │ • metrics.csv    │
                                    │ • model/         │
                                    │ • logs/          │
                                    └──────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │   实验对比分析    │
                                    │                  │
                                    │ • 指标曲线       │
                                    │ • 参数敏感性     │
                                    │ • 最佳模型选择    │
                                    └──────────────────┘
```

## 9. 超参数搜索

### 9.1 支持的方法

| 方法 | 适用场景 | 特点 |
|------|---------|------|
| GridSearch | 小参数空间 | 穷举搜索 |
| RandomSearch | 中等参数空间 | 随机采样 |
| Bayesian | 大参数空间 | 高效探索 |

### 9.2 搜索流程

```
┌─────────────────────────────────────────────────────────────┐
│                   超参数搜索流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐           │
│   │ 定义搜索空间│───▶│ 选择搜索方法│───▶│ 定义评估指标│           │
│   └───────────┘    └───────────┘    └───────────┘           │
│                                              │               │
│                                              ▼               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    搜索循环                          │   │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐  │   │
│   │  │采样参数 │──▶│训练模型 │──▶│评估指标 │──▶│更新策略│  │   │
│   │  └─────────┘  └─────────┘  └─────────┘  └────────┘  │   │
│   │       ▲              │              │       │        │   │
│   │       └──────────────┴──────────────┘       │        │   │
│   │              继续搜索? (是/否)                │        │   │
│   └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│              ┌──────────────────────┐                       │
│              │    返回最佳参数       │                       │
│              │  + 最佳模型 + 报告     │                       │
│              └──────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## 10. 模型注册表

```python
registry = ModelRegistry('mlkit')

# 注册模型
registry.register(
    name='resnet50',
    version='1.0.0',
    model=model,
    metrics={'accuracy': 0.95},
    metadata={'framework': 'pytorch', 'dataset': 'imagenet'}
)

# 获取模型
model = registry.get('resnet50', version='1.0.0')

# 列出版本
versions = registry.list_versions('resnet50')

# 模型对比
registry.compare_models(['resnet50:1.0.0', 'resnet50:1.1.0'])
```

## 11. 实现计划

| 阶段 | 任务 | 优先级 | 状态 |
|------|------|--------|------|
| 1 | 基础模型接口 (BaseModel + 工厂函数) | P0 | ✅ |
| 2 | sklearn/XGBoost/LightGBM 包装器 | P0 | ✅ |
| 3 | PyTorch 深度学习支持 | P0 | ✅ |
| 4 | 训练器 + 回调系统 | P1 | ⏳ |
| 5 | 实验追踪 | P1 | ⏳ |
| 6 | 超参数搜索 | P2 | ⏳ |
| 7 | 模型注册表 | P2 | ⏳ |

## 12. 已完成功能

### ✅ 模型训练
- [x] sklearn 模型 (RandomForest, LogisticRegression, etc.)
- [x] XGBoost 模型 (分类 & 回归)
- [x] LightGBM 模型 (分类 & 回归)
- [x] PyTorch 神经网络 (自定义 nn.Module)
- [x] GPU/CPU 设备支持
- [x] 批训练、流式训练
- [x] 模型保存/加载

### ⏳ 待实现
- [ ] 训练器 + 回调系统
- [ ] 实验追踪
- [ ] 超参数搜索
- [ ] 模型注册表

---

*创建时间: 2026-03-26*
*最后更新: 2026-03-26*
