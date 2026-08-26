import json
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from API.async_cache import AsyncCacheService


@pytest.mark.asyncio
class TestAsyncCacheService:
    @patch("API.async_cache.redis.from_url")
    async def test_cache_get_success(self, mock_redis_from_url):
        mock_client = AsyncMock()
        mock_client.get.return_value = json.dumps({"test": "data"})
        mock_redis_from_url.return_value = mock_client

        cache = AsyncCacheService()
        result = await cache.get("my_key")

        assert result == {"test": "data"}
        mock_client.get.assert_called_once_with("my_key")

    @patch("API.async_cache.redis.from_url")
    async def test_cache_get_redis_error_returns_none(self, mock_redis_from_url):
        mock_client = AsyncMock()
        mock_client.get.side_effect = RedisError("Connection lost")
        mock_redis_from_url.return_value = mock_client

        cache = AsyncCacheService()
        result = await cache.get("my_key")

        assert result is None

    @patch("API.async_cache.redis.from_url")
    async def test_cache_set_success(self, mock_redis_from_url):
        mock_client = AsyncMock()
        mock_redis_from_url.return_value = mock_client

        cache = AsyncCacheService()
        await cache.set("my_key", {"data": 123})

        mock_client.set.assert_called_once()

    @patch("API.async_cache.redis.from_url")
    async def test_cache_set_redis_error_handled(self, mock_redis_from_url):
        mock_client = AsyncMock()
        mock_client.set.side_effect = RedisError("Write error")
        mock_redis_from_url.return_value = mock_client

        cache = AsyncCacheService()
        await cache.set("my_key", {"data": 123})

    @patch("API.async_cache.redis.from_url")
    async def test_cache_close_client(self, mock_redis_from_url):
        mock_client = AsyncMock()
        mock_redis_from_url.return_value = mock_client

        cache = AsyncCacheService()
        cache.client = mock_client
        await cache.close()

        mock_client.aclose.assert_awaited_once()
