# Scalability And Future Architecture

FireSight is designed for long-term growth by keeping modules replaceable, using stable API contracts, and separating domain responsibilities so each area can become an independent service when scale requires it.

## Modular Architecture

Every module should be independently replaceable:

| Boundary | Current Module | Future Replacement Path |
| --- | --- | --- |
| API routing | `backend/routes/*` | API gateway or separate service routers |
| Validation and schemas | `backend/schemas/*`, Pydantic models | Shared contract package or OpenAPI-generated clients |
| Domain logic | `backend/services/*` | Independent domain services |
| Data access | `backend/repositories/*` | Per-service repositories or data APIs |
| Background work | `backend/tasks/*` | Dedicated worker services or event consumers |
| ETL | `backend/data/*` | Data platform service |
| ML inference | `backend/ml/*` | Model-serving service |
| Notifications | `NotificationService` | Provider-specific email/SMS/webhook adapters |
| Storage | Artifact directories | Object storage adapters for S3/GCS/Azure Blob |

Rules:

- Routes depend on services and schemas, not storage/provider details.
- Services depend on repositories, data clients, and adapters through small contracts.
- Provider-specific code should sit at the edge of the system.
- Public APIs remain stable while internals move from monolith modules to services.
- Large files are referenced by URI and metadata rather than copied through API responses.

## Dependency Inversion

The system already uses inversion-friendly boundaries:

- `DataSource` and refresh policies abstract satellite, API, CSV, raster, and future providers.
- `DataPipeline` composes ingestion, validation, quality, versioning, cache, and archive stages.
- `ModelRegistry` describes available and future model adapters without changing prediction APIs.
- Notification channels are represented as provider-neutral queue contracts.
- Repositories isolate SQLAlchemy from route handlers.

Future adapter interfaces should be added for:

- Object storage.
- Email providers.
- SMS providers.
- Drone telemetry.
- Real-time satellite stream consumers.
- Tenant configuration.

## Future Feature Readiness

| Feature | Prepared Boundary |
| --- | --- |
| Authentication | `backend/core/security.py`, auth routes, role dependencies |
| User accounts | user routes, schemas, admin tracking |
| Notifications | notification route/service contracts |
| SMS alerts | `sms` notification channel placeholder |
| Email alerts | `email` notification channel placeholder |
| Drone integration | future provider behind data ingestion and hotspot/imagery adapters |
| Real-time satellite streams | Celery/event worker boundary and data-source refresh policies |
| Deep learning models | `ModelRegistry` future adapters: `satellite_cnn`, `multimodal_fusion` |
| Mobile applications | stable `/api` and `/api/v1` contracts |
| Cloud storage | artifact directory settings ready for object-storage adapter replacement |
| Multiple countries | region/state boundaries can evolve into country/tenant scopes |
| Multi-tenant deployment | future tenant context can wrap auth, data access, storage prefixes, and rate limits |

## Async Processing

Background jobs are isolated in `backend/tasks/jobs.py`.

Current and future job categories:

- Satellite downloads: `firesight.download_satellite_scene`.
- Satellite processing: `firesight.process_satellite_scene`.
- Dataset processing: `firesight.run_data_pipeline`.
- Model retraining: `firesight.retrain_model`.
- Report generation: `firesight.generate_report`.
- Notification delivery: `firesight.deliver_notification`.
- Weather refreshes: `firesight.update_weather_records`.

Scaling path:

1. Keep Celery workers for the initial deployment.
2. Split queues by workload: `satellite`, `etl`, `ml`, `reports`, `notifications`.
3. Route long-running raster and model jobs to dedicated worker pools.
4. Move high-volume stream processing to Kafka, Pub/Sub, Kinesis, or Redis Streams when needed.
5. Keep job payloads stable and versioned.

## Microservice Readiness

Potential service extraction order:

1. Data ingestion service for satellite/weather/fire records.
2. Raster processing service for large geospatial imagery.
3. Model-serving service for low-latency inference and model version routing.
4. Notification service for SMS/email/webhook delivery.
5. Reporting service for long-running exports.
6. Tenant/account service for multi-tenant deployments.

Service contracts should use:

- OpenAPI for synchronous APIs.
- Versioned message schemas for async jobs.
- Dataset and model version IDs for reproducibility.
- Object-storage URIs for large files.

## Storage Scalability

| Storage Need | Strategy |
| --- | --- |
| Large raster files | Store in object storage as GeoTIFF/COG/Zarr; persist URI, bounds, CRS, checksum, and scene metadata |
| Large weather datasets | Partition by region and observation date; batch ingest; cache aggregates |
| Historical archives | Immutable archive paths with dataset version manifests |
| Multiple model versions | Store model artifacts by algorithm, version, training dataset, checksum, and compatibility metadata |
| Reports | Generate asynchronously and store exports by report type/version |
| Multi-tenant artifacts | Prefix storage by tenant/country/environment |

The API should return metadata, signed URLs, or tile manifests instead of streaming very large artifacts directly from FastAPI.

## AI Model Extensibility

Prediction APIs must stay stable when new models are added.

Current mechanism:

- `ModelRegistry` lists available and future adapters.
- `FireRiskModelService.predict()` always returns the same `PredictionResult` contract.
- Explainability is mandatory for all models.
- Training plans expose available and future adapters.

Adding a model should require:

1. Registering a new `ModelAdapter`.
2. Implementing training/loading/inference behind the model service or future model-serving service.
3. Preserving the prediction response fields.
4. Providing explanation methods and confidence rationale.
5. Adding tests without changing existing client payloads.

## Multi-Tenant And Multi-Country Path

Future tenant context should include:

- Tenant ID.
- Country or jurisdiction.
- Allowed regions.
- Data-source credentials.
- Storage prefix.
- Model policy.
- Notification provider configuration.
- Rate-limit tier.

The first implementation can add tenant context at auth/session boundaries, then propagate it to repositories, data pipelines, storage adapters, and notification providers.
