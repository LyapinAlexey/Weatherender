import json
import logging
from typing import Any, Optional

import redis.asyncio as redis  # type: ignore[import-untyped]
from redis.exceptions import RedisError  # type: ignore[import-untyped]

from config import Config

logger = logging.getLogger(__name__)


class AsyncCacheService:
    def __init__(self) -> None:
        self.client: Any = redis.from_url(
            Config.REDIS_URL,
            decode_responses=True,
        )

    async def get(self, key: str) -> Optional[Any]:
        try:
            value = await self.client.get(key)
            if value is not None:
                res = json.loads(value)
                return res
        except (RedisError, json.JSONDecodeError) as err:
            logger.warning("Failed to get key '%s' from cache: %s", key, err)
            return None
        return None

    async def set(self, key: str, value: Any) -> None:
        try:
            json_value = json.dumps(value)
            await self.client.set(
                name=key,
                value=json_value,
                ex=Config.REDIS_TTL,
            )
        except (RedisError, TypeError) as err:
            logger.warning("Failed to set key '%s' in cache: %s", key, err)
