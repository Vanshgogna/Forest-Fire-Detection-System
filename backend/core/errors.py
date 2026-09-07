from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

logger = logging.getLogger("firesight.errors")


class AppError(Exception):
    """Base application error that can be safely returned to API clients."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "service_error"
    message = "The service could not complete the request."

    def __init__(self, message: str | None = None, *, code: str | None = None, status_code: int | None = None):
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        super().__init__(self.message)


class ExternalServiceError(AppError):
    """Failure raised when a dependent network API is unavailable or invalid."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "external_service_unavailable"
    message = "A dependent service is temporarily unavailable."


class DatabaseError(AppError):
    """Failure raised when persistence cannot complete safely."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "database_unavailable"
    message = "The data store is temporarily unavailable."


class DatasetError(AppError):
    """Failure raised when required datasets are missing, invalid, or corrupted."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "dataset_error"
    message = "The dataset could not be processed."


class ModelError(AppError):
    """Failure raised when model training, loading, or inference cannot complete."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "model_unavailable"
    message = "The prediction engine is temporarily unavailable."


class SatelliteProcessingError(AppError):
    """Failure raised when satellite acquisition or raster processing fails."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "satellite_processing_error"
    message = "The satellite scene could not be processed."


def _request_path(request: Request) -> str:
    return request.url.path


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value or str(uuid4())


def _error_response(request: Request, status_code: int, code: str, message: str, *, details: list[dict] | None = None) -> JSONResponse:
    error_id = _request_id(request)
    content = {
        "error": code,
        "message": message,
        "error_id": error_id,
        "path": _request_path(request),
    }
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content, headers={"X-Request-ID": error_id})


def _safe_validation_errors(exc: RequestValidationError) -> list[dict]:
    sanitized = []
    for error in exc.errors():
        sanitized.append(
            {
                "location": [str(item) for item in error.get("loc", [])],
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "value_error")),
            }
        )
    return sanitized


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("validation_error request_id=%s method=%s path=%s", _request_id(request), request.method, _request_path(request))
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "The request contains invalid or incomplete data.",
        details=_safe_validation_errors(exc),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    logger.warning(
        "http_error request_id=%s method=%s path=%s status_code=%s",
        _request_id(request),
        request.method,
        _request_path(request),
        exc.status_code,
    )
    return _error_response(request, exc.status_code, "http_error", detail)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "application_error request_id=%s method=%s path=%s status_code=%s code=%s",
        _request_id(request),
        request.method,
        _request_path(request),
        exc.status_code,
        exc.code,
    )
    return _error_response(request, exc.status_code, exc.code, exc.message)

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = _request_id(request)
    logger.error(
        "unexpected_error request_id=%s method=%s path=%s error_type=%s",
        error_id,
        request.method,
        _request_path(request),
        exc.__class__.__name__,
    )
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_server_error",
        "The service could not complete the request.",
    )
