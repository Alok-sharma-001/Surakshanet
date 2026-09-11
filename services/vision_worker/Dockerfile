FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY ml/ ./ml/
COPY config/ ./config/
COPY services/vision_worker/ ./services/vision_worker/

ENV PYTHONPATH="/app"

CMD ["python", "services/vision_worker/main.py"]
