"""
E2E Inference 测试数据准备脚本

用途：在 Playwright E2E 测试运行前，准备好 inference.spec.ts 所需的数据：
1. 模型记录：RandomForestRegressor_job_23 (关联已存在的 models/job_23.joblib)
2. 数据文件：e2e_training_data.csv (用于数据集模式推理测试)

依赖：Python 3.8+, scikit-learn, pandas, numpy
用法（从项目根目录运行）：
    python scripts/seed_e2e_inference_data.py

也可以作为模块导入：
    from scripts.seed_e2e_inference_data import seed_e2e_inference_data
    seed_e2e_inference_data()
"""
import os
import sys
import csv
import math
import random
import sqlite3
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 从 .env 或环境变量获取 DB 路径（默认使用 ml_all_in_one.db）
DB_PATH = os.environ.get("DATABASE_PATH", str(PROJECT_ROOT / "ml_all_in_one.db"))
MODELS_DIR = os.environ.get("MODELS_DIR", str(PROJECT_ROOT / "models"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", str(PROJECT_ROOT / "uploads"))

# 硬编码：admin 用户 ID（从现有数据验证为 1）
ADMIN_USER_ID = 1

# 测试模型元数据
TEST_MODEL_NAME = "RandomForestRegressor_job_23"
TEST_MODEL_PATH = os.path.join(MODELS_DIR, "job_23.joblib")

# 测试数据文件元数据
TEST_DATA_FILENAME = "e2e_training_data.csv"


def _get_db_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_model_record(conn: sqlite3.Connection) -> dict:
    """
    确保 RandomForestRegressor_job_23 模型记录存在于数据库中。
    
    Returns:
        dict: {"action": "created"|"exists", "model_id": int}
    """
    cursor = conn.cursor()

    # 检查是否已存在
    cursor.execute(
        "SELECT id, name, model_path FROM trained_models WHERE name = ?",
        (TEST_MODEL_NAME,)
    )
    existing = cursor.fetchone()

    if existing:
        print(f"  ✅ 模型记录已存在: {existing['name']} (id={existing['id']})")
        return {"action": "exists", "model_id": existing["id"]}

    # 检查模型文件是否存在
    if not os.path.exists(TEST_MODEL_PATH):
        print(f"  ⚠️  模型文件不存在: {TEST_MODEL_PATH}")
        print(f"     尝试训练新模型...")

        # 训练一个新模型（使用合成数据 + feature_a/b/c/d）
        _train_rf_model(TEST_MODEL_PATH)

    # 获取文件大小
    file_size = os.path.getsize(TEST_MODEL_PATH)

    # 插入记录
    cursor.execute("""
        INSERT INTO trained_models
        (user_id, name, model_type, model_path, metrics, config, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        ADMIN_USER_ID,
        TEST_MODEL_NAME,
        "sklearn",
        TEST_MODEL_PATH,
        '{"r2": 0.85, "rmse": 0.42, "mae": 0.31}',
        '{"task_type": "regression", "model_name": "RandomForestRegressor"}',
    ))

    model_id = cursor.lastrowid
    conn.commit()

    print(f"  ✅ 创建模型记录: {TEST_MODEL_NAME} (id={model_id}, path={TEST_MODEL_PATH}, size={file_size} bytes)")
    return {"action": "created", "model_id": model_id}


def _seed_data_file_record(conn: sqlite3.Connection) -> dict:
    """
    确保 e2e_training_data.csv 记录存在于数据库中。
    同时确保文件物理存在。
    
    Returns:
        dict: {"action": "created"|"exists", "file_id": int}
    """
    cursor = conn.cursor()

    # 检查是否已存在
    cursor.execute(
        "SELECT id, filename, filepath FROM data_files WHERE filename = ? AND user_id = ?",
        (TEST_DATA_FILENAME, ADMIN_USER_ID)
    )
    existing = cursor.fetchone()

    if existing:
        # 检查物理文件是否存在
        if os.path.exists(existing["filepath"]):
            print(f"  ✅ 数据文件记录已存在: {existing['filename']} (id={existing['id']})")
            return {"action": "exists", "file_id": existing["id"]}
        else:
            print(f"  ⚠️  记录存在但文件丢失，重新创建: {existing['filename']}")
            cursor.execute("DELETE FROM data_files WHERE id = ?", (existing["id"],))

    # 创建物理 CSV 文件
    file_path = _create_e2e_csv()
    file_size = os.path.getsize(file_path)

    # 获取列信息
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        first_row = next(reader, None)

    import json
    dtypes = {}
    if first_row:
        for col in fieldnames:
            val = first_row.get(col, "")
            try:
                float(val)
                dtypes[col] = "float64"
            except (ValueError, TypeError):
                dtypes[col] = "object"

    row_count = sum(1 for _ in open(file_path)) - 1  # 减去 header

    cursor.execute("""
        INSERT INTO data_files
        (user_id, filename, filepath, size, rows, columns, dtypes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        ADMIN_USER_ID,
        TEST_DATA_FILENAME,
        file_path,
        file_size,
        row_count,
        json.dumps(fieldnames),
        json.dumps(dtypes),
    ))

    file_id = cursor.lastrowid
    conn.commit()

    print(f"  ✅ 创建数据文件记录: {TEST_DATA_FILENAME} (id={file_id}, path={file_path}, rows={row_count})")
    return {"action": "created", "file_id": file_id}


def _train_rf_model(output_path: str) -> None:
    """
    使用合成数据训练一个 RandomForestRegressor 模型，保存为 joblib 文件。
    特征名固定为 feature_a, feature_b, feature_c, feature_d。
    """
    import numpy as np
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

    print(f"  🔧 训练 RandomForestRegressor 模型...")

    rng = random.Random(42)
    n_samples = 200

    # 生成合成数据（固定随机种子保证可复现）
    X = np.array([
        [rng.gauss(0, 1) for _ in range(4)]
        for _ in range(n_samples)
    ], dtype=np.float64)

    # 目标变量：feature_a * 2 + feature_b * 1.5 + noise
    y = (
        X[:, 0] * 2.0
        + X[:, 1] * 1.5
        + X[:, 2] * 0.5
        + rng.gauss(0, 0.1)
    )

    # 训练/测试分割
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 训练模型
    model = RandomForestRegressor(
        n_estimators=50,
        max_depth=10,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 设置特征名（让推理时知道特征名）
    model.feature_names_in_ = np.array(
        ["feature_a", "feature_b", "feature_c", "feature_d"],
        dtype=object
    )

    # 评估
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = math.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    print(f"     训练完成: R²={r2:.4f}, RMSE={rmse:.4f}, MAE={mae:.4f}")

    # 保存
    joblib.dump(model, output_path)
    print(f"     已保存: {output_path}")


def _create_e2e_csv() -> str:
    """
    创建 e2e_training_data.csv 文件，包含 feature_a/b/c/d 列。
    放在 uploads/{ADMIN_USER_ID}/ 目录下。
    """
    user_dir = os.path.join(UPLOAD_DIR, str(ADMIN_USER_ID))
    os.makedirs(user_dir, exist_ok=True)

    file_path = os.path.join(user_dir, TEST_DATA_FILENAME)

    rng = random.Random(42)
    n_rows = 50

    rows = []
    for i in range(n_rows):
        feature_a = rng.uniform(-2, 2)
        feature_b = rng.uniform(-1, 3)
        feature_c = rng.uniform(0, 5)
        feature_d = rng.uniform(1, 4)
        # 目标变量（与模型训练一致）
        target = feature_a * 2.0 + feature_b * 1.5 + feature_c * 0.5 + rng.gauss(0, 0.1)
        rows.append({
            "feature_a": round(feature_a, 6),
            "feature_b": round(feature_b, 6),
            "feature_c": round(feature_c, 6),
            "feature_d": round(feature_d, 6),
            "target": round(target, 6),
        })

    fieldnames = ["feature_a", "feature_b", "feature_c", "feature_d", "target"]

    with open(file_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  ✅ 创建 CSV 文件: {file_path} ({n_rows} 行)")
    return file_path


def seed_e2e_inference_data() -> dict:
    """
    主函数：准备 E2E inference 测试所需的所有数据。
    
    Returns:
        dict: 执行摘要
    """
    print("=" * 60)
    print("E2E Inference 测试数据准备")
    print(f"  数据库: {DB_PATH}")
    print(f"  模型目录: {MODELS_DIR}")
    print(f"  上传目录: {UPLOAD_DIR}")
    print("=" * 60)

    conn = _get_db_connection()

    try:
        print("\n[1/2] 准备模型记录...")
        model_result = _seed_model_record(conn)

        print("\n[2/2] 准备数据文件记录...")
        data_result = _seed_data_file_record(conn)

        print("\n" + "=" * 60)
        print("✅ E2E Inference 数据准备完成")
        print(f"  模型: {TEST_MODEL_NAME} ({model_result['action']})")
        print(f"  数据: {TEST_DATA_FILENAME} ({data_result['action']})")
        print("=" * 60)

        return {
            "model": model_result,
            "data_file": data_result,
            "success": True,
        }

    except Exception as e:
        print(f"\n❌ 数据准备失败: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    seed_e2e_inference_data()
