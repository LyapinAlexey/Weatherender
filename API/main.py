import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "WEB"

for path in (ROOT_DIR, WEB_DIR):
    if str(path) not in sys.path:
        sys.path.append(str(path))

import logging

import httpx
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from snow import get_snow_state
from WEB.app import app as flask_app

try:
    from .async_cache import cache_service
    from .async_db import AsyncSessionLocal
    from .async_services import AsyncWeatherService
    from .pydantic_schemas import WeatherQueryParams, WeatherResponseV2
except ImportError:
    from async_services import AsyncWeatherService  # type: ignore[no-redef]
    from async_db import AsyncSessionLocal  # type: ignore[no-redef]
    from async_cache import cache_service  # type: ignore[no-redef]
    from pydantic_schemas import WeatherQueryParams, WeatherResponseV2  # type: ignore[no-redef]

from logging_config import setup_logging
from models import WeatherRequest

limiter = Limiter(key_func=get_remote_address)
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    )
    app.state.http_client = client
    yield
    await client.aclose()
    await cache_service.close()


app = FastAPI(
    lifespan=lifespan,
    docs_url="/v2/docs",
    redoc_url="/v2/redoc",
    openapi_url="/v2/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.2, max=2.0),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
@app.get("/api/v2/weather", response_model=WeatherResponseV2)
@limiter.limit("25/minute")
async def get_weather_v2(
    request: Request, params: Annotated[WeatherQueryParams, Query()]
) -> WeatherResponseV2:
    city = params.city
    client = request.app.state.http_client
    weather_data = await AsyncWeatherService.get_weather_async(client=client, city=city)
    if "error" in weather_data:
        info_err = WeatherRequest(
            city=str(city),
            source="api-v2",
            success=0,
            error_message=weather_data["error"].get("message"),
        )
        async with AsyncSessionLocal() as session:
            session.add(info_err)
            await session.commit()
        raise HTTPException(status_code=404, detail=weather_data["error"])
    else:
        info_suc = WeatherRequest(
            city=city,
            source="api-v2",
            temp_c=round(weather_data["current"]["temp_c"], 2),
            condition=weather_data["current"]["condition"]["text"],
            success=1,
            error_message=None,
        )
        async with AsyncSessionLocal() as session:
            session.add(info_suc)
            await session.commit()
    forecast_days = weather_data.get("forecast", {}).get("forecastday", [])
    current = weather_data.get("current", {})

    if forecast_days:
        today_day = forecast_days[0].get("day", {})
        weather_data["snow_state"] = get_snow_state(
            temp_c=current.get("temp_c", 0),
            min_temp_c=today_day.get("mintemp_c", current.get("temp_c", 0)),
            max_temp_c=today_day.get("maxtemp_c", current.get("temp_c", 0)),
            humidity=current.get("humidity", 50),
            snow_depth_cm=today_day.get("totalsnow_cm", 0.0),
            snow_24h_cm=today_day.get("totalsnow_cm", 0.0),
            wind_kph=current.get("wind_kph", 0),
            cloud_cover=current.get("cloud", 0),
            condition_text=current.get("condition", {}).get("text", ""),
            prev_day_max_temp=today_day.get("maxtemp_c", current.get("temp_c", 0)),
            totalprecip_mm=today_day.get("totalprecip_mm", 0.0),
            will_it_snow=today_day.get("daily_will_it_snow", 0),
            totalsnow_cm=today_day.get("totalsnow_cm", 0.0),
        )
    else:
        weather_data["snow_state"] = {"status": "No snow data"}

    snow_forecast = []
    for i, day in enumerate(forecast_days):
        day_info = day.get("day", {})
        if i > 0:
            prev_day_info = forecast_days[i - 1].get("day", {})
            prev_day_max_temp = prev_day_info.get(
                "maxtemp_c", day_info.get("avgtemp_c", 0)
            )
        else:
            prev_day_max_temp = day_info.get("maxtemp_c", 0)

        day_snow_state = get_snow_state(
            temp_c=day_info.get("avgtemp_c", 0),
            min_temp_c=day_info.get("mintemp_c", 0),
            max_temp_c=day_info.get("maxtemp_c", 0),
            humidity=day_info.get("avghumidity", 50),
            snow_depth_cm=day_info.get("totalsnow_cm", 0.0),
            snow_24h_cm=day_info.get("totalsnow_cm", 0.0),
            wind_kph=day_info.get("maxwind_kph", 0),
            cloud_cover=50,
            condition_text=day_info.get("condition", {}).get("text", ""),
            prev_day_max_temp=prev_day_max_temp,
            totalprecip_mm=day_info.get("totalprecip_mm", 0.0),
            will_it_snow=day_info.get("daily_will_it_snow", 0),
            totalsnow_cm=day_info.get("totalsnow_cm", 0.0),
        )
        snow_forecast.append(
            {
                "date": day.get("date"),
                "snow_state": day_snow_state,
            }
        )

    weather_data["snow_forecast"] = snow_forecast
    return WeatherResponseV2.model_validate(weather_data)


@app.get("/api/v2/health")
async def health_check() -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
            logger.info("Health check passed")
            return {"status": "ok"}
        except Exception:
            logger.exception("Health check error")
            raise HTTPException(status_code=503, detail="503 Service Unavailable")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Created to fix the 404 icon error."""
    return FileResponse("favicon.png")


app.mount("/", WSGIMiddleware(flask_app))
