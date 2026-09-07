from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

try:
    import redis
except Exception:  # pragma: no cover - Redis client is optional during local scaffold runs
    redis = None

from backend.core.config import get_settings
from backend.services.observability import observability_registry

logger = logging.getLogger("firesight.cache")


class CacheService:
    _memory_cache: dict[str, tuple[float, str]] = {}

    def __init__(self):
        self.settings = get_settings()
        self.client = redis.Redis.from_url(self.settings.redis_url, decode_responses=True) if redis else None

    def get_json(self, key: str, *, include_expired: bool = False) -> Any | None:
        if self.client and not include_expired:
            try:
                value = self.client.get(key)
                if value:
                    return json.loads(value)
            except Exception as exc:
                logger.warning("cache_read_failed key=%s error=%s", key, exc.__class__.__name__)
        entry = self._memory_cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at <= time.time():
            if include_expired:
                return json.loads(value)
            self._memory_cache.pop(key, None)
            return None
        return json.loads(value)

    def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        if self.client:
            try:
                self.client.setex(key, ttl_seconds, json.dumps(value, default=str))
                return
            except Exception as exc:
                logger.warning("cache_write_failed key=%s ttl_seconds=%s error=%s", key, ttl_seconds, exc.__class__.__name__)
        self._memory_cache[key] = (time.time() + ttl_seconds, json.dumps(value, default=str))

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl_seconds: int = 300) -> Any:
        cached = self.get_json(key)
        if cached is not None:
            logger.info("cache_hit key=%s", key)
            observability_registry.record_cache_hit()
            return cached
        logger.info("cache_miss key=%s", key)
        observability_registry.record_cache_miss()
        value = factory()
        self.set_json(key, value, ttl_seconds)
        return value

    def health(self) -> dict:
        if not self.client:
            return {"status": "disabled", "backend": "memoryless"}
        try:
            self.client.ping()
            return {"status": "ok", "backend": "redis"}
        except Exception as exc:  # pragma: no cover - depends on external Redis
            logger.warning("cache_health_degraded error=%s", exc.__class__.__name__)
            return {"status": "degraded", "backend": "redis", "error": "Redis is unavailable"}
