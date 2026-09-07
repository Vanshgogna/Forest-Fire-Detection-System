# Admin Guide

## Operational Endpoints

- `GET /api/health`: lightweight liveness check.
- `GET /api/readiness`: readiness status for API, cache, ML, workers, and versioned API.
- `GET /api/admin/system-health`: protected admin health summary.
- `GET /api/monitoring/dashboard`: protected observability dashboard for health, performance, datasets, storage, errors, and alerts.
- `GET /api/monitoring/metrics`: protected application metrics.
- `GET /api/monitoring/model`: protected model monitoring summary.
- `GET /api/admin/audit-summary`: protected audit capability summary.

## User Roles

- `admin`: full configuration, user, and operational access.
- `forest_officer`: alert and operational workflow access.
- `researcher`: prediction and model workflow access.
- `viewer`: read-only dashboard and intelligence access.

## Routine Operations

- Review open alerts and acknowledge critical events.
- Monitor weather and satellite refresh status.
- Review generated reports before external distribution.
- Rotate `JWT_SECRET_KEY` and provider credentials on a regular schedule.
- Keep database backups and recovery drills documented.
