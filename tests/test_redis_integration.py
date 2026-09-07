from __future__ import annotations

import asyncio

from backend.core.config import DEFAULT_REDIS_URL, Settings
from backend.database import redis as redis_module
from backend.services.cache import CacheService


def test_upstash_rest_only_configuration_is_redacted_and_not_used_as_redis_url():
    settings = Settings(
        ENVIRONMENT="development",
        REDIS_URL=DEFAULT_REDIS_URL,
        UPSTASH_REDIS_REST_URL="https://redis-rest.example",
        UPSTASH_REDIS_REST_TOKEN="secret-token",
    )

    public_config = settings.public_config()
    serialized = str(public_config)

    assert settings.upstash_rest_only_configured() is True
    assert settings.redis_connection_url() is None
    assert public_config["redis_configured"] is True
    assert public_config["redis_protocol_configured"] is False
    assert public_config["upstash_redis_rest_configured"] is True
    assert "secret-token" not in serialized
    assert "redis-rest.example" not in serialized


def test_upstash_protocol_url_takes_precedence_over_default_redis_url():
    settings = Settings(
        ENVIRONMENT="development",
        REDIS_URL=DEFAULT_REDIS_URL,
        UPSTASH_REDIS_URL="rediss://default:password@redis.example:6379",
        UPSTASH_REDIS_REST_URL="https://redis-rest.example",
        UPSTASH_REDIS_REST_TOKEN="secret-token",
    )

    assert settings.redis_connection_url() == "rediss://default:password@redis.example:6379"
    assert settings.public_config()["redis_protocol_configured"] is True


def test_async_redis_lifecycle_pings_and_closes_client(monkeypatch):
    class FakeRedis:
        pinged = False
        closed = False

        async def ping(self):
            self.pinged = True
            return True

        async def aclose(self):
            self.closed = True

    fake_client = FakeRedis()
    captured: dict[str, object] = {}

    def fake_from_url(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return fake_client

    monkeypatch.setattr(redis_module.redis, "from_url", fake_from_url)
    settings = Settings(ENVIRONMENT="development", REDIS_URL="redis://cache.example:6379/0")

    asyncio.run(redis_module.init_redis(settings))

    assert captured["url"] == "redis://cache.example:6379/0"
    assert captured["kwargs"]["decode_responses"] is True
    assert fake_client.pinged is True
    assert redis_module.current_redis_client() is fake_client
    assert redis_module.redis_health()["status"] == "ok"

    asyncio.run(redis_module.close_redis())

    assert fake_client.closed is True
    assert redis_module.current_redis_client() is None
    assert redis_module.redis_health()["status"] == "closed"


def test_cache_service_uses_redis_for_json_and_locks():
    class FakeRedisSync:
        def __init__(self):
            self.values: dict[str, str] = {}
            self.expirations: dict[str, int] = {}

        def get(self, key: str):
            return self.values.get(key)

        def setex(self, key: str, ttl_seconds: int, value: str):
            self.values[key] = value
            self.expirations[key] = ttl_seconds

        def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
            if nx and key in self.values:
                return False
            self.values[key] = value
            if ex is not None:
                self.expirations[key] = ex
            return True

        def eval(self, _: str, __: int, key: str, token: str):
            if self.values.get(key) == token:
                self.values.pop(key, None)
                return 1
            return 0

    fake_redis = FakeRedisSync()
    cache = CacheService()
    cache.client = fake_redis

    assert cache.get_json("weather:test") is None
    cache.set_json("weather:test", {"status": "ok"}, ttl_seconds=30)
    assert cache.get_json("weather:test") == {"status": "ok"}
    assert fake_redis.expirations["weather:test"] == 30

    token = cache.acquire_lock("weather:test:lock", ttl_seconds=5)
    assert token
    assert cache.acquire_lock("weather:test:lock", ttl_seconds=5) is None
    cache.release_lock("weather:test:lock", token)
    assert "weather:test:lock" not in fake_redis.values
