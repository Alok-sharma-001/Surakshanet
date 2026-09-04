import asyncio
import json
import logging
import random
import uuid
from datetime import datetime
from typing import Optional
import paho.mqtt.client as mqtt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import redis.asyncio as aioredis

from app.config import get_settings
from app.models.traffic import TrafficReading
from app.models.junction import Junction, TrafficSensor

logger = logging.getLogger(__name__)
settings = get_settings()

class MQTTTelemetryConsumer:
    """
    Asynchronous MQTT consumer and live telemetry generator that listens for IoT traffic telemetry,
    persists sensor readings to TimescaleDB, and relays live events to Redis pub/sub.
    """

    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_running = False
        self.engine = None
        self.async_session = None
        self.redis_client = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._ticker_task: Optional[asyncio.Task] = None

    def start(self):
        """Start the MQTT consumer and background live telemetry loop."""
        if self.is_running:
            return

        self.is_running = True
        self.loop = asyncio.get_event_loop()

        # Database engine
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        # MQTT Client
        client_id = f"surakshanet-consumer-{uuid.uuid4().hex[:8]}"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        try:
            logger.info(f"Connecting to MQTT broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}...")
            self.client.connect_async(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.warning(f"Could not connect to MQTT broker ({e}). Telemetry ingestion will run in standalone mode.")

        # Start continuous telemetry ticker
        if self.loop and self.loop.is_running():
            self._ticker_task = self.loop.create_task(self._live_telemetry_loop())

    def stop(self):
        """Stop the MQTT consumer cleanly."""
        self.is_running = False
        if self._ticker_task:
            self._ticker_task.cancel()
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        logger.info("MQTT Telemetry Consumer stopped.")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT Telemetry Consumer connected successfully.")
            client.subscribe("surakshanet/sensors/+/telemetry", qos=1)
            client.subscribe("surakshanet/junction/+/telemetry", qos=1)
            client.subscribe("surakshanet/telemetry/#", qos=1)
        else:
            logger.warning(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"MQTT Telemetry Consumer disconnected (code: {rc}).")

    def _on_message(self, client, userdata, msg):
        """Handle incoming sensor telemetry payload from MQTT."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            topic_parts = msg.topic.split("/")

            # Extract junction/sensor from topic if missing from payload
            if "junction" in msg.topic and len(topic_parts) >= 3 and not payload.get("junction_id"):
                payload["junction_id"] = topic_parts[2]
            elif "sensors" in msg.topic and len(topic_parts) >= 3 and not payload.get("sensor_id"):
                payload["sensor_id"] = topic_parts[2]

            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self._process_telemetry(payload), self.loop)
        except Exception as e:
            logger.error(f"Error parsing MQTT message on {msg.topic}: {e}")

    async def _process_telemetry(self, data: dict):
        """Store reading in TimescaleDB and forward to Redis channel."""
        try:
            junction_id_raw = data.get("junction_id")
            sensor_id_raw = data.get("sensor_id")

            if not junction_id_raw and not sensor_id_raw:
                return

            if junction_id_raw:
                try:
                    junction_id = uuid.UUID(str(junction_id_raw))
                except ValueError:
                    junction_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(junction_id_raw))
            else:
                junction_id = uuid.uuid4()

            if sensor_id_raw:
                try:
                    sensor_id = uuid.UUID(str(sensor_id_raw))
                except ValueError:
                    sensor_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(sensor_id_raw))
            else:
                sensor_id = uuid.uuid5(junction_id, "north_sensor")

            pcu = float(data.get("pcu_value", data.get("north_pcu", data.get("pcu", 28.0))))
            speed = float(data.get("avg_speed", data.get("speed", 32.0)))
            queue = float(data.get("queue_length", data.get("queue", 8.0)))
            v_count = float(data.get("vehicle_count", data.get("total_vehicles", 22.0)))

            reading = TrafficReading(
                id=uuid.uuid4(),
                timestamp=datetime.utcnow(),
                sensor_id=sensor_id,
                junction_id=junction_id,
                vehicle_count=v_count,
                pcu_value=pcu,
                avg_speed=speed,
                queue_length=queue,
                vehicle_breakdown=data.get("vehicle_breakdown", data.get("vehicle_counts", {"car": 12, "motorcycle": 8, "bus": 2}))
            )

            # 1. Insert into database
            async with self.async_session() as db:
                db.add(reading)
                await db.commit()

            # 2. Publish to Redis for live WebSocket streaming
            try:
                if not self.redis_client:
                    self.redis_client = aioredis.from_url(settings.REDIS_URL)
                event_payload = {
                    "type": "TELEMETRY_UPDATE",
                    "junction_id": str(junction_id),
                    "sensor_id": str(sensor_id),
                    "pcu": reading.pcu_value,
                    "speed": reading.avg_speed,
                    "queue": reading.queue_length,
                    "timestamp": reading.timestamp.isoformat()
                }
                await self.redis_client.publish("traffic_updates", json.dumps(event_payload))
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error persisting MQTT telemetry: {e}")

    async def _live_telemetry_loop(self):
        """
        Background live ticker: Emits periodic telemetry pulses across city junctions
        to ensure the command center and dashboards always have fresh live streams.
        """
        await asyncio.sleep(5)  # Initial grace delay
        while self.is_running:
            try:
                async with self.async_session() as db:
                    result = await db.execute(select(Junction.id, Junction.name).where(Junction.is_active == True).limit(12))
                    active_juncs = result.all()

                if active_juncs:
                    if not self.redis_client:
                        self.redis_client = aioredis.from_url(settings.REDIS_URL)

                    # Pick 2-3 junctions per tick
                    sampled = random.sample(active_juncs, min(len(active_juncs), 3))
                    for j_id, j_name in sampled:
                        pcu = round(random.uniform(25.0, 85.0), 1)
                        spd = round(max(12.0, 48.0 - (pcu * 0.35) + random.uniform(-2, 2)), 1)
                        q_len = round(max(0.0, (pcu - 20) * 0.8), 1)

                        tick_payload = {
                            "type": "TELEMETRY_UPDATE",
                            "junction_id": str(j_id),
                            "junction_name": j_name,
                            "pcu": pcu,
                            "speed": spd,
                            "queue": q_len,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        await self.redis_client.publish("traffic_updates", json.dumps(tick_payload))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Telemetry loop tick exception: {e}")

            await asyncio.sleep(5)

# Global daemon instance
mqtt_consumer = MQTTTelemetryConsumer()
