from collections import defaultdict
from time import time

from fastapi import Request, status

from backend.core.config import get_settings
from backend.middleware.responses import middleware_error_response

_BUCKET: dict[str, list[float]] = defaultdict(list)


async def rate_limit_middleware(request: Request, call_next):
    settings = get_settings()
    client = request.client.host if request.client else "unknown"
    now = time()
    _BUCKET[client] = [stamp for stamp in _BUCKET[client] if now - stamp < 60]
    if len(_BUCKET[client]) > settings.rate_limit_per_minute:
        return middleware_error_response(request, status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")
    _BUCKET[client].append(now)
    return await call_next(request)
