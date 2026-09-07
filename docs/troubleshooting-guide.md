# Troubleshooting Guide

## Frontend Build Fails

Run:

```bash
npm install
npm run typecheck
npm run build
```

Common causes:

- Missing `node_modules`
- Invalid TypeScript import
- A route page missing its named export

## Backend Tests Fail On Python 3.14

Use Python 3.9-3.12 for local backend tests. This workspace uses:

```bash
.test-venv/bin/python -m pytest
```

Some pinned scientific and Pydantic dependencies are not yet reliable on Python 3.14.

## Docker Is Not Available

Docker Desktop requires a newer macOS version than macOS 12. On older macOS, install a compatible runtime such as Colima if available:

```bash
brew install docker docker-compose colima
colima start
docker compose up --build
```

If Homebrew cannot complete the install, use a hosted environment such as Render, Railway, GitHub Codespaces, or a Linux machine with Docker.

## Backend Starts But Database Fails

Check:

- `DATABASE_URL`
- PostgreSQL server is reachable
- PostgreSQL database is reachable and migrations have been applied
- Alembic migrations have been applied

```bash
alembic upgrade head
```

## Redis Or Background Jobs Fail

Check:

- `REDIS_URL`
- Redis server is reachable
- Worker command: `celery -A backend.tasks.celery_app:celery_app worker --loglevel=INFO`
- Scheduler command: `celery -A backend.tasks.celery_app:celery_app beat --loglevel=INFO`

## Production Config Fails At Startup

Production validation intentionally rejects:

- Development JWT secret
- Short JWT secret
- Localhost database URL
- Localhost CORS origins

Set production values in the hosting provider secret manager.

## API Returns 422

The request failed validation. Responses include sanitized field locations and messages. Check the endpoint schema in `/docs`.

## API Returns 500

The client receives a safe message and request ID. Search backend logs for `request_id=<value>`.
