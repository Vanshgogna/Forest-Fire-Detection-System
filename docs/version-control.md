# Version Control

This project uses trunk-based development with short-lived branches, Semantic Versioning, conventional commits, and annotated release tags.

## Branch Strategy

| Branch | Purpose | Rules |
| --- | --- | --- |
| `main` | Production-ready source | Protected; merge only through reviewed pull requests |
| `develop` | Optional integration branch for multi-sprint work | Rebase or merge from `main` regularly |
| `feature/<scope>` | New features | Keep short-lived; squash or rebase before merge |
| `fix/<scope>` | Bug fixes | Include regression tests when practical |
| `docs/<scope>` | Documentation-only changes | May skip runtime tests if docs-only |
| `release/<version>` | Release stabilization | Only fixes, docs, version bump, changelog updates |
| `hotfix/<scope>` | Urgent production fix | Branch from `main`, tag patch release after merge |

## Commit Messages

Use conventional commit format:

```text
<type>(<scope>): <imperative summary>
```

Recommended types:

- `feat`: user-visible feature or new capability.
- `fix`: bug fix.
- `docs`: documentation-only change.
- `refactor`: code structure change without behavior change.
- `perf`: performance improvement.
- `test`: test additions or corrections.
- `build`: dependency, package, Docker, or CI change.
- `chore`: maintenance task.

Examples for recent work:

```text
feat(data): add refresh policies for scheduled ETL ingestion
fix(data): validate weather CSV rows without duplicate schema errors
docs(project): add roadmap, ADR, changelog, and review gates
test(data): cover raster integrity and incremental refresh planning
```

## Semantic Versioning

Use `MAJOR.MINOR.PATCH`:

- `MAJOR`: breaking API, data-contract, deployment, or migration changes.
- `MINOR`: backward-compatible features, new endpoints, new integrations, new pipeline stages.
- `PATCH`: backward-compatible fixes, documentation corrections, small performance improvements.

Pre-release labels:

- `0.2.0-alpha.1` for early integration snapshots.
- `0.2.0-beta.1` for feature-complete validation builds.
- `1.0.0-rc.1` for release candidates.

## Version Numbers

| Version | Meaning |
| --- | --- |
| `0.1.0` | Initial platform baseline |
| `0.2.0` | Data engineering and project governance baseline |
| `0.3.0` | Live data pilot |
| `0.8.0` | Production beta |
| `1.0.0` | Stable production release |

## Release Tags

Use annotated tags:

```bash
git tag -a v0.2.0 -m "Release v0.2.0: data pipeline baseline"
git push origin v0.2.0
```

Tag naming:

- `v0.1.0`: initial platform baseline.
- `v0.2.0`: data pipeline and governance baseline.
- `v0.3.0`: live data pilot.
- `v1.0.0`: stable production release.

## Release Workflow

1. Create `release/<version>`.
2. Confirm roadmap milestone exit criteria.
3. Update `CHANGELOG.md`.
4. Add or update ADRs for architectural decisions.
5. Run release checklist and CI.
6. Merge to `main`.
7. Create annotated tag.
8. Deploy and monitor.
9. Back-merge release fixes into `develop` if that branch is active.

## Suggested Commit For This Module

```text
docs(project): add project governance and release management
```
