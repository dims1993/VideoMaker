"""Transcripciones vía Cloudflare Worker (timedtext público, sin IP local)."""

from __future__ import annotations

import json
import os
from typing import Any

import requests


def worker_url_configured() -> bool:
    return bool((os.environ.get("YOUTUBE_TRANSCRIPT_WORKER_URL") or "").strip())


def worker_base_url() -> str:
    return (os.environ.get("YOUTUBE_TRANSCRIPT_WORKER_URL") or "").strip().rstrip("/")


def _worker_headers() -> dict[str, str]:
    secret = (os.environ.get("YOUTUBE_TRANSCRIPT_WORKER_SECRET") or "").strip()
    if not secret:
        return {}
    return {"Authorization": f"Bearer {secret}"}


def fetch_transcript_via_worker(video_id: str, *, lang: str = "es") -> tuple[str, str | None]:
    """
    Devuelve (texto, error). Llama al Worker desplegado en Cloudflare.
    """
    base = worker_base_url()
    if not base:
        return "", "Cloudflare Worker no configurado (YOUTUBE_TRANSCRIPT_WORKER_URL vacío)"

    vid = (video_id or "").strip()
    if not vid:
        return "", "video_id vacío"

    lang_code = (lang or "es").strip().lower() or "es"
    url = f"{base}/transcript"
    try:
        r = requests.get(
            url,
            params={"video_id": vid, "lang": lang_code},
            headers=_worker_headers(),
            timeout=45,
        )
    except requests.RequestException as e:
        return "", f"Worker no alcanzable: {type(e).__name__}: {e}"

    try:
        data: dict[str, Any] = r.json() if r.text else {}
    except json.JSONDecodeError:
        return "", f"Worker respondió sin JSON ({r.status_code}): {r.text[:200]}"

    if r.status_code == 200:
        text = str(data.get("text") or "").strip()
        if text:
            return text, None
        return "", "Worker devolvió texto vacío"

    err = str(data.get("error") or "worker_error").strip()
    msg = str(data.get("message") or r.text[:300]).strip()
    return "", f"{err}: {msg}" if msg else err
