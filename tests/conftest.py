# ML All In One Tests - shared fixtures
import os
import sys
import tempfile
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Set JWT secret for tests before any api imports
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_pytest_only_do_not_use_in_production"

# Add src to path for mlkit imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set a test database URL before importing api modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture
def rng():
    """Reproducible random number generator"""
    return np.random.default_rng(42)


@pytest.fixture
def classification_data(rng):
    """Standard classification dataset"""
    X_train = rng.normal(size=(200, 10))
    y_train = (X_train[:, 0] > 0).astype(int)
    X_val = rng.normal(size=(50, 10))
    y_val = (X_val[:, 0] > 0).astype(int)
    return X_train, y_train, X_val, y_val


@pytest.fixture
def regression_data(rng):
    """Standard regression dataset"""
    X_train = rng.normal(size=(200, 5))
    y_train = X_train[:, 0] * 2 + X_train[:, 1] + rng.normal(0, 0.1, size=200)
    X_val = rng.normal(size=(50, 5))
    y_val = X_val[:, 0] * 2 + X_val[:, 1] + rng.normal(0, 0.1, size=50)
    return X_train, y_train, X_val, y_val


@pytest.fixture
def small_classification_data(rng):
    """Small classification dataset for fast tests"""
    X_train = rng.normal(size=(50, 5))
    y_train = (X_train[:, 0] > 0).astype(int)
    X_val = rng.normal(size=(20, 5))
    y_val = (X_val[:, 0] > 0).astype(int)
    return X_train, y_train, X_val, y_val


@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file with sample data"""
    data = {
        "id": list(range(100)),
        "feature_a": list(np.random.randn(100)),
        "feature_b": list(np.random.randn(100)),
        "feature_c": list(np.random.randn(100)),
        "target": list(np.random.randint(0, 2, 100)),
    }
    df = pd.DataFrame(data)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        df.to_csv(f, index=False)
        filepath = f.name

    yield filepath

    # cleanup
    os.unlink(filepath)


@pytest.fixture
def mock_current_user():
    """Mock authenticated user"""
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from api.database import Base

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
