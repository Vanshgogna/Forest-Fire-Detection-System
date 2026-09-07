# Backup and Recovery

## Database Backups

Recommended production schedule:

- Full PostgreSQL backup daily.
- Point-in-time recovery enabled by the managed database provider.
- Weekly restore test into a staging database.
- Retain daily backups for 14 days and monthly backups for one year.

Example backup command:

```bash
pg_dump "$DATABASE_URL" --format=custom --file=firesight-backup.dump
```

Example restore command:

```bash
pg_restore --clean --if-exists --dbname "$DATABASE_URL" firesight-backup.dump
```

## Configuration Recovery

- Keep `.env.example` versioned.
- Store production secrets only in the hosting provider secret manager.
- Export provider configuration before major releases.

## Incident Recovery

1. Confirm `/api/health` and `/api/readiness`.
2. Check API, worker, scheduler, database, and Redis logs.
3. Restore database if data integrity checks fail.
4. Re-run Alembic migrations.
5. Restart API and worker services.
6. Verify dashboard, predictions, GIS, alerts, and reports.
