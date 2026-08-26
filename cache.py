import json
import logging
from typing import Any, Optional

import redis  # type: ignore[import-untyped]
from redis.exceptions import RedisError  # type: ignore[import-untyped]

from config import Config

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self.client: Any = redis.from_url(
            Config.REDIS_URL,
            decode_responses=True,
        )

    def get(self, key: str) -> Optional[Any]:
        try:
            value = self.client.get(key)
            if value is not None:
                return json.loads(value)
        except (RedisError, json.JSONDecodeError) as err:
            logger.warning("Failed to get key '%s' from cache: %s", key, err)
            return None
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            json_value = json.dumps(value)
            self.client.set(
                name=key,
                value=json_value,
                ex=ttl if ttl is not None else Config.REDIS_TTL,
            )
        except (RedisError, TypeError) as err:
            logger.warning("Failed to set key '%s' in cache: %s", key, err)
