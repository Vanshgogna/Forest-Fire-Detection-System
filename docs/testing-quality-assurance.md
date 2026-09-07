# Testing and Quality Assurance

## Automated Backend Coverage

Run:

```bash
.test-venv/bin/python -m pytest
```

The backend suite covers:

- API health and readiness contracts
- Public dashboard, weather, vegetation, hotspot, prediction, GIS, alert, analytics, report, and settings endpoints
- Authentication success and failure
- Role-based authorization failures and allowed access
- Weather validation and Fire Weather Index behavior
- Prediction single and batch contracts
- ML preprocessing, prediction, batch prediction, and training-plan contracts
- Remote-sensing scene validation, cache manifests, heatmap output, cleanup safety, and NDVI/NBR shared formulas

## Frontend Verification

Run:

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm run build
```

The frontend checks verify:

- All React pages compile
- All React pages render through shared providers in automated smoke tests
- Lazy-loaded route modules are importable
- TypeScript types are valid
- Production bundle generation succeeds
- Map, chart, motion, and page chunks are split for deployment

## Validation and Failure Testing

Current automated failure tests include:

- Invalid weather humidity returns `422`
- Invalid vegetation reflectance returns `422`
- Invalid satellite source returns `422`
- Viewer role is rejected from admin, user-management, notification, and model-training operations
- Unsupported remote-sensing scenes are blocked before download
- Unsafe scene IDs are sanitized before cleanup paths are generated

## Local Test Environment

The repository includes a Python 3.14 `.venv`, but several pinned backend packages are more reliable on Python 3.9-3.12. For local QA on this machine, `.test-venv` was created with macOS Python 3.9 and is ignored by Git.

Production containers use Python 3.12 through `Dockerfile.backend`.
