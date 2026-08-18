import logging

import requests

from cache import CacheService
from config import Config

logger = logging.getLogger(__name__)
cache_service = CacheService()


class WeatherService:
    @staticmethod
    def get_elevation(lat: float, lon: float):
        try:
            url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    return float(results[0].get("elevation", 0.0))
        except Exception as e:
            logger.error(f"Elevation API Error: {e}")
        return 0.0

    @staticmethod
    def get_snow_state(
        temp_c: float = 0.0,
        min_temp_c: float = 0.0,
        max_temp_c: float = 0.0,
        humidity: int = 50,
        snow_depth_cm: float = 0.0,
        snow_24h_cm: float = 0.0,
        wind_kph: float = 0.0,
        cloud_cover: int = 0,
        condition_text: str = "",
        prev_day_max_temp: float = 0.0,
        totalprecip_mm: float = 0.0,
    ) -> dict:

        cond = condition_text.lower()
        snow_density = (totalprecip_mm / (snow_24h_cm * 10)) if snow_24h_cm > 0 else 0.1

        if snow_depth_cm <= 0 and snow_24h_cm <= 0 and totalprecip_mm < 0.1:
            return {"status": "No snow data"}

        if snow_depth_cm > 0 or snow_24h_cm > 0:
            is_freeze_thaw = max_temp_c > 0 and min_temp_c < 0
            if (
                is_freeze_thaw
                or prev_day_max_temp > 2.0
                or "ice" in cond
                or "freezing" in cond
            ):
                if snow_24h_cm < 5:
                    return {"status": "Ice crust"}

        if temp_c > 0.5 or (temp_c >= -0.5 and humidity > 80):
            if cloud_cover < 30 and temp_c > 0:
                return {"status": "Spring slush"}
            return {"status": "Wet snow"}

        if temp_c <= -5 and snow_24h_cm >= 15:
            if snow_density < 0.08:
                return {"status": "Dry champagne powder!"}
            if wind_kph > 30:
                return {"status": "Wind-drifted powder"}
            return {"status": "Powder"}

        if wind_kph > 35:
            return {"status": "Wind slab"}

        if temp_c <= 0:
            if snow_24h_cm >= 8:
                return {"status": "Fresh, firm snow"}
            return {"status": "Hard-packed snow"}

        return {"status": "Unstable conditions"}

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
    ) -> dict:
        if isinstance(city, tuple):
            city = f"{city[0]},{city[1]}"
        else:
            city = city.strip()
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
