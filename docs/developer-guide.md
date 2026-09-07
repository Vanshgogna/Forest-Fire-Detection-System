# Developer Guide

## Local Setup

1. Copy `.env.example` to `.env`.
2. Install frontend dependencies with `npm install`.
3. Install backend dependencies with `pip install -r backend/requirements.txt`.
4. Start the frontend with `npm run dev`.
5. Start the backend with `npm run backend`.

For the complete stack, use:

```bash
docker compose up --build
```

## Quality Gates

```bash
npm run typecheck
npm run build
python3 -m pytest
python3 -m py_compile backend/main.py
```

## Architecture Rules

- Keep FastAPI routes thin; place domain behavior in `backend/services`.
- Use `backend/repositories` for database access.
- Use Pydantic schemas for request and response validation.
- Keep frontend API calls in `frontend/src/services`.
- Prefer reusable UI components under `frontend/src/components/common`.
- Add tests for new API contracts and risk-calculation behavior.

## Release Checklist

- No hardcoded production secrets.
- `.env.example` is current.
- Frontend typecheck and build pass.
- Backend tests pass.
- Docker stack starts successfully.
- `/api/health`, `/api/readiness`, and `/docs` respond.
