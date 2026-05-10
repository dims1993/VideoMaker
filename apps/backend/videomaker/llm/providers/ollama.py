"""Cliente mínimo para Ollama local."""

from __future__ import annotations

import os
from typing import Any

import requests


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def ollama_chat(*, system: str, user: str, model: str) -> str:
    """
    Requiere Ollama corriendo en local.

    Opcional:
    - OLLAMA_BASE_URL (por defecto http://localhost:11434)
    """
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{base}/api/chat"
    # Para guiones largos: evita que Ollama corte la respuesta demasiado pronto.
    # - VIDEOMAKER_OLLAMA_NUM_PREDICT: tokens máximos a generar (por defecto alto).
    # - VIDEOMAKER_OLLAMA_TEMPERATURE: opcional (default 0.7).
    num_predict = max(256, min(_env_int("VIDEOMAKER_OLLAMA_NUM_PREDICT", 12000), 50000))
    temperature = _env_float("VIDEOMAKER_OLLAMA_TEMPERATURE", 0.7)
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    r = requests.post(url, json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    msg = data.get("message") or {}
    return (msg.get("content") or "").strip()

