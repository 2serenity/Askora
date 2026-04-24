#!/usr/bin/env sh
set -e

echo "Waiting for PostgreSQL..."
python -c "import time; from sqlalchemy import create_engine; from app.core.config import settings; engine=create_engine(settings.database_url); attempts=0
while True:
    try:
        with engine.connect() as conn:
            conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        break
    except Exception:
        attempts += 1
        if attempts > 30:
            raise
        time.sleep(2)"

echo "Running migrations..."
alembic upgrade head

echo "Seeding demo data if needed..."
python -m app.seed.seed_demo

echo "Starting API..."
uvicorn app.main:app --host 0.0.0.0 --port 8000

