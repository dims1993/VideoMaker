"""Cliente mínimo para APIs compatibles con OpenAI (chat completions)."""

from __future__ import annotations

import os
from typing import Any

import requests


def openai_compat_chat(
    *,
    system: str,
    user: str,
    model: str,
    response_json: bool = False,
    temperature: float | None = None,
) -> str:
    """
    Requiere:
    - OPENAI_API_KEY
    Opcional:
    - OPENAI_BASE_URL (por defecto https://api.openai.com/v1)
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Falta OPENAI_API_KEY. Ponla en .env o configura VIDEOMAKER_LLM_PROVIDER=ollama."
        )
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7 if temperature is None else float(temperature),
    }
    if response_json:
        payload["response_format"] = {"type": "json_object"}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Respuesta vacía del proveedor OpenAI-compatible.")
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()

