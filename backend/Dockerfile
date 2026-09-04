# Build stage
FROM python:3.11-slim AS builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt

# Pre-install CPU PyTorch wheels to keep image lightweight and fast
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 --user --extra-index-url https://download.pytorch.org/whl/cpu torch torchvision
# Install remaining dependencies
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (OpenCV, GLib, libsumo requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app:$PYTHONPATH
ENV YOLO_CONFIG_DIR=/tmp/Ultralytics

# Copy backend application, ml engine, simulation wrappers, and shared constants
COPY backend/ /app/
COPY ml/ /app/ml/
COPY simulation/ /app/simulation/
COPY shared/ /app/shared/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
