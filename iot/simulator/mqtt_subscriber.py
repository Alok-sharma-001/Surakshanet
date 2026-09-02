import json
import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import Json

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
        client.subscribe("surakshanet/junction/+/telemetry")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            cursor = self.db_conn.cursor()
            
            insert_query = """
                INSERT INTO traffic_readings 
                (junction_id, timestamp, north_pcu, east_pcu, south_pcu, west_pcu, avg_speed, queue_length, phase, vehicle_counts) 
                VALUES (%s, to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                payload.get('junction_id'),
                payload.get('timestamp'),
                payload.get('north_pcu'),
                payload.get('east_pcu'),
                payload.get('south_pcu'),
                payload.get('west_pcu'),
                payload.get('avg_speed'),
                payload.get('queue_length'),
                payload.get('phase'),
                Json(payload.get('vehicle_counts')) if payload.get('vehicle_counts') else None
            ))
            
            self.db_conn.commit()
            cursor.close()
            print(f"Saved telemetry for junction {payload.get('junction_id')}")
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
