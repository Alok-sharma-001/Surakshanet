import time
from fastapi import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"]
)

ACTIVE_CONNECTIONS = Gauge(
    "active_connections",
    "Number of active connections"
)

WS_CONNECTIONS_ACTIVE = Gauge(
    "surakshanet_ws_active_connections",
    "Active WebSocket connections by channel",
    ["channel"]
)

REDIS_PUBSUB_MESSAGES_TOTAL = Counter(
    "surakshanet_redis_pubsub_messages_total",
    "Total Redis pub/sub messages processed",
    ["channel"]
)

ML_INFERENCE_DURATION_SECONDS = Histogram(
    "surakshanet_ml_inference_duration_seconds",
    "ML model inference duration in seconds",
    ["model_name"]
)

SIMULATION_STEP_DURATION_SECONDS = Histogram(
    "surakshanet_simulation_step_duration_seconds",
    "Traffic simulation step duration in seconds"
)


async def metrics_middleware(request: Request, call_next):
    ACTIVE_CONNECTIONS.inc()
    start_time = time.perf_counter()
    method = request.method
    endpoint = request.url.path

    try:
        response = await call_next(request)
        status = str(response.status_code)
    except Exception:
        status = "500"
        raise
    finally:
        duration = time.perf_counter() - start_time
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)
        ACTIVE_CONNECTIONS.dec()

    return response


async def MetricsEndpoint(request: Request) -> Response:
    """Endpoint exposing prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
