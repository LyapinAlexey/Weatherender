import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from redis.exceptions import RedisError

from config import Config

logger = logging.getLogger(__name__)


class AsyncCacheService:
    def __init__(self) -> None:
        self.client: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        if self.client is None:
            self.client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        return self.client

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()  # type: ignore[attr-defined]

    async def get(self, key: str) -> Optional[Any]:
        try:
            client = self._get_client()
            value = await client.get(key)
            if value is not None:
                return json.loads(value)
        except (RedisError, json.JSONDecodeError) as err:
            logger.warning("Failed to get key '%s' from cache: %s", key, err)
        return None

    async def set(self, key: str, value: Any) -> None:
        try:
            client = self._get_client()
            json_value = json.dumps(value, default=str)
            await client.set(
                name=key,
                value=json_value,
                ex=Config.REDIS_TTL,
            )
        except (RedisError, TypeError) as err:
            logger.warning("Failed to set key '%s' in cache: %s", key, err)


cache_service = AsyncCacheService()
