# ML All In One - 开发命令

.PHONY: help install test lint format clean run-example

help:
	@echo "ML All In One 开发命令"
	@echo "========================"
	@echo "make install        安装依赖"
	@echo "make test           运行测试"
	@echo "make lint          代码检查"
	@echo "make format        代码格式化"
	@echo "make clean         清理缓存"
	@echo "make run-example   运行示例"

install:
	pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

install-dev:
	pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
	pip install pytest ruff black -i https://pypi.tuna.tsinghua.edu.cn/simple

test:
	PYTHONPATH=src pytest tests/ -v

test-coverage:
	PYTHONPATH=src pytest tests/ --cov=mlkit --cov-report=html

lint:
	ruff check src/mlkit/

format:
	ruff format src/mlkit/
	black src/mlkit/

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find src -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage

run-example:
	PYTHONPATH=src python examples/train_sklearn.py

run-example-xgb:
	PYTHONPATH=src python examples/credit_fraud.py
