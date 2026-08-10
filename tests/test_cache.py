from unittest.mock import MagicMock

from redis.exceptions import RedisError  # type: ignore[import-untyped]

from cache import CacheService
from config import Config


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
        cache.client.setex = MagicMock()
        data = {"temp": 15}
        cache.set("weather:London", data)
        cache.client.setex.assert_called_once_with(
            "weather:London", Config.REDIS_TTL, '{"temp": 15}'
        )

    def test_set_type_error(self):
        cache = CacheService()
        cache.client.setex = MagicMock()
        cache.set("weather:London", {1, 2, 3})

    def test_set_redis_error(self):
        cache = CacheService()
        cache.client.setex = MagicMock(side_effect=RedisError("Write error"))
        cache.set("weather:London", {"temp": 15})
