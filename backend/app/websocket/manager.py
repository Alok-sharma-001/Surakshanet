import json
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            'traffic': set(),
            'signals': set(),
            'alerts': set(),
            'emergency': set(),
            'training': set(),
            'simulation': set(),
            'incidents': set(),
            'control': set(),
        }

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel in self.active_connections:
            self.active_connections[channel].add(websocket)
        else:
            self.active_connections[channel] = {websocket}
        self._update_metrics(channel)

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
        self._update_metrics(channel)

    def _update_metrics(self, channel: str):
        try:
            from app.middleware.metrics import WS_CONNECTIONS_ACTIVE
            count = len(self.active_connections.get(channel, set()))
            WS_CONNECTIONS_ACTIVE.labels(channel=channel).set(count)
        except Exception:
            pass

    async def broadcast(self, channel: str, data: dict):
        """
        Broadcast data across all workers by publishing to Redis pub/sub,
        as well as dispatching immediately to local clients.
        """
        # 1. Publish to Redis for cross-worker fanout
        try:
            from app.config import get_settings
            import redis.asyncio as aioredis
            settings = get_settings()
            r = aioredis.from_url(settings.REDIS_URL)
            redis_channel = f"surakshanet:events:{channel}"
            await r.publish(redis_channel, json.dumps(data))
            await r.aclose()
        except Exception:
            pass

        # 2. Local delivery
        await self.local_broadcast(channel, data)

    async def local_broadcast(self, channel: str, data: dict):
        """Dispatches data directly to locally connected WebSockets."""
        if channel in self.active_connections:
            disconnected = set()
            for connection in list(self.active_connections[channel]):
                try:
                    await connection.send_json(data)
                except Exception:
                    disconnected.add(connection)

            for conn in disconnected:
                self.disconnect(conn, channel)

    async def send_personal(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)

    def get_connection_count(self, channel: str = None) -> int:
        if channel:
            return len(self.active_connections.get(channel, set()))
        return sum(len(connections) for connections in self.active_connections.values())


manager = ConnectionManager()
