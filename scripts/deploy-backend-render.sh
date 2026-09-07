#!/usr/bin/env sh

set -eu

echo "Current directory:"
pwd

echo "Checking Alembic configuration:"
ls -la /app
ls -la /app/alembic.ini

attempt=1
max_attempts="${MIGRATION_MAX_ATTEMPTS:-5}"
delay_seconds="${MIGRATION_RETRY_DELAY_SECONDS:-2}"

until python -m alembic -c /app/alembic.ini upgrade head; do

  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "Database migration failed after ${attempt} attempts." >&2
    exit 1
  fi

  echo "Database migration attempt ${attempt} failed; retrying in ${delay_seconds}s..." >&2

  attempt=$((attempt + 1))

  sleep "$delay_seconds"

done

echo "Database migrations completed successfully."

exec uvicorn backend.main:app \
    --host "${BACKEND_HOST:-0.0.0.0}" \
    --port "${PORT:-8000}"