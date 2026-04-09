"""
模型训练模块测试 - Model Training Tests

测试 sklearn, XGBoost, LightGBM, PyTorch 模型训练功能
"""

import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mlkit.model import create_model, SKLearnModel, XGBoostModel, LightGBMModel, PyTorchModel


class TestSklearnModel:
    """sklearn 模型测试"""
    
    @pytest.fixture
    def data(self):
        """准备测试数据"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randint(0, 2, 100)
        return X, y
    
    def test_random_forest_classifier(self, data):
        """测试随机森林分类器"""
        X, y = data
        model = create_model('sklearn', model_class='RandomForestClassifier', n_estimators=10)
        model.fit(X, y)
        predictions = model.predict(X)
        assert len(predictions) == len(y)
    
    def test_random_forest_regressor(self):
        """测试随机森林回归器"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randn(100)
        model = create_model('sklearn', model_class='RandomForestRegressor', n_estimators=10)
        model.fit(X, y)
        predictions = model.predict(X)
        assert len(predictions) == len(y)
    
    def test_logistic_regression(self, data):
        """测试逻辑回归"""
        X, y = data
        model = create_model('sklearn', model_class='LogisticRegression', max_iter=100)
        model.fit(X, y)
        predictions = model.predict(X)
        probs = model.predict_proba(X)
        assert len(predictions) == len(y)
        assert probs.shape[1] == 2
    
    def test_save_load(self, data, tmp_path):
        """测试模型保存和加载"""
        X, y = data
        model = create_model('sklearn', model_class='RandomForestClassifier', n_estimators=10)
        model.fit(X, y)
        
        # 保存
        model_path = tmp_path / "model.joblib"
        model.save(model_path)
        
        # 加载
        new_model = create_model('sklearn', model_class='RandomForestClassifier')
        new_model.load(model_path)
        
        # 验证
        predictions1 = model.predict(X[:5])
        predictions2 = new_model.predict(X[:5])
        np.testing.assert_array_equal(predictions1, predictions2)


class TestXGBoostModel:
    """XGBoost 模型测试"""
    
    @pytest.fixture
    def data(self):
        """准备测试数据"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randint(0, 2, 100)
        return X, y
    
    def test_xgboost_classifier(self, data):
        """测试 XGBoost 分类器"""
        X, y = data
        model = create_model('xgboost', n_estimators=10, max_depth=3)
        model.fit(X, y)
        predictions = model.predict(X)
        probs = model.predict_proba(X)
        assert len(predictions) == len(y)
        assert probs.shape == (len(y), 2)
    
    def test_xgboost_regressor(self):
        """测试 XGBoost 回归器"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randn(100)
        model = create_model('xgboost', n_estimators=10, objective='reg:squarederror')
        model.fit(X, y)
        predictions = model.predict(X)
        assert len(predictions) == len(y)
    
    def test_save_load(self, data, tmp_path):
        """测试模型保存和加载"""
        X, y = data
        model = create_model('xgboost', n_estimators=10)
        model.fit(X, y)
        
        model_path = tmp_path / "xgboost.json"
        model.save(model_path)
        
        new_model = create_model('xgboost')
        new_model.load(model_path)
        
        predictions1 = model.predict(X[:5])
        predictions2 = new_model.predict(X[:5])
        np.testing.assert_array_equal(predictions1, predictions2)


class TestLightGBMModel:
    """LightGBM 模型测试"""
    
    @pytest.fixture
    def data(self):
        """准备测试数据"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randint(0, 2, 100)
        return X, y
    
    def test_lightgbm_classifier(self, data):
        """测试 LightGBM 分类器"""
        X, y = data
        model = create_model('lightgbm', n_estimators=10, max_depth=3)
        model.fit(X, y)
        predictions = model.predict(X)
        probs = model.predict_proba(X)
        assert len(predictions) == len(y)
        assert probs.shape == (len(y), 2)
    
    def test_lightgbm_regressor(self):
        """测试 LightGBM 回归器"""
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.randn(100)
        model = create_model('lightgbm', n_estimators=10, objective='regression')
        model.fit(X, y)
        predictions = model.predict(X)
        assert len(predictions) == len(y)


class TestPyTorchModel:
    """PyTorch 深度学习模型测试"""
    
    @pytest.fixture
    def data(self):
        """准备测试数据"""
        np.random.seed(42)
        X = np.random.randn(100, 10).astype(np.float32)
        y = np.random.randint(0, 3, 100)  # 3类分类
        return X, y
    
    @pytest.fixture
    def regression_data(self):
        """准备回归测试数据"""
        np.random.seed(42)
        X = np.random.randn(100, 10).astype(np.float32)
        y = np.random.randn(100).astype(np.float32)
        return X, y
    
    def test_pytorch_classifier(self, data):
        """测试 PyTorch 分类器"""
        X, y = data
        model = create_model('pytorch', input_dim=10, hidden_dim=32, output_dim=3, lr=0.01)
        model.fit(X, y, epochs=3, batch_size=16)
        predictions = model.predict(X[:10])
        probs = model.predict_proba(X[:10])
        assert len(predictions) == 10
        assert probs.shape == (10, 3)
    
    def test_pytorch_regressor(self, regression_data):
        """测试 PyTorch 回归器"""
        import torch.nn as nn
        
        X, y = regression_data
        model = create_model('pytorch', input_dim=10, hidden_dim=32, output_dim=1, lr=0.01)
        model.task_type = 'regression'
        # 使用 MSE 损失函数用于回归
        model.criterion = nn.MSELoss()
        model.fit(X, y, epochs=3, batch_size=16)
        predictions = model.predict(X[:10])
        assert len(predictions) == 10
    
    def test_custom_pytorch_model(self, data):
        """测试自定义 PyTorch 模型"""
        import torch.nn as nn
        
        X, y = data
        
        class SimpleNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.fc = nn.Linear(10, 3)
            
            def forward(self, x):
                return self.fc(x)
        
        model = PyTorchModel(SimpleNet())
        model.fit(X, y, epochs=3, batch_size=16)
        predictions = model.predict(X[:5])
        assert len(predictions) == 5
    
    def test_save_load(self, data, tmp_path):
        """测试 PyTorch 模型保存和加载"""
        X, y = data
        model = create_model('pytorch', input_dim=10, hidden_dim=16, output_dim=3, lr=0.01)
        model.fit(X, y, epochs=2, batch_size=16)
        
        model_path = tmp_path / "pytorch_model.pt"
        model.save(model_path)
        
        new_model = create_model('pytorch', input_dim=10, hidden_dim=16, output_dim=3, lr=0.01)
        new_model.load(model_path)
        
        predictions1 = model.predict(X[:5])
        predictions2 = new_model.predict(X[:5])
        np.testing.assert_array_equal(predictions1, predictions2)


class TestModelComparison:
    """模型对比测试"""
    
    @pytest.fixture
    def data(self):
        """准备测试数据"""
        np.random.seed(42)
        X = np.random.randn(200, 10)
        y = np.random.randint(0, 2, 200)
        return X, y
    
    def test_all_models_performance(self, data):
        """对比所有模型的性能"""
        X, y = data
        
        results = {}
        
        # sklearn
        model = create_model('sklearn', model_class='RandomForestClassifier', n_estimators=10)
        model.fit(X, y)
        results['sklearn'] = model.score(X, y)
        
        # XGBoost
        model = create_model('xgboost', n_estimators=10)
        model.fit(X, y)
        results['xgboost'] = model.score(X, y)
        
        # LightGBM
        model = create_model('lightgbm', n_estimators=10)
        model.fit(X, y)
        results['lightgbm'] = model.score(X, y)
        
        # PyTorch
        X_float = X.astype(np.float32)
        model = create_model('pytorch', input_dim=10, hidden_dim=32, output_dim=2, lr=0.01)
        model.fit(X_float, y, epochs=5, batch_size=16)
        results['pytorch'] = model.score(X_float, y)
        
        print(f"\n模型性能对比: {results}")
        
        # 所有模型都应该有合理的准确率
        for name, score in results.items():
            assert 0 <= score <= 1, f"{name} 分数异常: {score}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
