import os
import random
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

app = FastAPI()

MONOLITH_URL = os.getenv("MONOLITH_URL", "http://monolith:8080")
MOVIES_SERVICE_URL = os.getenv("MOVIES_SERVICE_URL", "http://movies-service:8081")
GRADUAL_MIGRATION = os.getenv("GRADUAL_MIGRATION", "false").lower() == "true"
MIGRATION_PERCENT = int(os.getenv("MOVIES_MIGRATION_PERCENT", "0"))

@app.get("/api/movies")
async def proxy_movies(request: Request):
    # логика фиче-флага
    if GRADUAL_MIGRATION and random.randint(1, 100) <= MIGRATION_PERCENT:
        target_url = f"{MOVIES_SERVICE_URL}/api/movies"
    else:
        target_url = f"{MONOLITH_URL}/api/movies"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(target_url)
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type=response.headers.get("Content-Type")
            )
        except httpx.RequestError as e:
            return JSONResponse(
                status_code=502,
                content={"error": f"Ошибка при обращении к целевому сервису: {str(e)}"}
            )
