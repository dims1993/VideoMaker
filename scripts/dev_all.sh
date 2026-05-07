#!/usr/bin/env bash
# Levanta docker (Redis+Celery) y luego la app (FastAPI+Vite).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Falta docker. Instala Docker Desktop."
  exit 1
fi

echo "==> Levantando servicios docker (redis + celery-worker)…"
docker compose up -d

echo "==> Lanzando app (scripts/dev.sh)…"
bash scripts/dev.sh

