# FireSight AI Phase 1 Deployment Readiness Audit

Audit date: 2026-09-05

Scope: complete source inspection plus local verification where possible. No production code was intentionally changed during this phase.

## 1. Project Architecture

The repository is a full-stack FireSight AI / Forest Fire Detecting System application.

High-level structure:

- `/frontend`: React frontend, Vite build, TypeScript source, Leaflet maps, Recharts charts, React Query data fetching.
- `/backend`: FastAPI backend with routers, services, SQLAlchemy models, Alembic migrations, Celery tasks, ML service, Sentinel/FIRMS/weather provider services.
- `/backend/alembic`: database migrations.
- `/backend/artifacts`: generated local raster/cache/report/model/upload artifact directories.
- `/datasets`: configured dataset root, currently empty.
- `/tests`: backend pytest suite.
- `/docs`: existing project, deployment, data, architecture, and operations docs.
- `Dockerfile.backend`, `docker-compose.yml`, `render.yaml`, `vercel.json`, `.github/workflows/*`: deployment/CI scaffolding.

Frontend location: `/frontend`.

Backend location: `/backend`.

Frontend framework:

- React: yes, `/frontend/package.json`.
- Vite: yes, `/frontend/package.json`, `/frontend/vite.config.ts`.
- TypeScript: yes, `/frontend/src/main.tsx`, `/frontend/src/App.tsx`, `/frontend/tsconfig.json`.
- JavaScript: only tooling/tests; application source is TypeScript/TSX.

Backend framework:

- FastAPI: yes, `/backend/main.py`.
- Flask/Django: no evidence found.

Entry points:

- Frontend entry point: `/frontend/src/main.tsx`.
- Frontend application router: `/frontend/src/App.tsx`.
- Backend entry point: `/backend/main.py`, app object is `backend.main:app`.

Exact backend production start paths found:

- Docker/Render command in `/render.yaml`: `sh /app/scripts/deploy-backend-render.sh`.
- Script body in `/scripts/deploy-backend-render.sh`: `python -m alembic upgrade head` then `uvicorn backend.main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${PORT:-8000}"`.
- Root package dev command in `/package.json`: `uvicorn backend.main:app --reload --host ${BACKEND_HOST:-0.0.0.0} --port ${PORT:-8000}`.

## 2. Deployment Risks

Major risks:

- Production database must be PostgreSQL with PostGIS support because `/backend/alembic/versions/20260726_0001_enterprise_backend_schema.py` runs `CREATE EXTENSION IF NOT EXISTS postgis`.
- `/backend/core/config.py` rejects production startup if `DATABASE_URL` is localhost, `JWT_SECRET_KEY` is the development value/too short, `CORS_ORIGINS` includes localhost/wildcard, or `DATA_MODE` is not `live`.
- `/backend/routes/auth.py` uses a hardcoded demo login identity and password hash source. This is not production user management.
- Live predictions require weather, vegetation, and hotspot data. In `DATA_MODE=live`, missing Sentinel/FIRMS/database-backed data returns `status: unavailable` rather than producing fake live predictions.
- Sentinel download/processing writes raster files to local storage. Render/Railway ephemeral disks will lose those files unless using a persistent disk or object storage.
- `backend/artifacts` contains generated Sentinel raster outputs even though `.gitignore` excludes this path. They should not be relied on for cloud state.
- Python version is not explicitly pinned in a `runtime.txt` or `pyproject.toml`. Docker uses Python 3.12; local verified tests used Python 3.11.16. Python 3.13+ has risk because `passlib` emits a `crypt` deprecation warning under 3.11 and `crypt` is removed in 3.13.
- `vercel.json` allows `connect-src 'self' https:` so HTTPS APIs are allowed, but production frontend still needs `VITE_API_URL` set to the deployed backend `/api` base.

## 3. Real Data vs Dummy Data Table

| Surface | Data Source Status | Exact files | Notes |
| --- | --- | --- | --- |
| Landing page | Mixed | `/frontend/src/pages/LandingPage.tsx`, `/frontend/src/hooks/useEnvironmentalData.ts`, `/frontend/src/constants/mockData.ts` | Uses first region from shared hook. Live data overlays are shown only if backend returns live prediction; otherwise preview labels unavailable/platform preview. |
| Dashboard | Mixed | `/frontend/src/pages/DashboardPage.tsx`, `/frontend/src/hooks/useEnvironmentalData.ts` | Selected region is honored. Metrics are live where API data exists; falls back to fixture regions/trends/alerts. |
| GIS map | Mixed / hardcoded geometry | `/frontend/src/pages/MapPage.tsx`, `/frontend/src/components/maps/GeographicRiskIntelligence.tsx`, `/frontend/src/components/dashboard/RiskMap.tsx` | Uses shared region array but creates synthetic polygons client-side. Base maps are external tile providers. `MapPage` passes `data.weatherData`, not selected region weather. |
| Predictions | Mixed | `/frontend/src/pages/PredictionPage.tsx`, `/frontend/src/components/prediction/ExplainabilityDashboard.tsx`, `/backend/routes/prediction.py`, `/backend/services/live_prediction_service.py` | Region-specific live endpoint is called; if sources missing, UI shows unavailable. Many explainability comparison/historical values are fixtures when no live prediction exists. |
| Alerts | Mixed | `/frontend/src/pages/AlertsPage.tsx`, `/backend/routes/alerts.py`, `/backend/services/alert_engine.py`, `/backend/services/mock_environment.py` | Alerts page calls region-specific live evaluation. Shared hook falls back to demo alerts. `/api/alerts/` is simulation-only. |
| Reports | Generated/queued placeholder | `/backend/routes/reports.py`, `/backend/services/report_service.py`, `/frontend/src/components/prediction/ExplainabilityDashboard.tsx` | Backend returns manifest/queued report payloads; frontend can generate an HTML explainability report client-side only when live prediction exists. No persisted report files are created by current service. |
| Environmental snapshot | Live-capable, unavailable without providers | `/backend/routes/environmental_snapshot.py`, `/backend/services/environmental_data_service.py` | Composes Open-Meteo live weather, latest persisted Sentinel NDVI, and persisted FIRMS aggregation. |
| Weather | Real live + cache | `/backend/services/weather_provider.py`, `/backend/routes/weather.py`, `/frontend/src/pages/WeatherPage.tsx` | Open-Meteo live API by configured region coordinates; in-memory/Redis cache via `/backend/services/cache.py`. |
| Sentinel NDVI/NBR | Persisted/generated when configured | `/backend/services/sentinel_provider.py`, `/backend/services/sentinel_acquisition_service.py`, `/backend/services/sentinel_ndvi_service.py`, `/backend/services/sentinel_raster_service.py`, `/backend/services/sentinel_quality_mask_service.py` | NDVI and NBR rasters can be produced. UI status endpoint uses acquired/processed DB metadata. |
| Hotspots | Live-capable persisted DB data | `/backend/services/firms_provider.py`, `/backend/services/hotspot_ingestion_service.py`, `/backend/services/hotspot_aggregation_service.py`, `/backend/routes/hotspots.py` | Requires `FIRMS_ENABLED=true` and `FIRMS_MAP_KEY`; otherwise unavailable or explicit simulation mode. |
| Analytics | Mostly fixture-derived | `/frontend/src/pages/AnalyticsPage.tsx`, `/frontend/src/components/analytics/RiskDistributionDashboard.tsx`, `/backend/routes/analytics.py` | Frontend uses shared mixed snapshot; backend analytics summary uses `mock_environment.REGIONS`. |
| Settings | Hardcoded UI | `/frontend/src/pages/SettingsPage.tsx`, `/backend/routes/settings.py` | Frontend settings controls are static defaults; backend settings exposes config-style values. |

## 4. Database Status

Database currently configured:

- Default backend database: PostgreSQL via `postgresql+psycopg://...`, `/backend/core/config.py`.
- Docker Compose database: `postgis/postgis:16-3.4`, `/docker-compose.yml`.
- SQLite support: only partial/testing compatibility through the custom `Geometry` type compiler in `/backend/database/models.py`; no SQLite production config was found.

Configuration files:

- `/backend/core/config.py`: `DATABASE_URL`, pool settings.
- `/backend/database/session.py`: SQLAlchemy engine/session.
- `/alembic.ini`: default local URL, overridden by settings in `/backend/alembic/env.py`.
- `/backend/alembic/versions/*`: migrations.

Schema includes:

- Regions: `/backend/database/models.py`, `Region`.
- Predictions: `AIPrediction`.
- Environmental/weather snapshots: no single snapshot table; weather stored in `WeatherRecord`, vegetation in `VegetationRecord`, hotspots in `FireHotspot`, satellite scenes in `SatelliteImage`.
- Sentinel NDVI/NBR: `VegetationRecord` plus raster references/metadata in `SatelliteImage.metadata_json` and local artifact files.
- FIRMS hotspots: `FireHotspot`.
- Alerts: `Alert`.
- Reports: `Report`.

Region creation:

- Canonical region registry is `/backend/services/region_registry.py`.
- `RegionRepository.get_or_create_from_registry()` in `/backend/repositories/environment.py` creates DB rows as ingestion/acquisition services run.
- There is no standalone production seed command found.

Production database recommendation:

- Use PostgreSQL with PostGIS enabled.
- Run Alembic migrations before serving traffic.
- Add a small seed/init command for registry regions or invoke a safe backend management task that creates `Region` rows from `/backend/services/region_registry.py`.
- Run provider ingestion after DB initialization: FIRMS ingestion, Sentinel acquisition, raster prep, quality mask, NDVI/NBR processing.

Local data disappearance:

- Any local DB data would not appear in a new cloud DB unless migrated. No local database file was found.
- Local raster artifacts under `/backend/artifacts/rasters` will disappear on ephemeral cloud storage unless persisted externally.

## 5. ML Model Status

Current ML implementation:

- ML service: `/backend/ml/pipeline.py`.
- Feature generation: `/backend/ml/features.py`.
- Registry: `/backend/ml/registry.py`.
- Explainability: `/backend/ml/explainability.py`.

Model artifact status:

- Expected artifact format when saved: `.joblib`, generated by `FireRiskModelService.save()`.
- Expected artifact directory: `MODEL_ARTIFACT_DIR`, default `/backend/artifacts/models`.
- Actual model artifact found: none. `/backend/artifacts/models` is empty.
- Current prediction path uses a heuristic baseline unless an artifact path is explicitly provided to `FireRiskModelService`.

Deployment suitability:

- No large trained model currently blocks deployment.
- Current heuristic inference is deployment-friendly and does not require retraining.
- If a trained model is added later, persist the `.joblib` in object storage or ship a small versioned artifact deliberately; do not depend on ephemeral generated files.

Inference dependencies:

- Current heuristic path: application Python code only.
- Trained artifact path: `joblib`, `scikit-learn`, optionally `xgboost`, `numpy`, `pandas`.

## 6. External API Status

| Provider | Service/API | Files | Key required | Cloud-ready | Cache/fallback |
| --- | --- | --- | --- | --- | --- |
| Open-Meteo | Forecast/current weather API | `/backend/services/weather_provider.py`, `/backend/routes/weather.py` | Optional `WEATHER_API_KEY`; base URL is `WEATHER_API_BASE_URL` | Yes, outbound HTTPS required | Redis or in-memory cache via `/backend/services/cache.py`; returns `UNAVAILABLE` on provider failure. |
| NASA FIRMS | Area CSV API | `/backend/services/firms_provider.py`, `/backend/services/hotspot_ingestion_service.py`, `/backend/routes/hotspots.py` | `FIRMS_MAP_KEY` when `FIRMS_ENABLED=true` | Yes, with key and scheduled ingestion | Persisted DB aggregation; disabled/missing key returns `UNAVAILABLE`; simulation mode returns fixtures. |
| Copernicus Data Space | OData catalogue/download, OAuth token | `/backend/services/sentinel_provider.py`, `/backend/services/sentinel_acquisition_service.py` | `COPERNICUS_CLIENT_ID`, `COPERNICUS_CLIENT_SECRET` when Sentinel enabled | Yes, but scene downloads can be large | Metadata persisted in DB; files written locally unless reconfigured; unavailable on missing credentials. |
| Sentinel Hub Process API | Raster NDVI/NBR processing endpoint | `/backend/services/sentinel_ndvi_service.py` | Same Copernicus credentials through token flow | Yes, outbound HTTPS required | Writes GeoTIFFs/manifests locally; caches by DB/artifact metadata. |
| Tile providers | OpenStreetMap, Carto, OpenTopoMap | `/frontend/src/components/maps/GeographicRiskIntelligence.tsx`, `/frontend/src/components/dashboard/RiskMap.tsx` | No key in current code | Yes, but subject to public tile provider usage policies | No app cache. |
| Cloudinary | Optional media/report storage | `/backend/core/config.py`, `/render.yaml`, `.env.example` | `CLOUDINARY_URL` if used | Configured but not actively used in report service | No active integration found beyond config. |

Current app depends on all of these categories:

- Real live data: Open-Meteo weather.
- Real persisted DB data: FIRMS/Sentinel when ingested.
- Seeded/configured data: region registry.
- Fixture/test data: backend tests and `mock_environment`.
- Mock/hardcoded UI data: frontend `mockData`, trend data, settings, some analytics/explainability panels.
- Generated fallback/default data: ML feature defaults, unavailable source objects, generated client downloads.

## 7. Required Environment Variables

Backend required for production:

- `ENVIRONMENT=production`
- `DATA_MODE=live`
- `DATABASE_URL=<managed-postgres-or-postgis-url>`
- `REDIS_URL=<managed-redis-url>`
- `JWT_SECRET_KEY=<long-random-secret>`
- `CORS_ORIGINS=<https://frontend.example>`
- `PORT=<provided-by-platform-or-8000>`

Backend provider variables:

- `WEATHER_API_BASE_URL=<https://api.open-meteo.com/v1>`
- `WEATHER_API_KEY=<optional>`
- `FIRMS_ENABLED=<true-or-false>`
- `FIRMS_MAP_KEY=<required-if-firms-enabled>`
- `FIRMS_BASE_URL=<https://firms.modaps.eosdis.nasa.gov/api>`
- `FIRMS_PRODUCT=<VIIRS_SNPP_NRT>`
- `FIRMS_LOOKBACK_HOURS=<24>`
- `FIRMS_MAX_RECORDS=<500>`
- `FIRMS_REQUEST_TIMEOUT=<10>`
- `FIRMS_REGION_BUFFER_DEGREES=<0.5>`
- `FIRMS_RETRY_ATTEMPTS=<2>`
- `FIRMS_RETRY_BACKOFF_SECONDS=<0.5>`
- `FIRMS_REFRESH_INTERVAL_MINUTES=<180>`
- `SENTINEL_ENABLED=<true-or-false>`
- `COPERNICUS_CLIENT_ID=<required-if-sentinel-enabled>`
- `COPERNICUS_CLIENT_SECRET=<required-if-sentinel-enabled>`
- `COPERNICUS_TOKEN_URL=<copernicus-oauth-token-url>`
- `SENTINEL_BASE_URL=<copernicus-catalog-url>`
- `SENTINEL_CATALOG_URL=<optional-override>`
- `SENTINEL_DOWNLOAD_URL=<copernicus-download-url>`
- `SENTINEL_PRODUCT_TYPE=<S2MSI2A>`
- `SENTINEL_LOOKBACK_DAYS=<14>`
- `SENTINEL_MAX_CLOUD_COVER=<40>`
- `SENTINEL_REQUEST_TIMEOUT=<30>`
- `SENTINEL_MAX_SCENE_SIZE_MB=<512>`
- `SENTINEL_TEMP_DIR=<tmp-or-persistent-path>`
- `SENTINEL_PROCESSING_DIR=<tmp-or-persistent-path>`
- `SENTINEL_REFRESH_INTERVAL_HOURS=<24>`
- `SENTINEL_ANALYSIS_RESOLUTION=<20>`
- `SENTINEL_RASTER_MAX_MEMORY_MB=<256>`
- `SENTINEL_MIN_VALID_PIXEL_PERCENT=<40>`
- `SENTINEL_QUALITY_MASK_VERSION=<6D-2-v1>`
- `SENTINEL_NDVI_PROCESSING_VERSION=<6D-3-v1>`
- `CLOUDINARY_URL=<optional>`

Backend operational variables:

- `APP_NAME`, `API_VERSION`, `LOG_LEVEL`, `BACKEND_HOST`
- `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_RECYCLE_SECONDS`
- `JWT_ALGORITHM`, `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`
- `DATASET_DIR`, `MODEL_ARTIFACT_DIR`, `UPLOAD_DIR`, `RASTER_ARTIFACT_DIR`, `CACHE_ARTIFACT_DIR`, `REPORT_ARTIFACT_DIR`, `DATA_ARCHIVE_DIR`, `DATA_CHECKPOINT_DIR`
- `RATE_LIMIT_PER_MINUTE`, `MAX_REQUEST_BODY_BYTES`, `REPLAY_WINDOW_SECONDS`
- `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`
- `WEATHER_CACHE_SECONDS`, `WEATHER_RECENT_MINUTES`, `WEATHER_STALE_MINUTES`
- `VEGETATION_MAX_AGE_DAYS`, `HOTSPOT_MAX_AGE_HOURS`
- `CRITICAL_RISK_THRESHOLD`, `HIGH_RISK_THRESHOLD`, `PREDICTION_BATCH_SIZE_LIMIT`

Frontend required:

- `VITE_API_URL=<https://deployed-backend.example/api>`

Important naming finding:

- The project uses `VITE_API_URL`, not `VITE_API_BASE_URL`, in `/frontend/src/services/api.ts` and `.env.example`.

## 8. Hardcoded Localhost URLs

Source/config findings:

- `/frontend/src/services/api.ts`: development fallback `http://localhost:8000/api`.
- `/.env.example`: `VITE_API_URL=http://localhost:8000/api`, local database/cache/CORS examples.
- `/backend/core/config.py`: default local `DATABASE_URL`, `REDIS_URL`, and CORS origins.
- `/alembic.ini`: default local PostgreSQL URL.
- `/docker-compose.yml`: local CORS and healthcheck URLs.
- `/Dockerfile.backend`: local container healthcheck URL.
- `/scripts/healthcheck.sh`: default `BASE_URL=http://localhost:8000`.
- `/tests/test_configuration_deployment.py`: expected localhost rejection tests.
- `/.github/workflows/ci.yml`, `/.github/workflows/release.yml`: CI local service URLs.
- Docs contain local development examples in `/docs/deployment.md`, `/docs/deployment-guide.md`, `/docs/installation-guide.md`, `/docs/data-accuracy-audit.md`, and others.

Production impact:

- Frontend production is safe if `VITE_API_URL` is set; otherwise it falls back to same-origin `/api`, which only works if frontend and backend are reverse-proxied together.
- Backend production is safe only if production env vars override localhost defaults.

## 9. Hardcoded Region IDs/Names

Canonical configured region IDs/names:

- `/backend/services/region_registry.py`: `r1` Bandipur Tiger Reserve, `r2` Simlipal Biosphere, `r3` Gir Forest, `r4` Kaziranga Landscape.
- `/frontend/src/constants/regionLocations.ts`: same four configured UI regions.

Fixture region data:

- `/backend/services/mock_environment.py`: hardcoded region metrics and alerts.
- `/frontend/src/constants/mockData.ts`: hardcoded region metrics, trend data, weather data, and alerts.

Default `r1` usage:

- `/frontend/src/contexts/EnvironmentalContext.tsx`: initial selected region is `r1`.
- `/backend/services/region_registry.py`: default region in `get_region_location()` is `r1`.
- `/backend/routes/weather.py`: default query region is `r1`.
- `/backend/routes/vegetation.py`: default region for latest/processing/quality/NDVI endpoints is `r1`.
- `/backend/routes/dashboard.py`: dashboard overview fetches weather for `r1`.
- `/backend/routes/prediction.py`: explainability sample fetches weather for `r1`.

Potential stale region behavior:

- `/frontend/src/pages/DashboardPage.tsx`, `/frontend/src/pages/PredictionPage.tsx`, `/frontend/src/pages/AlertsPage.tsx`, `/frontend/src/pages/WeatherPage.tsx`, `/frontend/src/pages/VegetationPage.tsx`, `/frontend/src/pages/HotspotsPage.tsx`, `/frontend/src/pages/AnalyticsPage.tsx` consume `selectedRegionId`.
- `/frontend/src/pages/MapPage.tsx` does not directly consume selected region and passes `data.weatherData` rather than selected-region weather into the map component.
- `/frontend/src/components/maps/GeographicRiskIntelligence.tsx` consumes `selectedRegionId`, but its `latestWeather` comes from the prop `weatherData`; if the page passes first-region weather, the weather overlay can be stale after region changes.
- Shared query key in `/frontend/src/hooks/useEnvironmentalData.ts` is global, not region-scoped. This is acceptable for all-region loading but can hide stale response/race issues when region-specific fetching grows.
- `/frontend/src/components/common/IntelligenceSyncBar.tsx` invalidates the global environmental query on region selection even though the query fetches all regions; this causes extra reloads.
- Fast switching is partially protected in `/frontend/src/pages/AlertsPage.tsx` because React Query passes an abort `signal` to Axios for `/alerts/evaluate/{selectedRegionId}`.

Recommended architecture:

- Keep one source of truth for selected region in context.
- Add a region registry API and hydrate frontend region options from backend, or generate frontend region constants from backend registry.
- Make all region-specific queries use keys containing `selectedRegionId`.
- Use abort signals for all region-specific live requests.
- Keep all-region operational overviews separate from selected-region detail queries.

## 10. Security Issues

Secrets:

- A root `/.env` file exists. `.gitignore` excludes it, but this workspace has no `.git` directory, so tracked history cannot be verified here. Do not expose or commit it.
- No real secret values were printed in this report.

Source-level security findings:

- `/backend/routes/auth.py`: hardcoded demo email/password behavior. Replace with database-backed users before real production.
- `/backend/core/config.py`: contains a development-only JWT secret default. Production validation rejects it, but relying on default in non-production remains risky.
- `/frontend/src/services/api.ts`: bearer token stored in `localStorage`; acceptable for a demo, higher XSS exposure for production. Prefer HttpOnly secure cookies or hardened token strategy if auth becomes real.
- `/backend/main.py`: CORS `allow_credentials=True`; production must never pair this with wildcard origins. Current production validation rejects wildcard/localhost.
- `/backend/core/errors.py` and tests indicate safe error handling; backend tests passed related assertions.
- `/backend/middleware/rate_limit.py`, `/backend/middleware/request_security.py`, `/backend/middleware/security_headers.py`: request hardening exists.

No committed API keys were found in source files scanned outside `/.env`; test strings are placeholders.

## 11. Exact Recommended Deployment Architecture

Recommended: Vercel frontend + Render backend services + PostgreSQL/PostGIS + Redis.

Why:

- `vercel.json` is already tailored for Vercel frontend deployment.
- `render.yaml` and `/scripts/deploy-backend-render.sh` are already tailored for Render Docker deployment.
- Dockerfile installs GDAL/geospatial system libraries needed by Rasterio/GeoPandas. This is safer than a simple non-Docker Python host.
- Worker and cron services are already represented in `render.yaml` for FIRMS/Sentinel scheduled jobs.
- PostgreSQL/PostGIS is required by migration design and geospatial hotspot geometry.
- Redis is used by Celery and cache configuration.

Option evaluation:

- Option 1, Vercel + Railway + PostgreSQL: viable, but no Railway config exists and PostGIS/GDAL/Celery scheduling would need more platform setup.
- Option 2, Vercel + Render + PostgreSQL/PostGIS: best fit because config already exists.
- Option 3, single platform: viable with Docker Compose on a VPS, but more operations burden and less aligned with current `vercel.json`/`render.yaml`.

## 12. Files That Must Be Changed Before Production

Minimum production-readiness changes:

- `/frontend/src/services/api.ts`: optionally standardize on `VITE_API_BASE_URL` or document `VITE_API_URL`; keep production URL explicit.
- `/.env.example`: split or clarify frontend/backend sections and replace local credential-looking examples with safer placeholders.
- `/backend/routes/auth.py`: replace hardcoded demo auth with database-backed users or explicitly disable auth-protected production features until real auth exists.
- `/backend/core/config.py`: consider removing credential-looking localhost defaults for production builds; keep validation.
- `/alembic.ini`: replace credential-looking default URL with placeholder or rely fully on env override.
- `/render.yaml`: confirm PostGIS provisioning, externalize `PORT` if Render provides it, and decide whether worker/cron are required on first deploy.
- `/scripts/deploy-backend-render.sh`: keep migration/start command; optionally add a registry seed/init step after migration.
- Add a new seed/init module or script, likely under `/backend` or `/scripts`, to create configured regions from `/backend/services/region_registry.py`.
- `/frontend/src/pages/MapPage.tsx` and/or `/frontend/src/components/maps/GeographicRiskIntelligence.tsx`: fix selected-region weather overlay staleness.
- `/backend/routes/dashboard.py`, `/backend/routes/prediction.py`, `/backend/routes/vegetation.py`, `/backend/routes/weather.py`: review default `r1` endpoints and ensure production UI always passes selected region explicitly.
- `/backend/services/report_service.py`: if production report downloads are required, implement persisted report storage or state that reports are queued-only.
- `.github/workflows/*`: update deployment secrets docs/healthchecks if using real production deployment.

## 13. Files That Must Not Be Changed

Do not change unless there is an explicit data/model migration reason:

- `/.env`: contains local secrets/config; do not print or commit.
- `/backend/artifacts/**`: generated local rasters/cache/uploads/reports/models; do not treat as source of truth.
- `/frontend/dist/**`: generated frontend build output.
- `/node_modules/**`, `/frontend/node_modules/**`: dependencies.
- `/.venv/**`, `/.backend-venv*/**`, `/.test-venv/**`: local virtual environments.
- `/tests/**`: do not rewrite tests to hide production-readiness failures; only update with corresponding behavior changes.
- Existing migration files under `/backend/alembic/versions/**`: avoid mutating applied migrations; add new migrations instead.
- Existing UI components that only need deployment configuration should not be redesigned.

## 14. Frontend Deployment Audit

Hardcoded backend URLs:

- `/frontend/src/services/api.ts` contains the only frontend source hardcoded localhost backend fallback.

Environment variables:

- Uses Vite `import.meta.env`.
- Existing env var is `VITE_API_URL`; no `VITE_API_BASE_URL` found.
- API URLs are centralized in `/frontend/src/services/api.ts`; actual endpoint calls are in `/frontend/src/hooks/useEnvironmentalData.ts` and `/frontend/src/pages/AlertsPage.tsx`.

Frontend calls:

- `GET /weather/`
- `GET /hotspots/`
- `GET /vegetation/satellite/status`
- `GET /prediction/{region.id}`
- `GET /alerts/evaluate/{region.id}`
- `GET /alerts/evaluate/{selectedRegionId}`

Verification:

- `npm --prefix frontend run typecheck`: passed.
- `npm --prefix frontend run build`: passed.
- `npm --prefix frontend run test`: passed, 13 tests.
- Browser console was not verified with an actual browser session during Phase 1; smoke render tests passed without source import failures.
- No broken imports or missing assets surfaced in typecheck/build.

Production config required:

- Development: set `VITE_API_URL=http://localhost:8000/api` or rely on dev fallback.
- Production: set `VITE_API_URL=https://deployed-backend-url/api`.

## 15. Backend Deployment Audit

Python version:

- No explicit project pin file found.
- Dockerfile uses `python:3.12-slim`.
- Local backend tests passed using `.backend-venv311/bin/python`, Python 3.11.16.
- System Python 3.14.2 lacks pytest and should not be used as the backend deployment target.

Dependency files:

- `/backend/requirements.txt` exists.
- No `pyproject.toml` found.

Dependencies:

- `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `python-dotenv`, `SQLAlchemy`, `psycopg[binary]`, `alembic`, `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt`, `email-validator`, `redis`, `celery`, `pandas`, `numpy`, `scikit-learn`, `joblib`, `xgboost`, `shapely`, `rasterio`, `geopandas`, `pytest`, `httpx`.

Cloud suitability:

- Suitable with Docker and GDAL/geospatial packages installed.
- Risky on non-Docker hosts unless GDAL, Rasterio, GeoPandas dependencies are supported.

Bind/port:

- `BACKEND_HOST` defaults to `0.0.0.0`.
- `PORT` defaults to `8000`.
- Render script uses both correctly.

Backend verification:

- `python3 -m py_compile backend/main.py`: passed with system Python 3.14.
- `.backend-venv311/bin/python -m py_compile backend/main.py`: passed.
- `.backend-venv311/bin/python -m pytest`: passed, 131 tests, 1 `passlib` deprecation warning.

## 16. API And CORS Audit

Backend API routes are registered in `/backend/main.py` under `/api/*` and hidden duplicates under `/api/v1/*`.

Health endpoints:

- `GET /api/health` exists.
- `GET /api/readiness` exists.

CORS:

- Configured in `/backend/main.py`.
- Origins come from `Settings.cors_origins` in `/backend/core/config.py`.
- Defaults allow localhost dev ports only.
- Production validation rejects wildcard, localhost, and empty CORS origins.

Production CORS recommendation:

- Set `CORS_ORIGINS=https://your-vercel-app.vercel.app,https://your-custom-domain.example`.
- Keep `allow_credentials=True` only with explicit origins.

## 17. File Storage Audit

Local storage paths:

- `/backend/artifacts/models`: trained `.joblib` model artifacts if saved; currently empty.
- `/backend/artifacts/uploads`: uploads; currently empty.
- `/backend/artifacts/rasters`: Sentinel downloaded/processed raster artifacts; contains generated `.tif` and manifest files.
- `/backend/artifacts/cache`: file cache; currently empty.
- `/backend/artifacts/reports`: reports; currently empty.
- `/backend/artifacts/data-archive`, `/backend/artifacts/data-checkpoints`: pipeline state; currently empty.
- `/datasets`: configured dataset root; currently empty.

Persistence requirements:

- Persist database, Redis, and any operational Sentinel raster products that must survive redeploys.
- Temporary Sentinel downloads can live in `/tmp`.
- Generated reports only need persistence if users must retrieve them later.

Object storage:

- Not required for first deployment if Sentinel file processing is disabled or treated as temporary.
- Required/recommended if Sentinel rasters, uploads, or generated reports must survive redeploys. Cloudinary is configured but not implemented as active storage.

Git readiness:

- `.gitignore` excludes `.env`, `.env.*`, pyc/cache, node_modules, dist/build, local DB files, archives, and `backend/artifacts`.
- `.dockerignore` excludes `.env`, virtualenvs, caches, node_modules, `frontend/dist`, `backend/artifacts`, and generated dataset paths.
- No `.git` directory exists in this workspace, so actual tracked status cannot be verified.

## 18. Deployment Readiness Score

Score: 72 / 100.

Reasons:

- Strong: frontend builds, backend tests pass, Dockerfile exists, Render/Vercel configs exist, centralized settings, production validation, health endpoint, Alembic migrations, provider error handling.
- Not ready yet: no verified managed PostGIS deployment, no production seed/init strategy, demo auth, local/ephemeral artifact assumptions, mixed real/fixture data, region source duplication between frontend and backend, no explicit Python version pin, no live browser console/CORS integration verification.

## 19. Phase 1 Verification Commands Run

- `npm --prefix frontend run typecheck`: passed.
- `npm --prefix frontend run build`: passed.
- `npm --prefix frontend run test`: passed.
- `python3 -m py_compile backend/main.py`: passed.
- `.backend-venv311/bin/python -m py_compile backend/main.py`: passed.
- `.backend-venv311/bin/python -m pytest`: passed, 131 passed.

## 20. Stop Point

Phase 1 is complete. No Phase 3 production-code changes should begin until explicit approval is given.
