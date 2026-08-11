from unittest.mock import MagicMock, patch

from redis.exceptions import RedisError  # type: ignore[import-untyped]

from cache import CacheService
from config import Config
from services import WeatherService


class TestCache:
    def test_get_success(self):
        cache = CacheService()
        cache.client.get = MagicMock(return_value='{"city": "London", "temp": 15}')
        result = cache.get("weather:London")
        assert result == {"city": "London", "temp": 15}
        cache.client.get.assert_called_once_with("weather:London")

    def test_get_key_not_found(self):
        cache = CacheService()
        cache.client.get = MagicMock(return_value=None)
        result = cache.get("weather:London")
        assert result is None

    def test_get_redis_error(self):
        cache = CacheService()
        cache.client.get = MagicMock(side_effect=RedisError("Connection lost"))
        result = cache.get("weather:London")
        assert result is None

    def test_get_json_decode_error(self):
        cache = CacheService()
        cache.client.get = MagicMock(return_value="invalid json")
        result = cache.get("weather:London")
        assert result is None

    def test_set_success(self):
        cache = CacheService()
        cache.client.set = MagicMock()
        data = {"temp": 15}
        cache.set("weather:London", data)
        cache.client.set.assert_called_once_with(
            name="weather:London",
            value='{"temp": 15}',
            ex=Config.REDIS_TTL,
        )

    def test_set_type_error(self):
        cache = CacheService()
        cache.client.setex = MagicMock()
        cache.set("weather:London", {1, 2, 3})

    def test_set_redis_error(self):
        cache = CacheService()
        cache.client.setex = MagicMock(side_effect=RedisError("Write error"))
        cache.set("weather:London", {"temp": 15})

    @patch("services.cache_service")
    @patch("requests.get")
    def test_get_weather_cache_hit(self, mock_requests, mock_cache):
        mock_cache.get.return_value = {"city": "London", "temp": 15}
        result = WeatherService.get_weather("London", "test_key")
        assert result == {"city": "London", "temp": 15}
        mock_cache.get.assert_called_once_with("weather:london")
        mock_requests.assert_not_called()

    @patch("services.cache_service")
    @patch("requests.get")
    def test_get_weather_cache_miss_and_set(self, mock_requests, mock_cache):
        mock_cache.get.return_value = None
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.headers = {"Content-Type": "application/json"}
        mock_requests.return_value.json.return_value = {"city": "London", "temp": 20}
        result = WeatherService.get_weather("London", "test_key")
        assert result == {"city": "London", "temp": 20}
        mock_cache.get.assert_called_once_with("weather:london")
        mock_cache.set.assert_called_once_with(
            "weather:london", {"city": "London", "temp": 20}
        )
