#!/bin/sh
# Aplica las migraciones antes de arrancar la API (una base nueva no tiene tablas).
set -e
alembic upgrade head
exec uvicorn app.infrastructure.entrypoints.api.main:app --host 0.0.0.0 --port 8000
