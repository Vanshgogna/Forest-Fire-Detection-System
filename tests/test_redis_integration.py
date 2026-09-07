from __future__ import annotations

import asyncio

from backend.core.config import DEFAULT_REDIS_URL, Settings
from backend.database import redis as redis_module


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
