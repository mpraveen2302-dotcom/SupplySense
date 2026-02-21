from kafka import KafkaProducer
import json
import os

producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_SERVER"),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def send_event(event_type, data):
    producer.send("supply_events", {
        "type": event_type,
        "data": data
    })
