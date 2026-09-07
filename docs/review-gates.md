# Review Gates

Every module must complete these reviews before it is marked complete in the roadmap or released.

## Architecture Review

- The module fits the existing route, service, repository, task, schema, or frontend boundary.
- Public contracts are documented and versioned when they affect users or integrations.
- Failure modes are explicit and recoverable.
- The implementation does not couple provider-specific code to core domain logic.
- ADRs are created for decisions that affect future architecture or operational posture.

## Code Review

- Code is readable, typed where the local stack supports it, and follows existing patterns.
- Tests cover the highest-risk behavior and any regression fixed by the change.
- Error messages are actionable and safe to expose.
- Unrelated refactors are avoided.
- New files are linked from the appropriate docs or package exports.

## Dependency Review

- New dependencies are justified by a clear capability need.
- Runtime dependencies are separated from dev/test-only dependencies.
- Licenses and maintenance posture are acceptable.
- Dependency versions are pinned where the project already pins them.
- Docker, CI, and local setup docs are updated when dependency installation changes.

## Performance Review

- Hot paths avoid unnecessary network, database, file-system, or render work.
- Large files are streamed rather than loaded fully into memory unless the format requires it.
- Cache and archive behavior is intentional.
- Batch operations define limits or pagination.
- Frontend changes preserve route lazy loading and avoid unnecessary re-renders.

## Security Review

- Auth and role requirements are correct for every endpoint.
- Secrets are not logged, committed, or returned in API responses.
- Inputs are validated through schemas or parser-backed validation.
- File paths, uploads, downloads, and external URLs are constrained.
- Error responses avoid leaking internals.

## Completion Sign-Off

| Review | Required Evidence |
| --- | --- |
| Architecture | ADR or note explaining why no ADR was needed |
| Code | Reviewer approval or self-review notes for solo work |
| Dependency | Dependency diff or confirmation that none changed |
| Performance | Test, measurement, or written risk assessment |
| Security | Security checklist result and any residual risks |

## Part 4C Review Result

| Review | Result |
| --- | --- |
| Architecture | Passed: governance artifacts are isolated to docs and do not alter runtime architecture |
| Code | Passed: documentation-only files use simple Markdown and existing documentation structure |
| Dependency | Passed: no dependencies added |
| Performance | Passed: no runtime path changed |
| Security | Passed: no secrets, permissions, or auth behavior changed |

## Part 4D Review Result

| Review | Result |
| --- | --- |
| Architecture | Passed: CI, deploy, and release workflows are isolated under `.github/workflows` and align with existing Vercel, Render, and Docker configuration |
| Code | Passed: workflow files and format checker are small, explicit, and source-controlled |
| Dependency | Passed: CI-only tools are installed in GitHub Actions and do not alter runtime dependencies |
| Performance | Passed: workflow jobs are split by concern and use dependency caches and Docker layer cache |
| Security | Passed: deployment credentials are referenced only through GitHub Secrets; CI includes dependency audits, Bandit, and Trivy |

## Part 4E Review Result

| Review | Result |
| --- | --- |
| Architecture | Passed: explainability is centralized in `backend/ml/explainability.py` and invoked from the prediction service before responses are returned |
| Code | Passed: prediction results preserve backward-compatible fields while adding structured explanation details |
| Dependency | Passed: no new runtime dependencies were added; future SHAP/LIME/PDP hooks are metadata-only |
| Performance | Passed: explanation generation uses lightweight deterministic calculations and chart-ready payloads |
| Security | Passed: explanations expose model reasoning and feature values without secrets, internal stack traces, or provider credentials |

## Part 4F Review Result

| Review | Result |
| --- | --- |
| Architecture | Passed: scalability plan defines replaceable module boundaries, dependency inversion points, async workers, storage strategy, microservice extraction order, and model registry extensibility |
| Code | Passed: model registry and async task additions are additive and keep prediction APIs stable |
| Dependency | Passed: no new runtime dependencies were added |
| Performance | Passed: registry metadata is in-memory and async contracts keep long-running work out of request paths |
| Security | Passed: multi-tenant and provider expansion guidance keeps credentials at adapter/config boundaries |

## Part 4G Review Result

| Review | Result |
| --- | --- |
| Architecture | Passed: observability is centralized in `backend/services/observability.py` and exposed through dedicated monitoring routes |
| Code | Passed: instrumentation is additive across middleware, cache, prediction, and raster planning paths |
| Dependency | Passed: no new runtime dependencies were added |
| Performance | Passed: metrics are bounded in-memory deques and lightweight summaries |
| Security | Passed: detailed metrics and dashboards are admin-only; public health endpoints avoid secrets |
