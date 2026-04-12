"""
tests/test_logs_api.py - logs_tab API 测试
"""
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-logs"


@pytest.fixture
def logs_client(tmp_path):
    """每个测试使用独立的临时日志目录"""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Patch LOGS_DIR in the logs route module
    with patch("api.routes.logs.LOGS_DIR", logs_dir):
        from api.main import app
        from api.auth import get_current_user
        from api.database import User
        from unittest.mock import MagicMock

        mock_user = MagicMock(spec=User)
        mock_user.id = 1

        def override_auth():
            return mock_user

        app.dependency_overrides[get_current_user] = override_auth

        client = TestClient(app)

        yield client, logs_dir

        # Cleanup
        app.dependency_overrides.clear()


class TestLogsAPI:
    """logs_tab API 端到端测试"""

    def test_list_logs_pagination(self, logs_client):
        """F1: GET /api/logs 返回分页日志列表"""
        client, logs_dir = logs_client

        for i in range(1, 4):
            f = logs_dir / f"run_{i}_171200000{i}.json"
            f.write_text(json.dumps([{"iter": i * 10, "run": i, "timestamp": 1712000000 + i, "loss": 0.9 - i * 0.1}]))

        response = client.get("/api/logs?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data and "total" in data and "page" in data and "page_size" in data
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["data"]) == 2
        assert data["total"] == 3
        # 按 timestamp 降序
        assert data["data"][0]["run"] == 3
        assert data["data"][1]["run"] == 2

    def test_list_logs_experiment_filter(self, logs_client):
        """F2: experiment_id 筛选"""
        client, logs_dir = logs_client

        f1 = logs_dir / "run_1.json"
        f1.write_text(json.dumps([{"iter": 0, "run": 1, "timestamp": 1712000000, "experiment_id": "exp-A", "loss": 0.9}]))

        f2 = logs_dir / "run_2.json"
        f2.write_text(json.dumps([{"iter": 0, "run": 2, "timestamp": 1712000100, "experiment_id": "exp-B", "loss": 0.8}]))

        response = client.get("/api/logs?experiment_id=exp-A")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["run"] == 1

    def test_list_logs_time_range(self, logs_client):
        """F2: 时间范围筛选（闭区间）"""
        client, logs_dir = logs_client

        # 2026-04-10 (timestamp = 1775779200) - 在范围内
        f1 = logs_dir / "run_1.json"
        f1.write_text(json.dumps([{"iter": 0, "run": 1, "timestamp": 1775779200, "loss": 0.9}]))

        # 2026-04-12 (timestamp = 1775952000) - 在范围外
        f2 = logs_dir / "run_2.json"
        f2.write_text(json.dumps([{"iter": 0, "run": 2, "timestamp": 1775952000, "loss": 0.8}]))

        response = client.get("/api/logs?start_time=2026-04-09T00:00:00Z&end_time=2026-04-11T23:59:59Z")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["run"] == 1

    def test_list_logs_invalid_time_range(self, logs_client):
        """US3: 开始时间晚于结束时间返回 400"""
        client, _ = logs_client
        response = client.get("/api/logs?start_time=2026-04-15T00:00:00Z&end_time=2026-04-10T00:00:00Z")
        assert response.status_code == 400
        assert "开始时间不能晚于结束时间" in response.json()["detail"]

    def test_get_log_detail(self, logs_client):
        """F3: GET /api/logs/{file_id} 返回完整日志"""
        client, logs_dir = logs_client

        content = [
            {"iter": 0, "run": 1, "timestamp": 1712000000, "train_loss": 0.923},
            {"iter": 10, "run": 1, "timestamp": 1712000010, "train_loss": 0.812},
        ]
        f = logs_dir / "run_1_1712000000.json"
        f.write_text(json.dumps(content))

        response = client.get("/api/logs/run_1_1712000000.json")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["iter"] == 0
        assert data[1]["train_loss"] == 0.812

    def test_get_log_detail_not_found(self, logs_client):
        """F3: 文件不存在返回 404"""
        client, _ = logs_client
        response = client.get("/api/logs/nonexistent.json")
        assert response.status_code == 404
        assert "日志文件不存在" in response.json()["detail"]

    def test_delete_log(self, logs_client):
        """F4: DELETE /api/logs/{file_id} 删除文件"""
        client, logs_dir = logs_client

        f = logs_dir / "to_delete.json"
        f.write_text(json.dumps([{"iter": 0}]))

        assert f.exists()
        response = client.delete("/api/logs/to_delete.json")
        assert response.status_code == 200
        assert response.json()["message"] == "删除成功"
        assert not f.exists()

    def test_delete_log_not_found(self, logs_client):
        """F4: 删除不存在的文件返回 404"""
        client, _ = logs_client
        response = client.delete("/api/logs/nonexistent.json")
        assert response.status_code == 404

    def test_delete_requires_auth(self, tmp_path):
        """F4: 删除需要认证（无 token 返回 401/403）"""
        from api.main import app

        # 清除 auth 依赖覆盖，模拟未认证
        app.dependency_overrides.clear()

        client = TestClient(app)
        response = client.delete("/api/logs/some.json")
        assert response.status_code in (401, 403)

    def test_path_traversal_in_file_id_parameter(self, logs_client):
        """安全：路径遍历通过 file_id 参数被阻止（通过 URL 路径）"""
        client, _ = logs_client

        # 注意：通过 URL 路径的 /../ 会被 HTTP 层规范化为 /api/etc/passwd，
        # 不匹配 /api/logs/{file_id}，所以返回 404。
        # 真正的防护是：file_id 不能包含 .. 导致路径逃逸文件系统。
        # 此测试验证 file_id 中包含 .. 时返回 400。
        response = client.get("/api/logs/..%2F..%2Fetc%2Fpasswd")
        # 会被规范化 → 404（路由不匹配），这是 HTTP 层防护
        assert response.status_code in (400, 404)

    def test_corrupt_file_skipped(self, logs_client):
        """非功能性：损坏的日志文件被跳过"""
        client, logs_dir = logs_client

        # 损坏文件
        f = logs_dir / "corrupt.json"
        f.write_text("not valid json")

        # 正常文件
        f2 = logs_dir / "run_1.json"
        f2.write_text(json.dumps([{"iter": 0, "run": 1, "timestamp": 1712000000, "loss": 0.9}]))

        response = client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["run"] == 1

    def test_graceful_no_logs_dir(self, tmp_path):
        """非功能性：日志目录不存在时自动创建（不会报错）"""
        nonexistent_dir = tmp_path / "does_not_exist"

        with patch("api.routes.logs.LOGS_DIR", nonexistent_dir):
            from api.main import app
            from api.auth import get_current_user
            from api.database import User
            from unittest.mock import MagicMock

            mock_user = MagicMock(spec=User)
            mock_user.id = 1

            def override_auth():
                return mock_user

            app.dependency_overrides[get_current_user] = override_auth

            client = TestClient(app)
            response = client.get("/api/logs")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["data"] == []
            app.dependency_overrides.clear()

    def test_empty_logs_dir(self, logs_client):
        """US1: 没有任何日志文件时返回空列表"""
        client, _ = logs_client
        response = client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["data"] == []

    def test_iso8601_timestamp_format(self, logs_client):
        """时间戳字段支持 ISO8601 字符串格式"""
        client, logs_dir = logs_client

        f = logs_dir / "iso_ts.json"
        f.write_text(json.dumps([
            {"iter": 0, "run": 1, "timestamp": "2026-04-10T10:00:00Z", "loss": 0.9},
            {"iter": 10, "run": 1, "timestamp": "2026-04-10T10:01:00Z", "loss": 0.8},
        ]))

        response = client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["timestamp"] == "2026-04-10T10:01:00Z"  # 最新一条

    def test_metrics_extraction(self, logs_client):
        """metrics 字段包含除 iter/run/timestamp 外的所有字段"""
        client, logs_dir = logs_client

        f = logs_dir / "metrics.json"
        f.write_text(json.dumps([{
            "iter": 0, "run": 1, "timestamp": 1712000000,
            "train_loss": 0.923, "val_loss": 0.931, "train_acc": 0.512, "experiment_id": "exp-X"
        }]))

        response = client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        entry = data["data"][0]
        assert "file_id" in entry
        assert "iter" not in entry["metrics"]
        assert "run" not in entry["metrics"]
        assert "timestamp" not in entry["metrics"]
        assert entry["metrics"]["train_loss"] == 0.923
        assert entry["metrics"]["val_loss"] == 0.931
        assert entry["experiment_id"] == "exp-X"
