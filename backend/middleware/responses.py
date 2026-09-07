from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.core.logging import safe_request_id


def middleware_error_response(request: Request, status_code: int, message: str, *, code: str = "http_error") -> JSONResponse:
    """Return a sanitized error response from request-bound middleware."""
    request_id = getattr(request.state, "request_id", None) or safe_request_id(request.headers.get("X-Request-ID"))
    return JSONResponse(
        status_code=status_code,
        content={
            "error": code,
            "message": message,
            "error_id": request_id,
            "path": request.url.path,
        },
        headers={"X-Request-ID": request_id},
    )
