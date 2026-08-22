#!/bin/bash
set -e

echo "Starting CodeMigration API Server..."

# Run migrations
echo "Running Alembic Migrations..."
alembic upgrade head

# Start Uvicorn
PORT="${PORT:-8000}"
echo "Starting Uvicorn on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 4
