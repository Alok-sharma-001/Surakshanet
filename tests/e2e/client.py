"""
Opaque-Box E2E Test Client Helpers.
Provides external-interface-only access to Surakshanet ITS:
- HTTP REST API client
- Redis cache & pub/sub client
- MQTT telemetry client
- Database verification client
- Filesystem & repository inspection helpers
"""

import os
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests

# Base URLs and network host resolution
DEFAULT_BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "http://surakshanet-backend:8000")
DEFAULT_NGINX_URL = os.environ.get("E2E_NGINX_URL", "http://surakshanet-nginx:80")
DEFAULT_NGINX_SSL_URL = os.environ.get("E2E_NGINX_SSL_URL", "https://surakshanet-nginx:443")
DEFAULT_REDIS_URL = os.environ.get("E2E_REDIS_URL", "redis://surakshanet-redis:6379/0")
DEFAULT_MQTT_HOST = os.environ.get("E2E_MQTT_HOST", "surakshanet-mosquitto")
DEFAULT_MQTT_PORT = int(os.environ.get("E2E_MQTT_PORT", "1883"))
DEFAULT_DB_URL = os.environ.get(
    "E2E_DB_URL",
    "postgresql://surakshanet:surakshanet_dev@surakshanet-timescaledb:5432/surakshanet"
)
DEFAULT_PROMETHEUS_URL = os.environ.get("E2E_PROMETHEUS_URL", "http://surakshanet-prometheus:9090")
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/workspace" if os.path.exists("/workspace/PROJECT.md") else "/home/alok/surakshanet")


class E2EResponse:
    """Wrapper around requests.Response for uniform assertions."""
    def __init__(self, raw: requests.Response):
        self.raw = raw
        self.status_code = raw.status_code
        self.headers = raw.headers
        self.text = raw.text
        self.elapsed = raw.elapsed.total_seconds()

    def json(self) -> Any:
        try:
            return self.raw.json()
        except Exception as e:
            raise ValueError(f"Response is not JSON: {self.text[:200]}") from e

    def get_header(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for k, v in self.headers.items():
            if k.lower() == key.lower():
                return v
        return default


class E2EHttpClient:
    """Opaque-box HTTP client interacting strictly via REST endpoints."""
    def __init__(self, base_url: str = DEFAULT_BACKEND_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.default_headers: Dict[str, str] = {}

    def set_auth_token(self, token: str) -> None:
        self.default_headers["Authorization"] = f"Bearer {token}"

    def clear_auth_token(self) -> None:
        self.default_headers.pop("Authorization", None)

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
        allow_redirects: bool = True,
        verify: bool = False,
    ) -> E2EResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        merged_headers = dict(self.default_headers)
        if headers:
            merged_headers.update(headers)

        res = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json_data,
            data=data,
            headers=merged_headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=verify,
        )
        return E2EResponse(res)

    def get(self, path: str, **kwargs) -> E2EResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> E2EResponse:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> E2EResponse:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> E2EResponse:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> E2EResponse:
        return self.request("DELETE", path, **kwargs)

    def options(self, path: str, **kwargs) -> E2EResponse:
        return self.request("OPTIONS", path, **kwargs)

    def register_user(
        self,
        email: str,
        password: str = "SecureP@ssw0rd123!",
        name: str = "Test Operator",
        role: Optional[str] = None,
    ) -> E2EResponse:
        payload: Dict[str, Any] = {
            "email": email,
            "password": password,
            "name": name,
        }
        if role is not None:
            payload["role"] = role
        return self.post("/api/v1/auth/register", json_data=payload)

    def login_user(
        self,
        email: str,
        password: str = "SecureP@ssw0rd123!",
    ) -> Tuple[E2EResponse, Optional[str]]:
        payload = {"email": email, "password": password}
        res = self.post("/api/v1/auth/login", json_data=payload)
        token = None
        if res.status_code == 200:
            try:
                body = res.json()
                token = body.get("access_token")
            except Exception:
                pass
        return res, token


class E2ERedisClient:
    """Opaque-box Redis client for verifying state, tokens, and pub/sub."""
    def __init__(self, redis_url: str = DEFAULT_REDIS_URL):
        self.redis_url = redis_url
        import redis
        self.client = redis.from_url(redis_url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self.client.ping())

    def get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def exists(self, key: str) -> int:
        return self.client.exists(key)

    def ttl(self, key: str) -> int:
        return self.client.ttl(key)

    def publish(self, channel: str, message: str) -> int:
        return self.client.publish(channel, message)

    def keys(self, pattern: str = "*") -> List[str]:
        return self.client.keys(pattern)


class E2EMqttClient:
    """Opaque-box MQTT client for testing telemetry topics and event ingestion."""
    def __init__(self, host: str = DEFAULT_MQTT_HOST, port: int = DEFAULT_MQTT_PORT):
        self.host = host
        self.port = port

    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> bool:
        import paho.mqtt.client as mqtt
        client = mqtt.Client()
        try:
            rc = client.connect(self.host, self.port, 5)
            if rc != 0:
                return False
            payload_str = json.dumps(payload) if not isinstance(payload, str) else payload
            client.publish(topic, payload_str, qos=qos, retain=retain)
            client.disconnect()
            return True
        except Exception:
            return False

    def collect_messages(self, topic: str, timeout: float = 2.0, count: int = 1) -> List[Dict[str, Any]]:
        import paho.mqtt.client as mqtt
        messages: List[Dict[str, Any]] = []

        def on_message(client, userdata, msg):
            try:
                data = json.loads(msg.payload.decode())
            except Exception:
                data = {"raw": msg.payload.decode()}
            messages.append({"topic": msg.topic, "payload": data})

        client = mqtt.Client()
        client.on_message = on_message
        try:
            client.connect(self.host, self.port, 5)
            client.subscribe(topic)
            client.loop_start()
            start = time.time()
            while time.time() - start < timeout and len(messages) < count:
                time.sleep(0.05)
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
        return messages


class E2EDatabaseClient:
    """Opaque-box database client to verify schema, PostGIS, and TimescaleDB."""
    def __init__(self, db_url: str = DEFAULT_DB_URL):
        self.db_url = db_url

    def execute_query(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Tuple[Any, ...]]:
        import psycopg2
        conn = psycopg2.connect(self.db_url)
        try:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if cur.description:
                    return cur.fetchall()
                return []
        finally:
            conn.close()

    def execute_scalar(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> Any:
        rows = self.execute_query(query, params)
        if rows and len(rows) > 0 and len(rows[0]) > 0:
            return rows[0][0]
        return None
