"""
ML All In One - FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from api.database import engine, Base
from api.routes import auth, data, train, experiments, models, viz, automl, preprocessing, monitor, logs


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
    yield


app = FastAPI(
    title="ML All In One API",
    version="2.0.0",
    description="机器学习训练平台 API",
    lifespan=lifespan
)

# Add middleware to fix trailing slash redirects
app.add_middleware(RelativeRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
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

@app.get("/")
async def root():
    return {"message": "ML All In One API", "version": "2.0.0"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}
