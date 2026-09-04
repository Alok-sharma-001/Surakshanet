import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from app.config import get_settings
from app.database import init_db
from app.middleware.metrics import metrics_middleware, MetricsEndpoint
from app.websocket.manager import manager

settings = get_settings()

async def redis_pubsub_bridge():
    """
    Subscribes to internal Redis channels and broadcasts telemetry, signals,
    and alert events live to connected frontend WebSockets.
    """
    retry_delay = 2
    while True:
        try:
            redis = aioredis.from_url(settings.REDIS_URL)
            pubsub = redis.pubsub()
            await pubsub.subscribe("traffic_updates", "signal_events", "alert_events", "emergency_events")
            print("Redis-to-WebSocket bridge listening on pub/sub channels...")

            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    ch = message.get("channel")
                    channel_name = ch.decode("utf-8") if isinstance(ch, bytes) else str(ch)
                    raw_data = message.get("data")
                    text_data = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)

                    try:
                        payload = json.loads(text_data)
                    except Exception:
                        payload = {"raw": text_data}

                    # Map Redis channel to WebSocket room
                    ws_target = "traffic"
                    if "signal" in channel_name:
                        ws_target = "signals"
                    elif "alert" in channel_name:
                        ws_target = "alerts"
                    elif "emergency" in channel_name:
                        ws_target = "emergency"

                    await manager.broadcast(ws_target, payload)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Redis pubsub bridge reconnecting in {retry_delay}s ({e})...")
            await asyncio.sleep(retry_delay)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    await init_db()
    
    # 1. Start MQTT IoT Telemetry Consumer
    try:
        from app.services.mqtt_consumer import mqtt_consumer
        mqtt_consumer.start()
    except Exception as e:
        print(f"MQTT consumer startup bypassed: {e}")

    # 2. Start Redis-to-WebSocket live bridge
    bridge_task = asyncio.create_task(redis_pubsub_bridge())

    yield

    # Shutdown
    bridge_task.cancel()
    try:
        from app.services.mqtt_consumer import mqtt_consumer
        mqtt_consumer.stop()
    except Exception:
        pass

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(metrics_middleware)
app.add_route("/metrics", MetricsEndpoint)

from app.api.router import api_router
from app.api.websocket_routes import ws_router

app.include_router(api_router, prefix=settings.API_PREFIX)
app.include_router(ws_router)

@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> dict:
    """Root health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
