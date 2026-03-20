# ============================================
# ML All In One - 开发命令
# ============================================

.PHONY: help install install-dev test lint format check clean run-examples

# ============================================
# 帮助
# ============================================
help:
	@echo "ML All In One - 开发命令"
	@echo ""
	@echo "  make install        安装依赖"
	@echo "  make install-dev   安装开发依赖"
	@echo "  make test          运行测试"
	@echo "  make lint          代码检查"
	@echo "  make format        代码格式化"
	@echo "  make check         全面检查"
	@echo "  make clean         清理缓存"
	@echo "  make run-examples  运行示例"

# ============================================
# 安装
# ============================================
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

# ============================================
# 测试
# ============================================
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=mlkit --cov-report=html --cov-report=term

test-watch:
	pytest tests/ -v --watch

# ============================================
# 代码检查
# ============================================
lint:
	@echo "=== Ruff ==="
	ruff check src/mlkit/
	@echo "=== mypy ==="
	mypy src/mlkit/

# ============================================
# 代码格式化
# ============================================
format:
	@echo "=== Black ==="
	black src/mlkit/ examples/
	@echo "=== isort ==="
	isort src/mlkit/ examples/

# ============================================
# 全面检查
# ============================================
check: format lint test

# ============================================
# 清理
# ============================================
clean:
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf **/__pycache__
	rm -rf **/*.pyc
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# ============================================
# 运行示例
# ============================================
run-examples:
	@echo "=== sklearn 示例 ==="
	python examples/train_sklearn.py
	@echo ""
	@echo "=== PyTorch 示例 ==="
	python examples/train_pytorch.py

# ============================================
# 开发相关
# ============================================
dev: install-dev
	@echo "开发环境已安装"

typecheck:
	mypy src/mlkit/

security:
	ruff check src/mlkit/ --select=S

# ============================================
# Git Hooks
# ============================================
pre-commit:
	pre-commit run --all-files
