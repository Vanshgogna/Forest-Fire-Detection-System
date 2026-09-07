# FireSight Deployment

FireSight deploys with the existing architecture:

- Backend API: Render Docker web service
- Frontend: Vercel Vite app
- Database: managed PostgreSQL
- Redis/Celery: optional for scheduled FIRMS/Sentinel ingestion jobs; not required for the API process to answer health, weather, prediction-unavailable, and alert-unavailable responses

## Required Environment

Set these in the production host secret manager:

- `ENVIRONMENT=production`
- `DATA_MODE=live`
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`
- `VITE_API_URL`
- `DEMO_LOGIN_ENABLED`
- `DEMO_LOGIN_EMAIL` and `DEMO_LOGIN_PASSWORD` if the public demo login remains enabled

Production validation rejects the development JWT secret, localhost database URLs, wildcard CORS, loopback CORS, non-live `DATA_MODE`, and the default demo login password.

## Provider Configuration

Open-Meteo works through `WEATHER_API_BASE_URL`; `WEATHER_API_KEY` is optional unless the selected provider requires it.

NASA FIRMS:

- `FIRMS_ENABLED`
- `FIRMS_MAP_KEY`
- `FIRMS_PRODUCT`
- `FIRMS_LOOKBACK_HOURS`
- `FIRMS_REFRESH_INTERVAL_MINUTES`

If FIRMS is disabled or credentials are missing, hotspot endpoints report unavailable and the UI must not show fixture hotspot values as live.

Sentinel/Copernicus:

- `SENTINEL_ENABLED`
- `COPERNICUS_CLIENT_ID`
- `COPERNICUS_CLIENT_SECRET`
- `SENTINEL_PROCESSING_DIR`
- `SENTINEL_TEMP_DIR`

Render container filesystems are ephemeral. For this MVP, Sentinel/NDVI can safely report `UNAVAILABLE` when credentials, ingestion, or durable storage are not configured. Do not fabricate NDVI.

## Database Migrations

Run migrations against the production `DATABASE_URL` before relying on the schema:

```bash
python -m alembic upgrade head
```

The backend Docker image copies `alembic.ini`, and Alembic reads `DATABASE_URL` from runtime settings.
Common platform URLs such as `postgres://...` and `postgresql://...` are normalized to the psycopg SQLAlchemy dialect used by the app.

No PostGIS extension is required. Hotspot locations are stored with standard latitude and longitude columns, so managed PostgreSQL providers such as Supabase and Neon can run the schema without extension privileges.

## Render Backend

Use `render.yaml`.

The web service starts with:

```bash
sh /app/scripts/deploy-backend-render.sh
```

That script runs `alembic upgrade head`, then starts FastAPI. Set `CORS_ORIGINS` to the deployed Vercel origin only, for example:

```text
https://your-firesight-frontend.vercel.app
```

Health check:

```text
GET /api/health
```

Readiness check:

```text
GET /api/readiness
```

`/api/health` is a liveness check. `/api/readiness` performs component checks, including a safe database `SELECT 1`, and reports `degraded` when the database is not reachable.

## Vercel Frontend

Set:

```text
VITE_API_URL=https://your-render-backend.example/api
```

`vercel.json` builds `frontend/dist`. The frontend development fallback uses localhost only in development; production uses `VITE_API_URL` or same-origin `/api`.

## Post-Deployment Verification

Check:

- `GET /api/health` returns healthy process status
- `GET /api/environmental-snapshot/r1` returns provider statuses
- `GET /api/prediction/r1` returns a prediction only when required live data exists
- `GET /api/alerts/evaluate/r1` returns no live alert when prediction is unavailable
- Vercel frontend loads and calls the Render `/api` base URL

Expected MVP behavior without FIRMS/Sentinel credentials:

- Health remains healthy
- FIRMS and Sentinel-dependent data report unavailable
- Prediction reports unavailable when required live inputs are missing
- Alerts do not fabricate live warnings
