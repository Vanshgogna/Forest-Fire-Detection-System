# Project Management

FireSight is organized as a staged environmental intelligence platform. This document is the source of truth for development roadmap, milestones, sprint planning, implementation order, dependency graph, and module status.

## Development Roadmap

| Phase | Outcome | Status |
| --- | --- | --- |
| Phase 1: Foundation | Repository structure, frontend shell, backend shell, environment configuration, CI | Complete |
| Phase 2: Core Platform | Dashboard, weather, GIS, alerts, reports, auth, admin APIs | Complete |
| Phase 3: Intelligence | ML contracts, explainability, satellite and vegetation contracts, analytics | Complete |
| Phase 4A: Remote Sensing | Sentinel/MODIS/VIIRS contracts, raster utilities, cache and cleanup contracts | Complete |
| Phase 4B: Data Engineering | Ingestion, validation, ETL, versioning, quality, checkpointing, automation | Complete |
| Phase 4C: Project Governance | Roadmap, changelog, ADRs, versioning, review gates | Complete |
| Phase 5: Live Integrations | Real satellite catalogs, live weather providers, historical fire datasets, object storage | Pending |
| Phase 6: Production Hardening | Observability, infrastructure as code, blue/green deploys, backup restore drills | Pending |
| Phase 7: Field Operations | Incident workflow, assignment, mobile APIs, provider notifications, audit exports | Pending |

## Milestones

| Milestone | Target Version | Exit Criteria | Status |
| --- | --- | --- | --- |
| M1 Platform Baseline | `0.1.0` | Frontend, backend, CI, docs, and mock-data contracts are usable | Complete |
| M2 Data Pipeline Baseline | `0.2.0` | ETL supports source refresh policies, validation, quality reports, version manifests, and checkpoints | Complete in code, release pending |
| M3 Live Data Pilot | `0.3.0` | At least one live weather provider and one live hotspot/satellite feed are connected behind existing interfaces | Pending |
| M4 Production Beta | `0.8.0` | Managed PostgreSQL/PostGIS, Redis, object storage, observability, and restore validation are deployed | Pending |
| M5 Public Stable | `1.0.0` | Real data integrations, tested rollback, security review, and operational runbooks are complete | Pending |

## Sprint Plan

| Sprint | Scope | Dependencies | Definition of Done |
| --- | --- | --- | --- |
| Sprint 1 | Connect live weather ingestion to data pipeline | Data pipeline baseline, provider credentials | Scheduled weather refresh writes validated records |
| Sprint 2 | Connect MODIS/VIIRS hotspot feed | Celery worker, archive storage | Incremental hotspot job produces versioned datasets |
| Sprint 3 | Add Sentinel catalog download adapter | Object storage, raster validation | Scene metadata and raster artifacts are archived |
| Sprint 4 | Replace mock read endpoints with repositories | Database schema, ingestion jobs | Dashboard reads persisted regional/weather/hotspot records |
| Sprint 5 | Add observability and incident runbooks | Deployment targets, logging policy | Metrics, traces, alerts, and operational playbooks are active |

## Implementation Order

1. Keep API contracts stable while replacing mock service data with repository-backed data.
2. Connect provider adapters one at a time behind existing source interfaces.
3. Persist validated ETL outputs before enabling model retraining from those outputs.
4. Add object storage for raster/report/archive artifacts before large scene downloads.
5. Add observability before public beta traffic.
6. Run security, performance, dependency, and architecture reviews before release tagging.

## Dependency Graph

```text
Provider credentials
  -> ingestion adapters
  -> ETL validation and quality
  -> versioned datasets
  -> repository persistence
  -> dashboard/API reads
  -> model retraining
  -> alerting and reports

Object storage
  -> raster archive
  -> report exports
  -> model registry
  -> production backup strategy

PostgreSQL/PostGIS + Redis
  -> repository-backed APIs
  -> Celery scheduled jobs
  -> operational health checks
```

## Module Completion Checklist

| Module | Status | Notes |
| --- | --- | --- |
| Frontend dashboard and pages | Complete | Mock-backed UX is implemented and buildable |
| Backend API surface | Complete | Route contracts and schemas are organized by domain |
| Auth and security middleware | Complete | JWT, roles, request security, headers, and rate limits are present |
| Database schema | Complete | Models and Alembic migration are present |
| ML pipeline contracts | Complete | Training, prediction, model metadata, enforced explainability, and recommendation rationale contracts are present |
| Remote-sensing contracts | Complete | Scene planning, vegetation indices, raster utilities, tiling, and cleanup contracts are present |
| Data engineering pipeline | Complete | Ingestion, validation, quality, versioning, checkpointing, and automation planning are present |
| Project governance | Complete | Roadmap, changelog, ADR, versioning, and review gates are present |
| CI/CD and DevOps automation | Complete | GitHub Actions quality gates, Vercel deployment, Render deployment, Docker build checks, and release workflows are present |
| Scalability architecture | Complete | Replaceable module boundaries, async job plan, microservice extraction path, storage scaling, and model registry extensibility are documented |
| Live provider adapters | Pending | Requires credentials and source-specific implementation |
| Repository-backed public reads | Pending | Replace mock services after ingestion writes real records |
| Object storage integration | Pending | Needed for production raster/report/model artifacts |
| Observability | Complete | Component health, application metrics, model monitoring, alert summaries, structured logs, trace context, and dashboard payloads are present |
| Infrastructure as code | Pending | Terraform or Pulumi definitions are future work |

## Tracking Register

### Completed Modules

- Frontend application shell, dashboard, GIS, weather, vegetation, prediction, alerts, analytics, reports, settings.
- FastAPI backend, schemas, services, middleware, repositories, tasks, and deployment configuration.
- Data engineering and remote-sensing contract layers.
- CI workflow with PostgreSQL/PostGIS and Redis services.
- Deployment and release automation for Vercel, Render, Docker, and future platform handoff.

### Pending Modules

- Live Sentinel, MODIS, VIIRS, weather, and historical fire ingestion adapters.
- Persistent repository-backed reads for all production datasets.
- Object storage and model registry integration.
- External observability export and backup restore automation.

### Blocked Modules

- Live provider integrations are blocked on provider credentials, rate-limit policy, and target geographic coverage.
- Docker runtime validation is blocked on local Docker availability for this macOS machine.
- Production deployment validation is blocked on managed PostgreSQL/PostGIS, Redis, object storage, and secrets.

### Future Enhancements

- Multi-country monitoring profiles.
- Incident assignment and escalation workflows.
- Mobile field APIs.
- Organization audit exports.
- Infrastructure as code.

### Technical Debt

- Public read endpoints still depend on realistic mock data until ingestion jobs are connected to repositories.
- Local virtual environments are inconsistent; CI should remain the authoritative test environment until local envs are recreated.
- Satellite APIs currently return processing manifests rather than full provider downloads.

### Known Limitations

- See [Known Limitations](known-limitations.md) for the maintained limitation register.
