# Performance Optimization

## Frontend

- Route-level lazy loading keeps page bundles split.
- React Query caches environmental data for one minute and avoids focus/remount refetches for stable dashboard snapshots.
- Dashboard tables and maps memoize row, marker, polygon, and aggregate calculations.
- Heavy map/chart libraries remain isolated in separate Vite chunks.
- Frontend smoke tests protect lazy page imports and provider rendering.

## Backend

- SQLAlchemy uses connection pooling, pre-ping, overflow control, and pool recycling from environment variables.
- Repository pagination clamps negative offsets and excessive limits.
- Hotspot date-range queries now apply a default bounded result limit.
- Weather Fire Weather Index calculations are cached for repeated normalized inputs.
- Redis-backed API caches remain available for dashboard, GIS, analytics, prediction, and weather data.

## GIS And Raster Processing

- Remote-sensing manifests use windowed chunk processing for large rasters.
- Raster operations avoid loading unrelated bands and expose cache keys for reusable tile and processing outputs.
- Heatmap weights are clamped before rendering.
- Temporary raster workspaces use sanitized scene identifiers.

## ML Inference

- Training and inference share the same preprocessing pipeline.
- Batch prediction reuses the service instance and model/preprocessor state.
- Model artifacts include serialized preprocessing metadata for fast loading and consistent inference.

## Monitoring

- Request logging records latency and warning-level slow responses.
- Readiness exposes redacted performance settings such as page-size limits and database pool size.
- Tests cover query clamping, cached weather calculations, API behavior, ML contracts, and GIS contracts.
