import os
import sys
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

# Ensure repo root is available for shared imports
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from shared.sumo_bootstrap import require_traci

traci = require_traci(extra_paths=[_repo_root])

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
            from shared.constants import REDIS_CHANNELS
            from app.middleware.metrics import REDIS_PUBSUB_MESSAGES_TOTAL
            redis = aioredis.from_url(settings.REDIS_URL)
            pubsub = redis.pubsub()
            channels = list(REDIS_CHANNELS.values())
            await pubsub.subscribe(*channels)
            print(f"Redis-to-WebSocket bridge listening on {len(channels)} canonical pub/sub channels...")

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
                    if channel_name == REDIS_CHANNELS["signals"]:
                        ws_target = "signals"
                    elif channel_name == REDIS_CHANNELS["alerts"]:
                        ws_target = "alerts"
                        if isinstance(payload, dict):
                            try:
                                from app.services.vision_service import persist_behavior_flag
                                await persist_behavior_flag(payload)
                            except Exception:
                                pass
                    elif channel_name == REDIS_CHANNELS["emergency"]:
                        ws_target = "emergency"
                    elif channel_name == REDIS_CHANNELS["simulation"]:
                        ws_target = "simulation"
                        if isinstance(payload, dict):
                            try:
                                from app.services.bridge_observer import record_bridge_tick
                                record_bridge_tick(payload)
                            except Exception:
                                pass
                    elif channel_name == REDIS_CHANNELS["control_decisions"]:
                        ws_target = "control"
                    elif channel_name == REDIS_CHANNELS["traffic"]:
                        ws_target = "traffic"
                        if isinstance(payload, dict):
                            try:
                                from app.services.routing_telemetry import record_junction_telemetry
                                record_junction_telemetry(payload)
                            except Exception:
                                pass
                    elif channel_name == REDIS_CHANNELS["cv_detections"]:
                        ws_target = channel_name
                        if isinstance(payload, dict):
                            try:
                                from app.services.vision_service import persist_cv_detections
                                await persist_cv_detections(payload)
                            except Exception:
                                pass
                    elif channel_name == REDIS_CHANNELS["incidents"]:
                        ws_target = "incidents"
                    else:
                        ws_target = channel_name

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

    # 0. Clear any stale "simulation running" flag left in Redis by a
    # previous process incarnation. A brand-new worker's in-memory
    # sim_instance (backend/app/api/simulation.py) is always None at this
    # point — it cannot possibly match whatever Redis says, so any
    # "running": true left over from before this restart is definitely
    # stale and would otherwise make POST /simulation/start falsely 409
    # ("already running") with no real simulation to stop or step. Found
    # live 2026-09-12: restarting this container after a Simulation-page
    # scenario had been running left exactly this stuck state, only
    # recoverable by manually flushing these two Redis keys.
    try:
        redis_startup = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_startup.delete("simulation:state", "simulation:running")
        await redis_startup.aclose()
    except Exception as e:
        print(f"Stale simulation-state cleanup skipped: {e}")

    # 1. Start MQTT IoT Telemetry Consumer
    try:
        from app.services.mqtt_consumer import mqtt_consumer
        mqtt_consumer.start()
    except Exception as e:
        print(f"MQTT consumer startup bypassed: {e}")

    # 2. Start Redis-to-WebSocket live bridge
    bridge_task = asyncio.create_task(redis_pubsub_bridge())

    # 3. Build the routing graph from the DB when it's actually seeded with the
    #    real corridor junctions/network_links (SN-041); falls back to the
    #    in-code corridor topology otherwise (RoutingService.initialize_from_db
    #    already does this internally).
    try:
        from app.database import async_session_factory
        from app.services.routing_service import routing_service
        async with async_session_factory() as _db:
            await routing_service.initialize_from_db(_db)
    except Exception as e:
        print(f"Routing graph DB initialization skipped, using in-code corridor topology: {e}")

    # 4. Start the routing graph's live telemetry refresh loop (SN-041)
    from app.services.routing_telemetry import periodic_routing_refresh
    routing_refresh_task = asyncio.create_task(periodic_routing_refresh())

    # 5. Start the SUMO auto-step loop: advances whatever simulation this
    # worker is holding once per real second, so a scenario started from the
    # Simulation page actually plays instead of sitting at step 0 until
    # someone clicks Step. See app/api/simulation.py::auto_step_loop.
    from app.api.simulation import auto_step_loop
    sim_auto_step_task = asyncio.create_task(auto_step_loop())

    yield

    # Shutdown
    bridge_task.cancel()
    routing_refresh_task.cancel()
    sim_auto_step_task.cancel()
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
from app.api.ab import router as ab_router
from app.api.public import router as public_router
from app.api.vision import router as vision_router
from app.api.incidents import router as incidents_router

app.include_router(health_router)
app.include_router(health_router, prefix=settings.API_PREFIX)
app.include_router(ab_router)
app.include_router(public_router)
app.include_router(public_router, prefix=settings.API_PREFIX)
app.include_router(vision_router)
app.include_router(incidents_router)


@app.get("/", tags=["Health"])
async def root_check() -> dict:
    """Root endpoint."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
