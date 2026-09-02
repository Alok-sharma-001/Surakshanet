from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.manager import manager
import asyncio

ws_router = APIRouter()

async def handle_websocket(websocket: WebSocket, channel: str):
    await manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming data if needed, like heartbeats
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
