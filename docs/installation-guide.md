# Installation Guide

## Prerequisites

- Node.js 22 or compatible LTS
- Python 3.12 for production parity, or Python 3.9-3.12 for local tests
- PostgreSQL with PostGIS for persistent production data
- Redis for cache and background jobs
- Docker or a compatible runtime for the full local stack

## Local Frontend

```bash
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`.

## Local Backend

```bash
cp .env.example .env
pip install -r backend/requirements.txt
npm run backend
```

The backend runs at `http://localhost:8000`.

## Test Environment Used On This Machine

This workspace uses `.test-venv` for backend verification because the default `.venv` is Python 3.14 and some pinned geospatial and Pydantic dependencies are more reliable on Python 3.9-3.12.

```bash
.test-venv/bin/python -m pytest
```

## Full Stack

```bash
cp .env.example .env
docker compose up --build
```

This starts FastAPI, PostgreSQL/PostGIS, Redis, Celery worker, Celery scheduler, and Nginx.

## Verification

```bash
npm test
npm run typecheck
npm run build
.test-venv/bin/python -m pytest
```

## Health Checks

- Liveness: `GET /api/health`
- Readiness: `GET /api/readiness`
- API docs: `GET /docs`
- OpenAPI schema: `GET /openapi.json`
