"""Punto único para obtener transcripciones de vídeos (Data API, Worker CF, scrape)."""

from __future__ import annotations

import os
from typing import Any

from videomaker.youtube.captions_data_api import (
    fetch_transcript_data_api,
    oauth_configured,
    transcript_provider,
)
from videomaker.youtube.transcript_client import (
    create_youtube_transcript_api,
    fetch_video_transcript as fetch_video_transcript_scrape,
    is_youtube_ip_block_error,
    shorten_transcript_error,
    transcript_fetch_delay_sec,
    transcript_status_from_error,
)
from videomaker.youtube.worker_transcript import (
    fetch_transcript_via_worker,
    worker_url_configured,
)

__all__ = [
    "fetch_delay_sec",
    "fetch_video_transcript",
    "is_ip_block_error",
    "provider_label",
    "shorten_error",
    "status_from_error",
    "transcript_provider",
    "worker_url_configured",
]


def fetch_delay_sec() -> float:
    return transcript_fetch_delay_sec()


def is_ip_block_error(exc: BaseException | str | None) -> bool:
    return is_youtube_ip_block_error(exc)


def shorten_error(err: str | None, *, max_len: int = 400) -> str | None:
    return shorten_transcript_error(err, max_len=max_len)


def status_from_error(err: str | None, *, has_text: bool) -> str:
    return transcript_status_from_error(err, has_text=has_text)


def provider_label() -> str:
    p = transcript_provider()
    if p == "data_api":
        return "YouTube Data API v3 (captions, solo vídeos propios)"
    if p == "scrape":
        return "youtube-transcript-api (scrape directo)"
    if p == "worker":
        return "Cloudflare Worker → timedtext público"
    if worker_url_configured():
        return "auto: Data API → Worker CF → scrape"
    return "auto: Data API → scrape (sin Worker configurado)"


def _should_fallback_to_worker(err: str | None) -> bool:
    if not worker_url_configured():
        return False
    if not err:
        return True
    if is_youtube_ip_block_error(err):
        return True
    markers = (
        "oauth_missing",
        "403",
        "forbidden",
        "captions.download",
        "Sin pistas",
        "quota",
        "Quota",
        "no_captions",
    )
    return any(m.lower() in err.lower() for m in markers)


def _should_fallback_to_scrape(err: str | None) -> bool:
    if not err:
        return False
    if is_youtube_ip_block_error(err):
        return True
    markers = (
        "oauth_missing",
        "403",
        "forbidden",
        "Sin pistas",
        "quota",
        "Quota",
        "worker",
        "Worker",
        "no_captions",
        "timedtext",
        "watch_failed",
    )
    return any(m in err for m in markers)


def _try_worker(video_id: str, *, lang: str) -> tuple[str, str | None, str]:
    text, err = fetch_transcript_via_worker(video_id, lang=lang)
    if text:
        return text, None, "worker"
    return "", err, "none"


def _try_scrape(
    video_id: str,
    *,
    lang: str,
    scrape_client: Any | None,
) -> tuple[str, str | None, str]:
    ytt = scrape_client or create_youtube_transcript_api()
    text, err = fetch_video_transcript_scrape(ytt, video_id, lang=lang)
    if text:
        return text, None, "scrape"
    return "", err, "none"


def fetch_video_transcript(
    video_id: str,
    *,
    lang: str = "es",
    scrape_client: Any | None = None,
) -> tuple[str, str | None, str]:
    """
    Devuelve (texto, error, método_usado).
    método_usado: data_api | worker | scrape | none
    """
    mode = transcript_provider()

    if mode == "worker":
        return _try_worker(video_id, lang=lang)

    if mode == "scrape":
        return _try_scrape(video_id, lang=lang, scrape_client=scrape_client)

    if mode in ("data_api", "youtube_data_api", "api"):
        text, err = fetch_transcript_data_api(video_id, lang=lang)
        if text:
            return text, None, "data_api"
        return "", err, "none"

    if mode == "auto":
        text, err = fetch_transcript_data_api(video_id, lang=lang)
        if text:
            return text, None, "data_api"
        if err and _should_fallback_to_worker(err):
            text_w, err_w, method = _try_worker(video_id, lang=lang)
            if text_w:
                return text_w, None, method
            err = err_w or err
        if err and _should_fallback_to_scrape(err):
            text_s, err_s, method = _try_scrape(
                video_id, lang=lang, scrape_client=scrape_client
            )
            if text_s:
                return text_s, None, method
            return "", err_s, "none"
        return "", err, "none"

    return "", f"VIDEOMAKER_TRANSCRIPT_PROVIDER no válido: {mode}", "none"


def data_api_ready() -> bool:
    return oauth_configured()


def missing_oauth_message() -> str:
    return (
        "Tienes YOUTUBE_API_KEY (metadatos), pero los subtítulos requieren OAuth aparte — "
        "Google no acepta solo API key en captions.list/download. "
        "Añade YOUTUBE_OAUTH_CLIENT_ID, YOUTUBE_OAUTH_CLIENT_SECRET y "
        "YOUTUBE_OAUTH_REFRESH_TOKEN; luego: python youtube_oauth_setup.py. "
        "Para canales ajenos sin 403, configura YOUTUBE_TRANSCRIPT_WORKER_URL (Cloudflare Worker)."
    )
