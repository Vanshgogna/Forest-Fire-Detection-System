# ADR-0001: Maintain Project Governance As Versioned Repository Artifacts

## Status

Accepted

## Date

2026-08-24

## Context

FireSight has grown into a multi-module platform covering frontend UX, FastAPI services, GIS, remote sensing, ML contracts, ETL, deployment, and operations. The project needs durable project-management records that survive handoff and do not live only in chat, issue trackers, or personal notes.

## Decision

Maintain project governance as versioned repository artifacts:

- Roadmap, milestones, sprint plan, dependency graph, and module status in `docs/project-management.md`.
- Changelog in root `CHANGELOG.md`.
- Branch strategy, commit-message conventions, release tags, and Semantic Versioning policy in `docs/version-control.md`.
- Review criteria in `docs/review-gates.md`.
- Architecture decisions in `docs/adr/`.

## Alternatives Considered

- Use only GitHub Issues and Projects: good for execution tracking, but not always available offline and weaker for architectural handoff.
- Use only README sections: easy to find, but the README would become too large and harder to maintain.
- Use a separate project-management tool: useful for day-to-day planning, but creates an external dependency and can drift from the codebase.

## Tradeoffs

- Versioned Markdown is simple, reviewable, and portable.
- The team must keep docs updated as part of the definition of done.
- Detailed day-to-day task ownership may still belong in an issue tracker.
- ADRs add a small writing cost but reduce future uncertainty about why decisions were made.

## Reasoning

FireSight has several delayed integration points: live provider credentials, object storage, production databases, and observability. Keeping governance in the repository makes current status, blocked modules, and future work explicit for any engineer or stakeholder opening the project.

## Future Impact

- Releases must update `CHANGELOG.md` and roadmap status.
- Major architectural changes should add a new ADR.
- Pull requests should reference the review gates before merging.
- External project boards can mirror these docs, but the repository remains the canonical technical record.
