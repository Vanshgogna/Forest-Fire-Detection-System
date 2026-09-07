# Error Handling and Logging

## API Error Policy

All API errors use a consistent JSON shape:

```json
{
  "error": "validation_error",
  "message": "The request contains invalid or incomplete data.",
  "error_id": "request-id",
  "path": "/api/example"
}
```

The platform returns safe client-facing messages for validation errors, authentication failures, domain failures, dependent-service failures, and unexpected exceptions. Internal exception text, stack traces, connection strings, file paths, tokens, passwords, and raw request bodies are not returned to clients.

## Failure Categories

- `validation_error` for invalid user input
- `http_error` for expected API failures such as authentication and authorization
- `database_unavailable` for database failures
- `external_service_unavailable` for weather, satellite, notification, or other network dependency failures
- `dataset_error` for missing, invalid, or corrupted datasets
- `model_unavailable` for ML loading, training, or prediction failures
- `satellite_processing_error` for satellite acquisition or raster-processing failures
- `internal_server_error` for unexpected exceptions

## Logging Coverage

The backend logs:

- Application startup and shutdown
- API request start
- API response completion
- Request duration and slow or failed requests
- Validation failures
- Authentication and authorization failures
- Cache hits, misses, and Redis degradation
- Dataset and remote-sensing validation
- GIS clipping, GeoJSON generation, and tile cache manifest generation
- Model prediction, batch prediction, training, save, and load events

## Sensitive Data Rules

Logs intentionally avoid:

- Passwords
- JWTs and refresh tokens
- Raw request bodies
- Authorization headers
- Database URLs
- External API keys
- Full exception text from dependency failures

Each response includes `X-Request-ID`, and callers may supply their own safe request ID with the same header.
