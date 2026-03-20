# ML All In One

一个集成机器学习和深度学习模型训练全流程的平台。

## 核心特性

- ✅ 支持 sklearn、PyTorch 训练
- ✅ 支持超大数据集（分块读取、流式训练）
- ✅ 样本不均衡多种解决方案
- ✅ 实时训练日志与可视化
- ✅ 模型保存、下载、在线推理
- ✅ 多环境部署（本地、Docker、K8s）
- ✅ 支持 GPU / NPU

## 快速开始

```bash
# 安装依赖（推荐使用清华源）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 运行示例
python examples/train_sklearn.py
python examples/train_pytorch.py
```

## 项目结构

```
ml-all-in-one/
├── src/
│   ├── mlkit/          # 核心框架
│   ├── api/           # API 服务
│   └── algorithms/    # 算法实现
├── frontend/          # 前端项目
├── tests/            # 测试
├── docs/             # 文档
└── examples/         # 示例
```

## 文档

- [设计文档](docs/design.md)
- [API 文档](docs/api.md)
- [部署指南](docs/deployment.md)

---

*本项目遵循 vibe-coding 最佳实践构建*
