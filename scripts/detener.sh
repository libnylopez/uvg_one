#!/bin/sh
# Detiene UVG ONE en modo local (los datos se conservan).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pkill -f "uvicorn app.infrastructure.entrypoints.api.main:app --host 127.0.0.1 --port 8010" && echo "Backend detenido"
pkill -f "vite --host 127.0.0.1 --port 5180" && echo "Frontend detenido"
cd "$ROOT" && docker compose stop postgres >/dev/null && echo "Postgres detenido"
