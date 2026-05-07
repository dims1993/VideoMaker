"""Cliente mínimo para Ollama local."""

from __future__ import annotations

import os
from typing import Any

import requests


def ollama_chat(*, system: str, user: str, model: str) -> str:
    """
    Requiere Ollama corriendo en local.

    Opcional:
    - OLLAMA_BASE_URL (por defecto http://localhost:11434)
    """
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{base}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.7},
    }
    r = requests.post(url, json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    msg = data.get("message") or {}
    return (msg.get("content") or "").strip()

