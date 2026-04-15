"""
Pipeline DSL 解析器

支持 JSON 和 YAML 两种 DSL 格式，解析后验证 DAG 结构。
"""
from __future__ import annotations
import json
import logging
from typing import Any
from pydantic import BaseModel, Field, field_validator
from networkx import DiGraph, NetworkXError, topological_sort as nx_toposort

logger = logging.getLogger("mlkit.pipeline.dsl")

# =============================================================================
# DSL Schema（Pydantic 验证）
# =============================================================================

VALID_STEP_TYPES = {
    "preprocessing",
    "feature_engineering",
    "training",
    "automl",
    "evaluation",
    "model_registration",
}


class PipelineStep(BaseModel):
    """Pipeline DSL 步骤定义"""
    name: str = Field(..., min_length=1, max_length=100, description="步骤名称（唯一）")
    type: str = Field(..., description="步骤类型")
    config: dict[str, Any] = Field(default_factory=dict, description="步骤配置参数")
    depends_on: list[str] = Field(default_factory=list, description="依赖的步骤名列表")
    timeout_seconds: int | None = Field(default=None, ge=1, le=7200, description="超时秒数")
    max_retries: int | None = Field(default=None, ge=0, le=5, description="最大重试次数")

    @field_validator("type")
    @classmethod
    def validate_step_type(cls, v: str) -> str:
        if v not in VALID_STEP_TYPES:
            raise ValueError(
                f"不支持的步骤类型 '{v}'，支持：{sorted(VALID_STEP_TYPES)}"
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(
                "步骤名称只能包含字母、数字、下划线，且不能以数字开头"
            )
        return v


class PipelineDSL(BaseModel):
    """Pipeline DSL 根结构"""
    steps: list[PipelineStep] = Field(..., min_length=1, description="步骤列表（至少一个）")

    @field_validator("steps")
    @classmethod
    def validate_unique_names(cls, v: list[PipelineStep]) -> list[PipelineStep]:
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            raise ValueError("步骤名称不能重复")
        return v


class DAGValidationError(Exception):
    """DSL / DAG 验证错误"""
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


# =============================================================================
# DSL 解析入口
# =============================================================================

def parse_dsl(
    content: str,
    fmt: str = "json",
) -> PipelineDSL:
    """
    解析 DSL 内容（JSON 或 YAML），返回 PipelineDSL 对象。

    Args:
        content: DSL 文本内容
        fmt:    格式，json 或 yaml

    Returns:
        PipelineDSL 实例

    Raises:
        DAGValidationError: DSL 格式或语义错误
    """
    if fmt not in ("json", "yaml"):
        raise DAGValidationError(f"不支持的 DSL 格式 '{fmt}'，支持 json / yaml")

    try:
        if fmt == "json":
            data = json.loads(content)
        else:
            try:
                import yaml
            except ImportError:
                raise DAGValidationError("YAML 解析需要 pyyaml 库，请运行: pip install pyyaml")
            data = yaml.safe_load(content)

    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise DAGValidationError(f"DSL 内容解析失败（{fmt} 格式错误）: {e}")

    if not isinstance(data, dict):
        raise DAGValidationError("DSL 根对象必须是字典")

    if "steps" not in data:
        raise DAGValidationError("DSL 必须包含 'steps' 字段")

    # Pydantic 验证（会抛出 ValidationError → 包装为 DAGValidationError）
    try:
        dsl = PipelineDSL(**data)
    except Exception as e:
        raise DAGValidationError(f"DSL 语义验证失败: {e}")

    # 验证依赖引用的步骤名是否存在于 steps 中
    step_names = {s.name for s in dsl.steps}
    for step in dsl.steps:
        for dep in step.depends_on:
            if dep not in step_names:
                raise DAGValidationError(
                    f"步骤 '{step.name}' 的依赖 '{dep}' 不存在，请检查 depends_on"
                )

    return dsl


def validate_dag(dsl: PipelineDSL) -> tuple[DiGraph, list[str]]:
    """
    验证 DSL 是否形成有向无环图（DAG），并返回拓扑排序结果。

    Args:
        dsl: 已解析的 PipelineDSL

    Returns:
        (DiGraph, 拓扑排序列表)

    Raises:
        DAGValidationError: 存在循环依赖
    """
    graph = DiGraph()

    # 添加节点
    for step in dsl.steps:
        graph.add_node(
            step.name,
            type=step.type,
            config=step.config,
            timeout_seconds=step.timeout_seconds,
            max_retries=step.max_retries,
        )

    # 添加边（source → target 表示 source 执行完后才能执行 target）
    for step in dsl.steps:
        for dep in step.depends_on:
            graph.add_edge(dep, step.name)

    # 检测循环依赖
    try:
        topo_order = list(nx_toposort(graph))
    except NetworkXError as e:
        raise DAGValidationError(
            f"DSL 存在循环依赖，无法形成 DAG: {e}",
            errors=[str(e)],
        )

    return graph, topo_order


def validate_dsl(content: str, fmt: str = "json") -> PipelineDSL:
    """
    解析 + 验证 DSL（格式 + 语义 + DAG）。

    Returns:
        验证通过的 PipelineDSL 对象

    Raises:
        DAGValidationError: 任何验证失败
    """
    dsl = parse_dsl(content, fmt)
    graph, topo_order = validate_dag(dsl)
    logger.info(
        f"[DSL] 验证通过，steps={len(dsl.steps)}，拓扑序={topo_order}"
    )
    return dsl


def dsl_to_json_schema() -> dict[str, Any]:
    """
    返回 Pipeline DSL 的 JSON Schema（供前端 DSL 编辑器使用）。
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "PipelineDSL",
        "type": "object",
        "required": ["steps"],
        "properties": {
            "steps": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name", "type"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
                            "maxLength": 100,
                        },
                        "type": {
                            "type": "string",
                            "enum": list(VALID_STEP_TYPES),
                        },
                        "config": {"type": "object"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 7200,
                        },
                        "max_retries": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 5,
                        },
                    },
                },
            },
        },
    }
