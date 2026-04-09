"""
ML All In One - FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.database import engine, Base
from api.routes import auth, data, train, experiments, models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建数据库表
    Base.metadata.create_all(bind=engine)
    yield
    # 关闭时清理

app = FastAPI(
    title="ML All In One API",
    version="2.0.0",
    description="机器学习训练平台 API",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(data.router, prefix="/api/data", tags=["数据"])
app.include_router(train.router, prefix="/api/train", tags=["训练"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["实验"])
app.include_router(models.router, prefix="/api/models", tags=["模型"])

@app.get("/")
async def root():
    return {"message": "ML All In One API", "version": "2.0.0"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}
