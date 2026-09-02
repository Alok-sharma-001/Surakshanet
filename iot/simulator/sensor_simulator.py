import json
import time
import random
import paho.mqtt.client as mqtt
from typing import Dict, Any, List

class SensorSimulator:
    def __init__(self, broker_host: str, broker_port: int, junctions: List[Dict[str, Any]]):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.junctions = junctions
        self.client = mqtt.Client()
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()

    def generate_camera_data(self, junction_id: str, approach: str) -> Dict[str, Any]:
        hour = time.localtime().tm_hour
        peak = (8 <= hour <= 11) or (17 <= hour <= 20)
        multiplier = 2.0 if peak else 1.0
        
        counts = {
            "car": int(random.uniform(5, 15) * 0.25 * multiplier),
            "motorcycle": int(random.uniform(5, 15) * 0.40 * multiplier),
            "bus": int(random.uniform(0, 2) * 0.05 * multiplier),
            "truck": int(random.uniform(0, 2) * 0.05 * multiplier),
            "auto_rickshaw": int(random.uniform(2, 5) * 0.15 * multiplier),
            "bicycle": int(random.uniform(1, 3) * 0.10 * multiplier)
        }
        
        pcu = (
            counts["car"] * 1.0 +
            counts["motorcycle"] * 0.5 +
            counts["bus"] * 3.0 +
            counts["truck"] * 3.0 +
            counts["auto_rickshaw"] * 0.75 +
            counts["bicycle"] * 0.2
        )
        return {"counts": counts, "pcu": pcu}

    def generate_induction_data(self, junction_id: str, approach: str) -> Dict[str, float]:
        return {
            "vehicle_count": random.uniform(10, 50),
            "occupancy": random.uniform(0.1, 0.9)
        }

    def generate_acoustic_data(self, junction_id: str, approach: str) -> Dict[str, float]:
        return {
            "noise_level": random.uniform(60.0, 90.0),
            "estimated_density": random.uniform(0.1, 0.8)
        }

    def generate_gps_probe_data(self, junction_id: str) -> Dict[str, float]:
        return {
            "avg_speed": random.uniform(10.0, 60.0),
            "sample_size": random.uniform(5, 20)
        }

    def generate_telemetry(self, junction_id: str) -> Dict[str, Any]:
        telemetry = {
            "junction_id": junction_id,
            "timestamp": time.time(),
            "north_pcu": self.generate_camera_data(junction_id, "N")["pcu"],
            "east_pcu": self.generate_camera_data(junction_id, "E")["pcu"],
            "south_pcu": self.generate_camera_data(junction_id, "S")["pcu"],
            "west_pcu": self.generate_camera_data(junction_id, "W")["pcu"],
            "avg_speed": self.generate_gps_probe_data(junction_id)["avg_speed"],
            "queue_length": random.uniform(0.0, 100.0),
            "phase": random.choice(["NS_green", "EW_green", "N_right", "S_right"]),
            "vehicle_counts": self.generate_camera_data(junction_id, "N")["counts"]
        }
        return telemetry

    def publish_telemetry(self, junction_id: str, data: Dict[str, Any]) -> None:
        topic = f"surakshanet/junction/{junction_id}/telemetry"
        self.client.publish(topic, json.dumps(data))
        print(f"Published to {topic}: {data}")

    def run(self, interval_seconds: int = 5) -> None:
        try:
            while True:
                for junction in self.junctions:
                    data = self.generate_telemetry(junction["id"])
                    self.publish_telemetry(junction["id"], data)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("Simulator stopped.")
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == '__main__':
    sample_junctions = [
        {"id": "j1", "name": "Connaught Place", "approaches": ["N", "E", "S", "W"]},
        {"id": "j2", "name": "India Gate", "approaches": ["N", "E", "S", "W"]},
        {"id": "j3", "name": "Rajiv Chowk", "approaches": ["N", "E", "S", "W"]},
        {"id": "j4", "name": "ITO", "approaches": ["N", "E", "S", "W"]}
    ]
    simulator = SensorSimulator("localhost", 1883, sample_junctions)
    simulator.run()
