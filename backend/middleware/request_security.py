from __future__ import annotations

from time import time

from fastapi import Request, status

from backend.core.config import get_settings
from backend.middleware.responses import middleware_error_response

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_REPLAY_CACHE: dict[str, float] = {}


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else "unknown"


def _prune_replay_cache(now: float, window_seconds: int) -> None:
    expired = [key for key, timestamp in _REPLAY_CACHE.items() if now - timestamp > window_seconds]
    for key in expired:
        _REPLAY_CACHE.pop(key, None)


async def request_size_limit_middleware(request: Request, call_next):
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if not content_length:
        return await call_next(request)
    try:
        declared_size = int(content_length)
    except ValueError:
        return middleware_error_response(request, status.HTTP_400_BAD_REQUEST, "Invalid Content-Length header")
    if declared_size > settings.max_request_body_bytes:
        return middleware_error_response(request, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Request body is too large")
    return await call_next(request)


async def replay_protection_middleware(request: Request, call_next):
    if request.method not in MUTATING_METHODS:
        return await call_next(request)

    replay_key = request.headers.get("X-Idempotency-Key")
    if not replay_key:
        return await call_next(request)

    settings = get_settings()
    now = time()
    _prune_replay_cache(now, settings.replay_window_seconds)
    cache_key = f"{_client_key(request)}:{request.method}:{request.url.path}:{replay_key[:128]}"
    if cache_key in _REPLAY_CACHE:
        return middleware_error_response(request, status.HTTP_409_CONFLICT, "Duplicate request rejected")
    _REPLAY_CACHE[cache_key] = now
    return await call_next(request)
