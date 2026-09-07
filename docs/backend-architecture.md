# Backend Architecture

The backend is organized as a modular FastAPI environmental intelligence API. It keeps demo data available for local exploration, while production-facing interfaces are separated into route, schema, service, repository, task, and database layers.

## Layers

- `routes/` exposes REST APIs for authentication, users, dashboard, predictions, weather, vegetation, hotspots, GIS, alerts, notifications, analytics, reports, settings, and admin.
- `schemas/` contains request and response contracts, pagination helpers, GeoJSON contracts, and domain validation.
- `services/` contains domain logic for fire risk prediction, weather index calculation, reusable remote-sensing processing, GIS feature generation, alert evaluation, recommendations, Redis-backed caching, notification queue contracts, and report export orchestration.
- `repositories/` provides SQLAlchemy access patterns for regions, weather, vegetation, predictions, hotspots, and alerts.
- `database/` contains normalized SQLAlchemy models for PostgreSQL/PostGIS and Alembic migrations.
- `ml/` contains feature engineering, Random Forest/XGBoost training contracts, model metrics, model serialization, and versioning metadata.
- `tasks/` contains Celery jobs for scheduled predictions, satellite scene processing, weather updates, report generation, and model retraining.
- `core/` contains environment configuration, JWT access/refresh tokens, password hashing, role checks, request logging, rate-limit configuration, and security dependencies.

## API Surface

- `/api/dashboard/*`: operational overview and top-risk regions.
- `/api/weather/*`: forecast, fire weather index, alert flags, and historical trend analysis.
- `/api/vegetation/*`: vegetation summaries, NDVI/NBR/VHI calculations, Sentinel preprocessing plans, scene processing manifests, tile manifests, and cleanup plans.
- `/api/gis/*`: region layers, risk GeoJSON, heatmap data, cache manifests, search, and spatial statistics.
- `/api/prediction/*`: single prediction, batch prediction, explainability, scheduled job contracts, and model training contracts.
- `/api/alerts/*`: active alerts, threshold evaluation, acknowledgement, and resolution lifecycle.
- `/api/notifications/*`: dashboard/email/SMS/webhook notification queue contracts.
- `/api/admin/*`: protected system health and audit summaries.

Versioned aliases are available under `/api/v1/*` for client stability.

## Deployment Services

- `api`: FastAPI application.
- `postgres`: PostgreSQL with PostGIS.
- `redis`: cache, broker, and task result backend.
- `worker`: Celery worker.
- `scheduler`: Celery beat scheduler.
- `nginx`: reverse proxy for API and OpenAPI documentation.

The schema supports future integrations for Sentinel-2, MODIS, VIIRS, drone feeds, mobile clients, SMS/email providers, Cloudinary assets, and deep learning model registries without changing the public API shape.

See [Scalability And Future Architecture](scalability-architecture.md) for the long-term modularity, microservice-readiness, storage, async processing, and multi-tenant architecture plan.
