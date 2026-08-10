import logging

import requests

from cache import CacheService
from config import Config

logger = logging.getLogger(__name__)
cache_service = CacheService()


class WeatherService:
    @staticmethod
    def get_city_by_ip(ip_address: str | None = None) -> str:
        if not ip_address or ip_address in ("127.0.0.1", "localhost", None):
            return "London"
        if "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()
        try:
            geo_resp = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=3)
            if geo_resp.status_code == 200:
                data = geo_resp.json()
                if data.get("status") == "success" and data.get("city"):
                    return str(data.get("city"))
        except Exception as e:
            logger.error(f"IP-API Error: {e}")
        try:
            response = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("city"):
                    return str(data.get("city"))
        except Exception as e:
            logger.error(f"Ipinfo Error: {e}")
        return "London"  # default city if all else fails

    @staticmethod
    def get_weather(city: str, api_key: str | None = None) -> dict:
        active_key = api_key or getattr(Config, "WEATHER_API_KEY", None)
        cache_key = f"weather:{city.strip().lower()}"
        cached_data = cache_service.get(cache_key)
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
                return data
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
