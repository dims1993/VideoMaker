#!/usr/bin/env bash
# Proxy de subtítulos (sin Cloudflare). Misma API que el Worker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/workers/youtube-transcript-proxy"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/.env"
  set +a
fi

export TRANSCRIPT_PROXY_SECRET="${YOUTUBE_TRANSCRIPT_WORKER_SECRET:-${TRANSCRIPT_PROXY_SECRET:-}}"
export TRANSCRIPT_PROXY_PORT="${TRANSCRIPT_PROXY_PORT:-8787}"
export TRANSCRIPT_PROXY_HOST="${TRANSCRIPT_PROXY_HOST:-127.0.0.1}"

echo "Proxy: http://${TRANSCRIPT_PROXY_HOST}:${TRANSCRIPT_PROXY_PORT}"
echo "Prueba: curl \"http://127.0.0.1:${TRANSCRIPT_PROXY_PORT}/health\""
exec python3 proxy_server.py
