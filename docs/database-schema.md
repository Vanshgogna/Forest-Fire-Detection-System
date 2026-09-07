# Database Schema

The backend uses PostgreSQL with PostGIS enabled through Alembic migrations.

All application tables include:

- Primary key `id`
- `created_at` for audit creation time
- `updated_at` for last mutation time
- Timestamp indexes for operational filtering and diagnostics

Core tables:

- `users`: authenticated users, roles, password hashes, and account status.
- `regions`: monitored regions with centroid and boundary metadata.
- `forest_boundaries`: protected or monitored forest polygons as GeoJSON plus area metadata.
- `weather_records`: timestamped weather observations and Fire Weather Index values.
- `vegetation_records`: NDVI, NBR, vegetation health, cloud percentage, and satellite source.
- `satellite_images`: Sentinel/MODIS/VIIRS-ready scene metadata, tiles, cloud percentage, and file references.
- `fire_hotspots`: hotspot detections with source, confidence, severity, and coordinates.
- `ai_predictions`: risk score, category, confidence, feature importance, explanation, and model version.
- `alerts`: generated alert lifecycle from new to acknowledged to resolved.
- `reports`: generated report metadata and export locations.
- `analytics_snapshots`: periodic aggregate metrics for dashboards and trend views.
- `activity_logs` and `notification_logs`: audit and delivery history.
- `model_metadata`: model registry metadata, metrics, feature schema, and artifact path.
- `system_settings`: configurable thresholds and platform settings.
- `refresh_tokens`: refresh-token registry for revocation workflows.

Important indexes are defined around region/time access patterns, including weather observations, vegetation captures, hotspot detections, prediction generation, and alert status.

Migration entry point:

```bash
alembic upgrade head
```
