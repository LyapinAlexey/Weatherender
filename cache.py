import json
import logging
from typing import Any, Optional

import redis  # type: ignore[import-untyped]
from redis.exceptions import RedisError  # type: ignore[import-untyped]

from config import Config

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        if not Config.REDIS_HOST or Config.REDIS_HOST in ["127.0.0.1", "cache"]:
            self.client = None
        else:
            self.client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                decode_responses=True,
            )

    def get(self, key: str) -> Optional[Any]:
        if self.client is None:
            return None
        try:
            value = self.client.get(key)
            if value is not None:
                return json.loads(value)
        except (RedisError, json.JSONDecodeError) as err:
            logger.warning("Failed to get key '%s' from cache: %s", key, err)
            return None
        return None

    def set(self, key: str, value: Any) -> None:
        if self.client is None:
            return
        try:
            json_value = json.dumps(value)
            self.client.setex(
                key,
                Config.REDIS_TTL,
                json_value,
            )
        except (RedisError, TypeError) as err:
            logger.warning("Failed to set key '%s' in cache: %s", key, err)
