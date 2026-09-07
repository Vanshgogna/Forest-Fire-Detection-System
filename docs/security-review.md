# Security Review

## Security Controls Implemented

- JWT access and refresh tokens with expiration.
- Role-based access control for admin, forest officer, government officer, researcher, and viewer-style access.
- Strict request schemas that reject unexpected fields.
- Coordinate, weather, vegetation, satellite, model-training, and alert lifecycle validation.
- Request size limits through `MAX_REQUEST_BODY_BYTES`.
- Rate limiting through `RATE_LIMIT_PER_MINUTE`.
- Optional replay protection for mutating requests using `X-Idempotency-Key`.
- Secure error responses without stack traces or internal implementation details.
- Request IDs for traceability without exposing secrets.
- Security headers including CSP, frame protection, content sniffing protection, referrer policy, permissions policy, and HSTS on HTTPS.
- ORM-based database access through SQLAlchemy repositories.
- Environment-only configuration for secrets, database URLs, API keys, cache URLs, model paths, dataset paths, and deployment settings.

## Frontend Security

- React escapes rendered values by default.
- No unsafe HTML rendering or Markdown rendering is used.
- API errors are normalized to user-safe messages.
- Frontend API URL is provided through `VITE_API_URL`.
- CSP is emitted by the backend for API responses and by `vercel.json` for the deployed React application.

## Attack Surface

- Public read APIs for dashboard, weather, GIS, vegetation, hotspots, prediction, analytics, reports, and settings.
- Authenticated APIs for users, notifications, admin, prediction jobs, model training, and alert lifecycle operations.
- Future file upload and satellite ingestion surfaces.
- Redis, PostgreSQL, Celery workers, and object storage integrations.

## Dependency Security

Run local audits before release:

```bash
npm audit
python -m pip check
```

Current local result:

- `python -m pip check` passes with no broken Python requirements.
- `npm ls --omit=dev` passes with a consistent production dependency tree.
- `npm audit --omit=dev --audit-level=moderate` requires access to the npm advisory service. The local sandbox could not resolve `registry.npmjs.org`, and the follow-up network approval timed out, so this remains a release-gate check for CI or an unrestricted developer machine.

Recommended production additions:

- Add `pip-audit` or Safety to CI.
- Add Dependabot or Renovate.
- Pin and review geospatial binary dependencies.
- Track CVEs for GDAL, Rasterio, GeoPandas, XGBoost, FastAPI, SQLAlchemy, and JWT libraries.

## Residual Risks And Recommendations

- Add OAuth/OIDC provider integration for enterprise identity.
- Add refresh-token rotation and revocation storage.
- Add CSRF protection if browser cookie authentication is introduced.
- Add signed upload URLs and content scanning for file uploads.
- Add WAF/CDN rules in front of production APIs.
- Add security event export to SIEM.
- Add OpenTelemetry traces and Sentry-style error monitoring.
- Add database row-level permissions if multi-tenant organizations are introduced.
- Add live dependency vulnerability scanning in CI.
