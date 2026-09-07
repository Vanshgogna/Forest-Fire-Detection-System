# FireSight Finalization Plan

Feature freeze is active. The goal for the final two days is to connect the existing real-data path, remove demo dependence from the main user flow, verify deployment, and defer everything else.

## 1. Current Architecture

The backend is a FastAPI application mounted from `backend/main.py`. It exposes health, dashboard, environmental snapshot, weather, vegetation, hotspots, prediction, GIS, alerts, analytics, reports, and settings routes.

The intended production flow already has most of its pieces:

`Open-Meteo + NASA FIRMS + Sentinel NDVI` -> `EnvironmentalDataService.get_environmental_snapshot(region_id)` -> `FireRiskModelService.predict(...)` -> dashboard, map, alerts, explanations.

That flow is not yet wired end to end. The frontend currently builds much of the displayed risk state from local fixture regions, while selected live weather, hotspot, and Sentinel status fields are merged in by `useEnvironmentalData`.

## 2. Existing Working Components

- FastAPI app wiring, route registration, health/readiness metadata, and public config are present.
- Open-Meteo weather provider is live-capable, cached, provenance-aware, and does not require a key by default.
- FIRMS provider, ingestion service, aggregation service, and database models exist and are covered by tests.
- Sentinel acquisition, raster preparation, quality masking, and NDVI processing services exist and are covered by tests.
- Celery worker and beat configuration exist.
- ML feature builder and `FireRiskModelService` exist. The service can score a payload with either a loaded model artifact or the existing heuristic fallback.
- Explainability logic exists for a supplied prediction payload.
- Alert engine exists for a supplied risk payload.
- Frontend pages and smoke-tested render paths exist for dashboard, map, vegetation, hotspots, weather, predictions, analytics, reports, alerts, settings, and about.

## 3. Real-Data Components

- Weather: usable now through `backend/services/weather_provider.py` and weather/environmental routes.
- FIRMS hotspots: real-capable through `backend/services/firms_provider.py`, `backend/services/hotspot_ingestion_service.py`, and `backend/services/hotspot_aggregation_service.py`; requires `FIRMS_ENABLED=true`, `FIRMS_MAP_KEY`, database access, and scheduled ingestion.
- Sentinel acquisition: real-capable through `backend/services/sentinel_acquisition_service.py`; requires `SENTINEL_ENABLED=true` and Copernicus credentials.
- Sentinel raster, quality mask, NDVI: implemented as service/task layers, but the scheduled job currently stops at acquisition. Raster -> quality -> NDVI needs to be invoked after a scene is acquired.
- Environmental snapshot API: already exists at `/api/environmental-snapshot/{region_id}` and should be the canonical environmental input for prediction.
- Prediction API: `POST /api/prediction/` already calls `FireRiskModelService.predict(...)`, but it expects a payload and does not compose a live snapshot itself.

## 4. Mock-Data Locations

- `backend/services/mock_environment.py`: backend fixture regions, weather, risk, alerts, and reports.
- `backend/routes/prediction.py`: `GET /api/prediction/` returns simulated regional predictions; explainability route still uses fixture NDVI, NBR, and hotspot values.
- `backend/routes/dashboard.py`: overview mixes live weather/FIRMS summary with fixture risk, alert counts, and top-risk region.
- `backend/routes/alerts.py`: list endpoint returns fixture alerts; evaluation only works when given a payload.
- `backend/routes/gis.py` and `backend/services/gis_service.py`: risk layers, heatmap, statistics, and region risk values are fixture-based.
- `frontend/src/constants/mockData.ts`: main frontend fixture source for regions, risk, vegetation, weather, trends, alerts, and reports.
- `frontend/src/hooks/useEnvironmentalData.ts`: uses fixtures as the base state and overlays partial live weather/hotspot/Sentinel metadata.
- `frontend/src/pages/DashboardPage.tsx` and `frontend/src/pages/PredictionPage.tsx`: still calculate/display key risk values from frontend fixtures.
- `frontend/src/components/prediction/ExplainabilityDashboard.tsx`: hardcoded probability, feature-importance, reasoning, recommendations, and what-if inputs.

## 5. Required Integration Steps

1. Add one backend live prediction composition path using existing code only:
   - read `EnvironmentalDataService.get_environmental_snapshot(region_id)`;
   - map the snapshot into the existing ML feature schema;
   - call `FireRiskModelService.predict(...)`;
   - return risk, confidence, feature values, explanation, provenance, and data freshness.

2. Use that live prediction path in the existing frontend hook:
   - update `frontend/src/hooks/useEnvironmentalData.ts` to fetch live prediction summaries;
   - preserve fixture fallback only for unavailable real-data fields;
   - clearly label unavailable NDVI/FIRMS data instead of showing fake precision.

3. Replace high-impact fixture displays only:
   - Dashboard summary risk and top-risk region;
   - Prediction page risk, confidence, factors, and explanation;
   - Map risk coloring/tooltip values;
   - Alerts page/evaluation source.

4. Wire scheduled real-data jobs:
   - keep existing FIRMS ingestion schedule;
   - chain or schedule Sentinel raster preparation, quality masking, and NDVI calculation after acquisition;
   - avoid adding new satellite algorithms or providers.

5. Remove confusing visual clutter without redesigning the product:
   - keep primary dashboard/prediction cards only;
   - shorten labels and descriptions;
   - enforce responsive card bounds so text cannot overflow.

## 6. Deployment Blockers

- Local PostgreSQL is not ready for online migration checks: the configured role `firesight` does not exist.
- `render.yaml` is missing production env vars for `DATA_MODE`, FIRMS, Sentinel/Copernicus, and Sentinel processing directories on worker/cron services.
- `Dockerfile.backend` copies backend code but not the root `alembic.ini`; deployment needs either an explicit migration run from the repo root or an image/command that includes Alembic config.
- No deployment migration step is defined in Render or GitHub Actions.
- Sentinel raster/NDVI artifacts need persistent storage policy. Render's normal container filesystem should be treated as ephemeral unless a disk or external object storage is configured.
- Vercel needs `VITE_API_URL` set to the deployed backend `/api` base URL.
- Production `JWT_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, and `CORS_ORIGINS` must be set and must pass `backend/core/config.py` production validation.

## 7. Explicitly Deferred Features

Defer NBR work, new ML models, deep learning, CNN/LSTM, advanced forecasting, new satellite providers, new weather providers, Kafka, Kubernetes, Terraform, microservices, complex notification systems, new dashboards, major UI redesign, advanced time-series infrastructure, and raw raster tile serving.

## Exact Remaining Work

- Backend: add a live prediction summary endpoint/service that composes environmental snapshots into `FireRiskModelService`.
- Backend: adjust dashboard/GIS/alerts routes only where needed to read the live prediction result instead of fixture risk.
- Frontend: make `useEnvironmentalData` the single consumer of live prediction summaries and reduce fixture use to fallback states.
- Frontend: simplify crowded dashboard/prediction cards and add responsive text constraints.
- Deployment: add missing production env vars, document/run migrations, configure artifact persistence or explicit ephemeral fallback.
- Operations: provision database role/database locally or use Render's managed `DATABASE_URL`, then run migrations.

## Files Likely To Change

- `backend/routes/prediction.py`
- `backend/routes/dashboard.py`
- `backend/routes/gis.py`
- `backend/routes/alerts.py`
- `backend/services/environmental_data_service.py`
- `backend/tasks/celery_app.py`
- `backend/tasks/jobs.py`
- `frontend/src/hooks/useEnvironmentalData.ts`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/PredictionPage.tsx`
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/pages/AlertsPage.tsx`
- `frontend/src/components/prediction/ExplainabilityDashboard.tsx`
- `frontend/src/constants/mockData.ts`
- `render.yaml`
- `Dockerfile.backend`
- `.env.example`
- `docs/deployment.md` or a short deployment runbook

## Verification

- Backend tests: `116 passed, 1 warning`.
- Frontend typecheck: passed.
- Frontend smoke tests: `13 passed`.
- Frontend production build: passed.
- Alembic heads: single head, `20260829_0005`.
- Alembic offline SQL generation: passed with `PYTHONPATH=.`.
- Alembic online check: blocked by local PostgreSQL configuration; `role "firesight" does not exist`.

