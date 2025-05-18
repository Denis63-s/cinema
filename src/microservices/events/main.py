import os
import asyncio
import json
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer, errors

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
TOPICS = ["user-events", "payment-events", "movie-events"]

app = FastAPI()

producer: AIOKafkaProducer = None  # глобальная переменная

class EventPayload(BaseModel):
    # Movie event
    movie_id: Optional[int] = None
    title: Optional[str] = None
    action: Optional[str] = None
    user_id: Optional[int] = None

    # User event
    username: Optional[str] = None
    timestamp: Optional[str] = None

    # Payment event
    payment_id: Optional[int] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    method_type: Optional[str] = None

class Event(BaseModel):
    type: str
    payload: EventPayload

@app.on_event("startup")
async def startup_event():
    global producer
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()
    asyncio.create_task(consume_messages())

@app.on_event("shutdown")
async def shutdown_event():
    await producer.stop()

@app.post("/api/events/{event_type}", status_code=201)
async def send_event(event_type: str, event: Event):
    if event_type not in ["user", "payment", "movie"]:
        return JSONResponse(status_code=400, content={"error": "Invalid event type"})

    topic = f"{event_type}-events"
    msg = json.dumps(event.payload.dict()).encode("utf-8")
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
