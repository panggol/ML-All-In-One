"""
集成测试：训练曲线 API (metrics_curve 字段)

验证 /api/train/{id}/status 返回的 metrics_curve 字段结构正确性。
"""

import pytest
import requests
import time
import os
import signal
import subprocess
import sys


BACKEND_HOST = os.environ.get("BACKEND_HOST", "http://localhost:8000")
API_BASE = f"{BACKEND_HOST}/api"


def wait_for_backend(host=BACKEND_HOST, timeout=30):
    """等待后端服务就绪"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{host}/health", timeout=5)
            if r.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"Backend not available at {host} after {timeout}s")


def find_csv_file():
    """在 tests/ 目录中查找一个 CSV 测试文件"""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, files in os.walk(test_dir):
        for f in files:
            if f.endswith('.csv'):
                return os.path.join(root, f)
    return None


@pytest.fixture(scope="module")
def backend_process():
    """启动后端服务（如果未运行）"""
    # 先检查是否已在运行
    try:
        r = requests.get(f"{BACKEND_HOST}/health", timeout=5)
        if r.status_code == 200:
            # 后端已运行
            proc = None
            try:
                r2 = requests.get(f"{BACKEND_HOST}/api/train", timeout=5)
            except:
                pass
            yield None
            return
    except requests.exceptions.RequestException:
        pass

    # 尝试从项目根目录启动后端
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 查找后端入口文件
    for candidate in ["main.py", "app/main.py", "run.py"]:
        backend_path = os.path.join(root, candidate)
        if os.path.exists(backend_path):
            break
    else:
        # 找不到后端入口，跳过测试
        pytest.skip("Backend entry point not found")

    # 启动后端
    env = os.environ.copy()
    env["HOST"] = "0.0.0.0"
    env["PORT"] = "8000"
    proc = subprocess.Popen(
        [sys.executable, backend_path],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    wait_for_backend()
    yield proc

    # 清理
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="module")
def auth_token(backend_process):
    """获取认证 token"""
    # 注册一个测试用户
    import uuid
    username = f"test_curves_{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{API_BASE}/auth/register",
        json={"username": username, "password": "test123456"},
        timeout=10,
    )
    assert r.status_code == 200, f"Register failed: {r.text}"
    data = r.json()

    # 登录
    r = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": username, "password": "test123456"},
        timeout=10,
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return token


def test_metrics_curve_structure(backend_process, auth_token):
    """
    验证 metrics_curve 字段存在且结构正确。

    步骤：
    1. 上传一个 CSV 文件
    2. 创建训练任务
    3. 轮询 /api/train/{id}/status 直到 completed
    4. 验证 metrics_curve 字段存在
    5. 验证结构包含：epochs, train_loss, val_loss, train_accuracy, val_accuracy
    6. 验证所有数组长度一致
    """
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 1. 上传 CSV 文件
    csv_path = find_csv_file()
    if csv_path is None:
        pytest.skip("No CSV test file found in tests/")

    with open(csv_path, "rb") as f:
        r = requests.post(
            f"{API_BASE}/data/upload",
            files={"file": ("test.csv", f, "text/csv")},
            headers=headers,
            timeout=30,
        )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    file_data = r.json()
    file_id = file_data.get("id")
    assert file_id is not None, f"No file id in response: {file_data}"

    # 获取列信息
    r = requests.get(f"{API_BASE}/data/{file_id}/stats", headers=headers, timeout=10)
    assert r.status_code == 200, f"Stats failed: {r.text}"
    columns = r.json().get("columns", [])
    assert len(columns) >= 2, f"Not enough columns: {columns}"
    target_column = columns[-1]
    feature_columns = columns[:-1]

    # 2. 创建训练任务
    r = requests.post(
        f"{API_BASE}/train",
        json={
            "data_file_id": file_id,
            "target_column": target_column,
            "task_type": "classification",
            "model_type": "sklearn",
            "model_name": "RandomForestClassifier",
            "feature_columns": feature_columns,
        },
        headers=headers,
        timeout=10,
    )
    assert r.status_code == 200, f"Create train failed: {r.text}"
    job = r.json()
    job_id = job["id"]
    assert job["status"] in ("pending", "running"), f"Unexpected initial status: {job['status']}"

    # 3. 轮询直到完成（或超时）
    max_wait = 120  # 最多等 2 分钟
    start = time.time()
    metrics_curve = None

    while time.time() - start < max_wait:
        r = requests.get(f"{API_BASE}/train/{job_id}/status", headers=headers, timeout=10)
        assert r.status_code == 200, f"Status check failed: {r.text}"
        status_data = r.json()

        if status_data["status"] == "completed":
            metrics_curve = status_data.get("metrics_curve")
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"Training failed: {status_data.get('logs', '')}")

        time.sleep(2)

    assert metrics_curve is not None, (
        f"metrics_curve not found in completed status response: {status_data}"
    )

    # 4. 验证字段存在
    required_fields = ["epochs", "train_loss", "val_loss", "train_accuracy", "val_accuracy"]
    for field in required_fields:
        assert field in metrics_curve, f"Missing field '{field}' in metrics_curve: {metrics_curve}"
        assert isinstance(metrics_curve[field], list), (
            f"Field '{field}' should be a list, got {type(metrics_curve[field])}"
        )

    # 5. 验证所有数组长度一致
    lengths = [len(metrics_curve[field]) for field in required_fields]
    assert len(set(lengths)) == 1, (
        f"Array lengths mismatch: {dict(zip(required_fields, lengths))}"
    )
    assert lengths[0] > 0, "Curves arrays should not be empty"

    # 6. 验证数值合理性（epoch 从 1 开始递增，指标为数字）
    epochs = metrics_curve["epochs"]
    assert epochs == list(range(1, len(epochs) + 1)), f"Epochs should be 1-indexed: {epochs}"

    for field in required_fields:
        for val in metrics_curve[field]:
            assert isinstance(val, (int, float)), (
                f"Non-numeric value in '{field}': {val}"
            )


def test_metrics_curve_schema_fields():
    """
    单元测试：验证 metrics_curve 数据结构符合前端需求。
    """
    # 模拟后端返回的数据结构
    mock_curve = {
        "epochs": [1, 2, 3, 4, 5],
        "train_loss": [0.9231, 0.7123, 0.5432, 0.4123, 0.3210],
        "val_loss": [0.9543, 0.7654, 0.6123, 0.4987, 0.4102],
        "train_accuracy": [0.5123, 0.6543, 0.7654, 0.8234, 0.8765],
        "val_accuracy": [0.4890, 0.6234, 0.7123, 0.7890, 0.8456],
    }

    required_fields = ["epochs", "train_loss", "val_loss", "train_accuracy", "val_accuracy"]
    for field in required_fields:
        assert field in mock_curve

    lengths = [len(mock_curve[f]) for f in required_fields]
    assert len(set(lengths)) == 1, f"Length mismatch: {lengths}"
