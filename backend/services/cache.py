from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

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
        redis_url = self.settings.redis_connection_url()
        if redis_url and not redis_url.startswith(("redis://", "rediss://", "unix://")):
            redis_url = None
        self.client = redis.Redis.from_url(redis_url, decode_responses=True) if redis and redis_url else None

    def get_json(self, key: str, *, include_expired: bool = False) -> Any | None:
        if self.client and not include_expired:
            try:
                value = self.client.get(key)
                if value:
                    logger.info("redis_cache_hit key=%s", key)
                    return json.loads(value)
                logger.info("redis_cache_miss key=%s", key)
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
                logger.info("redis_cache_write key=%s ttl_seconds=%s", key, ttl_seconds)
                return
            except Exception as exc:
                logger.warning("cache_write_failed key=%s ttl_seconds=%s error=%s", key, ttl_seconds, exc.__class__.__name__)
        self._memory_cache[key] = (time.time() + ttl_seconds, json.dumps(value, default=str))

    def acquire_lock(self, key: str, ttl_seconds: int = 15) -> str | None:
        token = uuid4().hex
        if self.client:
            try:
                acquired = self.client.set(key, token, nx=True, ex=ttl_seconds)
                logger.info("redis_lock_%s key=%s ttl_seconds=%s", "acquired" if acquired else "busy", key, ttl_seconds)
                return token if acquired else None
            except Exception as exc:
                logger.warning("cache_lock_acquire_failed key=%s error=%s", key, exc.__class__.__name__)
        return token

    def release_lock(self, key: str, token: str) -> None:
        if not self.client:
            return
        try:
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            end
            return 0
            """
            self.client.eval(script, 1, key, token)
            logger.info("redis_lock_released key=%s", key)
        except Exception as exc:
            logger.warning("cache_lock_release_failed key=%s error=%s", key, exc.__class__.__name__)

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
            reason = "redis_protocol_url_missing" if self.settings.upstash_rest_only_configured() else "redis_client_unavailable"
            return {"status": "disabled", "backend": "memoryless", "reason": reason}
        try:
            self.client.ping()
            return {"status": "ok", "backend": "redis"}
        except Exception as exc:  # pragma: no cover - depends on external Redis
            logger.warning("cache_health_degraded error=%s", exc.__class__.__name__)
            return {"status": "degraded", "backend": "redis", "error": "Redis is unavailable"}
