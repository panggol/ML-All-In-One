"""
推理服务 API - Inference API

提供模型推理 RESTful 接口
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


@dataclass
class ModelInfo:
    """模型信息"""

    name: str
    model_type: str
    task_type: str  # classification, regression
    input_features: list[str]
    output_classes: list[str] | None = None
    version: str = "1.0.0"
    description: str = ""
    created_at: str = ""
    file_path: str = ""


class InferenceRequest(BaseModel):
    """推理请求"""

    data: list[list[float]] | list[dict[str, float]] = Field(
        ..., description="输入数据，支持 list 或 dict 格式"
    )
    return_proba: bool = Field(False, description="是否返回概率")


class InferenceResponse(BaseModel):
    """推理响应"""

    request_id: str
    predictions: list | Any
    probabilities: list | None = None
    model_info: dict[str, str]


class ModelRegistry:
    """模型注册表"""

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.models: dict[str, dict] = {}

    def register(
        self,
        name: str,
        model,
        model_type: str,
        task_type: str,
        input_features: list[str],
        output_classes: list[str] | None = None,
        description: str = "",
    ) -> str:
        """注册模型"""
        model_id = str(uuid.uuid4())[:8]

        model_info = ModelInfo(
            name=name,
            model_type=model_type,
            task_type=task_type,
            input_features=input_features,
            output_classes=output_classes,
            description=description,
            created_at=pd.Timestamp.now().isoformat(),
        )

        self.models[model_id] = {
            "model": model,
            "info": model_info,
            "model_id": model_id,
        }

        return model_id

    def get(self, model_id: str) -> dict:
        """获取模型"""
        if model_id not in self.models:
            raise KeyError(f"Model {model_id} not found")
        return self.models[model_id]

    def list(self) -> list[dict]:
        """列出所有模型"""
        return [
            {
                "model_id": model_id,
                "name": info["info"].name,
                "model_type": info["info"].model_type,
                "task_type": info["info"].task_type,
                "created_at": info["info"].created_at,
            }
            for model_id, info in self.models.items()
        ]

    def delete(self, model_id: str) -> bool:
        """删除模型"""
        if model_id in self.models:
            del self.models[model_id]
            return True
        return False


class InferenceEngine:
    """推理引擎"""

    def __init__(self, model_registry: ModelRegistry):
        self.registry = model_registry

    def predict(
        self,
        model_id: str,
        data: list | np.ndarray | pd.DataFrame,
        return_proba: bool = False,
    ) -> dict:
        """执行推理"""
        model_info = self.registry.get(model_id)
        model = model_info["model"]

        # 转换数据格式
        if isinstance(data, list):
            if isinstance(data[0], dict):
                X = pd.DataFrame(data)
            else:
                X = np.array(data)
        elif isinstance(data, np.ndarray):
            X = data
        elif isinstance(data, pd.DataFrame):
            X = data
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        # 执行预测
        predictions = model.predict(X)

        result = {
            "predictions": (
                predictions.tolist() if hasattr(predictions, "tolist") else predictions
            )
        }

        # 如果支持，返回概率
        if return_proba and hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(X)
            result["probabilities"] = (
                probabilities.tolist()
                if hasattr(probabilities, "tolist")
                else probabilities
            )

        return result


def create_inference_app(
    model_registry: ModelRegistry | None = None, model_dir: str = "./models"
) -> FastAPI:
    """创建推理服务 FastAPI 应用"""

    if model_registry is None:
        model_registry = ModelRegistry(model_dir)

    app = FastAPI(
        title="ML Kit Inference API",
        description="机器学习模型推理服务",
        version="1.0.0",
    )

    # 添加 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    inference_engine = InferenceEngine(model_registry)

    @app.get("/")
    def root():
        return {"name": "ML Kit Inference API", "version": "1.0.0", "status": "running"}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/models")
    def list_models():
        """列出所有模型"""
        return {"models": model_registry.list()}

    @app.get("/models/{model_id}")
    def get_model(model_id: str):
        """获取模型信息"""
        try:
            info = model_registry.get(model_id)["info"]
            return {
                "model_id": model_id,
                "name": info.name,
                "model_type": info.model_type,
                "task_type": info.task_type,
                "input_features": info.input_features,
                "output_classes": info.output_classes,
                "description": info.description,
                "created_at": info.created_at,
            }
        except KeyError:
            raise HTTPException(status_code=404, detail="Model not found")

    @app.post("/models/{model_id}/predict", response_model=InferenceResponse)
    def predict(model_id: str, request: InferenceRequest):
        """执行推理"""
        try:
            result = inference_engine.predict(
                model_id=model_id, data=request.data, return_proba=request.return_proba
            )

            info = model_registry.get(model_id)["info"]

            return InferenceResponse(
                request_id=str(uuid.uuid4()),
                predictions=result["predictions"],
                probabilities=result.get("probabilities"),
                model_info={
                    "name": info.name,
                    "model_type": info.model_type,
                    "task_type": info.task_type,
                },
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Model not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/models/{model_id}")
    def delete_model(model_id: str):
        """删除模型"""
        if model_registry.delete(model_id):
            return {"status": "deleted", "model_id": model_id}
        raise HTTPException(status_code=404, detail="Model not found")

    return app


def run_inference_server(
    model_registry: ModelRegistry | None = None,
    model_dir: str = "./models",
    host: str = "0.0.0.0",
    port: int = 8000,
):
    """运行推理服务"""
    app = create_inference_app(model_registry, model_dir)
    uvicorn.run(app, host=host, port=port)


# 便捷函数：加载模型并启动服务
def serve_model(
    model,
    model_name: str,
    model_type: str,
    task_type: str,
    input_features: list[str],
    output_classes: list[str] | None = None,
    model_dir: str = "./models",
    host: str = "0.0.0.0",
    port: int = 8000,
):
    """加载模型并启动推理服务"""
    registry = ModelRegistry(model_dir)

    model_id = registry.register(
        name=model_name,
        model=model,
        model_type=model_type,
        task_type=task_type,
        input_features=input_features,
        output_classes=output_classes,
    )

    print(f"Model registered: {model_id}")
    print(f"Starting inference server at http://{host}:{port}")

    run_inference_server(registry, model_dir, host, port)


# 创建全局 app 对象供 uvicorn 启动
app = create_inference_app()
