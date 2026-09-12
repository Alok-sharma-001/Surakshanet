from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.websocket.manager import manager
from app.services.auth_service import get_user_from_token_or_none
from app.models.user import UserRole

ws_router = APIRouter()

# Every channel here carries the same class of live operational telemetry
# (junction/signal/alert/emergency state) that GET /junctions, GET
# /simulation/*, etc. already gate behind ADMIN/OPERATOR/VIEWER/
# EMERGENCY_SERVICES — CITIZEN access to this data goes through the
# separate, deliberately unauthenticated /public/* advisory endpoints
# instead. Matches the REST roles already enforced for this data class,
# rather than introducing new per-channel granularity.
_ALLOWED_WS_ROLES = {UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER, UserRole.EMERGENCY_SERVICES}


async def handle_websocket(websocket: WebSocket, channel: str):
    token = websocket.query_params.get("token")
    user = await get_user_from_token_or_none(token)
    if user is None or user.role not in _ALLOWED_WS_ROLES:
        # Found live (2026-09-12 acceptance audit): every /ws/* route
        # previously accepted any connection with no authentication at
        # all, unlike the equivalent REST reads. Close before accepting —
        # never silently degrade to broadcasting anyway.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data in ("ping", '{"type":"ping"}', '{"type": "ping"}'):
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)


@ws_router.websocket('/ws/traffic')
async def traffic_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'traffic')


@ws_router.websocket('/ws/signals')
async def signals_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'signals')


@ws_router.websocket('/ws/alerts')
async def alerts_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'alerts')


@ws_router.websocket('/ws/emergency')
async def emergency_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'emergency')


@ws_router.websocket('/ws/training')
async def training_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'training')


@ws_router.websocket('/ws/control')
async def control_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'control')


@ws_router.websocket('/ws/incidents')
async def incidents_ws(websocket: WebSocket):
    """SN-091: Live incident stream WebSocket."""
    await handle_websocket(websocket, 'incidents')


@ws_router.websocket('/api/v1/ws')
async def root_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'default')


@ws_router.websocket('/ws/{channel}')
async def dynamic_channel_ws(websocket: WebSocket, channel: str):
    await handle_websocket(websocket, channel)
