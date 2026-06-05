#!/usr/bin/env bash
# Libera puertos de desarrollo (Vite 5173, FastAPI 8000) si quedaron colgados.
set -euo pipefail

for port in 5173 8000; do
  pids=$(lsof -ti ":${port}" 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    echo "Matando procesos en :${port} → ${pids}"
    kill -9 ${pids} 2>/dev/null || true
  else
    echo "Puerto ${port} libre."
  fi
done

echo "Listo. Reinicia con: bash scripts/dev.sh"
