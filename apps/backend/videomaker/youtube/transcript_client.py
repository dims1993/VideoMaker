"""Cliente youtube-transcript-api con proxy opcional y manejo de bloqueos."""

from __future__ import annotations

import os
import time
from typing import Any

_YOUTUBE_BLOCK_MARKERS = ("IpBlocked", "RequestBlocked", "TooManyRequests")


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def create_youtube_transcript_api():
    """
    Crea YouTubeTranscriptApi leyendo proxy desde .env si está configurado.

    - WEBSHARE_PROXY_USERNAME + WEBSHARE_PROXY_PASSWORD → Webshare residential
    - YOUTUBE_TRANSCRIPT_PROXY_HTTP / YOUTUBE_TRANSCRIPT_PROXY_HTTPS → proxy genérico
    """
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

    proxy_config = _proxy_config_from_env()
    if proxy_config is not None:
        return YouTubeTranscriptApi(proxy_config=proxy_config)
    return YouTubeTranscriptApi()


def _proxy_config_from_env():
    ws_user = (os.environ.get("WEBSHARE_PROXY_USERNAME") or "").strip()
    ws_pass = (os.environ.get("WEBSHARE_PROXY_PASSWORD") or "").strip()
    if ws_user and ws_pass:
        from youtube_transcript_api.proxies import WebshareProxyConfig  # type: ignore

        locations_raw = (os.environ.get("WEBSHARE_FILTER_IP_LOCATIONS") or "").strip()
        locations = [x.strip() for x in locations_raw.split(",") if x.strip()] or None
        return WebshareProxyConfig(
            proxy_username=ws_user,
            proxy_password=ws_pass,
            filter_ip_locations=locations,
        )

    http_url = (os.environ.get("YOUTUBE_TRANSCRIPT_PROXY_HTTP") or "").strip()
    https_url = (os.environ.get("YOUTUBE_TRANSCRIPT_PROXY_HTTPS") or "").strip()
    if http_url or https_url:
        from youtube_transcript_api.proxies import GenericProxyConfig  # type: ignore

        return GenericProxyConfig(http_url=http_url or None, https_url=https_url or None)
    return None


def transcript_fetch_delay_sec() -> float:
    return max(0.0, _env_float("YOUTUBE_TRANSCRIPT_FETCH_DELAY_SEC", 0.35))


def is_youtube_ip_block_error(exc: BaseException | str | None) -> bool:
    if exc is None:
        return False
    if isinstance(exc, str):
        blob = exc
    else:
        blob = f"{type(exc).__name__}: {exc}"
    return any(m in blob for m in _YOUTUBE_BLOCK_MARKERS)


def shorten_transcript_error(err: str | None, *, max_len: int = 400) -> str | None:
    if not err:
        return None
    if is_youtube_ip_block_error(err):
        return (
            "YouTube bloqueó las peticiones desde tu IP (IpBlocked). "
            "Despliega el Cloudflare Worker (workers/youtube-transcript-proxy) y pon "
            "YOUTUBE_TRANSCRIPT_WORKER_URL en .env, o usa WEBSHARE_PROXY_* / YOUTUBE_TRANSCRIPT_PROXY_*."
        )
    s = err.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def transcript_status_from_error(err: str | None, *, has_text: bool) -> str:
    if has_text:
        return "ok"
    if err and is_youtube_ip_block_error(err):
        return "blocked"
    return "missing"


def _seg_text(seg: object) -> str:
    if isinstance(seg, dict):
        return str(seg.get("text") or "").strip()
    return str(getattr(seg, "text", "") or "").strip()


def fetch_video_transcript(
    ytt: Any,
    video_id: str,
    *,
    lang: str = "es",
) -> tuple[str, str | None]:
    """
    Devuelve (texto, error). Si hay texto, error es None.
    """
    lang_code = (lang or "es").strip().lower()
    langs = [lang_code]
    for x in ("es", "en"):
        if x not in langs:
            langs.append(x)

    err: str | None = None
    rows: list[Any] = []
    try:
        rows = list(ytt.fetch(video_id, languages=langs))
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        try:
            lst = ytt.list(video_id)
            picked = None
            try:
                picked = lst.find_transcript([lang_code])
            except Exception:
                picked = None
            if picked is None:
                try:
                    picked = lst.find_transcript(["es", "en"])
                except Exception:
                    picked = None
            if picked is None:
                try:
                    picked = next(iter(lst), None)
                except Exception:
                    picked = None
            if picked is not None:
                try:
                    rows = list(picked.fetch())
                    err = None
                except Exception as e2:
                    err = f"{err} | fetch failed: {type(e2).__name__}: {e2}"
        except Exception as e2:
            err = f"{err} | list failed: {type(e2).__name__}: {e2}"

    lines = [_seg_text(s) for s in (rows or [])]
    text = "\n".join(t for t in lines if t).strip()
    if text:
        return text, None
    return "", shorten_transcript_error(err)
