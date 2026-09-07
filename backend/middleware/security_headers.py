from collections.abc import Callable

from fastapi import Request, Response

from backend.core.config import get_settings


async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
    response = await call_next(request)
    settings = get_settings()
    connect_sources = ["'self'", "https:"]
    if settings.environment == "development":
        connect_sources.extend(settings.cors_origins)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        f"connect-src {' '.join(connect_sources)}; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "0"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
