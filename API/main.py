from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app):
    client = httpx.AsyncClient()
    app.state.http_client = client
    yield
    await client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/api/v2/weather")
async def get_weather_v2(request: Request): ...
