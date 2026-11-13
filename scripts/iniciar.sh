#!/bin/sh
# Levanta UVG ONE en modo local: Postgres en Docker + backend (Python) + frontend (Vite).
# Uso: ./scripts/iniciar.sh             (Claude real)
#      ./scripts/iniciar.sh --simulado  (sin API: respuestas locales marcadas como SIMULACIÓN)
# Detener: ./scripts/detener.sh
# Logs: .logs/backend.log y .logs/frontend.log
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/.logs"
cd "$ROOT"

if [ ! -f .env ]; then echo "Falta .env (cp .env.example .env)"; exit 1; fi
if [ ! -x backend/.venv/bin/uvicorn ]; then echo "Falta backend/.venv (ver README, Desarrollo local)"; exit 1; fi
if [ ! -d frontend/node_modules ]; then (cd frontend && npm install --no-audit --no-fund); fi

echo "1/3 Postgres (Docker)…"
docker compose up -d postgres >/dev/null
until docker compose exec -T postgres pg_isready -q >/dev/null 2>&1; do sleep 1; done

if [ "$1" = "--simulado" ]; then
  export ANTHROPIC_MODE=simulado
  echo "   MODO SIMULACIÓN: no se llamará a la API de Anthropic."
fi
echo "2/3 Backend → http://localhost:8010 (indexando documentos_uvg/ si hay cambios)…"
nohup ./scripts/backend_local.sh > .logs/backend.log 2>&1 &
i=0; until curl -sf http://127.0.0.1:8010/health >/dev/null; do
  i=$((i+1)); sleep 2
  if ! pgrep -f "uvicorn app.infrastructure.entrypoints.api.main:app" >/dev/null; then
    echo "El backend se detuvo. Revisa .logs/backend.log"; tail -20 .logs/backend.log; exit 1
  fi
  [ $i -gt 150 ] && { echo "El backend tarda demasiado. Revisa .logs/backend.log"; exit 1; }
done

echo "3/3 Frontend → http://localhost:5180 …"
(cd frontend && VITE_API_BASE_URL=http://localhost:8010 nohup npx vite --host 127.0.0.1 --port 5180 --strictPort > ../.logs/frontend.log 2>&1 &)
until curl -sf http://127.0.0.1:5180 >/dev/null; do sleep 1; done

curl -s http://127.0.0.1:8010/health; echo
echo "UVG ONE listo: abre http://localhost:5180"
