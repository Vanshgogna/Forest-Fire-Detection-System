from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Request
import redis.asyncio as redis
from redis.exceptions import RedisError

from backend.core.config import Settings, get_settings

logger = logging.getLogger("firesight.redis")

_redis_client: redis.Redis | None = None
_redis_health: dict[str, object] = {
    "status": "not_initialized",
    "backend": "redis",
    "detail": "Redis startup check has not run.",
}


def _redis_url(settings: Settings) -> str | None:
    url = settings.redis_connection_url()
    if url and url.startswith(("redis://", "rediss://", "unix://")):
        return url
    if settings.upstash_rest_only_configured():
        logger.warning(
            "redis_protocol_url_missing provider=upstash detail=UPSTASH_REDIS_REST_URL is configured, "
            "but redis.asyncio requires REDIS_URL or UPSTASH_REDIS_URL with a redis:// or rediss:// URL."
        )
    elif url:
        logger.warning("redis_invalid_url_scheme detail=Redis URL must use redis://, rediss://, or unix://.")
    return None


async def init_redis(settings: Settings | None = None) -> None:
    global _redis_client, _redis_health

    settings = settings or get_settings()
    url = _redis_url(settings)
    if not url:
        _redis_client = None
        _redis_health = {
            "status": "disabled",
            "backend": "redis",
            "detail": "Redis protocol URL is not configured.",
        }
        return

    try:
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            health_check_interval=30,
        )
        await client.ping()
    except RedisError as exc:
        _redis_client = None
        _redis_health = {
            "status": "degraded",
            "backend": "redis",
            "detail": "Redis PING failed.",
            "error": exc.__class__.__name__,
        }
        logger.warning("redis_connection_unavailable error=%s", exc.__class__.__name__)
        return

    _redis_client = client
    _redis_health = {
        "status": "ok",
        "backend": "redis",
        "detail": "Redis PING succeeded.",
    }
    logger.info("redis_connection_ready backend=redis")


async def close_redis() -> None:
    global _redis_client, _redis_health

    if _redis_client is None:
        return
    try:
        await _redis_client.aclose()
    except RedisError as exc:
        logger.warning("redis_close_failed error=%s", exc.__class__.__name__)
    finally:
        _redis_client = None
        _redis_health = {
            "status": "closed",
            "backend": "redis",
            "detail": "Redis connection has been closed.",
        }


def current_redis_client() -> redis.Redis | None:
    return _redis_client


def redis_health() -> dict[str, object]:
    return dict(_redis_health)


async def get_redis_client(request: Request) -> redis.Redis | None:
    return getattr(request.app.state, "redis", None) or current_redis_client()


RedisClient = Annotated[redis.Redis | None, Depends(get_redis_client)]
