"""Cliente mínimo para Ollama local."""

from __future__ import annotations

import json
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


def _env_stream_enabled() -> bool:
    raw = (os.environ.get("VIDEOMAKER_OLLAMA_STREAM", "") or "").strip().lower()
    if not raw:
        return True
    return raw not in ("0", "false", "no", "off")


def _merge_stream_content(acc: str, chunk: str) -> str:
    """Ollama puede enviar deltas o el texto acumulado por chunk; soportamos ambos."""
    if not chunk:
        return acc
    if chunk.startswith(acc):
        return chunk
    return acc + chunk


def _ollama_chat_stream(
    *,
    url: str,
    payload: dict[str, Any],
    idle_between_chunks_sec: int,
) -> str:
    """
    `timeout` (connect, read) con stream=True: el read es tiempo máximo *entre* líneas NDJSON,
    no sobre toda la generación — evita ReadTimeout en guiones largos.
    """
    p = dict(payload)
    p["stream"] = True
    r = requests.post(url, json=p, stream=True, timeout=(30, idle_between_chunks_sec))
    try:
        r.raise_for_status()
        acc = ""
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            err = data.get("error")
            if err:
                raise RuntimeError(str(err))
            msg = data.get("message") or {}
            c = msg.get("content")
            if isinstance(c, str) and c:
                acc = _merge_stream_content(acc, c)
            if data.get("done"):
                break
        return acc.strip()
    finally:
        r.close()


def ollama_chat(
    *,
    system: str,
    user: str,
    model: str,
    response_json: bool = False,
    temperature: float | None = None,
) -> str:
    """
    Requiere Ollama corriendo en local.

    Opcional:
    - OLLAMA_BASE_URL (por defecto http://localhost:11434)
    - VIDEOMAKER_OLLAMA_STREAM: 1/true (default) usa NDJSON streaming; 0 desactiva.
    - VIDEOMAKER_OLLAMA_STREAM_IDLE_SEC: segundos sin recibir un chunk (default 900).
    - VIDEOMAKER_OLLAMA_TIMEOUT_SEC: solo modo sin stream — timeout de lectura (default 3600).
    """
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{base}/api/chat"
    # Para guiones largos: evita que Ollama corte la respuesta demasiado pronto.
    # - VIDEOMAKER_OLLAMA_NUM_PREDICT: tokens máximos a generar (por defecto alto).
    # - VIDEOMAKER_OLLAMA_TEMPERATURE: opcional (default 0.7).
    num_predict = max(256, min(_env_int("VIDEOMAKER_OLLAMA_NUM_PREDICT", 12000), 50000))
    temp = (
        float(temperature)
        if temperature is not None
        else _env_float("VIDEOMAKER_OLLAMA_TEMPERATURE", 0.7)
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temp, "num_predict": num_predict},
    }
    # Modo JSON nativo de Ollama: evita que el modelo siga escribiendo guion en lugar del objeto.
    if response_json:
        payload["format"] = "json"
    if _env_stream_enabled():
        idle = max(60, min(_env_int("VIDEOMAKER_OLLAMA_STREAM_IDLE_SEC", 900), 86400))
        return _ollama_chat_stream(url=url, payload=payload, idle_between_chunks_sec=idle)

    read_sec = max(60, min(_env_int("VIDEOMAKER_OLLAMA_TIMEOUT_SEC", 3600), 86400))
    p = dict(payload)
    p["stream"] = False
    r = requests.post(url, json=p, timeout=(30, read_sec))
    r.raise_for_status()
    data = r.json()
    msg = data.get("message") or {}
    return (msg.get("content") or "").strip()

