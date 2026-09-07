# AI-Based Forest Fire Risk Prediction and Early Warning System

A production-oriented environmental intelligence platform for monitoring vegetation health, weather stress, fire hotspots, GIS risk layers, explainable AI predictions, alerts, analytics, and reports.

## Capabilities

- FastAPI backend with modular routes, services, repositories, schemas, middleware, Celery tasks, and Alembic migrations
- React, TypeScript, Vite frontend with dashboard, GIS, weather, vegetation, hotspot, prediction, alert, analytics, report, and settings pages
- PostgreSQL/PostGIS schema, Redis cache hooks, JWT authentication, role-based access control, safe logging, and rate limiting
- ML pipeline contracts for preprocessing, Random Forest/XGBoost training, prediction, batch prediction, confidence, explainability, model persistence, and retraining
- GIS and remote-sensing pipeline contracts for Sentinel-2, MODIS, future VIIRS, NDVI, NBR, heatmaps, GeoJSON, tiling, caching, storage, and cleanup
- Docker, Render, Vercel, CI, health checks, readiness checks, and production configuration validation

## Documentation

- [Installation Guide](docs/installation-guide.md)
- [Developer Guide](docs/developer-guide.md)
- [Architecture Documentation](docs/backend-architecture.md)
- [API Documentation](docs/api-documentation.md)
- [Database Schema](docs/database-schema.md)
- [ML Workflow](docs/ml-workflow.md)
- [Explainable AI](docs/explainable-ai.md)
- [Data Engineering Pipeline](docs/data-engineering-pipeline.md)
- [Remote-Sensing Pipeline](docs/remote-sensing-pipeline.md)
- [Project Management](docs/project-management.md)
- [Version Control](docs/version-control.md)
- [Review Gates](docs/review-gates.md)
- [CI/CD and DevOps](docs/ci-cd-devops.md)
- [Scalability Architecture](docs/scalability-architecture.md)
- [Monitoring and Observability](docs/monitoring-observability.md)
- [Changelog](CHANGELOG.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Folder Structure](docs/folder-structure.md)
- [User Manual](docs/user-guide.md)
- [Admin Guide](docs/admin-guide.md)
- [Testing and QA](docs/testing-quality-assurance.md)
- [Error Handling and Logging](docs/error-handling-logging.md)
- [Security Review](docs/security-review.md)
- [Performance Optimization](docs/performance-optimization.md)
- [Troubleshooting Guide](docs/troubleshooting-guide.md)
- [Known Limitations](docs/known-limitations.md)
- [Future Improvements](docs/future-improvements.md)
- [Project Completion Summary](docs/project-completion.md)

## Run Locally

Copy the example environment file and replace secrets before running services:

```bash
cp .env.example .env
```

Frontend:

```bash
npm install
npm run dev
```

Backend:

```bash
pip install -r backend/requirements.txt
npm run backend
```

Full local stack:

```bash
docker compose up --build
```

This starts FastAPI, PostgreSQL/PostGIS, Redis, Celery worker, Celery scheduler, and Nginx. The current implementation keeps realistic mock data available for exploration while exposing production-ready contracts for database persistence, Redis-backed caching, dashboard aggregation, model training/versioning, satellite preprocessing, weather history analysis, alert lifecycle management, notification queues, report export jobs, and role-protected administration.

Demo login:

- Email: `officer@firesight.ai`
- Password: set `DEMO_LOGIN_PASSWORD` in your local `.env` file.

## Quality Checks

```bash
npm run typecheck
npm test
npm run build
.test-venv/bin/python -m pytest
```

See `docs/testing-quality-assurance.md` for the full QA matrix. GitHub Actions runs frontend and backend verification with PostgreSQL/PostGIS and Redis service containers.
