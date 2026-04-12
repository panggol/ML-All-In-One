# -*- coding: utf-8 -*-
"""
data_management API Integration Tests
Covers all data API endpoints: upload, list, preview, stats, delete
"""
import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.database import Base, get_db, User, DataFile
from api.auth import get_current_user, create_access_token


# ===== Test Database Setup =====

TEST_DATABASE_URL = "sqlite:///:memory:"

_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _db_override():
    """
    Per-test setup & teardown for the database dependency override.

    Why this exists:
    - Other test files (test_api_automl.py, test_api_viz.py, etc.) call
      `app.dependency_overrides.clear()` in their fixture teardown.
    - We cannot rely on a module-level override (set at import time) because
      it has no pytest-controlled teardown — other files' teardowns can wipe it.
    - This autouse fixture guarantees the override is active for every test
      and is properly cleaned up afterward, regardless of test ordering.

    Teardown order: tables are dropped by db_session (LIFO), then the override
    is cleared here.  This is safe because by this point no more requests will
    use the override.
    """
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def db_session():
    """
    Each test gets a fresh in-memory database with all tables created.
    Tables are dropped at teardown to ensure clean state for the next test.
    """
    Base.metadata.create_all(bind=_engine)
    session = TestingSessionLocal()
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI test client. Depends on db_session to ensure tables are
    committed before any request is made.
    """
    yield TestClient(app)
    # teardown handled by db_session


@pytest.fixture
def test_user(db_session):
    """Create test user in the db session."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password_here",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate auth token for the test user."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(client, auth_headers):
    """Authenticated test client with auth headers pre-set."""
    client.headers.update(auth_headers)
    return client


def create_csv_file(content: str) -> bytes:
    """Create a temporary CSV file content."""
    return content.encode("utf-8")


# ===== Functional Tests =====


class TestDataUpload:
    """Upload functionality tests."""

    def test_upload_csv_success(self, auth_client, db_session, test_user):
        """Upload CSV file successfully."""
        csv_content = "name,age,score\nAlice,25,95.5\nBob,30,88.0\nCharlie,22,92.0"
        files = {"file": ("test.csv", create_csv_file(csv_content), "text/csv")}

        response = auth_client.post("/api/data/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.csv"
        assert data["rows"] == 3  # 3 data rows (header excluded)
        assert data["columns"] == ["name", "age", "score"]
        assert "id" in data
        assert "created_at" in data

        # Verify DB record
        record = db_session.query(DataFile).filter(DataFile.id == data["id"]).first()
        assert record is not None
        assert record.user_id == test_user.id
        assert record.filename == "test.csv"

    def test_upload_non_csv_rejected(self, auth_client):
        """Non-CSV file is rejected."""
        files = {"file": ("test.txt", b"hello world", "text/plain")}
        response = auth_client.post("/api/data/upload", files=files)
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_upload_without_auth_rejected(self, client):
        """Unauthenticated upload is rejected."""
        files = {"file": ("test.csv", b"name,age\nAlice,25", "text/csv")}
        response = client.post("/api/data/upload", files=files)
        assert response.status_code == 401


class TestDataList:
    """List functionality tests."""

    def test_list_empty(self, auth_client):
        """Empty list returns empty array."""
        response = auth_client.get("/api/data/list")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_files(self, auth_client, db_session, test_user):
        """List files sorted by time descending."""
        from datetime import datetime, timezone

        for i, name in enumerate(["file1.csv", "file2.csv"]):
            f = DataFile(
                user_id=test_user.id,
                filename=name,
                filepath=f"/tmp/{name}",
                size=100 * i,
                rows=10 * i,
                columns=["col1", "col2"],
            )
            db_session.add(f)
        db_session.commit()

        response = auth_client.get("/api/data/list")
        assert response.status_code == 200
        files = response.json()
        assert len(files) == 2
        # newest first
        assert files[0]["filename"] == "file2.csv"
        assert files[1]["filename"] == "file1.csv"

    def test_list_only_own_files(self, auth_client, db_session, test_user):
        """Only return own files (isolation)."""
        # Create another user
        other_user = User(username="other", email="other@example.com", password_hash="x")
        db_session.add(other_user)
        db_session.commit()

        # Write files for both users
        for uid, name in [(test_user.id, "mine.csv"), (other_user.id, "other.csv")]:
            f = DataFile(
                user_id=uid,
                filename=name,
                filepath=f"/tmp/{name}",
                size=100,
                rows=10,
                columns=["col1"],
            )
            db_session.add(f)
        db_session.commit()

        response = auth_client.get("/api/data/list")
        assert response.status_code == 200
        files = response.json()
        assert len(files) == 1
        assert files[0]["filename"] == "mine.csv"


class TestDataPreview:
    """Preview functionality tests."""

    def test_preview_success(self, auth_client, db_session, test_user):
        """Preview returns correct columns and row data."""
        csv_content = "name,age\nAlice,25\nBob,30\nCharlie,35"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        f = DataFile(
            user_id=test_user.id,
            filename="preview_test.csv",
            filepath=tmp_path,
            size=os.path.getsize(tmp_path),
            rows=3,
            columns=["name", "age"],
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)

        response = auth_client.get(f"/api/data/{f.id}/preview")
        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == ["name", "age"]
        assert len(data["rows"]) >= 3
        assert "total_rows" in data

        os.unlink(tmp_path)

    def test_preview_not_found(self, auth_client):
        """Preview non-existent file returns 404."""
        response = auth_client.get("/api/data/99999/preview")
        assert response.status_code == 404


class TestDataStats:
    """Statistics functionality tests."""

    def test_stats_numerical_column(self, auth_client, db_session, test_user):
        """Numerical column statistics are correct."""
        csv_content = "age,salary\n25,50000\n30,60000\n35,70000\n40,80000\n45,90000"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        f = DataFile(
            user_id=test_user.id,
            filename="stats_test.csv",
            filepath=tmp_path,
            size=os.path.getsize(tmp_path),
            rows=5,
            columns=["age", "salary"],
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)

        response = auth_client.get(f"/api/data/{f.id}/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 5
        assert data["total_columns"] == 2

        col_stats = {s["column"]: s for s in data["column_stats"]}
        assert "age" in col_stats
        age_stat = col_stats["age"]
        assert age_stat["dtype"] in ["int64", "int32"]
        assert age_stat["null_count"] == 0
        assert "min" in age_stat
        assert "max" in age_stat
        assert "mean" in age_stat
        assert age_stat["min"] == 25
        assert age_stat["max"] == 45

        os.unlink(tmp_path)

    def test_stats_categorical_column(self, auth_client, db_session, test_user):
        """Categorical column statistics are correct (top_values)."""
        csv_content = "gender\nmale\nfemale\nmale\nmale\nfemale"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        f = DataFile(
            user_id=test_user.id,
            filename="cat_test.csv",
            filepath=tmp_path,
            size=os.path.getsize(tmp_path),
            rows=5,
            columns=["gender"],
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)

        response = auth_client.get(f"/api/data/{f.id}/stats")
        assert response.status_code == 200
        data = response.json()

        gender_stat = data["column_stats"][0]
        assert gender_stat["dtype"] in ("object", "str"), f"unexpected dtype: {gender_stat['dtype']}"
        assert gender_stat["null_count"] == 0
        assert "unique_count" in gender_stat
        assert "top_values" in gender_stat
        assert len(gender_stat["top_values"]) > 0

        os.unlink(tmp_path)


class TestDataDelete:
    """Delete functionality tests."""

    def test_delete_success(self, auth_client, db_session, test_user):
        """Delete file successfully."""
        csv_content = "name,age\nAlice,25"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        f = DataFile(
            user_id=test_user.id,
            filename="delete_me.csv",
            filepath=tmp_path,
            size=100,
            rows=1,
            columns=["name", "age"],
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)
        file_id = f.id

        response = auth_client.delete(f"/api/data/{file_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "文件已删除"

        # Verify DB record is deleted
        record = db_session.query(DataFile).filter(DataFile.id == file_id).first()
        assert record is None

    def test_delete_not_found(self, auth_client):
        """Deleting non-existent file returns 404."""
        response = auth_client.delete("/api/data/99999")
        assert response.status_code == 404

    def test_delete_other_user_file_rejected(self, auth_client, db_session, test_user):
        """Cannot delete other user's file."""
        other_user = User(username="other2", email="other2@example.com", password_hash="x")
        db_session.add(other_user)
        db_session.commit()

        f = DataFile(
            user_id=other_user.id,
            filename="other_file.csv",
            filepath="/tmp/other.csv",
            size=100,
            rows=10,
            columns=["col1"],
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)

        response = auth_client.delete(f"/api/data/{f.id}")
        assert response.status_code == 404  # 404 (cannot find own file)


class TestDataExport:
    """Export functionality tests — full CSV download via /export endpoint."""

    def test_export_returns_full_file(self, auth_client, db_session, test_user):
        """导出端点返回完整文件，不只是前50行。"""
        # 创建一个超过50行的 CSV 文件
        rows = ["col1,col2,col3"] + [f"{i},{i*2},{i*3}" for i in range(1, 101)]
        csv_content = "\n".join(rows)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        f = DataFile(
            user_id=test_user.id,
            filename="large_export.csv",
            filepath=tmp_path,
            size=os.path.getsize(tmp_path),
            rows=100,
            columns=["col1", "col2", "col3"],
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)

        response = auth_client.get(f"/api/data/{f.id}/export")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "content-disposition" in response.headers

        # 验证返回的是完整 CSV（100行数据 + 1行 header = 101行）
        content = response.text
        lines = content.strip().split("\n")
        assert len(lines) == 101, f"Expected 101 lines, got {len(lines)}"

        os.unlink(tmp_path)

    def test_export_not_found(self, auth_client):
        """导出不存在的文件返回404。"""
        response = auth_client.get("/api/data/99999/export")
        assert response.status_code == 404

    def test_export_other_user_file_rejected(self, auth_client, db_session, test_user):
        """无法导出其他用户的文件。"""
        other_user = User(username="other_export", email="other_export@example.com", password_hash="x")
        db_session.add(other_user)
        db_session.commit()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write("col1,col2\n1,2\n3,4\n")
            tmp_path = tmp.name

        f = DataFile(
            user_id=other_user.id,
            filename="other_export.csv",
            filepath=tmp_path,
            size=os.path.getsize(tmp_path),
            rows=2,
            columns=["col1", "col2"],
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)

        response = auth_client.get(f"/api/data/{f.id}/export")
        assert response.status_code == 404  # 隔离：查不到 own 的文件

        os.unlink(tmp_path)


# ===== Acceptance Criteria =====

ACCEPTANCE_CRITERIA = [
    ("Upload CSV file", "test_upload_csv_success"),
    ("Non-CSV rejected", "test_upload_non_csv_rejected"),
    ("Unauthenticated upload rejected", "test_upload_without_auth_rejected"),
    ("Empty list", "test_list_empty"),
    ("File list sorted by time desc", "test_list_with_files"),
    ("User file isolation", "test_list_only_own_files"),
    ("Preview returns correct data", "test_preview_success"),
    ("Preview non-existent file", "test_preview_not_found"),
    ("Numerical column stats", "test_stats_numerical_column"),
    ("Categorical column stats", "test_stats_categorical_column"),
    ("Delete success", "test_delete_success"),
    ("Delete non-existent file", "test_delete_not_found"),
    ("Cannot delete other user's file", "test_delete_other_user_file_rejected"),
    ("Export returns full file (>50 rows)", "test_export_returns_full_file"),
    ("Export non-existent file", "test_export_not_found"),
    ("Cannot export other user's file", "test_export_other_user_file_rejected"),
]


if __name__ == "__main__":
    print("Running data_management API tests...")
    pytest.main([__file__, "-v", "--tb=short"])
    print("\nAcceptance criteria coverage:")
    for criterion, test_name in ACCEPTANCE_CRITERIA:
        print(f"  {criterion}")
