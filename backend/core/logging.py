from __future__ import annotations

import logging
import json
import time
from collections.abc import Callable
from uuid import uuid4

from fastapi import Request, Response

from backend.services.observability import observability_registry

logger = logging.getLogger("firesight")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

MAX_REQUEST_ID_LENGTH = 80
SLOW_REQUEST_THRESHOLD_MS = 500.0


class JsonLogFormatter(logging.Formatter):
    """Emit structured JSON logs for log aggregation and tracing."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Configure process-wide application logging."""
    from backend.core.config import get_settings

    level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)


def safe_request_id(raw_value: str | None) -> str:
    """Return a bounded request identifier safe for logs and response headers."""
    if raw_value:
        value = "".join(char for char in raw_value if char.isalnum() or char in "-_")[:MAX_REQUEST_ID_LENGTH]
        if value:
            return value
    return str(uuid4())


def log_startup_event(message: str, **fields: object) -> None:
    """Log application lifecycle events without secrets or request payloads."""
    safe_fields = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("%s %s", message, safe_fields)


async def request_logging_middleware(request: Request, call_next: Callable) -> Response:
    request_id = safe_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    request.state.trace = observability_registry.trace_context(request_id, f"{request.method} {request.url.path}")
    started = time.perf_counter()
    logger.info("api_request_started request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.error(
            "api_request_failed request_id=%s method=%s path=%s elapsed_ms=%.2f error_type=%s",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
            exc.__class__.__name__,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    observability_registry.record_api_request(request.method, request.url.path, response.status_code, elapsed_ms)
    log_method = logger.warning if elapsed_ms >= SLOW_REQUEST_THRESHOLD_MS or response.status_code >= 500 else logger.info
    log_method(
        "api_response_completed request_id=%s method=%s path=%s status_code=%s elapsed_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response
