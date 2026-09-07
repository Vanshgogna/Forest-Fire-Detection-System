# Folder Structure

```text
.
├── .github/
│   └── workflows/            CI, deployment, and release workflows
├── backend/
│   ├── alembic/              Database migrations
│   ├── core/                 Configuration, security, logging, errors
│   ├── data/                 Data ingestion, validation, quality, versioning, ETL
│   ├── database/             SQLAlchemy engine, session, models
│   ├── middleware/           Rate limiting and security headers
│   ├── ml/                   Feature engineering and model pipeline
│   ├── repositories/         Database access layer
│   ├── routes/               FastAPI route modules
│   ├── schemas/              Pydantic request/response models
│   ├── services/             Domain services and processing logic
│   └── tasks/                Celery app and background jobs
├── docs/                     Architecture, ADRs, setup, operations, CI/CD, XAI, scalability, monitoring, QA, deployment
├── frontend/
│   ├── src/
│   │   ├── components/       Reusable UI and domain widgets
│   │   ├── constants/        Mock environmental data
│   │   ├── contexts/         Theme and environmental state
│   │   ├── hooks/            Data loading hooks
│   │   ├── layouts/          Dashboard shell
│   │   ├── pages/            Routed product pages
│   │   ├── services/         API client
│   │   ├── styles/           Global styling
│   │   ├── types/            Frontend TypeScript types
│   │   └── utils/            Shared helpers
│   └── tests/                Frontend page smoke tests
├── scripts/                  Deployment and healthcheck scripts
├── tests/                    Backend, API, ML, GIS, config, performance tests
├── Dockerfile.backend        Backend container image
├── CHANGELOG.md              Release history and implementation notes
├── docker-compose.yml        Local multi-service stack
├── render.yaml               Render backend deployment blueprint
├── vercel.json               Vercel frontend deployment config
└── .env.example              Environment variable template
```

Generated or local-only folders such as `.venv`, `.test-venv`, `.pytest_cache`, `frontend/dist`, `node_modules`, `datasets/raw`, `datasets/processed`, `datasets/versions`, and `backend/artifacts` should not be committed.
