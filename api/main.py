# ML All In One - FastAPI Backend

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any
import sys
import os

# Add src to path for mlkit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

app = FastAPI(title="ML All In One API", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Health Check ============
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

# ============ Data Endpoints ============
@app.post("/api/data/upload")
async def upload_data(file: UploadFile = File(...)):
    """Upload CSV data file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files supported")
    
    # TODO: Implement with mlkit DataLoader
    return {
        "filename": file.filename,
        "status": "uploaded",
        "rows": 0,
        "columns": []
    }

@app.get("/api/data/info")
async def get_data_info():
    """Get uploaded data info"""
    # TODO: Return from session/context
    return {
        "rows": 150,
        "columns": ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"],
        "dtypes": {"sepal_length": "float64", "species": "category"}
    }

# ============ Training Endpoints ============
class TrainRequest(BaseModel):
    model_type: str
    task_type: str
    target_column: str
    hyperparameters: Optional[dict] = {}

@app.post("/api/train")
async def train(request: TrainRequest):
    """Start training job"""
    # TODO: Integrate with mlkit Runner
    return {
        "job_id": "job_001",
        "status": "started",
        "message": "Training started"
    }

@app.get("/api/train/{job_id}/status")
async def get_train_status(job_id: str):
    """Get training status"""
    # TODO: Return real-time status
    return {
        "job_id": job_id,
        "status": "running",
        "progress": 67,
        "current_iter": 67,
        "accuracy": 0.892,
        "loss": 0.234
    }

@app.post("/api/train/{job_id}/stop")
async def stop_train(job_id: str):
    """Stop training"""
    return {"job_id": job_id, "status": "stopped"}

# ============ Model Endpoints ============
@app.get("/api/models")
async def list_models():
    """List trained models"""
    return {
        "models": [
            {"id": "model_001", "name": "RF-iris-v1", "accuracy": 94.2, "created": "2026-04-09"},
            {"id": "model_002", "name": "XGB-iris-v1", "accuracy": 95.1, "created": "2026-04-09"},
        ]
    }

@app.post("/api/predict")
async def predict(data: List[dict], model_id: Optional[str] = None):
    """Run prediction"""
    # TODO: Use loaded model
    return {
        "predictions": [0, 1, 2] * len(data),
        "probabilities": [[0.1, 0.8, 0.1]] * len(data)
    }

# ============ Experiment Endpoints ============
@app.get("/api/experiments")
async def list_experiments():
    """List all experiments"""
    return {
        "experiments": [
            {
                "id": "exp_001",
                "name": "RF-iris-baseline",
                "status": "completed",
                "metrics": {"accuracy": 94.2, "f1": 93.8},
                "created": "2026-04-09 18:00"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
