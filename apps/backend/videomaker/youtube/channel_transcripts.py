"""Obtención de transcripciones de vídeos de un canal guardado."""

from __future__ import annotations

import time
from typing import Any

from videomaker.youtube.channel_store import (
    get_channel,
    list_channel_videos_detail,
    list_channel_videos_detail_by_ids,
)
from videomaker.youtube.captions_data_api import oauth_configured, transcript_provider
from videomaker.youtube.transcript_client import create_youtube_transcript_api
from videomaker.youtube.transcript_fetch import (
    data_api_ready,
    fetch_delay_sec,
    fetch_video_transcript,
    is_ip_block_error,
    missing_oauth_message,
    provider_label,
    status_from_error,
)


def fetch_channel_transcripts_payload(
    channel_id: str,
    *,
    video_ids: list[str] | None = None,
    limit: int = 50,
    lang: str = "es",
) -> dict[str, Any]:
    """
    Devuelve { channel, count, videos } con transcripciones.

    Por defecto usa YouTube Data API v3 (captions.list/download + OAuth + quota).
    Fallback scrape solo si VIDEOMAKER_TRANSCRIPT_PROVIDER=scrape|auto.
    """
    ch = get_channel(channel_id)
    if not ch:
        raise ValueError("Canal no encontrado en el directorio.")

    mode = transcript_provider()
    if mode == "data_api" and not data_api_ready():
        raise RuntimeError(missing_oauth_message())

    want = [v.strip() for v in (video_ids or []) if v and v.strip()]
    if want:
        vids_raw = list_channel_videos_detail_by_ids(channel_id, video_ids=want)
        by_id = {v.get("video_id"): v for v in vids_raw}
        vids = [by_id[i] for i in want if i in by_id]
    else:
        vids = list_channel_videos_detail(channel_id, limit=max(1, min(int(limit), 200)))

    delay = fetch_delay_sec()
    out_videos: list[dict[str, Any]] = []
    ip_blocked_seen = False
    scrape_fallback_count = 0
    worker_fallback_count = 0
    data_api_forbidden_count = 0
    provider = provider_label()
    mode_fetch = transcript_provider()
    scrape_client = (
        create_youtube_transcript_api() if mode_fetch in ("scrape", "auto") else None
    )

    for i, v in enumerate(vids):
        if i > 0 and delay > 0:
            time.sleep(delay)
        vid = v.get("video_id") or ""
        if not vid:
            continue
        text, err, method = fetch_video_transcript(
            vid, lang=lang, scrape_client=scrape_client
        )
        if method == "worker" and text:
            worker_fallback_count += 1
        if method == "scrape" and text:
            scrape_fallback_count += 1
        if err and is_ip_block_error(err):
            ip_blocked_seen = True
        dur = v.get("duration_s")
        try:
            duration_s = int(dur) if dur is not None else None
        except (TypeError, ValueError):
            duration_s = None
        status = status_from_error(err, has_text=bool(text))
        if (
            not text
            and err
            and ("403" in err or "forbidden" in err.lower() or "captions.download" in err)
        ):
            if method != "scrape":
                data_api_forbidden_count += 1
            if status == "missing":
                status = "forbidden"
        out_videos.append(
            {
                "video_id": vid,
                "title": v.get("title") or "",
                "duration_s": duration_s,
                "transcript": text,
                "status": status,
                "error": err,
                "fetch_method": method if method != "none" else None,
            }
        )

    payload: dict[str, Any] = {
        "channel": ch,
        "count": len(out_videos),
        "videos": out_videos,
        "transcript_provider": provider,
        "transcript_provider_mode": mode_fetch,
    }
    if worker_fallback_count > 0:
        payload["worker_fallback_count"] = worker_fallback_count
    if scrape_fallback_count > 0:
        payload["scrape_fallback_count"] = scrape_fallback_count
    if data_api_forbidden_count > 0 and mode_fetch == "data_api":
        payload["data_api_forbidden_count"] = data_api_forbidden_count
        payload["data_api_forbidden_hint"] = (
            "YouTube Data API no permite descargar subtítulos de vídeos ajenos (403). "
            "Configura YOUTUBE_TRANSCRIPT_WORKER_URL (Cloudflare Worker) o VIDEOMAKER_TRANSCRIPT_PROVIDER=auto."
        )
    if mode == "data_api" and oauth_configured():
        payload["youtube_data_api"] = True
    if ip_blocked_seen and mode_fetch != "data_api":
        payload["youtube_ip_blocked"] = True
        payload["youtube_ip_blocked_hint"] = (
            "Modo scrape: YouTube bloqueó tu IP. Configura proxy (WEBSHARE_*) o reintenta más tarde."
        )
    return payload
