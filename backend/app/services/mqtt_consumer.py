import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional
import paho.mqtt.client as mqtt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import redis.asyncio as aioredis

from sqlalchemy import select
from app.config import get_settings
from app.models.traffic import TrafficReading
from app.models.junction import Junction, TrafficSensor, SensorType, ApproachDirection
from shared.constants import (
    REDIS_CHANNELS,
    MQTT_SENSOR_TELEMETRY_TOPIC,
    MQTT_JUNCTION_TELEMETRY_TOPIC,
    DataSource,
)
from shared.telemetry import (
    validate_telemetry,
    resolve_junction_uuid,
    TelemetryValidationError,
    JunctionTelemetry,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Measured provenance a device or bridge may legitimately declare on ingest.
_MEASURED_SOURCES = frozenset(
    {DataSource.MQTT.value, DataSource.SUMO.value, DataSource.VISION.value}
)


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
        if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
            self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        try:
            logger.info(f"Connecting to MQTT broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}...")
            self.client.connect_async(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.warning(f"Could not connect to MQTT broker ({e}). Telemetry ingestion will run in standalone mode.")

    def stop(self):
        """Stop the MQTT consumer cleanly."""
        self.is_running = False
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
            sensor_sub = MQTT_SENSOR_TELEMETRY_TOPIC.replace("{sensor_id}", "+")
            junction_sub = MQTT_JUNCTION_TELEMETRY_TOPIC.replace("{junction_id}", "+")
            client.subscribe(sensor_sub, qos=1)
            client.subscribe(junction_sub, qos=1)
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

            # Stamp source=MQTT at ingress if not already explicitly declared
            if "source" not in payload:
                payload["source"] = DataSource.MQTT.value

            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self._process_telemetry(payload), self.loop)
        except Exception as e:
            logger.error(f"Error parsing MQTT message on {msg.topic}: {e}")

    async def _process_telemetry(self, data: dict):
        """Validate against canonical JunctionTelemetry schema, store in TimescaleDB, and forward to Redis."""
        try:
            # Validate schema and provenance
            try:
                telemetry = validate_telemetry(data)
            except TelemetryValidationError as e:
                logger.warning("Rejecting malformed telemetry: %s", e)
                return

            async with self.async_session() as db:
                # Resolve junction
                j_uuid = resolve_junction_uuid(telemetry.junction_id)
                if j_uuid:
                    result = await db.execute(select(Junction).where(Junction.id == j_uuid))
                    j = result.scalars().first()
                else:
                    result = await db.execute(select(Junction).where(Junction.name.ilike(telemetry.junction_id)))
                    j = result.scalars().first()

                if not j:
                    logger.warning("Rejecting telemetry: unresolvable junction_id %r", telemetry.junction_id)
                    return

                # Resolve sensor
                sensor_id_raw = data.get("sensor_id")
                sensor = None
                if sensor_id_raw:
                    s_uuid = resolve_junction_uuid(str(sensor_id_raw))
                    if s_uuid:
                        s_res = await db.execute(select(TrafficSensor).where(TrafficSensor.id == s_uuid))
                        sensor = s_res.scalars().first()
                if not sensor:
                    s_res = await db.execute(select(TrafficSensor).where(TrafficSensor.junction_id == j.id))
                    sensor = s_res.scalars().first()
                if not sensor:
                    sensor = TrafficSensor(
                        id=uuid.uuid4(),
                        junction_id=j.id,
                        sensor_type=SensorType.RADAR,
                        approach_direction=ApproachDirection.NORTH,
                        is_active=True
                    )
                    db.add(sensor)
                    await db.flush()

                # Aggregate approach statistics
                v_count = sum(a.vehicle_count for a in telemetry.approaches)
                pcu = telemetry.total_pcu if telemetry.total_pcu > 0 else sum(a.pcu for a in telemetry.approaches)
                speeds = [a.mean_speed_kmh for a in telemetry.approaches if a.mean_speed_kmh is not None and a.mean_speed_kmh > 0]
                avg_speed = (sum(speeds) / len(speeds)) if speeds else None
                queue_lengths = [a.queue_length_m for a in telemetry.approaches if a.queue_length_m is not None]
                max_queue = max(queue_lengths) if queue_lengths else None

                breakdown = {}
                for a in telemetry.approaches:
                    for k, v in a.vehicle_breakdown.items():
                        breakdown[k] = breakdown.get(k, 0) + int(v)

                try:
                    ts = datetime.fromisoformat(telemetry.timestamp.replace("Z", "+00:00"))
                except Exception:
                    ts = datetime.utcnow()

                reading = TrafficReading(
                    id=uuid.uuid4(),
                    timestamp=ts,
                    sensor_id=sensor.id,
                    junction_id=j.id,
                    vehicle_count=v_count,
                    pcu_value=pcu,
                    avg_speed=avg_speed,
                    queue_length=max_queue,
                    vehicle_breakdown=breakdown if breakdown else None,
                    source=telemetry.source.value
                )
                db.add(reading)
                await db.commit()

            # Publish to Redis
            try:
                if not self.redis_client:
                    self.redis_client = aioredis.from_url(settings.REDIS_URL)
                await self.redis_client.publish(REDIS_CHANNELS["traffic"], telemetry.to_json())
            except Exception as e:
                logger.warning("Failed to publish telemetry to Redis: %s", e)

        except Exception as e:
            logger.error(f"Error persisting MQTT telemetry: {e}")


# Global daemon instance
mqtt_consumer = MQTTTelemetryConsumer()
