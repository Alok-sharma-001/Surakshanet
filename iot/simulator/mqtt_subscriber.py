import json
import uuid
import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import Json

try:
    from shared.constants import MQTT_JUNCTION_TELEMETRY_TOPIC
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from shared.constants import MQTT_JUNCTION_TELEMETRY_TOPIC

class MQTTSubscriber:
    def __init__(self, broker_host: str, broker_port: int, database_url: str):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.database_url = database_url
        self.db_conn = psycopg2.connect(self.database_url)
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        sub_topic = MQTT_JUNCTION_TELEMETRY_TOPIC.replace("{junction_id}", "+")
        client.subscribe(sub_topic)
        client.subscribe("surakshanet/junction/+/telemetry")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            cursor = self.db_conn.cursor()

            reading_id = str(uuid.uuid4())
            ts = payload.get('timestamp')
            pcu = float(payload.get('pcu_value', (payload.get('north_pcu', 0.0) or 0.0) + (payload.get('south_pcu', 0.0) or 0.0) + (payload.get('east_pcu', 0.0) or 0.0) + (payload.get('west_pcu', 0.0) or 0.0) or 25.0))
            v_count = float(payload.get('vehicle_count', 20.0))
            speed = float(payload.get('avg_speed', 35.0))
            queue = float(payload.get('queue_length', 0.0))
            source = payload.get('source', 'sim')
            breakdown = payload.get('vehicle_breakdown', payload.get('vehicle_counts', {}))
            junction_id = payload.get('junction_id')
            sensor_id = payload.get('sensor_id') or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{junction_id}-N"))
            
            insert_query = """
                INSERT INTO traffic_readings 
                (id, timestamp, sensor_id, junction_id, vehicle_count, pcu_value, avg_speed, queue_length, vehicle_breakdown, source) 
                VALUES (%s, COALESCE(to_timestamp(%s), CURRENT_TIMESTAMP), %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                reading_id,
                ts if isinstance(ts, (int, float)) else None,
                sensor_id,
                junction_id,
                v_count,
                pcu,
                speed,
                queue,
                Json(breakdown) if breakdown else None,
                source
            ))
            
            self.db_conn.commit()
            cursor.close()
            print(f"Saved telemetry for junction {junction_id} [source={source}]")
        except Exception as e:
            print(f"Error processing message: {e}")
            self.db_conn.rollback()

    def run(self):
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_forever()

if __name__ == '__main__':
    DB_URL = "postgresql://user:password@localhost/surakshanet"
    subscriber = MQTTSubscriber("localhost", 1883, DB_URL)
    subscriber.run()
