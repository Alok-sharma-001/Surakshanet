FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY backend/ ./backend/
COPY services/anomaly_service/ ./services/anomaly_service/

ENV PYTHONPATH="/app:/app/backend"

CMD ["python", "services/anomaly_service/main.py"]
