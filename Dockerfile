# =============================================================================
# ML All In One - Dockerfile
# =============================================================================
# Build: docker build -t mlkit .
# Run:   docker run --rm -v $(pwd)/data:/app/data mlkit python run_example.py
# =============================================================================

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install torch CPU-only (much faster than GPU version)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY api/ ./api/
COPY examples/ ./examples/
COPY README.md ./

# Create directories
RUN mkdir -p /app/data /app/logs /app/checkpoints /app/experiments /app/uploads

# Set PYTHONPATH so mlkit can be imported
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Verify mlkit can be imported
RUN python -c "import mlkit; print(f'mlkit {mlkit.__version__} installed successfully')"

CMD ["python", "-c", "import mlkit; print(f'mlkit {mlkit.__version__} ready!')"]
