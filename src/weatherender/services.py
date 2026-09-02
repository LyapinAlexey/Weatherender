import logging
from typing import Any

import requests

from weatherender.cache import CacheService
from weatherender.config import Config

logger = logging.getLogger(__name__)
cache_service = CacheService()


class WeatherService:
    @staticmethod
    def get_elevation(lat: float, lon: float) -> float:
        cache_key = f"elevation:{lat}:{lon}"
        cached_val = cache_service.get(cache_key)
        if cached_val is not None:
            return float(cached_val)
        try:
            url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                elevations = data.get("elevation", [])
                if elevations:
                    elevation = float(elevations[0])
                    cache_service.set(cache_key, elevation, ttl=86400)
                    return elevation
        except Exception as e:
            logger.warning(f"Open-meteo elevation API Error: {e}")

        return 0.0

    @staticmethod
    def get_city_by_ip(ip_address: str | None = None) -> str | tuple[float, float]:
        if not ip_address or ip_address in ("127.0.0.1", "localhost", None):
            return "London"
        if "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()
        try:
            geo_resp = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=3)
            if geo_resp.status_code == 200:
                data = geo_resp.json()
                if data.get("status") == "success":
                    provider = (
                        str(data.get("org", "")) + " " + str(data.get("as", ""))
                    ).lower()
                    if (
                        "google" in provider
                        or "render" in provider
                        or "amazon" in provider
                    ):
                        return "Robot-Datacenter"

                    lat = data.get("lat")
                    lon = data.get("lon")
                    if lat is not None and lon is not None:
                        return f"{lat},{lon}"
        except Exception as e:
            logger.error(f"IP-API Error: {e}")
        try:
            response = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=3)
            if response.status_code == 200:
                data = response.json()
                provider = str(data.get("org", "")).lower()
                if "google" in provider or "render" in provider or "amazon" in provider:
                    return "Robot-Datacenter"

                loc = data.get("loc")
                if loc:
                    lat_str, lon_str = loc.split(",")
                    return float(lat_str), float(lon_str)
        except Exception as e:
            logger.error(f"Ipinfo Error: {e}")
        return "London"  # Fallback

    @staticmethod
    def get_weather(
        city: str | tuple[float, float], api_key: str | None = None
    ) -> dict[str, Any]:
        if isinstance(city, tuple):
            city = f"{city[0]},{city[1]}"
        else:
            city = city.strip()
        active_key = api_key or getattr(Config, "WEATHER_API_KEY", None)
        cache_key = f"weather:{city.strip().lower()}"
        cached_data = cache_service.get(cache_key)
        if cached_data:
            return cached_data  # type: ignore

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
            response = requests.get(Config.WEATHER_URL, params=params, timeout=5)
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
                cache_service.set(cache_key, data)
                return data  # type: ignore
            except ValueError:
                return {
                    "error": {
                        "message": "Error parsing response from server. Please check your internet connection."
                    }
                }
        except requests.RequestException as e:
            logger.error(f"Network error while fetching weather for {city}: {e}")
            return {
                "error": {
                    "message": "Network error. Look up your internet connection or try again later."
                }
            }
