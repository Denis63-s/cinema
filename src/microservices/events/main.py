import os
import asyncio
import json
from fastapi import FastAPI
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer, errors

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
TOPICS = ["user-events", "payment-events", "movie-events"]

app = FastAPI()
producer: AIOKafkaProducer = None

class Event(BaseModel):
    payload: dict

@app.on_event("startup")
async def startup_event():
    global producer
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()
    asyncio.create_task(consume_messages())

@app.on_event("shutdown")
async def shutdown_event():
    await producer.stop()

@app.get("/api/events/health")
async def health_check():
    return {"status": True}

@app.post("/api/events/{event_type}")
async def send_event(event_type: str, event: Event):
    if event_type not in ["user", "payment", "movie"]:
        return {"error": "Invalid event type"}
    
    topic = f"{event_type}-events"
    msg = json.dumps(event.payload).encode("utf-8")
    await producer.send_and_wait(topic, msg)
    return {"status": "success", "topic": topic}

async def consume_messages():
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="events-service"
    )

    for i in range(5):
        try:
            await consumer.start()
            print("[Kafka] Consumer started.")
            break
        except errors.KafkaError as e:
            print(f"[Kafka] Retry consumer start in 3s ({i+1}/5): {e}")
            await asyncio.sleep(3)
    else:
        print("[Kafka] Failed to start consumer after retries")
        return

    try:
        async for msg in consumer:
            print(f"[Kafka] Consumed from {msg.topic}: {msg.value.decode()}")
            await asyncio.sleep(0.01)
    finally:
        await consumer.stop()
