# Monitoring And Observability

FireSight exposes component health, application metrics, model monitoring, alert summaries, structured logs, trace context, and dashboard-ready observability reports.

## System Health

Public health endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Backend liveness |
| `GET /api/readiness` | Readiness plus component summary |
| `GET /api/monitoring/health` | Backend, database, weather API, satellite pipeline, prediction engine, and GIS engine health |
| `GET /api/monitoring/health/backend` | Backend process health |
| `GET /api/monitoring/health/database` | Database configuration/readiness status |
| `GET /api/monitoring/health/weather-api` | Weather provider adapter status |
| `GET /api/monitoring/health/satellite-pipeline` | Satellite/raster processing pipeline status |
| `GET /api/monitoring/health/prediction-engine` | Prediction engine status |
| `GET /api/monitoring/health/gis-engine` | GIS engine status |

Admin-only monitoring endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/monitoring/metrics` | Application metrics |
| `GET /api/monitoring/model` | Model monitoring |
| `GET /api/monitoring/alerts` | Observability alert summary |
| `GET /api/monitoring/dashboard` | System health, API performance, model performance, dataset status, storage usage, recent errors, alerts, and overall platform health |
| `GET /api/admin/system-health` | Admin health summary with metrics and alerts |

## Application Metrics

The in-process metrics registry tracks:

- API response time.
- Prediction time.
- Raster processing time.
- Database query time.
- Memory usage.
- CPU/load usage.
- Cache hit rate.
- Request count.
- Error count.
- Error rate.

These payloads are designed to be forwarded later to Prometheus, OpenTelemetry, Datadog, CloudWatch, or another platform metric backend.

## Model Monitoring

Model monitoring reports:

- Prediction accuracy status.
- Inference time.
- Feature drift status.
- Data drift status.
- Model drift status.
- Confidence distribution.
- Prediction count by risk category.

Accuracy and drift require labeled feedback and production baselines. Until those are connected, the API returns explicit `baseline_required` or `requires_labeled_feedback` states rather than pretending the values are available.

## Alerting

The observability registry generates alert objects for:

- API failures.
- High error rates.
- Slow response times.
- Slow prediction inference.
- Slow raster processing.
- Dataset failures.
- Model failures.
- Weather API downtime.
- Storage issues.

Current implementation computes API/error/latency/dataset alerts locally. Provider downtime and storage alerts are represented in the health and dashboard contracts and can be connected to external monitors in production.

## Structured Logs And Tracing

Runtime logging uses structured JSON records with:

- Timestamp.
- Level.
- Logger name.
- Message.
- Request ID.
- Method.
- Path.
- Status code.
- Elapsed milliseconds.
- Error type when failures occur.

Each request gets an `X-Request-ID` response header and an internal trace context with `trace_id`, `span_id`, operation name, and timestamp. This keeps local debugging useful now and prepares the service for OpenTelemetry tracing later.

## Reporting Dashboard

`GET /api/monitoring/dashboard` summarizes:

- System health.
- API performance.
- Model performance.
- Dataset status.
- Storage usage.
- Recent errors.
- Observability alerts.
- Overall platform health.

## Production Recommendations

- Export metrics to Prometheus or OpenTelemetry.
- Send structured logs to a searchable log backend.
- Add Sentry-style error aggregation.
- Add uptime checks for API, frontend, weather provider, and satellite provider endpoints.
- Add storage bucket usage alarms.
- Add model drift and confidence-distribution dashboards after labeled feedback is available.
- Page operators only on actionable critical alerts.
