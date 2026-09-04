import json
import time
import random
import uuid
import paho.mqtt.client as mqtt
from typing import Dict, Any, List

class SensorSimulator:
    def __init__(self, broker_host: str, broker_port: int, junctions: List[Dict[str, Any]]):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.junctions = junctions
        self.client = mqtt.Client(client_id=f"sim-{uuid.uuid4().hex[:6]}")
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            print(f"Connected to MQTT broker at {broker_host}:{broker_port}")
        except Exception as e:
            print(f"Failed to connect to broker: {e}")

    def generate_telemetry(self, junction: Dict[str, Any]) -> Dict[str, Any]:
        hour = time.localtime().tm_hour
        peak = (8 <= hour <= 11) or (17 <= hour <= 20)
        multiplier = 1.8 if peak else 1.0

        cars = int(random.uniform(10, 30) * multiplier)
        motorcycles = int(random.uniform(15, 45) * multiplier)
        buses = int(random.uniform(1, 5) * multiplier)
        trucks = int(random.uniform(1, 4) * multiplier)
        autos = int(random.uniform(5, 15) * multiplier)

        pcu = round(cars * 1.0 + motorcycles * 0.5 + buses * 3.0 + trucks * 3.0 + autos * 1.0, 1)
        speed = round(max(8.0, 52.0 - (pcu * 0.4) + random.uniform(-3, 3)), 1)
        queue = round(max(0.0, (pcu - 25) * 1.2), 1)

        sensor_id = junction.get("sensor_id", str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{junction['id']}-N")))

        return {
            "junction_id": junction["id"],
            "junction_name": junction["name"],
            "sensor_id": sensor_id,
            "timestamp": time.time(),
            "pcu_value": pcu,
            "avg_speed": speed,
            "queue_length": queue,
            "vehicle_count": cars + motorcycles + buses + trucks + autos,
            "vehicle_breakdown": {
                "car": cars,
                "motorcycle": motorcycles,
                "bus": buses,
                "truck": trucks,
                "auto_rickshaw": autos
            }
        }

    def publish_telemetry(self, junction: Dict[str, Any], data: Dict[str, Any]) -> None:
        topic = f"surakshanet/sensors/{data['sensor_id']}/telemetry"
        self.client.publish(topic, json.dumps(data))
        print(f"[{time.strftime('%H:%M:%S')}] Published to {topic} -> {junction['name']}: {data['pcu_value']} PCU, {data['avg_speed']} km/h")

    def run(self, interval_seconds: int = 5) -> None:
        try:
            print(f"Starting IoT Sensor Simulator across {len(self.junctions)} corridors (interval: {interval_seconds}s)...")
            while True:
                for junction in self.junctions:
                    data = self.generate_telemetry(junction)
                    self.publish_telemetry(junction, data)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("Simulator stopped.")
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == '__main__':
    city_corridors = [
        {"id": "DEL-CP-01", "name": "Connaught Place Outer Circle"},
        {"id": "DEL-ITO-02", "name": "ITO Crossing - Vikas Marg"},
        {"id": "DEL-AIIMS-03", "name": "AIIMS Flyover - Ring Road"},
        {"id": "DEL-ASH-04", "name": "Ashram Chowk - Mathura Road"},
        {"id": "DEL-DHK-05", "name": "Dhaula Kuan Interchange"},
        {"id": "DEL-LAJ-06", "name": "Lajpat Nagar Ring Road"},
        {"id": "BLR-MGR-01", "name": "MG Road - Brigade Junction"},
        {"id": "BLR-SLK-02", "name": "Silk Board Junction"},
        {"id": "BLR-IND-03", "name": "Indiranagar 100ft Road"},
        {"id": "BLR-KOR-04", "name": "Koramangala Sony World Signal"}
    ]
    simulator = SensorSimulator("localhost", 1883, city_corridors)
    simulator.run(interval_seconds=5)
