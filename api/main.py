"""
ML All In One - FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from api.database import engine, Base, SessionLocal
from api.routes import auth, data, train, experiments, models, viz, automl, preprocessing, monitor, logs, platform_logs, admin, drift, model_registry, explain, forecast, scheduler, pipelines
from api.auth import get_or_create_admin_user
import os
from api.middleware.logging_middleware import PlatformLoggingMiddleware
from api.services.log_aggregator import init_platform_loggers, cleanup_old_logs
import asyncio
import os as _os


def _get_db_factory():
    return SessionLocal


class RelativeRedirectMiddleware(BaseHTTPMiddleware):
    """Convert absolute backend redirects to relative paths so Vite proxy can intercept them"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code in (301, 307, 308):
            location = response.headers.get("location", "")
            if location.startswith("http://localhost:8000"):
                # Convert to relative path so browser stays on port 3000
                relative = location.replace("http://localhost:8000", "")
                return RedirectResponse(
                    url=relative,
                    status_code=307
                )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    get_or_create_admin_user()
    # 初始化平台 logger 并清理超期日志（启动时同步清理，不阻塞 API）
    init_platform_loggers()
    asyncio.create_task(cleanup_old_logs())
    # 启动调度器：创建 scheduler 表 + 注册活跃 Job
    try:
        from src.mlkit.scheduler.models import Base as SchedulerBase
        SchedulerBase.metadata.create_all(bind=engine)
        _jwt_secret = _os.getenv("SECRET_KEY", _os.getenv("MLKIT_JWT_SECRET", "mlkit-jwt-dev-secret-key-32chars!"))
        from src.mlkit.scheduler.scheduler import init_scheduler
        init_scheduler(_get_db_factory, _jwt_secret)
    except Exception as e:
        import logging
        logging.getLogger("platform.scheduler").error(f"调度器启动失败: {e}")
    yield
    # 关闭调度器
    try:
        from src.mlkit.scheduler.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass


app = FastAPI(
    title="ML All In One API",
    version="2.0.0",
    description="机器学习训练平台 API",
    lifespan=lifespan
)

# Add middleware to fix trailing slash redirects
app.add_middleware(RelativeRedirectMiddleware)

# 注册平台日志中间件（拦截所有 /api/* 请求）
app.add_middleware(PlatformLoggingMiddleware)

# CORS 配置：从环境变量读取允许的 origins，支持逗号分隔多个地址
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
_allowed_origins = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(data.router, prefix="/api/data", tags=["数据"])
app.include_router(train.router, prefix="/api/train", tags=["训练"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["实验"])
app.include_router(models.router, prefix="/api/models", tags=["模型"])
app.include_router(viz.router, prefix="/api/viz", tags=["可视化"])
app.include_router(automl.router, prefix="/api/automl", tags=["AutoML"])
app.include_router(preprocessing.router, prefix="/api/preprocessing", tags=["预处理"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["系统监控"])
app.include_router(logs.router, prefix="/api/logs", tags=["日志"])
app.include_router(platform_logs.router, prefix="/api/platform-logs", tags=["平台日志"])
app.include_router(admin.router, prefix="/api/admin", tags=["用户管理"])
app.include_router(drift.router, prefix="/api/drift", tags=["漂移检测"])
app.include_router(model_registry.router, prefix="/api/models", tags=["模型版本管理"])
app.include_router(explain.router, prefix="/api/explain", tags=["可解释性"])
app.include_router(forecast.router, prefix="/api/forecast", tags=["时序预测"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["任务调度"])
app.include_router(pipelines.router, prefix="/api/pipelines", tags=["Pipeline编排"])

@app.get("/")
async def root():
    return {"message": "ML All In One API", "version": "2.0.0"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}
