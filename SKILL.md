# ML All In One - 项目技能

ML 机器学习全流程训练平台开发技能。

## 项目结构

```
ml-all-in-one/
├── src/mlkit/          # 核心框架
│   ├── config/         # 配置系统
│   ├── registry/       # 注册机制
│   ├── model/         # 模型基类
│   ├── data/          # 数据处理
│   ├── hooks/         # 生命周期钩子
│   ├── runner/        # 训练运行器
│   ├── experiment/    # 实验管理
│   ├── api/          # 在线推理
│   └── utils/        # 工具函数
├── examples/          # 示例代码
├── docs/             # 文档
│   └── design/       # 设计文档
└── tests/            # 测试
```

## 开发命令

```bash
# 安装依赖
make install

# 运行测试
make test

# 代码检查
make lint

# 运行示例
make run-example
```

## 常用操作

### 安装依赖（清华源）
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 运行示例
```bash
cd ml-all-in-one
PYTHONPATH=src python examples/train_sklearn.py
```

### 调试模型
```python
from mlkit import create_runner, Config

config = Config.from_yaml('config.yaml')
runner = create_runner(config)
runner.train()
```

## 添加新模块

1. 在 `src/mlkit/` 下创建模块目录
2. 在模块 `__init__.py` 中导出接口
3. 更新根 `__init__.py` 导出
4. 添加测试用例到 `tests/`
5. 更新设计文档 `docs/design/`

## 提交规范

参考 Conventional Commits：
- `feat: 新功能`
- `fix: 修复 bug`
- `docs: 文档更新`
- `refactor: 重构`

---

*最后更新: 2026-03-21*
