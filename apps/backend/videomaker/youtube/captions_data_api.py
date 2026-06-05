"""
Transcripciones vía YouTube Data API v3 (captions.list + captions.download).

Requiere OAuth 2.0 (refresh token), no basta con YOUTUBE_API_KEY sola.
Quota oficial (~50 unidades por list + ~50 por download por vídeo).
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from videomaker.web.transcript_files import parse_subtitle_text

_TOKEN_CACHE: dict[str, Any] = {"access_token": "", "expires_at": 0.0}
_YT_API = "https://www.googleapis.com/youtube/v3"


class YouTubeCaptionsError(RuntimeError):
    """Error recuperable o de configuración al usar Data API captions."""

    def __init__(self, message: str, *, code: str = "error", http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def transcript_provider() -> str:
    """auto (default) | data_api | scrape | worker — auto: Data API → Worker → scrape"""
    raw = (os.environ.get("VIDEOMAKER_TRANSCRIPT_PROVIDER") or "auto").strip().lower()
    if raw in ("youtube_data_api", "api", "data-api"):
        return "data_api"
    if raw in ("data_api", "scrape", "auto", "worker"):
        return raw
    return "auto"


def oauth_configured() -> bool:
    return bool(_oauth_refresh_token() and _oauth_client_id() and _oauth_client_secret())


def _oauth_client_id() -> str:
    return (os.environ.get("YOUTUBE_OAUTH_CLIENT_ID") or "").strip()


def _oauth_client_secret() -> str:
    return (os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip()


def _oauth_refresh_token() -> str:
    return (os.environ.get("YOUTUBE_OAUTH_REFRESH_TOKEN") or "").strip()


def _access_token() -> str:
    if not oauth_configured():
        raise YouTubeCaptionsError(
            "Faltan credenciales OAuth para subtítulos. YOUTUBE_API_KEY no sustituye "
            "a OAuth en captions.list/download (requisito de Google). "
            "Configura YOUTUBE_OAUTH_CLIENT_ID, YOUTUBE_OAUTH_CLIENT_SECRET y "
            "YOUTUBE_OAUTH_REFRESH_TOKEN en .env. "
            "Genera el refresh token: python youtube_oauth_setup.py",
            code="oauth_missing",
        )
    now = time.time()
    cached = str(_TOKEN_CACHE.get("access_token") or "")
    expires = float(_TOKEN_CACHE.get("expires_at") or 0)
    if cached and now < expires - 30:
        return cached

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": _oauth_client_id(),
            "client_secret": _oauth_client_secret(),
            "refresh_token": _oauth_refresh_token(),
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if r.status_code >= 400:
        raise YouTubeCaptionsError(
            f"No se pudo renovar el token OAuth ({r.status_code}): {r.text[:300]}",
            code="oauth_refresh_failed",
            http_status=r.status_code,
        )
    data = r.json() or {}
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise YouTubeCaptionsError("Respuesta OAuth sin access_token.", code="oauth_refresh_failed")
    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"] = now + float(data.get("expires_in") or 3600)
    return token


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_access_token()}"}


def _lang_prefs(lang: str) -> list[str]:
    code = (lang or "es").strip().lower()
    prefs = [code]
    for x in ("es", "en"):
        if x not in prefs:
            prefs.append(x)
    return prefs


def list_caption_tracks(video_id: str) -> list[dict[str, Any]]:
    """captions.list — requiere OAuth."""
    params = {"part": "snippet", "videoId": video_id}
    r = requests.get(
        f"{_YT_API}/captions",
        params=params,
        headers=_auth_headers(),
        timeout=30,
    )
    if r.status_code == 403:
        raise YouTubeCaptionsError(
            "YouTube rechazó captions.list (403). Comprueba OAuth y que la cuenta tenga "
            "acceso al vídeo. En canales ajenos Google a veces no permite descarga oficial.",
            code="forbidden",
            http_status=403,
        )
    if r.status_code == 404:
        return []
    if r.status_code >= 400:
        raise YouTubeCaptionsError(
            f"captions.list falló ({r.status_code}): {r.text[:400]}",
            code="api_error",
            http_status=r.status_code,
        )
    data = r.json() or {}
    items = data.get("items") or []
    return [it for it in items if isinstance(it, dict)]


def _pick_track(items: list[dict[str, Any]], lang_prefs: list[str]) -> dict[str, Any] | None:
    if not items:
        return None

    def score(item: dict[str, Any]) -> tuple[int, int]:
        sn = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        lang = str(sn.get("language") or "").lower()
        kind = str(sn.get("trackKind") or "")
        lang_rank = len(lang_prefs)
        for i, pref in enumerate(lang_prefs):
            if lang == pref or lang.startswith(pref):
                lang_rank = i
                break
        # ASR (auto) suele ser lo disponible en vídeos públicos
        kind_penalty = 0 if kind in ("standard", "ASR", "forced") else 5
        return (lang_rank, kind_penalty)

    return min(items, key=score)


def download_caption_track(caption_id: str, *, tfmt: str = "srt") -> str:
    """captions.download — devuelve cuerpo SRT/VTT como texto."""
    r = requests.get(
        f"{_YT_API}/captions/{caption_id}",
        params={"tfmt": tfmt},
        headers=_auth_headers(),
        timeout=60,
    )
    if r.status_code == 403:
        raise YouTubeCaptionsError(
            "captions.download 403: Google solo permite descargar subtítulos de vídeos "
            "que tu cuenta puede editar (suele ser contenido propio). En canales ajenos "
            "usa VIDEOMAKER_TRANSCRIPT_PROVIDER=auto para intentar scrape como respaldo.",
            code="forbidden",
            http_status=403,
        )
    if r.status_code == 404:
        raise YouTubeCaptionsError(
            "Track de subtítulos no encontrado (404).",
            code="not_found",
            http_status=404,
        )
    if r.status_code >= 400:
        raise YouTubeCaptionsError(
            f"captions.download falló ({r.status_code}): {r.text[:400]}",
            code="api_error",
            http_status=r.status_code,
        )
    return r.text or ""


def fetch_transcript_data_api(video_id: str, *, lang: str = "es") -> tuple[str, str | None]:
    """
    Devuelve (texto, error). Usa quota oficial; no hace scraping a timedtext.
    """
    vid = (video_id or "").strip()
    if not vid:
        return "", "video_id vacío"
    try:
        tracks = list_caption_tracks(vid)
        if not tracks:
            return "", "Sin pistas de subtítulos en YouTube Data API"
        picked = _pick_track(tracks, _lang_prefs(lang))
        if not picked:
            return "", "No se pudo elegir pista de subtítulos"
        cap_id = str(picked.get("id") or "").strip()
        if not cap_id:
            return "", "Pista sin id"
        raw = download_caption_track(cap_id, tfmt="srt")
        text = parse_subtitle_text(raw, filename="captions.srt")
        if text:
            return text, None
        return "", "Subtítulo descargado vacío"
    except YouTubeCaptionsError as e:
        return "", str(e)
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"
