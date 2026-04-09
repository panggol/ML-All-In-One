# =============================================================================
# ML All In One - Dockerfile
# =============================================================================
# Build: docker build -t mlkit .
# Run:   docker run --rm -v $(pwd)/data:/app/data mlkit python run_example.py
#       docker run --rm -p 8000:8000 mlkit uvicorn mlkit.api.inference:app --host 0.0.0.0 --port 8000
# =============================================================================

FROM python:3.12-slim

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first (for caching)
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/ ./src/
COPY examples/ ./examples/
COPY README.md ./

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/checkpoints /app/experiments

# Set Python path
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Default command - run a simple test
CMD ["python", "-c", "import mlkit; print(f'mlkit {mlkit.__version__} ready!')"]
