import logging

import httpx

from API.async_cache import AsyncCacheService
from config import Config

logger = logging.getLogger(__name__)
cache_service = AsyncCacheService()


class AsyncWeatherService:
    @staticmethod
    async def get_weather_async(
        client: httpx.AsyncClient, city: str, api_key: str | None = None
    ) -> dict:
        if isinstance(city, tuple):
            city = f"{city[0]},{city[1]}"
        else:
            city = city.strip()
        active_key = api_key or getattr(Config, "WEATHER_API_KEY", None)
        cache_key = f"weather:{city.strip().lower()}"
        cached_data = await cache_service.get(cache_key)
        if cached_data:
            return cached_data

        if not active_key:
            return {
                "error": {
                    "message": "API key is missing. Please provide a valid WeatherAPI key."
                }
            }
        params = {
            "key": active_key,
            "q": city,
            "days": 3,
            "aqi": "yes",
            "alerts": "no",
            "lang": "en",
        }
        try:
            response = await client.get(Config.WEATHER_URL, params=params, timeout=5)
            if response.status_code in [401, 403]:
                return {
                    "error": {
                        "message": "Invalid API key. Please check your key and try again."
                    }
                }
            if response.status_code == 400:
                return {"error": {"message": f"City '{city}' not found."}}
            if "application/json" not in response.headers.get("Content-Type", ""):
                return {
                    "error": {
                        "message": f"API returned invalid response format (Status: {response.status_code}). "
                        f"Perhaps access is blocked. Please enable or change your VPN location!"
                    }
                }
            if response.status_code != 200:
                return {
                    "error": {
                        "message": f"Weather service error. Status code: {response.status_code}"
                    }
                }
            try:
                data = response.json()
                await cache_service.set(cache_key, data)
                return data
            except ValueError:
                return {
                    "error": {
                        "message": "Error parsing response from server. Please check your internet connection."
                    }
                }
        except httpx.RequestError as e:
            logger.error(f"Network error while fetching weather for {city}: {e}")
            return {
                "error": {
                    "message": "Network error. Look up your internet connection or try again later."
                }
            }
