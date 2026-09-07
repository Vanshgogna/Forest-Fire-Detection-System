# Changelog

All notable changes to FireSight are recorded here. The project follows Semantic Versioning and keeps release notes grouped by Added, Changed, Fixed, Breaking Changes, and Performance Improvements.

## [Unreleased]

### Added

- Monitoring and observability service for application metrics, model monitoring, alert summaries, storage usage, recent errors, trace context, and platform health dashboards.
- Component health endpoints for backend, database, weather API, satellite pipeline, prediction engine, and GIS engine.
- Admin monitoring endpoints for metrics, model monitoring, alerting, and dashboard summaries.
- Structured JSON logging formatter and request trace context.
- Scalability architecture documentation covering replaceable modules, dependency inversion, async processing, microservice readiness, storage scalability, future features, and multi-tenant growth.
- Model adapter registry for current and future AI models so prediction APIs remain stable as new model families are added.
- Async job contracts for future satellite downloads and notification delivery.
- Explainable AI engine that creates structured explanation details for every prediction.
- Prediction API fields for top contributing features, feature importance, risk factors, historical comparison, weather influence, vegetation influence, historical trend influence, confidence rationale, visual explanations, interpretability roadmap, and recommendation rationales.
- Explainable AI documentation covering no-black-box prediction rules, visual explanation payloads, and future SHAP/LIME/permutation/PDP integrations.
- Complete CI/CD and DevOps documentation covering source control, branch protection, CI jobs, CD targets, quality gates, rollback, and future blue/green deployment.
- GitHub Actions CI workflow with dependency installation, type checking, linting, formatting checks, tests, build verification, Docker build verification, dependency audits, Bandit, and Trivy scans.
- GitHub Actions deployment workflow for Vercel frontend deploys, Render backend/worker/scheduler deploy triggers, and post-deploy health checks.
- GitHub Actions release workflow for SemVer tag validation, changelog enforcement, release artifact generation, GHCR Docker publishing, and GitHub releases.
- Project-management governance docs covering roadmap, milestones, sprint planning, implementation order, dependency graph, and module completion tracking.
- Version-control guide covering branch strategy, semantic versioning, release tags, and meaningful commit-message examples.
- Architecture Decision Record process and ADR-0001 for docs-driven project governance.
- Module completion review gates for architecture, code, dependencies, performance, and security.
- Data engineering refresh policy support for manual, scheduled, and incremental ingestion.
- Data pipeline automation planner for scheduled and incremental worker execution.
- Download progress tracking in data ingestion results.
- Weather CSV validation and raster integrity validation in the enterprise ETL pipeline.

### Changed

- Request logging, cache access, prediction inference, and raster processing plans now record observability metrics.
- Admin system health now includes component health, metrics, and observability alerts.
- Model training plans now disclose available and future model adapters through the registry.
- Prediction responses now enforce explainability as part of the API contract instead of returning only a simple explanation string.
- Expanded `.gitignore` and `.dockerignore` for local environments, secrets, build outputs, caches, datasets, and generated artifacts.
- Release checklist now requires CI quality-gate and release-workflow verification.
- Data pipeline checkpoints now include completed stages, next stage, and resumability metadata.
- Data API source contract now documents the full ETL stage list and refresh modes.
- Data engineering documentation now describes ingestion, validation, versioning, quality, automation, and storage contracts.

### Fixed

- Standalone ETL imports no longer require FastAPI when only data ingestion utilities are used.
- Weather validation now reports missing schema fields once while keeping row-level value errors clear.

### Breaking Changes

- None.

### Performance Improvements

- Data ingestion now avoids redundant work when expected checksums match existing downloaded files.

## [0.1.0] - 2026-08-24

### Added

- Initial production-oriented FireSight platform with React dashboard, FastAPI backend, PostgreSQL schema, Redis/Celery contracts, ML pipeline contracts, remote-sensing pipeline contracts, security middleware, CI, deployment scripts, and operational documentation.
