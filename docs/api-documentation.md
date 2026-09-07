# API Documentation

The API is exposed by FastAPI and documented automatically at `/docs` and `/openapi.json`. Stable aliases are available under `/api/v1/*`.

## Authentication

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | Public | Exchange email and password for access and refresh tokens |
| POST | `/api/auth/refresh` | Public | Exchange refresh token for a new access token |

Roles: `admin`, `forest_officer`, `researcher`, `viewer`.

## Core Operations

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/health` | Public | Liveness check |
| GET | `/api/readiness` | Public | Readiness and redacted configuration summary |
| GET | `/api/dashboard/overview` | Public | Dashboard risk, weather, hotspot, alert summary |
| GET | `/api/dashboard/top-risk-regions` | Public | Ranked high-risk regions |

## Monitoring

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/monitoring/health` | Public | Component health for backend, database, weather API, satellite pipeline, prediction engine, and GIS engine |
| GET | `/api/monitoring/health/{component}` | Public | Individual component health check |
| GET | `/api/monitoring/metrics` | Admin | API, prediction, raster, database, memory, CPU, cache, request, and error metrics |
| GET | `/api/monitoring/model` | Admin | Model accuracy status, inference time, drift status, and confidence distribution |
| GET | `/api/monitoring/alerts` | Admin | Observability alert summary |
| GET | `/api/monitoring/dashboard` | Admin | Platform health, API performance, model performance, dataset status, storage usage, and recent errors |

## Data Engineering

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/data/sources` | Researcher/Admin | Supported source contracts and ETL stages |
| POST | `/api/data/pipeline/run` | Admin | Run extract, transform, validate, normalize, enrich, store, quality, archive, version, cache, and checkpoint stages |
| POST | `/api/data/pipeline/resume` | Admin | Inspect the latest checkpoint for a dataset/version |

## Weather

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/weather/` | Public | Current weather records |
| GET | `/api/weather/forecast` | Public | Forecast snapshot |
| POST | `/api/weather/fire-weather-index` | Public | Calculate Fire Weather Index and alert flags |
| POST | `/api/weather/history/analyze` | Public | Summarize historical weather trend |

## Vegetation And Satellite

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/vegetation/summary` | Public | Vegetation health summary |
| POST | `/api/vegetation/indices` | Public | Calculate NDVI, NBR, and vegetation health |
| POST | `/api/vegetation/satellite/preprocess` | Public | Build satellite preprocessing manifest |
| GET | `/api/vegetation/satellite/tiles/{scene_id}` | Public | Return tile cache manifest |
| POST | `/api/vegetation/satellite/scene-plan` | Public | Validate and plan scene processing |
| GET | `/api/vegetation/satellite/cleanup/{scene_id}` | Public | Return safe temporary cleanup plan |

## GIS

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/gis/regions` | Public | Region layer data |
| GET | `/api/gis/layers` | Public | Available GIS layers |
| GET | `/api/gis/risk-geojson` | Public | Risk GeoJSON feature collection |
| GET | `/api/gis/heatmap` | Public | Hotspot heatmap points |
| GET | `/api/gis/search` | Public | Region search and spatial filtering |
| GET | `/api/gis/spatial-statistics` | Public | Spatial risk statistics |
| GET | `/api/gis/cache-manifest/{layer}` | Public | GIS layer cache metadata |

## Predictions

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/prediction/` | Public | Recent prediction records |
| POST | `/api/prediction/` | Public | Generate one explainable risk prediction with drivers, confidence rationale, visual explanation payloads, and recommendation rationales |
| POST | `/api/prediction/batch` | Public | Generate batch predictions with explanation details for every result |
| POST | `/api/prediction/jobs` | Researcher/Admin | Schedule prediction job |
| POST | `/api/prediction/train` | Researcher/Admin | Create model training plan |
| GET | `/api/prediction/explainability` | Public | Feature importance and recommendations |

## Alerts, Reports, Analytics

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/alerts/` | Public | Active alerts |
| POST | `/api/alerts/evaluate` | Public | Evaluate alert thresholds |
| PATCH | `/api/alerts/{alert_id}` | Forest Officer/Admin | Acknowledge or resolve alert |
| GET | `/api/reports/` | Public | List reports |
| POST | `/api/reports/prediction` | Public | Create prediction report |
| POST | `/api/reports/{report_type}/export` | Public | Export report plan |
| GET | `/api/analytics/summary` | Public | Analytics dashboard summary |

## Admin And Settings

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/users/` | Admin | List users |
| GET | `/api/users/me` | Any authenticated role | Current principal |
| GET | `/api/settings/` | Public | Public settings |
| PUT | `/api/settings/` | Admin | Update settings |
| GET | `/api/admin/system-health` | Admin | System health |
| GET | `/api/admin/audit-summary` | Admin | Audit summary |
| POST | `/api/notifications/` | Forest Officer/Admin | Queue notification |
| POST | `/api/notifications/alert-plan` | Public | Notification plan for alert |

## Error Shape

```json
{
  "error": "validation_error",
  "message": "The request contains invalid or incomplete data.",
  "error_id": "request-id",
  "path": "/api/example"
}
```
