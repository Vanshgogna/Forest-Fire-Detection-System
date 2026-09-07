# Release Checklist

## Build

- `CHANGELOG.md` is updated.
- Required ADRs are added or updated.
- Roadmap and module status are current.
- Frontend typecheck passes.
- Frontend production build completes.
- Backend tests pass.
- Backend modules compile.
- Docker stack builds.
- CI quality gate passes.
- Release workflow validates the changelog version.

## Security

- Production `JWT_SECRET_KEY` is rotated and not committed.
- CORS origins are restricted to deployed frontend URLs.
- HTTPS is enabled at the platform or proxy layer.
- Admin APIs are role-protected.
- Rate limits are configured for the deployment tier.

## Product QA

- Dashboard loads with no console errors.
- Navigation works on desktop, tablet, and mobile widths.
- Map and GIS layers render.
- Prediction flow returns score, confidence, explanation, and recommendations.
- Alert acknowledgement and report export contracts respond.
- Light and dark themes remain readable.

## Operations

- Database backups are scheduled.
- Health checks are configured.
- Worker and scheduler services are running.
- Logs are visible in the hosting provider.
- Vercel and Render deploy histories show the new release.
- Rollback plan is documented.
