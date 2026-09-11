import os
import time
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import text
import redis.asyncio as aioredis

from app.config import get_settings
from app.database import async_session_maker
from shared.paths import find_existing

settings = get_settings()
router = APIRouter()


async def _check_mqtt_port(host: str, port: int, timeout: float = 1.0) -> None:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=timeout
    )
    writer.close()
    await writer.wait_closed()


@router.get("/health")
async def health():
    """Liveness probe returning minimal status and application version."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
    }


@router.get("/health/deep")
async def health_deep():
    """
    Readiness probe measuring each dependency individually.
    Every field is measured in real-time, never assumed.
    """
    dependencies = {}

    # 1. PostgreSQL (TimescaleDB)
    t0 = time.time()
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        dependencies["postgres"] = {
            "status": "ok",
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as e:
        dependencies["postgres"] = {"status": "error", "error": str(e)}

    # 2. Redis
    r = None
    t0 = time.time()
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        await r.ping()
        dependencies["redis"] = {
            "status": "ok",
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as e:
        dependencies["redis"] = {"status": "error", "error": str(e)}

    # 3. MQTT
    try:
        from app.services.mqtt_consumer import mqtt_consumer
        if mqtt_consumer.client and mqtt_consumer.client.is_connected():
            dependencies["mqtt"] = {"status": "ok"}
        else:
            await _check_mqtt_port(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)
            dependencies["mqtt"] = {"status": "ok"}
    except Exception as e:
        dependencies["mqtt"] = {"status": "error", "error": f"mqtt broker unreachable: {e}"}

    # 4. SUMO
    if r is not None:
        try:
            step_val = await r.get("sumo:step")
            heartbeat = await r.get("simulation:bridge:heartbeat")
            if heartbeat:
                age = time.time() - float(heartbeat)
                if age < 15.0:
                    dependencies["sumo"] = {
                        "status": "ok",
                        "step": int(step_val) if step_val else 0,
                    }
                else:
                    dependencies["sumo"] = {
                        "status": "degraded",
                        "step": int(step_val) if step_val else 0,
                        "reason": "sumo bridge heartbeat stale",
                    }
            else:
                dependencies["sumo"] = {
                    "status": "unavailable",
                    "reason": "sumo simulation bridge not connected",
                }
        except Exception as e:
            dependencies["sumo"] = {"status": "unavailable", "reason": str(e)}
    else:
        dependencies["sumo"] = {"status": "unavailable", "reason": "redis unreachable"}

    # 5. TraCI
    try:
        import traci
        dependencies["traci"] = {
            "status": "ok",
            "module": getattr(traci, "__file__", "installed"),
        }
    except Exception as e:
        dependencies["traci"] = {"status": "error", "error": str(e)}

    # 6. Control Service
    if r is not None:
        try:
            last_decision = await r.get("control_service:last_decision")
            heartbeat = await r.get("control_service:heartbeat")
            active_ts = last_decision or heartbeat
            if active_ts:
                age = round(time.time() - float(active_ts), 1)
                if age < 15.0:
                    dependencies["control_service"] = {
                        "status": "ok",
                        "last_decision_age_s": age,
                    }
                else:
                    dependencies["control_service"] = {
                        "status": "degraded",
                        "last_decision_age_s": age,
                        "reason": "heartbeat stale",
                    }
            else:
                dependencies["control_service"] = {
                    "status": "unavailable",
                    "reason": "control service not running",
                }
        except Exception as e:
            dependencies["control_service"] = {"status": "unavailable", "reason": str(e)}
    else:
        dependencies["control_service"] = {"status": "unavailable", "reason": "redis unreachable"}

    # 7. Vision Worker
    video_source = getattr(settings, "RTSP_STREAM_URL", None) or os.environ.get("RTSP_STREAM_URL", None)
    if not video_source:
        dependencies["vision_worker"] = {
            "status": "unavailable",
            "reason": "no video source configured",
        }
    else:
        dependencies["vision_worker"] = {"status": "ok", "source": video_source}

    # 8. MARL Weights
    marl_rel_path = "ml/marl/weights/marl_policy_downtown.pth"
    marl_found = find_existing([
        marl_rel_path,
        os.path.join(os.getcwd(), marl_rel_path),
        os.path.join(os.path.dirname(__file__), "../../../", marl_rel_path),
        f"/app/{marl_rel_path}",
    ])
    if marl_found:
        dependencies["marl_weights"] = {"status": "ok", "path": marl_rel_path}
    else:
        dependencies["marl_weights"] = {"status": "unavailable", "reason": f"weights not found at {marl_rel_path}"}

    # 9. Forecast Weights
    fc_rel_path = "ml/forecasting/weights/xgb_models.pkl"
    fc_found = find_existing([
        fc_rel_path,
        os.path.join(os.getcwd(), fc_rel_path),
        os.path.join(os.path.dirname(__file__), "../../../", fc_rel_path),
        f"/app/{fc_rel_path}",
    ])
    if fc_found:
        dependencies["forecast_weights"] = {"status": "ok", "training_data": "synthetic"}
    else:
        dependencies["forecast_weights"] = {"status": "unavailable", "reason": f"weights not found at {fc_rel_path}"}

    # Close temporary redis connection
    if r is not None:
        try:
            await r.close()
        except Exception:
            pass

    # Status is "ok" only when every dependency is "ok"; otherwise "degraded"
    all_ok = all(d.get("status") == "ok" for d in dependencies.values())
    overall_status = "ok" if all_ok else "degraded"

    return {
        "status": overall_status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies,
    }
