import os
import sys
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

# Ensure SUMO tools are in sys.path
candidate_paths = [
    os.path.join(os.environ.get("SUMO_HOME", "/usr/share/sumo"), "tools"),
    "/usr/share/sumo/tools",
    "/usr/lib/python3/dist-packages",
    "/usr/local/share/sumo/tools",
]
for p in candidate_paths:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    import traci  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "FATAL: 'traci' is not importable from this interpreter.\n"
        f"  interpreter: {sys.executable}\n"
        "  fix: see docs/04-environment-setup.md §2 (SN-013)"
    ) from exc

from app.config import get_settings
from app.database import init_db
from app.middleware.metrics import metrics_middleware, MetricsEndpoint
from app.websocket.manager import manager

settings = get_settings()


async def redis_pubsub_bridge():
    """
    Subscribes to internal Redis channels and broadcasts telemetry, signals,
    and alert events live to connected frontend WebSockets across all workers.
    """
    retry_delay = 2
    while True:
        try:
            from app.middleware.metrics import REDIS_PUBSUB_MESSAGES_TOTAL
            redis = aioredis.from_url(settings.REDIS_URL)
            pubsub = redis.pubsub()
            channels = [
                "traffic_updates", "signal_events", "alert_events", "emergency_events", "simulation_updates",
                "surakshanet:events:traffic", "surakshanet:events:signals", "surakshanet:events:alerts",
                "surakshanet:events:emergency", "surakshanet:events:training", "surakshanet:events:simulation"
            ]
            await pubsub.subscribe(*channels)
            print("Redis-to-WebSocket bridge listening on pub/sub channels...")

            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    ch = message.get("channel")
                    channel_name = ch.decode("utf-8") if isinstance(ch, bytes) else str(ch)
                    raw_data = message.get("data")
                    text_data = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)

                    try:
                        REDIS_PUBSUB_MESSAGES_TOTAL.labels(channel=channel_name).inc()
                    except Exception:
                        pass

                    try:
                        payload = json.loads(text_data)
                    except Exception:
                        payload = {"raw": text_data}

                    # Map Redis channel to WebSocket room
                    if "surakshanet:events:" in channel_name:
                        ws_target = channel_name.replace("surakshanet:events:", "")
                    elif "signal" in channel_name:
                        ws_target = "signals"
                    elif "alert" in channel_name:
                        ws_target = "alerts"
                    elif "emergency" in channel_name:
                        ws_target = "emergency"
                    elif "simulation" in channel_name:
                        ws_target = "simulation"
                    elif "training" in channel_name:
                        ws_target = "training"
                    else:
                        ws_target = "traffic"

                    await manager.local_broadcast(ws_target, payload)
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

from app.middleware.correlation import CorrelationIdMiddleware
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uuid

app.add_middleware(CorrelationIdMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": {
                "code": exc.status_code,
                "message": str(exc.detail),
                "details": exc.detail,
                "request_id": req_id
            }
        },
        headers={"X-Request-ID": req_id}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "error": {
                "code": 422,
                "message": "Validation error",
                "details": exc.errors(),
                "request_id": req_id
            }
        },
        headers={"X-Request-ID": req_id}
    )


app.middleware("http")(metrics_middleware)
app.add_route("/metrics", MetricsEndpoint)

from app.api.router import api_router
from app.api.websocket_routes import ws_router

app.include_router(api_router, prefix=settings.API_PREFIX)
app.include_router(ws_router)


from app.api.health import router as health_router

app.include_router(health_router)
app.include_router(health_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["Health"])
async def root_check() -> dict:
    """Root endpoint."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
