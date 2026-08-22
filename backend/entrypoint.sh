#!/bin/bash
set -e

echo "Starting CodeMigration API Server..."

# Run migrations
echo "Running Alembic Migrations..."
alembic upgrade head

# Start Uvicorn
PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
echo "Starting Uvicorn on port $PORT with $WEB_CONCURRENCY worker(s)..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers "$WEB_CONCURRENCY" --proxy-headers --forwarded-allow-ips "*"
