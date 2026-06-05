#!/usr/bin/env bash
# Desarrollo recomendado: FastAPI (:8000) + Vite (:5173). Abre http://localhost:5173
set -euo pipefail

# Optional: run Redis + Celery for channel sync/cache.
# You can start Redis separately (e.g. `brew services start redis`) and set REDIS_URL.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Puertos colgados (reload de uvicorn + tormenta de fetch) impiden reiniciar
if lsof -ti :8000 >/dev/null 2>&1 || lsof -ti :5173 >/dev/null 2>&1; then
  echo "==> Liberando puertos 8000 / 5173 si estaban ocupados…"
  bash "$ROOT/scripts/dev-kill.sh"
fi

# Exporta .env del repo (evita ANTHROPIC_API_KEY="" en el shell que bloquea python-dotenv)
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ ! -d .venv ]]; then
  echo "No hay .venv. Crea el entorno con:"
  echo "  bash scripts/setup_venv.sh"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Falta npm (Node.js). En Mac:  brew install node"
  exit 1
fi

if [[ ! -d apps/frontend/node_modules ]]; then
  echo "==> Instalando dependencias npm en apps/frontend/ …"
  (cd apps/frontend && npm install)
fi

UV_PID=""
FE_PID=""
cleanup() {
  if [[ -n "${UV_PID}" ]]; then
    kill "${UV_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FE_PID}" ]]; then
    kill "${FE_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo ""
echo "  FastAPI  →  http://127.0.0.1:8000   (API + /docs)"
echo "  React UI →  http://localhost:5173  (interfaz; proxy → 8000)"
echo ""
echo "  Ctrl+C para detener ambos procesos."
echo ""

.venv/bin/python -m uvicorn --app-dir "$ROOT/apps/backend" videomaker.web.app:app \
  --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 3 &
UV_PID=$!

(cd apps/frontend && npm run dev) &
FE_PID=$!

wait "${UV_PID}" "${FE_PID}" || true
