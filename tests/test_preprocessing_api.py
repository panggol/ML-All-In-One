# -*- coding: utf-8 -*-
"""
预处理 API 测试
"""
import os
import sys
import tempfile
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture
def app():
    """构建 FastAPI 测试应用"""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from api.database import Base
    from api.main import app
    from api.auth import get_current_user
    from api.database import get_db

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db_session = TestingSession()

    def override_get_current_user():
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        return user

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    client.db = db_session
    yield client
    db_session.close()
    app.dependency_overrides.clear()


@pytest.fixture
def test_csv_file():
    """创建测试 CSV 文件"""
    data = {
        'A': [1.0, 2.0, np.nan, 4.0, 5.0],
        'B': [5.0, np.nan, 7.0, 8.0, 9.0],
        'C': ['x', 'y', 'z', 'w', 'v'],
        'target': [0, 1, 0, 1, 0],
    }
    df = pd.DataFrame(data)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def auth_headers():
    """返回空的认证头（因为我们 override 了认证依赖）"""
    return {}


@pytest.fixture
def auth_data_file(app, auth_headers, test_csv_file):
    """上传测试数据文件并返回文件 ID"""
    with open(test_csv_file, 'rb') as f:
        response = app.post(
            '/api/data/upload',
            headers=auth_headers,
            files={'file': ('test_data.csv', f, 'text/csv')},
        )

    assert response.status_code == 200
    return response.json()['id']


class TestPreprocessingPreview:
    """预览 API 测试"""

    def test_preview_imputer_mean(self, app, auth_headers, auth_data_file):
        """测试均值填充预览"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': True, 'strategy': 'mean'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert 'original_preview' in data
        assert 'transformed_preview' in data
        assert 'columns' in data
        assert 'stats' in data
        assert 'shape' in data

        # 验证缺失值被填充
        for row in data['transformed_preview']:
            assert None not in row

        # 原始数据中第二行 B 列原本是 NaN
        assert None in data['original_preview'][1]

    def test_preview_imputer_median(self, app, auth_headers, auth_data_file):
        """测试中位数填充"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': True, 'strategy': 'median'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        for row in data['transformed_preview']:
            assert None not in row

    def test_preview_minmax_scaler(self, app, auth_headers, auth_data_file):
        """测试 MinMax 归一化"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': False, 'strategy': 'mean'},
                    'scaler': {'enabled': True, 'type': 'minmax'},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()

        # A 列范围 [1, 5]，归一化后 min=0, max=1
        a_stats = next(s for s in data['stats'] if s['column'] == 'A')
        assert a_stats['transformed_min'] is not None
        assert a_stats['transformed_max'] is not None

    def test_preview_standard_scaler(self, app, auth_headers, auth_data_file):
        """测试标准化（均值接近 0）"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': False, 'strategy': 'mean'},
                    'scaler': {'enabled': True, 'type': 'standard'},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 标准化后均值应接近 0
        for stat in data['stats']:
            if stat['transformed_mean'] is not None:
                assert abs(stat['transformed_mean']) < 0.1

    def test_preview_feature_select(self, app, auth_headers, auth_data_file):
        """测试特征选择"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': False, 'strategy': 'mean'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': True, 'threshold': 0.0, 'selected_columns': ['A', 'B']},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert set(data['columns']) == {'A', 'B'}

    def test_preview_full_pipeline(self, app, auth_headers, auth_data_file):
        """测试完整流水线：缺失值填充 + 归一化 + 特征选择"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': True, 'strategy': 'mean'},
                    'scaler': {'enabled': True, 'type': 'minmax'},
                    'feature_select': {'enabled': True, 'threshold': 0.0, 'selected_columns': ['A', 'B', 'C', 'target']},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()

        # 无缺失值
        for row in data['transformed_preview']:
            assert None not in row

        # A 列归一化后 min=0, max=1
        a_stats = next(s for s in data['stats'] if s['column'] == 'A')
        assert a_stats['transformed_min'] == pytest.approx(0.0, abs=1e-9)
        assert a_stats['transformed_max'] == pytest.approx(1.0, abs=1e-9)

    def test_preview_no_steps(self, app, auth_headers, auth_data_file):
        """测试不启用任何步骤"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': False, 'strategy': 'mean'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['original_preview'] == data['transformed_preview']

    def test_preview_file_not_found(self, app, auth_headers):
        """测试文件不存在"""
        response = app.post(
            '/api/preprocessing/preview',
            headers=auth_headers,
            json={
                'data_file_id': 99999,
                'steps': {
                    'imputer': {'enabled': False, 'strategy': 'mean'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
            },
        )

        assert response.status_code == 404
        assert '不存在' in response.json()['detail']


class TestPreprocessingTransform:
    """保存 API 测试"""

    def test_transform_and_save(self, app, auth_headers, auth_data_file):
        """测试保存预处理结果"""
        response = app.post(
            '/api/preprocessing/transform',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': True, 'strategy': 'mean'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
                'output_name': 'test_transformed_data',
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert 'data_file_id' in data
        assert 'filename' in data
        assert data['filename'] == 'test_transformed_data.csv'
        assert data['rows'] == 5
        assert data['columns'] == 4

    def test_transform_with_feature_select(self, app, auth_headers, auth_data_file):
        """测试带特征选择的保存"""
        response = app.post(
            '/api/preprocessing/transform',
            headers=auth_headers,
            json={
                'data_file_id': auth_data_file,
                'steps': {
                    'imputer': {'enabled': False, 'strategy': 'mean'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': True, 'threshold': 0.0, 'selected_columns': ['A', 'target']},
                },
                'output_name': 'test_feature_select',
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['columns'] == 2

    def test_transform_file_not_found(self, app, auth_headers):
        """测试文件不存在"""
        response = app.post(
            '/api/preprocessing/transform',
            headers=auth_headers,
            json={
                'data_file_id': 99999,
                'steps': {
                    'imputer': {'enabled': False, 'strategy': 'mean'},
                    'scaler': {'enabled': False, 'type': None},
                    'feature_select': {'enabled': False, 'threshold': 0.0, 'selected_columns': []},
                },
            },
        )

        assert response.status_code == 404
