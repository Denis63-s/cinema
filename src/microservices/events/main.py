import os
import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer, errors
from pydantic import BaseModel
from typing import Optional, Dict, Any

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
TOPICS = ["user-events", "payment-events", "movie-events"]

app = FastAPI()
producer: AIOKafkaProducer = None

class Event(BaseModel):
    type: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

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
async def send_event(event_type: str, request: Request):
    if event_type not in ["user", "payment", "movie"]:
        return JSONResponse(status_code=400, content={"error": "Invalid event type"})

    body = await request.json()

    # если это user-event — берём payload из вложенного поля
    if event_type == "user" and "payload" in body:
        message = body["payload"]
    else:
        message = body

    topic = f"{event_type}-events"
    msg = json.dumps(message).encode("utf-8")
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
    finally:
        await consumer.stop()
# Health check endpoint — ДОБАВЬ В САМЫЙ КОНЕЦ:
@app.get("/api/events/health")
async def health_check():
    return {"status": True}