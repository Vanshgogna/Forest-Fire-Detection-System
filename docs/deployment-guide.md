# Deployment Guide

This project is configured for local Docker, Render backend hosting, and Vercel frontend hosting. Runtime configuration must come from environment variables, not hardcoded values.

## Required Configuration

Copy `.env.example` to `.env` for local development. In production, set these in the host secret manager:

- `ENVIRONMENT=production`
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`
- `DEMO_LOGIN_ENABLED`
- `DEMO_LOGIN_EMAIL` and `DEMO_LOGIN_PASSWORD` if the public demo login remains enabled
- `VITE_API_URL`

Optional integrations:

- `WEATHER_API_KEY`
- `SENTINEL_CATALOG_URL`
- `MODIS_HOTSPOT_URL`
- `VIIRS_HOTSPOT_URL`
- `CLOUDINARY_URL`

Storage paths:

- `DATASET_DIR`
- `MODEL_ARTIFACT_DIR`
- `UPLOAD_DIR`
- `RASTER_ARTIFACT_DIR`
- `CACHE_ARTIFACT_DIR`
- `REPORT_ARTIFACT_DIR`

Production validation rejects the development JWT secret, localhost database URLs, and localhost CORS origins.
It also rejects wildcard production CORS, non-live `DATA_MODE`, and the default demo login password.

## Local Docker

```bash
cp .env.example .env
docker compose up --build
```

Services:

- FastAPI API: `http://localhost:8000`
- Nginx reverse proxy: `http://localhost:8080`
- PostgreSQL/PostGIS: `localhost:5432`
- Redis: `localhost:6379`
- Celery worker and scheduler

Health checks:

```bash
BASE_URL=http://localhost:8000 scripts/healthcheck.sh
```

## Render Backend

The repository includes `render.yaml`.

1. Create managed PostgreSQL with PostGIS enabled.
2. Create managed Redis.
3. Create a Render Blueprint from `render.yaml`.
4. Set `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, and `CORS_ORIGINS` in Render.
5. Deploy the API, worker, and scheduled job services.
6. Confirm `/api/health` and `/api/readiness`.

`/api/health` confirms the API process is running. `/api/readiness` checks configured components and pings the database with `SELECT 1`.

Backend start command:

```bash
scripts/deploy-backend-render.sh
```

## Vercel Frontend

The repository includes `vercel.json`.

1. Import the repository into Vercel.
2. Set `VITE_API_URL=https://your-backend.example/api`.
3. Use the default build from `vercel.json`.
4. Deploy and verify dashboard navigation.

Frontend build verification:

```bash
scripts/deploy-frontend-vercel.sh
```

## Manual Docker Image

```bash
docker build -f Dockerfile.backend -t firesight-api .
docker run --env-file .env -p 8000:8000 firesight-api
```

## CI/CD

`.github/workflows/ci.yml` runs on pull requests and pushes to `main` or `master`.

The workflow verifies:

- Frontend dependency installation, smoke tests, type checking, and production build
- Backend dependency installation, API/ML/GIS/config tests, and module compilation
- PostgreSQL/PostGIS and Redis service readiness

## Release Checklist

1. Update `.env.example` when new settings are introduced.
2. Run `npm test`, `npm run typecheck`, `npm run build`, and `.test-venv/bin/python -m pytest`.
3. Build the backend image with `docker build -f Dockerfile.backend .`.
4. Apply database migrations with `alembic upgrade head`.
5. Confirm `/api/health` and `/api/readiness`.
6. Confirm `/api/monitoring/health` and the admin-only `/api/monitoring/dashboard`.
7. Confirm `/api/readiness` does not expose secrets.
8. Rotate demo credentials before public exposure.

## Backup And Recovery

PostgreSQL:

- Schedule daily logical backups with `pg_dump`.
- Keep at least seven daily backups and four weekly backups.
- Test restore procedures monthly in a non-production environment.

Redis:

- Enable append-only persistence for local Docker and managed Redis persistence in production.
- Treat Redis as recoverable cache state unless queues contain operationally critical jobs.

Configuration:

- Store production environment variables in the hosting provider secret manager.
- Keep `.env.example` current, but never commit `.env` or real secrets.

Recovery:

1. Restore the latest verified PostgreSQL backup.
2. Reapply migrations with `alembic upgrade head`.
3. Redeploy the backend and worker services using the same release image.
4. Verify `/api/readiness`, dashboard data, alert creation, prediction explainability, and report export.
