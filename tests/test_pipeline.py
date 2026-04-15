# -*- coding: utf-8 -*-
"""
Pipeline Orchestration 模块测试
覆盖 Pipeline CRUD、DAG 执行、失败处理、版本管理、Cron 调度。

≥10 个测试用例，使用 @pytest.mark.asyncio 风格。
"""
import os
import sys
import json
import uuid
from datetime import datetime, timezone as dt_tz
from unittest.mock import MagicMock, patch, AsyncMock
from copy import deepcopy
import pytest

# 路径配置
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'api'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_pipeline"
os.environ["MLKIT_JWT_SECRET"] = "test_secret_pipeline"


# =============================================================================
# DSL Fixtures（共享的 DSL 样本）
# =============================================================================

MINIMAL_DSL_JSON = json.dumps({
    "steps": [
        {
            "name": "preprocess",
            "type": "preprocessing",
            "config": {"dataset_path": "/data/train.csv"},
        }
    ]
})

LINEAR_DSL_JSON = json.dumps({
    "steps": [
        {
            "name": "preprocess",
            "type": "preprocessing",
            "config": {"dataset_path": "/data/train.csv"},
        },
        {
            "name": "train",
            "type": "training",
            "config": {"model_type": "random_forest"},
            "depends_on": ["preprocess"],
        },
        {
            "name": "eval",
            "type": "evaluation",
            "config": {"metrics": ["accuracy"]},
            "depends_on": ["train"],
        },
    ]
})

BRANCH_DSL_JSON = json.dumps({
    "steps": [
        {
            "name": "preprocess",
            "type": "preprocessing",
            "config": {"dataset_path": "/data/train.csv"},
        },
        {
            "name": "train_rf",
            "type": "training",
            "config": {"model_type": "random_forest"},
            "depends_on": ["preprocess"],
        },
        {
            "name": "train_xgb",
            "type": "training",
            "config": {"model_type": "xgboost"},
            "depends_on": ["preprocess"],
        },
        {
            "name": "eval",
            "type": "evaluation",
            "config": {"metrics": ["accuracy"]},
            "depends_on": ["train_rf", "train_xgb"],
        },
    ]
})

CYCLE_DSL_JSON = json.dumps({
    "steps": [
        {
            "name": "step_a",
            "type": "preprocessing",
            "config": {},
            "depends_on": ["step_b"],
        },
        {
            "name": "step_b",
            "type": "preprocessing",
            "config": {},
            "depends_on": ["step_a"],
        },
    ]
})

INVALID_STEP_TYPE_DSL_JSON = json.dumps({
    "steps": [
        {
            "name": "bad_step",
            "type": "not_a_real_type",
            "config": {},
        }
    ]
})

DUPLICATE_NAME_DSL_JSON = json.dumps({
    "steps": [
        {"name": "dup", "type": "preprocessing", "config": {}},
        {"name": "dup", "type": "training", "config": {}},
    ]
})


# =============================================================================
# App Fixture（参考 test_scheduler.py）
# =============================================================================

@pytest.fixture
def app():
    """构建 FastAPI 测试应用（含 pipeline 相关表）"""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from api.database import Base as DBBase
    # Import pipeline models to register them with Base.metadata
    from src.mlkit.pipeline.models import Pipeline, PipelineVersion, PipelineRun, PipelineStepRun

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    DBBase.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(bind=engine)
    db_session = TestingSession()

    # 创建测试用户
    from api.database import User
    user = User(
        id=1,
        username="pipeline_test_user",
        email="pipeline_test@example.com",
        password_hash="dummy_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()

    # 构建 FastAPI 应用
    from api.main import app as fastapi_app
    from api.auth import get_current_user
    from api.database import get_db

    def override_get_current_user():
        u = MagicMock()
        u.id = 1
        u.username = "pipeline_test_user"
        u.email = "pipeline_test@example.com"
        u.role = "user"
        return u

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_current_user] = override_get_current_user
    fastapi_app.dependency_overrides[get_db] = override_get_db

    client = TestClient(fastapi_app)
    client.db = db_session
    client.engine = engine
    return client


# =============================================================================
# T1: Pipeline CRUD
# =============================================================================

class TestPipelineCRUD:
    """Pipeline 创建/列表/详情/更新/删除"""

    def test_create_pipeline_success(self, app):
        """T1.1: 创建 Pipeline 成功"""
        response = app.post("/api/pipelines", json={
            "name": "test-pipeline-001",
            "description": "端到端测试 Pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
            "status": "draft",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-pipeline-001"
        assert data["version"] == 1
        assert data["dsl_format"] == "json"
        assert data["status"] == "draft"
        assert data["schedule_enabled"] is False

    def test_create_pipeline_duplicate_name(self, app):
        """T1.2: 重复名称返回 409"""
        app.post("/api/pipelines", json={
            "name": "duplicate-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        response = app.post("/api/pipelines", json={
            "name": "duplicate-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        assert response.status_code == 409

    def test_create_pipeline_name_traversal_blocked(self, app):
        """T1.3: Pipeline 名称含路径分隔符被拒绝"""
        response = app.post("/api/pipelines", json={
            "name": "bad/../name",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        assert response.status_code == 400
        assert "路径分隔符" in response.json()["detail"]

    def test_create_pipeline_invalid_dsl(self, app):
        """T1.4: 无效 DSL 返回 400"""
        response = app.post("/api/pipelines", json={
            "name": "bad-dsl-pipeline",
            "dsl_content": "not valid json",
            "dsl_format": "json",
        })
        assert response.status_code == 400
        assert "DSL 验证失败" in response.json()["detail"]

    def test_create_pipeline_cycle_detected(self, app):
        """T1.5: 循环依赖 DSL 被拒绝"""
        response = app.post("/api/pipelines", json={
            "name": "cycle-pipeline",
            "dsl_content": CYCLE_DSL_JSON,
            "dsl_format": "json",
        })
        assert response.status_code == 400
        assert "循环" in response.json()["detail"]

    def test_create_pipeline_invalid_step_type(self, app):
        """T1.6: 非法步骤类型被拒绝"""
        response = app.post("/api/pipelines", json={
            "name": "bad-type-pipeline",
            "dsl_content": INVALID_STEP_TYPE_DSL_JSON,
            "dsl_format": "json",
        })
        assert response.status_code == 400

    def test_create_pipeline_duplicate_step_names(self, app):
        """T1.7: 重复步骤名被拒绝"""
        response = app.post("/api/pipelines", json={
            "name": "dup-names-pipeline",
            "dsl_content": DUPLICATE_NAME_DSL_JSON,
            "dsl_format": "json",
        })
        assert response.status_code == 400

    def test_list_pipelines_empty(self, app):
        """T1.8: 空列表返回 200"""
        response = app.get("/api/pipelines")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_list_pipelines_pagination(self, app):
        """T1.9: 列表分页"""
        for i in range(3):
            app.post("/api/pipelines", json={
                "name": f"pagination-test-{i}",
                "dsl_content": MINIMAL_DSL_JSON,
                "dsl_format": "json",
            })
        response = app.get("/api/pipelines?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["total"] >= 3
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_list_pipelines_filter_by_name(self, app):
        """T1.10: 按名称关键词搜索"""
        app.post("/api/pipelines", json={
            "name": "unique-searchable-name-xyz",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        response = app.get("/api/pipelines?q=unique-searchable")
        assert response.status_code == 200
        data = response.json()
        assert any("unique-searchable" in p["name"] for p in data["data"])

    def test_get_pipeline_success(self, app):
        """T1.11: 获取单个 Pipeline"""
        create_resp = app.post("/api/pipelines", json={
            "name": "get-test-pipeline",
            "description": "详情测试",
            "dsl_content": LINEAR_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.get(f"/api/pipelines/{pipeline_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pipeline_id
        assert data["name"] == "get-test-pipeline"
        assert data["description"] == "详情测试"
        assert data["version"] == 1

    def test_get_pipeline_not_found(self, app):
        """T1.12: 获取不存在的 Pipeline 返回 404"""
        response = app.get("/api/pipelines/99999")
        assert response.status_code == 404

    def test_update_pipeline_description_only(self, app):
        """T1.13: 仅更新描述（不触发版本递增）"""
        create_resp = app.post("/api/pipelines", json={
            "name": "update-desc-pipeline",
            "description": "原描述",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.patch(f"/api/pipelines/{pipeline_id}", json={
            "description": "新描述",
        })
        assert response.status_code == 200
        assert response.json()["description"] == "新描述"
        assert response.json()["version"] == 1  # 版本不变

    def test_update_pipeline_dsl_increments_version(self, app):
        """T1.14: 更新 DSL 内容触发版本递增"""
        create_resp = app.post("/api/pipelines", json={
            "name": "version-bump-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        new_dsl = json.dumps({
            "steps": [
                {"name": "preprocess", "type": "preprocessing",
                 "config": {"dataset_path": "/data/v2.csv"}},
            ]
        })
        response = app.patch(f"/api/pipelines/{pipeline_id}", json={
            "dsl_content": new_dsl,
            "changelog": "更新数据集路径",
        })
        assert response.status_code == 200
        assert response.json()["version"] == 2

    def test_update_pipeline_not_found(self, app):
        """T1.15: 更新不存在的 Pipeline 返回 404"""
        response = app.patch("/api/pipelines/99999", json={
            "description": "新描述",
        })
        assert response.status_code == 404

    def test_delete_pipeline_success(self, app):
        """T1.16: 软删除 Pipeline"""
        create_resp = app.post("/api/pipelines", json={
            "name": "delete-test-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.delete(f"/api/pipelines/{pipeline_id}")
        assert response.status_code == 204

        # 再次 GET 应该 404
        get_resp = app.get(f"/api/pipelines/{pipeline_id}")
        assert get_resp.status_code == 404

    def test_delete_pipeline_not_found(self, app):
        """T1.17: 删除不存在的 Pipeline 返回 404"""
        response = app.delete("/api/pipelines/99999")
        assert response.status_code == 404


# =============================================================================
# T2: DAG 执行
# =============================================================================

class TestDAGExecution:
    """DAG 拓扑排序、依赖解析、并行执行"""

    def test_validate_linear_dag_topo_sort(self):
        """T2.1: 线性 DAG 拓扑排序正确"""
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag

        dsl = parse_dsl(LINEAR_DSL_JSON, "json")
        graph, topo_order = validate_dag(dsl)

        # 顺序必须是 preprocess → train → eval
        assert topo_order.index("preprocess") < topo_order.index("train")
        assert topo_order.index("train") < topo_order.index("eval")

    def test_validate_branch_dag_topo_sort(self):
        """T2.2: 分支 DAG 拓扑排序正确（preprocess 优先）"""
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag

        dsl = parse_dsl(BRANCH_DSL_JSON, "json")
        graph, topo_order = validate_dag(dsl)

        # preprocess 必须在所有子节点之前
        assert topo_order[0] == "preprocess"
        # train_rf 和 train_xgb 必须在 eval 之前
        assert topo_order.index("train_rf") < topo_order.index("eval")
        assert topo_order.index("train_xgb") < topo_order.index("eval")

    def test_validate_cycle_dag_raises(self):
        """T2.3: 循环依赖抛出 DAGValidationError"""
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag, DAGValidationError

        dsl = parse_dsl(CYCLE_DSL_JSON, "json")
        with pytest.raises(DAGValidationError) as exc_info:
            validate_dag(dsl)
        assert "循环" in str(exc_info.value) or "cycle" in str(exc_info.value).lower()

    def test_parse_dsl_missing_steps_field(self):
        """T2.4: DSL 缺少 steps 字段抛出错误"""
        from src.mlkit.pipeline.dsl import parse_dsl, DAGValidationError

        bad = json.dumps({"wrong_field": []})
        with pytest.raises(DAGValidationError):
            parse_dsl(bad, "json")

    def test_parse_dsl_invalid_json(self):
        """T2.5: 非 JSON 内容抛出解析错误"""
        from src.mlkit.pipeline.dsl import parse_dsl, DAGValidationError

        with pytest.raises(DAGValidationError):
            parse_dsl("not json at all {{{", "json")

    def test_depends_on_nonexistent_step_raises(self):
        """T2.6: 引用不存在的步骤名抛出错误"""
        from src.mlkit.pipeline.dsl import DAGValidationError

        bad_dsl = json.dumps({
            "steps": [
                {"name": "parent", "type": "preprocessing", "config": {}},
                {"name": "child", "type": "training", "config": {},
                 "depends_on": ["nonexistent_step"]},
            ]
        })
        from src.mlkit.pipeline.dsl import parse_dsl
        with pytest.raises(DAGValidationError) as exc_info:
            parse_dsl(bad_dsl, "json")
        assert "不存在" in str(exc_info.value) or "nonexistent" in str(exc_info.value).lower()

    def test_graph_contains_all_steps_as_nodes(self):
        """T2.7: DAG 包含所有步骤作为节点"""
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag

        dsl = parse_dsl(BRANCH_DSL_JSON, "json")
        graph, topo_order = validate_dag(dsl)

        assert set(graph.nodes) == {"preprocess", "train_rf", "train_xgb", "eval"}

    def test_graph_edges_reflect_depends_on(self):
        """T2.8: DAG 边反映 depends_on 关系"""
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag

        dsl = parse_dsl(BRANCH_DSL_JSON, "json")
        graph, topo_order = validate_dag(dsl)

        edges = list(graph.edges)
        # preprocess → train_rf
        assert ("preprocess", "train_rf") in edges
        # preprocess → train_xgb
        assert ("preprocess", "train_xgb") in edges
        # train_rf → eval, train_xgb → eval
        assert ("train_rf", "eval") in edges
        assert ("train_xgb", "eval") in edges

    def test_dsl_json_schema_generated(self):
        """T2.9: DSL JSON Schema 可正常生成"""
        from src.mlkit.pipeline.dsl import dsl_to_json_schema

        schema = dsl_to_json_schema()
        assert schema["title"] == "PipelineDSL"
        assert "steps" in schema["properties"]
        assert "type" in schema["properties"]["steps"]["items"]["properties"]


# =============================================================================
# T3: 失败处理
# =============================================================================

class TestFailureHandling:
    """步骤失败状态传播、超时处理"""

    def test_step_status_enum_completeness(self):
        """T3.1: StepStatus 包含所有预期状态"""
        from src.mlkit.pipeline.models import StepStatus

        assert StepStatus.PENDING is not None
        assert StepStatus.RUNNING is not None
        assert StepStatus.SUCCESS is not None
        assert StepStatus.FAILED is not None
        assert StepStatus.SKIPPED is not None
        assert StepStatus.TIMEOUT is not None

    def test_run_status_enum_completeness(self):
        """T3.2: RunStatus 包含所有预期状态"""
        from src.mlkit.pipeline.models import RunStatus

        assert RunStatus.PENDING is not None
        assert RunStatus.RUNNING is not None
        assert RunStatus.SUCCESS is not None
        assert RunStatus.FAILED is not None
        assert RunStatus.TIMEOUT is not None
        assert RunStatus.CANCELLED is not None

    def test_step_execution_error_carries_step_name(self):
        """T3.3: StepExecutionError 包含步骤名"""
        from src.mlkit.pipeline.engine import StepExecutionError

        err = StepExecutionError("preprocess_step", "参数缺失")
        assert err.step_name == "preprocess_step"
        assert "preprocess_step" in str(err)

    def test_depends_on_failed_step_returns_true(self):
        """T3.4: _depends_on_failed 对直接依赖返回 True"""
        from src.mlkit.pipeline.engine import PipelineEngine
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag
        import networkx as nx

        dsl = parse_dsl(LINEAR_DSL_JSON, "json")
        graph, _ = validate_dag(dsl)

        engine = PipelineEngine(db_session_factory=MagicMock())
        assert engine._depends_on_failed(graph, "train", "preprocess") is True

    def test_depends_on_failed_indirect_returns_true(self):
        """T3.5: _depends_on_failed 对间接依赖返回 True"""
        from src.mlkit.pipeline.engine import PipelineEngine
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag

        dsl = parse_dsl(LINEAR_DSL_JSON, "json")
        graph, _ = validate_dag(dsl)

        engine = PipelineEngine(db_session_factory=MagicMock())
        # eval 间接依赖 preprocess（通过 train）
        assert engine._depends_on_failed(graph, "eval", "preprocess") is True

    def test_depends_on_unrelated_step_returns_false(self):
        """T3.6: 无依赖关系的步骤返回 False"""
        from src.mlkit.pipeline.engine import PipelineEngine
        from src.mlkit.pipeline.dsl import parse_dsl, validate_dag

        # 构造两个无关联的步骤
        separate_dsl = json.dumps({
            "steps": [
                {"name": "step_a", "type": "preprocessing", "config": {}},
                {"name": "step_b", "type": "training", "config": {}},
            ]
        })
        dsl = parse_dsl(separate_dsl, "json")
        graph, _ = validate_dag(dsl)

        engine = PipelineEngine(db_session_factory=MagicMock())
        assert engine._depends_on_failed(graph, "step_b", "step_a") is False

    def test_pipeline_status_reflects_step_failure(self):
        """T3.7: PipelineRun 状态反映步骤失败"""
        from src.mlkit.pipeline.models import PipelineRun, RunStatus, TriggerType

        run = PipelineRun(
            id=1,
            pipeline_id=1,
            pipeline_version=1,
            run_number=1,
            status=RunStatus.FAILED,
            triggered_by=TriggerType.MANUAL,
            error_message="步骤 'preprocess' 执行失败",
        )
        assert run.status == RunStatus.FAILED
        assert "preprocess" in run.error_message

    def test_timeout_status_on_step_record(self):
        """T3.8: 超时步骤记录状态为 TIMEOUT"""
        from src.mlkit.pipeline.models import PipelineStepRun, StepStatus

        step_run = PipelineStepRun(
            id=1,
            run_id=1,
            step_name="slow_step",
            step_type="preprocessing",
            status=StepStatus.TIMEOUT,
            order_index=0,
            error_message="步骤执行超时（3600s）",
        )
        assert step_run.status == StepStatus.TIMEOUT
        assert "超时" in step_run.error_message


# =============================================================================
# T4: 版本管理
# =============================================================================

class TestVersionManagement:
    """Pipeline 版本快照创建与历史查询"""

    def test_version_response_structure(self, app):
        """T4.1: 创建 Pipeline 后自动生成 v1 快照"""
        create_resp = app.post("/api/pipelines", json={
            "name": "version-test-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.get(f"/api/pipelines/{pipeline_id}/versions")
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 1
        assert versions[0]["version"] == 1
        assert versions[0]["changelog"] == "初始版本"

    def test_version_increments_on_dsl_update(self, app):
        """T4.2: 更新 DSL 后版本递增"""
        create_resp = app.post("/api/pipelines", json={
            "name": "version-bump-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        # 第一次更新 DSL
        new_dsl = json.dumps({
            "steps": [
                {"name": "preprocess", "type": "preprocessing",
                 "config": {"dataset_path": "/data/v2.csv"}},
            ]
        })
        app.patch(f"/api/pipelines/{pipeline_id}", json={
            "dsl_content": new_dsl,
            "changelog": "更新数据集",
        })

        versions_response = app.get(f"/api/pipelines/{pipeline_id}/versions")
        versions = versions_response.json()
        assert len(versions) == 2
        assert versions[0]["version"] == 2  # 最新版本在前
        assert versions[1]["version"] == 1

    def test_get_specific_version(self, app):
        """T4.3: 获取指定版本内容"""
        create_resp = app.post("/api/pipelines", json={
            "name": "specific-version-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.get(f"/api/pipelines/{pipeline_id}/versions/1")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
        assert data["dsl_format"] == "json"

    def test_get_nonexistent_version_returns_404(self, app):
        """T4.4: 获取不存在的版本返回 404"""
        create_resp = app.post("/api/pipelines", json={
            "name": "no-version-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.get(f"/api/pipelines/{pipeline_id}/versions/99")
        assert response.status_code == 404

    def test_version_changelog_is_saved(self, app):
        """T4.5: 版本变更说明被正确保存"""
        create_resp = app.post("/api/pipelines", json={
            "name": "changelog-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        new_dsl = json.dumps({
            "steps": [
                {"name": "preprocess", "type": "preprocessing",
                 "config": {"dataset_path": "/data/v3.csv"}},
            ]
        })
        app.patch(f"/api/pipelines/{pipeline_id}", json={
            "dsl_content": new_dsl,
            "changelog": "修复数据集路径 bug",
        })

        versions_response = app.get(f"/api/pipelines/{pipeline_id}/versions")
        versions = versions_response.json()
        v2 = next(v for v in versions if v["version"] == 2)
        assert v2["changelog"] == "修复数据集路径 bug"

    def test_version_unique_constraint(self, app):
        """T4.6: pipeline_id + version 唯一约束"""
        from src.mlkit.pipeline.models import PipelineVersion

        # 同一个 pipeline_id 和 version 不能重复
        from sqlalchemy.exc import IntegrityError
        # 验证模型层面约束存在（通过 DB 层面测试）
        # 这里验证 PipelineVersion 有 UniqueConstraint 定义
        constraints = [c.name for c in PipelineVersion.__table__.constraints]
        assert "uq_pipeline_version" in constraints


# =============================================================================
# T5: Cron 调度配置
# =============================================================================

class TestCronScheduling:
    """Pipeline Cron 调度配置创建/更新/删除"""

    def test_get_schedule_empty_by_default(self, app):
        """T5.1: 新 Pipeline 默认无调度配置"""
        create_resp = app.post("/api/pipelines", json={
            "name": "no-schedule-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.get(f"/api/pipelines/{pipeline_id}/schedule")
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == pipeline_id
        assert data["schedule_cron"] is None
        assert data["schedule_enabled"] is True  # 默认 True

    def test_set_schedule_success(self, app):
        """T5.2: 设置调度配置成功"""
        create_resp = app.post("/api/pipelines", json={
            "name": "schedule-test-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.post(f"/api/pipelines/{pipeline_id}/schedule", json={
            "cron_expression": "0 8 * * *",
            "is_enabled": True,
            "timeout_seconds": 3600,
            "auto_retry": False,
            "retry_count": 0,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == pipeline_id
        assert data["schedule_cron"] == "0 8 * * *"
        assert data["schedule_enabled"] is True

    def test_set_schedule_missing_cron_raises(self, app):
        """T5.3: 未提供 cron_expression 返回 400"""
        create_resp = app.post("/api/pipelines", json={
            "name": "no-cron-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.post(f"/api/pipelines/{pipeline_id}/schedule", json={
            "is_enabled": True,
        })
        assert response.status_code == 400
        assert "cron_expression" in response.json()["detail"]

    def test_set_schedule_invalid_cron_raises(self, app):
        """T5.4: 无效 Cron 表达式返回 422"""
        create_resp = app.post("/api/pipelines", json={
            "name": "bad-cron-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.post(f"/api/pipelines/{pipeline_id}/schedule", json={
            "cron_expression": "not valid at all",
            "is_enabled": True,
        })
        assert response.status_code == 422

    def test_set_schedule_internal_webhook_blocked(self, app):
        """T5.5: 内网 Webhook URL 被拒绝"""
        create_resp = app.post("/api/pipelines", json={
            "name": "webhook-test-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.post(f"/api/pipelines/{pipeline_id}/schedule", json={
            "cron_expression": "0 8 * * *",
            "webhook_url": "http://localhost:8080/webhook",
        })
        assert response.status_code == 400
        assert "内网" in response.json()["detail"]

    def test_update_schedule_pause(self, app):
        """T5.6: 更新调度配置（暂停）"""
        create_resp = app.post("/api/pipelines", json={
            "name": "pause-test-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        # 先设置调度
        app.post(f"/api/pipelines/{pipeline_id}/schedule", json={
            "cron_expression": "0 8 * * *",
            "is_enabled": True,
        })

        # 暂停
        response = app.patch(f"/api/pipelines/{pipeline_id}/schedule", json={
            "is_enabled": False,
        })
        assert response.status_code == 200
        assert response.json()["schedule_enabled"] is False

    def test_update_schedule_no_existing_raises_404(self, app):
        """T5.7: 未配置调度的 Pipeline 更新返回 404"""
        create_resp = app.post("/api/pipelines", json={
            "name": "no-existing-schedule",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.patch(f"/api/pipelines/{pipeline_id}/schedule", json={
            "cron_expression": "0 9 * * *",
        })
        assert response.status_code == 404

    def test_delete_pipeline_removes_schedule(self, app):
        """T5.8: 删除 Pipeline 时移除调度关联"""
        create_resp = app.post("/api/pipelines", json={
            "name": "delete-schedule-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        app.post(f"/api/pipelines/{pipeline_id}/schedule", json={
            "cron_expression": "0 8 * * *",
            "is_enabled": True,
        })

        app.delete(f"/api/pipelines/{pipeline_id}")

        # Pipeline 已不存在，GET 应返回 404
        get_resp = app.get(f"/api/pipelines/{pipeline_id}")
        assert get_resp.status_code == 404


# =============================================================================
# T6: Run 管理
# =============================================================================

class TestRunManagement:
    """Pipeline Run 创建、列表、详情"""

    def test_trigger_run_success(self, app):
        """T6.1: 手动触发 Pipeline Run 成功"""
        create_resp = app.post("/api/pipelines", json={
            "name": "run-trigger-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.post(f"/api/pipelines/{pipeline_id}/run", json={
            "params": {"dataset_path": "/data/train.csv"},
            "triggered_by": "manual",
        })
        assert response.status_code == 202
        data = response.json()
        assert data["pipeline_id"] == pipeline_id
        assert data["status"] in ("pending", "running")
        assert data["run_number"] == 1

    def test_trigger_run_run_number_increments(self, app):
        """T6.2: 每次触发 run_number 递增"""
        create_resp = app.post("/api/pipelines", json={
            "name": "run-number-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        run1 = app.post(f"/api/pipelines/{pipeline_id}/run", json={}).json()
        run2 = app.post(f"/api/pipelines/{pipeline_id}/run", json={}).json()

        assert run2["run_number"] == run1["run_number"] + 1

    def test_list_runs_empty(self, app):
        """T6.3: 无 Run 时返回空列表"""
        create_resp = app.post("/api/pipelines", json={
            "name": "no-runs-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        response = app.get(f"/api/pipelines/{pipeline_id}/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_get_run_detail(self, app):
        """T6.4: 获取 Run 详情（含步骤列表）"""
        create_resp = app.post("/api/pipelines", json={
            "name": "run-detail-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        run_resp = app.post(f"/api/pipelines/{pipeline_id}/run", json={})
        run_id = run_resp.json()["id"]

        detail_resp = app.get(f"/api/pipelines/{pipeline_id}/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert "run" in detail
        assert "steps" in detail
        assert detail["run"]["id"] == run_id

    def test_cancel_run_success(self, app):
        """T6.5: 取消运行中的 Pipeline Run"""
        create_resp = app.post("/api/pipelines", json={
            "name": "cancel-run-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        run_resp = app.post(f"/api/pipelines/{pipeline_id}/run", json={})
        run_id = run_resp.json()["id"]

        cancel_resp = app.post(f"/api/pipelines/{pipeline_id}/runs/{run_id}/cancel")
        # 刚创建的 Run 状态为 pending，取消可能成功或 409（取决于并发时序）
        assert cancel_resp.status_code in (200, 409)

    def test_retry_run_creates_new_run(self, app):
        """T6.6: 重试 Run 创建新记录"""
        create_resp = app.post("/api/pipelines", json={
            "name": "retry-run-test",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        run_resp = app.post(f"/api/pipelines/{pipeline_id}/run", json={})
        run_id = run_resp.json()["id"]

        retry_resp = app.post(f"/api/pipelines/{pipeline_id}/runs/{run_id}/retry", json={
            "full_rerun": True,
        })
        assert retry_resp.status_code == 200
        new_run = retry_resp.json()
        assert new_run["run_number"] == 2

    def test_list_steps_for_run(self, app):
        """T6.7: 获取 Run 的所有步骤记录"""
        create_resp = app.post("/api/pipelines", json={
            "name": "list-steps-test",
            "dsl_content": LINEAR_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        run_resp = app.post(f"/api/pipelines/{pipeline_id}/run", json={})
        run_id = run_resp.json()["id"]

        steps_resp = app.get(f"/api/pipelines/{pipeline_id}/runs/{run_id}/steps")
        assert steps_resp.status_code == 200
        steps = steps_resp.json()
        assert isinstance(steps, list)

    def test_run_logs_endpoint(self, app):
        """T6.8: Run 日志端点返回格式正确"""
        create_resp = app.post("/api/pipelines", json={
            "name": "logs-test-pipeline",
            "dsl_content": MINIMAL_DSL_JSON,
            "dsl_format": "json",
        })
        pipeline_id = create_resp.json()["id"]

        run_resp = app.post(f"/api/pipelines/{pipeline_id}/run", json={})
        run_id = run_resp.json()["id"]

        logs_resp = app.get(f"/api/pipelines/{pipeline_id}/runs/{run_id}/logs")
        assert logs_resp.status_code == 200
        logs = logs_resp.json()
        assert "logs" in logs
        assert isinstance(logs["logs"], str)


# =============================================================================
# T7: DSL 验证辅助
# =============================================================================

class TestDSLValidationHelpers:
    """DSL 格式验证辅助函数"""

    def test_valid_step_name_pattern(self):
        """T7.1: 合法步骤名通过验证"""
        from src.mlkit.pipeline.dsl import PipelineStep

        step = PipelineStep(
            name="valid_step_name_123",
            type="preprocessing",
            config={},
        )
        assert step.name == "valid_step_name_123"

    def test_invalid_step_name_pattern_rejected(self):
        """T7.2: 非法步骤名（数字开头/含特殊字符）被拒绝"""
        from src.mlkit.pipeline.dsl import PipelineStep
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PipelineStep(name="123invalid", type="preprocessing", config={})

        with pytest.raises(ValidationError):
            PipelineStep(name="bad-name", type="preprocessing", config={})

    def test_timeout_and_retry_config(self):
        """T7.3: 超时和重试配置正确"""
        from src.mlkit.pipeline.dsl import PipelineStep

        step = PipelineStep(
            name="configured_step",
            type="training",
            config={},
            timeout_seconds=1800,
            max_retries=3,
        )
        assert step.timeout_seconds == 1800
        assert step.max_retries == 3

    def test_timeout_out_of_range_rejected(self):
        """T7.4: 超时超出范围（>7200s）被拒绝"""
        from src.mlkit.pipeline.dsl import PipelineStep
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PipelineStep(
                name="bad_timeout",
                type="training",
                config={},
                timeout_seconds=99999,
            )

    def test_max_retries_out_of_range_rejected(self):
        """T7.5: 重试次数超出范围（>5）被拒绝"""
        from src.mlkit.pipeline.dsl import PipelineStep
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PipelineStep(
                name="bad_retries",
                type="training",
                config={},
                max_retries=99,
            )


# =============================================================================
# T8: PipelineEngine 集成
# =============================================================================

class TestPipelineEngine:
    """PipelineEngine 核心逻辑测试"""

    def test_engine_initialization(self):
        """T8.1: PipelineEngine 正确初始化"""
        from src.mlkit.pipeline.engine import PipelineEngine, get_executor_registry

        def dummy_factory():
            return MagicMock()

        engine = PipelineEngine(dummy_factory)
        assert engine.db_factory is not None
        assert engine.executor_registry is get_executor_registry()

    def test_executor_registry_has_builtin_types(self):
        """T8.2: 执行器注册表包含内置步骤类型"""
        from src.mlkit.pipeline.engine import get_executor_registry

        registry = get_executor_registry()
        for step_type in ("preprocessing", "training", "evaluation",
                           "automl", "model_registration", "feature_engineering"):
            assert registry.get(step_type) is not None, f"Missing executor for {step_type}"

    def test_executor_registry_unknown_type_returns_none(self):
        """T8.3: 未知步骤类型返回 None"""
        from src.mlkit.pipeline.engine import get_executor_registry

        registry = get_executor_registry()
        assert registry.get("totally_fake_type") is None

    def test_execution_context_persists_outputs(self):
        """T8.4: ExecutionContext 跨步骤保留输出数据"""
        from src.mlkit.pipeline.engine import ExecutionContext

        ctx = ExecutionContext(
            run_id=1,
            pipeline_id=1,
            pipeline_version=1,
            params={"dataset_path": "/data/train.csv"},
        )
        ctx.step_outputs["preprocess"] = {"output_dataset_path": "/data/processed.csv"}

        assert "preprocess" in ctx.step_outputs
        assert ctx.step_outputs["preprocess"]["output_dataset_path"] == "/data/processed.csv"

    def test_cancelled_flag_works(self):
        """T8.5: ExecutionContext 取消标记可设置"""
        from src.mlkit.pipeline.engine import ExecutionContext

        ctx = ExecutionContext(
            run_id=1,
            pipeline_id=1,
            pipeline_version=1,
            params={},
        )
        assert ctx.cancelled is False
        ctx.cancelled = True
        assert ctx.cancelled is True

    def test_executor_registry_decorator_register(self):
        """T8.6: @register 装饰器正确注册执行器"""
        from src.mlkit.pipeline.engine import StepExecutorRegistry

        registry = StepExecutorRegistry()

        @registry.register("test_custom_type")
        async def my_executor(ctx, config):
            return {"result": "ok"}

        assert registry.get("test_custom_type") is not None
        assert registry.get("test_custom_type").__name__ == "my_executor"
