#!/bin/bash
set -e

echo "Starting CodeMigration API Server..."

# Run migrations
echo "Running Alembic Migrations..."
alembic upgrade head

# Start Uvicorn
echo "Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
