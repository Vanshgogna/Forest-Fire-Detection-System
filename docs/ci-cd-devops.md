# CI/CD And DevOps

FireSight uses GitHub Actions for Continuous Integration, deployment automation, release automation, and deploy-blocking quality gates.

## Source Control

### Git Best Practices

- Keep `main` production-ready.
- Use short-lived branches: `feature/*`, `fix/*`, `docs/*`, `release/*`, and `hotfix/*`.
- Use conventional commits as described in [Version Control](version-control.md).
- Require pull requests for changes to protected branches.
- Keep generated artifacts, local datasets, virtual environments, caches, and secrets out of Git through `.gitignore`.
- Keep deployment configuration declarative through `.github/workflows/`, `render.yaml`, `vercel.json`, `Dockerfile.backend`, and `docker-compose.yml`.

### Branch Protection Recommendations

Protect `main` and any active `release/*` branch with:

- Require pull request before merging.
- Require at least one approval.
- Require conversation resolution.
- Require status checks:
  - `Frontend quality and build`
  - `Backend quality and tests`
  - `Docker build verification`
  - `Repository security scan`
  - `Quality gate`
- Require branches to be up to date before merge.
- Require signed commits when organization policy supports it.
- Restrict force pushes and deletions.
- Require CODEOWNERS review for security, infrastructure, and data-pipeline files when maintainers are assigned.

### Repository Structure

```text
.github/workflows/
  ci.yml             Continuous Integration quality gates
  deploy.yml         Vercel and Render deployment automation
  release.yml        Release artifacts, Docker publishing, GitHub releases
backend/             FastAPI, data, ML, GIS, tasks, schemas, database
frontend/            React, TypeScript, Vite dashboard
docs/                Architecture, governance, operations, CI/CD, ADRs
scripts/             Local deploy and healthcheck helpers
Dockerfile.backend   Backend, worker, and scheduler image
docker-compose.yml   Local multi-service stack
render.yaml          Render service blueprint
vercel.json          Vercel frontend configuration
```

## CI Pipeline

Workflow: `.github/workflows/ci.yml`.

CI runs on pull requests, pushes to protected/integration branches, release branches, and manual dispatch.

### Frontend Job

- Install dependencies with `npm ci`.
- Type check with `npm run typecheck`.
- Check formatting hygiene with `scripts/check-format.py`.
- Run smoke/unit tests with `npm test`.
- Verify production build with `npm run build`.
- Run dependency audit with `npm audit --audit-level=high`.
- Upload `frontend/dist` as a build artifact.

### Backend Job

- Start PostgreSQL and Redis service containers.
- Install backend dependencies.
- Install CI-only quality tools: Ruff, Bandit, and pip-audit.
- Lint with Ruff.
- Check formatting hygiene with `scripts/check-format.py`.
- Compile backend modules.
- Run unit and integration tests with Pytest.
- Audit Python dependencies with pip-audit.
- Run backend security scan with Bandit.

### Docker Job

- Build `Dockerfile.backend` using Docker Buildx.
- Fail the pipeline if the backend image cannot be built.

### Security Job

- Run Trivy filesystem scan.
- Fail on unfixed high or critical vulnerabilities.
- Upload SARIF output to GitHub code scanning.

### Quality Gate

The final `quality-gate` job depends on frontend, backend, Docker, and security jobs. Deployment automation should treat this as the required CI status.

## CD Pipeline

Workflow: `.github/workflows/deploy.yml`.

CD runs only when CI completes successfully, or when a maintainer starts a manual deployment.

### Vercel

The frontend deploy job:

- Installs dependencies.
- Pulls Vercel project configuration.
- Builds with Vercel CLI.
- Deploys preview environments for development/testing.
- Deploys production when the selected environment is `production` or the CI source branch is `main`.

Required secrets:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

### Render

The backend deploy job triggers Render deploys through the Render API.

Required secrets:

- `RENDER_API_KEY`
- `RENDER_SERVICE_ID`

Optional secrets:

- `RENDER_WORKER_SERVICE_ID`
- `RENDER_SCHEDULER_SERVICE_ID`

### Docker

Docker support is provided by:

- `Dockerfile.backend` for API, worker, and scheduler runtime.
- `docker-compose.yml` for local development and test stacks.
- Release workflow publishing to GitHub Container Registry.

### Future Cloud Platforms

Future deployments can reuse the same build artifacts and quality gates for:

- AWS ECS or App Runner.
- Google Cloud Run.
- Azure Container Apps.
- Kubernetes with Helm.
- Terraform or Pulumi-managed infrastructure.

## Release Workflow

Workflow: `.github/workflows/release.yml`.

Release automation runs on `v*.*.*` tags or manual dispatch.

The release workflow:

- Validates Semantic Versioning tag format.
- Requires a matching `CHANGELOG.md` entry.
- Builds and tests frontend and backend.
- Creates a source archive.
- Builds and pushes a backend Docker image to GitHub Container Registry.
- Publishes a GitHub release with generated release notes.

## Quality Gates

Deployment fails when any of these fail:

- Dependency installation.
- Type checking.
- Linting.
- Formatting check.
- Unit tests.
- Integration tests.
- Frontend build.
- Backend compile.
- Docker build.
- Security scan.
- Dependency audit.

## Deployment Strategy

### Development

- Branches: `feature/*`, `fix/*`, `docs/*`.
- Deployment: Vercel preview and optional Render preview service.
- Data: mock or isolated test data.
- Goal: rapid feedback without affecting shared testing or production services.

### Testing

- Branches: `develop` or `release/*`.
- Deployment: shared testing environment through manual deploy or CI-gated deploy.
- Data: representative non-production datasets.
- Goal: integration testing with PostgreSQL, Redis, workers, and scheduler enabled.

### Production

- Branch: `main`.
- Deployment: CI-gated Vercel production deploy and Render production deploy.
- Data: managed PostgreSQL, managed Redis, external object storage, provider secrets.
- Goal: stable operator-facing deployment with health checks and rollback plan.

## Rollback Strategy

Frontend rollback:

- Use Vercel deployment history to promote the previous healthy deployment.
- Re-run the deploy workflow with a known good commit when needed.

Backend rollback:

- Use Render deploy history to roll back to the previous successful deploy.
- Keep release tags immutable so backend Docker images can be redeployed by tag.
- Run database migrations with backward compatibility in mind.
- Prefer expand-and-contract migrations for production schema changes.

Data rollback:

- Preserve archived ETL outputs and dataset version manifests.
- Repoint model compatibility metadata to the last verified dataset/model pair.

## Blue/Green Deployment

Blue/green is a future production-hardening phase:

- Maintain two Render service groups or cloud service revisions.
- Deploy new version to the inactive environment.
- Run smoke tests against the inactive environment.
- Switch traffic through DNS, load balancer, or platform routing.
- Keep the old environment warm until post-deploy monitoring passes.

## Required Repository Secrets

| Secret | Purpose |
| --- | --- |
| `VERCEL_TOKEN` | Vercel deployments |
| `VERCEL_ORG_ID` | Vercel project linkage |
| `VERCEL_PROJECT_ID` | Vercel project linkage |
| `RENDER_API_KEY` | Render deploy trigger |
| `RENDER_SERVICE_ID` | Render API service deploy |
| `RENDER_WORKER_SERVICE_ID` | Optional Render worker deploy |
| `RENDER_SCHEDULER_SERVICE_ID` | Optional Render scheduler deploy |
| `PUBLIC_API_BASE_URL` | Optional post-deploy healthcheck |
