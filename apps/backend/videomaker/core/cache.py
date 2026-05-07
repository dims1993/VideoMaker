"""Cache simple con Redis (opcional).

Se usa para reducir cuota de YouTube Data API cacheando resultados 24h.
Si REDIS_URL no está configurado o Redis no está disponible, se comporta como cache vacía.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any


def _redis_url() -> str | None:
    u = os.environ.get("REDIS_URL", "").strip()
    return u or None


def _client():
    url = _redis_url()
    if not url:
        return None
    try:
        import redis

        return redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None


def get_json(key: str) -> Any | None:
    r = _client()
    if not r:
        return None
    try:
        v = r.get(key)
        if not v:
            return None
        return json.loads(v)
    except Exception:
        return None


def set_json(key: str, value: Any, *, ttl_s: int) -> None:
    r = _client()
    if not r:
        return
    try:
        r.setex(key, int(ttl_s), json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


def cache_key(*parts: str) -> str:
    safe = [p.replace(" ", "_") for p in parts if p]
    return "videomaker:" + ":".join(safe)

