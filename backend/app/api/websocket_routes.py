from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.manager import manager

ws_router = APIRouter()


async def handle_websocket(websocket: WebSocket, channel: str):
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


@ws_router.websocket('/api/v1/ws')
async def root_ws(websocket: WebSocket):
    await handle_websocket(websocket, 'default')


@ws_router.websocket('/ws/{channel}')
async def dynamic_channel_ws(websocket: WebSocket, channel: str):
    await handle_websocket(websocket, channel)
