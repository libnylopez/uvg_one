#!/bin/sh
# Ejecuta el backend de UVG ONE fuera de Docker (desarrollo). Requiere:
#   - backend/.venv creado (ver README) y el contenedor de Postgres levantado:
#       docker compose up -d postgres
# Uso: ./scripts/backend_local.sh            → API en http://localhost:8010
#      ./scripts/backend_local.sh migrate    → solo aplica migraciones
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a; . "$ROOT/.env"; set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5442/${POSTGRES_DB}"
export CHROMA_PERSIST_DIR="$ROOT/backend/data/chroma"
export DOCUMENTS_DIR="$ROOT/documentos_uvg"
export CORS_ORIGINS="http://localhost:5180,http://127.0.0.1:5180"
cd "$ROOT/backend"
.venv/bin/alembic upgrade head
[ "$1" = "migrate" ] && exit 0
exec .venv/bin/uvicorn app.infrastructure.entrypoints.api.main:app --host 127.0.0.1 --port 8010 --app-dir src
