"""Análisis de vídeos de YouTube para alimentar la pipeline de creación.

Extrae metadata + transcripción + comentarios (si hay API key) y genera insights
con el LLM configurado (openai-compatible u ollama).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from videomaker.core.cache import cache_key, get_json, set_json

@dataclass(frozen=True)
class YoutubeAnalyzeInputs:
    url: str
    lang: str = "es"
    max_comments: int = 20


@dataclass(frozen=True)
class YoutubeChannelAnalyzeInputs:
    channel: str  # @handle, URL del canal o nombre
    lang: str = "es"
    max_videos: int = 10
    max_comments: int = 10


def extract_video_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if not s:
        raise ValueError("URL/ID de YouTube vacío.")

    # Ya es un ID (11 chars típicos), lo aceptamos.
    if re.fullmatch(r"[-_0-9A-Za-z]{11}", s):
        return s

    # Parse URL de forma robusta (watch, shorts, embed, youtu.be, m.youtube.com…)
    try:
        u = urlparse(s)
        host = (u.netloc or "").lower()
        path = u.path or ""
        qs = parse_qs(u.query or "")

        # Si es una URL de YouTube pero apunta a canal/handle/playlist, no intentes adivinar.
        is_youtube = ("youtube.com" in host) or ("youtu.be" in host)
        if is_youtube and (path.startswith("/@") or path.startswith("/channel/") or re.search(r"^/(?:c/|user/|feed/|results|playlist)(?:/|$)", path)):
            raise ValueError("Parece una URL de canal/playlist, no de vídeo. Pega la URL de un vídeo o el ID (11 caracteres).")

        # watch?v=
        v = (qs.get("v") or [""])[0]
        if v:
            m = re.search(r"[-_0-9A-Za-z]{11}", v)
            if m:
                return m.group(0)

        # youtu.be/<id>
        if "youtu.be" in host:
            m = re.search(r"/([-_0-9A-Za-z]{11})(?:[/?#]|$)", path)
            if m:
                return m.group(1)

        # /shorts/<id> o /embed/<id>
        m = re.search(r"/(?:shorts|embed)/([-_0-9A-Za-z]{11})(?:[/?#]|$)", path)
        if m:
            return m.group(1)
    except ValueError:
        raise
    except Exception:
        # si urlparse falla, seguimos con el flujo normal
        pass

    # Fallback final solo si NO parece URL: evita capturar handles de canal por accidente.
    if "://" not in s and "youtube" not in s.lower():
        m = re.search(r"[-_0-9A-Za-z]{11}", s)
        if m:
            return m.group(0)

    raise ValueError("No pude extraer el video_id de la URL. Usa una URL estándar o el ID (11 caracteres).")


def _youtube_get(path: str, params: dict[str, Any], *, timeout: int = 30) -> dict[str, Any]:
    key = _youtube_api_key()
    if not key:
        raise RuntimeError("Falta YOUTUBE_API_KEY para analizar canales completos.")
    url = f"https://www.googleapis.com/youtube/v3/{path.lstrip('/')}"
    p = dict(params)
    p["key"] = key
    # Cache 24h en Redis (si está configurado).
    ck = cache_key("yt", path, json.dumps(p, sort_keys=True, ensure_ascii=False))
    cached = get_json(ck)
    if isinstance(cached, dict):
        return cached

    r = requests.get(url, params=p, timeout=timeout)
    r.raise_for_status()
    data = r.json() or {}
    set_json(ck, data, ttl_s=24 * 3600)
    return data


def extract_handle_or_channel_id(channel: str) -> tuple[str | None, str | None]:
    """Devuelve (handle_without_at, channel_id) si se puede inferir desde el input."""
    s = (channel or "").strip()
    if not s:
        raise ValueError("Canal vacío.")

    # channelId clásico
    if re.fullmatch(r"UC[-_0-9A-Za-z]{20,30}", s):
        return None, s

    # @handle directo
    if s.startswith("@") and len(s) > 2:
        return s[1:], None

    # URL del canal: /@handle o /channel/UC...
    try:
        u = urlparse(s)
        host = (u.netloc or "").lower()
        path = u.path or ""
        if "youtube.com" in host:
            if path.startswith("/@"):
                h = path[2:].split("/", 1)[0]
                return (h or None), None
            if path.startswith("/channel/"):
                cid = path.split("/channel/", 1)[1].split("/", 1)[0]
                if cid:
                    return None, cid
    except Exception:
        pass

    # nombre / búsqueda
    return None, None


def resolve_channel_id(channel: str) -> dict[str, Any]:
    """Resuelve un canal a channelId usando forHandle o search.list."""
    handle, cid = extract_handle_or_channel_id(channel)
    if cid:
        return {"channel_id": cid, "resolved_via": "channel_id"}

    if handle:
        data = _youtube_get("channels", {"part": "snippet,contentDetails", "forHandle": handle})
        items = data.get("items") or []
        if items:
            it = items[0]
            return {
                "channel_id": it.get("id") or "",
                "title": ((it.get("snippet") or {}).get("title") or ""),
                "resolved_via": "forHandle",
            }

    # fallback: search por nombre
    q = (channel or "").strip()
    data = _youtube_get("search", {"part": "snippet", "q": q, "type": "channel", "maxResults": 1})
    items = data.get("items") or []
    if not items:
        raise RuntimeError("No pude resolver el canal. Prueba con la URL del canal o el @handle.")
    it = items[0]
    ch = ((it.get("id") or {}).get("channelId") or "")
    return {"channel_id": ch, "title": ((it.get("snippet") or {}).get("title") or ""), "resolved_via": "search"}


def list_channel_videos(channel_id: str, *, max_videos: int = 10) -> list[dict[str, Any]]:
    """
    Lista los vídeos recientes del canal (IDs + título básico) usando search.list.
    Nota: search.list no devuelve duración; se enriquece luego con videos.list.
    """
    max_videos = max(1, min(int(max_videos), 50))
    out: list[dict[str, Any]] = []
    page = ""
    while len(out) < max_videos:
        params: dict[str, Any] = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": min(50, max_videos - len(out)),
        }
        if page:
            params["pageToken"] = page
        data = _youtube_get("search", params)
        for it in data.get("items") or []:
            vid = ((it.get("id") or {}).get("videoId") or "")
            sn = it.get("snippet") or {}
            if vid:
                out.append({"video_id": vid, "title": sn.get("title") or "", "published_at": sn.get("publishedAt") or ""})
        page = data.get("nextPageToken") or ""
        if not page:
            break
    return out[:max_videos]


def enrich_videos_metadata(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not video_ids:
        return {}
    # API permite hasta 50 ids por llamada
    joined = ",".join(video_ids[:50])
    data = _youtube_get("videos", {"part": "snippet,contentDetails,statistics", "id": joined})
    out: dict[str, dict[str, Any]] = {}
    for it in data.get("items") or []:
        vid = it.get("id") or ""
        if not vid:
            continue
        sn = it.get("snippet") or {}
        cd = it.get("contentDetails") or {}
        st = it.get("statistics") or {}
        out[vid] = {
            "video_id": vid,
            "title": sn.get("title") or "",
            "channel": sn.get("channelTitle") or "",
            "description": sn.get("description") or "",
            "published_at": sn.get("publishedAt") or "",
            "tags": sn.get("tags") or [],
            "category_id": sn.get("categoryId") or "",
            "default_language": sn.get("defaultLanguage") or "",
            "default_audio_language": sn.get("defaultAudioLanguage") or "",
            "duration_s": _iso8601_duration_to_seconds(cd.get("duration") or ""),
            "views": st.get("viewCount"),
            "likes": st.get("likeCount"),
            "comments": st.get("commentCount"),
        }
    return out


def search_channels(query: str, *, max_results: int = 10) -> list[dict[str, Any]]:
    """Busca canales por texto y devuelve candidatos (channelId + título + thumbnail)."""
    q = (query or "").strip()
    if not q:
        return []
    max_results = max(1, min(int(max_results), 25))
    data = _youtube_get(
        "search",
        {"part": "snippet", "q": q, "type": "channel", "maxResults": max_results},
    )
    out: list[dict[str, Any]] = []
    for it in data.get("items") or []:
        cid = ((it.get("id") or {}).get("channelId") or "")
        sn = it.get("snippet") or {}
        thumbs = sn.get("thumbnails") or {}
        avatar = (
            (thumbs.get("default") or {}).get("url")
            or (thumbs.get("medium") or {}).get("url")
            or (thumbs.get("high") or {}).get("url")
            or None
        )
        if cid:
            out.append(
                {
                    "channel_id": cid,
                    "title": sn.get("title") or "",
                    "description": sn.get("description") or "",
                    "avatar_url": avatar,
                }
            )
    return out


def enrich_channels_stats(channel_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Enriquece canales con subscribers/total views/video count + handle si existe."""
    if not channel_ids:
        return {}
    joined = ",".join(channel_ids[:50])
    data = _youtube_get("channels", {"part": "snippet,statistics", "id": joined})
    out: dict[str, dict[str, Any]] = {}
    for it in data.get("items") or []:
        cid = it.get("id") or ""
        if not cid:
            continue
        sn = it.get("snippet") or {}
        st = it.get("statistics") or {}
        thumbs = sn.get("thumbnails") or {}
        avatar = (
            (thumbs.get("default") or {}).get("url")
            or (thumbs.get("medium") or {}).get("url")
            or (thumbs.get("high") or {}).get("url")
            or None
        )
        out[cid] = {
            "channel_id": cid,
            "title": sn.get("title") or "",
            "handle": sn.get("customUrl") or "",
            "description": sn.get("description") or "",
            "avatar_url": avatar,
            "subscribers": st.get("subscriberCount"),
            "total_views": st.get("viewCount"),
            "video_count": st.get("videoCount"),
        }
    return out


def enrich_videos_snippet(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Añade thumbnail_url y snippet básico por vídeo."""
    if not video_ids:
        return {}
    joined = ",".join(video_ids[:50])
    data = _youtube_get("videos", {"part": "snippet", "id": joined})
    out: dict[str, dict[str, Any]] = {}
    for it in data.get("items") or []:
        vid = it.get("id") or ""
        if not vid:
            continue
        sn = it.get("snippet") or {}
        thumbs = sn.get("thumbnails") or {}
        thumb = (
            (thumbs.get("maxres") or {}).get("url")
            or (thumbs.get("standard") or {}).get("url")
            or (thumbs.get("high") or {}).get("url")
            or (thumbs.get("medium") or {}).get("url")
            or (thumbs.get("default") or {}).get("url")
            or None
        )
        out[vid] = {"thumbnail_url": thumb, "title": sn.get("title") or ""}
    return out


def analyze_channel(inputs: YoutubeChannelAnalyzeInputs) -> tuple[dict[str, Any], str]:
    logs: list[str] = []
    resolved = resolve_channel_id(inputs.channel)
    channel_id = resolved.get("channel_id") or ""
    if not channel_id:
        raise RuntimeError("No se pudo resolver el canal a channelId.")
    logs.append(f"channel_id={channel_id} via={resolved.get('resolved_via')}")
    videos = list_channel_videos(channel_id, max_videos=inputs.max_videos)
    logs.append(f"videos_listed={len(videos)}")
    meta_map = enrich_videos_metadata([v["video_id"] for v in videos if v.get("video_id")])

    analyzed: list[dict[str, Any]] = []
    for i, v in enumerate(videos):
        vid = v.get("video_id") or ""
        if not vid:
            continue
        logs.append(f"[{i+1}/{len(videos)}] video={vid}")
        md = meta_map.get(vid) or fetch_metadata(vid)
        lang_detected, transcript = fetch_transcript(vid, lang=inputs.lang)
        comments = fetch_top_comments(vid, max_comments=inputs.max_comments)
        insights = build_analysis_report(
            url=f"https://www.youtube.com/watch?v={vid}",
            video_id=vid,
            metadata=md,
            transcript=transcript,
            top_comments=comments,
            lang=inputs.lang,
        )
        analyzed.append(
            {
                "video_id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": md.get("title") or v.get("title") or "",
                "channel": md.get("channel") or "",
                "published_at": md.get("published_at") or v.get("published_at") or "",
                "duration_s": md.get("duration_s"),
                "views": md.get("views"),
                "likes": md.get("likes"),
                "comments": md.get("comments"),
                "transcript_lang": lang_detected,
                "top_comments": comments,
                "insights": insights,
            }
        )

    report = {
        "channel": inputs.channel,
        "channel_id": channel_id,
        "resolved": resolved,
        "count": len(analyzed),
        "videos": analyzed,
    }
    return report, "\n".join(logs)


def _youtube_api_key() -> str | None:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    return key or None


def _iso8601_duration_to_seconds(s: str) -> int | None:
    # PT#H#M#S
    if not s or not s.startswith("PT"):
        return None
    h = m = sec = 0
    mh = re.search(r"(\d+)H", s)
    mm = re.search(r"(\d+)M", s)
    ms = re.search(r"(\d+)S", s)
    if mh:
        h = int(mh.group(1))
    if mm:
        m = int(mm.group(1))
    if ms:
        sec = int(ms.group(1))
    return h * 3600 + m * 60 + sec


def fetch_metadata(video_id: str) -> dict[str, Any]:
    key = _youtube_api_key()
    if not key:
        return {"video_id": video_id, "warning": "Falta YOUTUBE_API_KEY: metadata limitada."}

    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet,contentDetails", "id": video_id, "key": key}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json() or {}
    items = data.get("items") or []
    if not items:
        return {"video_id": video_id, "warning": "No se encontró metadata para este video_id."}
    it = items[0]
    snippet = it.get("snippet") or {}
    cd = it.get("contentDetails") or {}
    return {
        "video_id": video_id,
        "title": snippet.get("title") or "",
        "channel": snippet.get("channelTitle") or "",
        "description": snippet.get("description") or "",
        "published_at": snippet.get("publishedAt") or "",
        "duration_s": _iso8601_duration_to_seconds(cd.get("duration") or ""),
        "tags": snippet.get("tags") or [],
    }


def fetch_top_comments(video_id: str, *, max_comments: int = 20) -> list[dict[str, Any]]:
    key = _youtube_api_key()
    if not key:
        return []
    url = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": max(1, min(int(max_comments), 100)),
        "order": "relevance",
        "textFormat": "plainText",
        "key": key,
    }
    r = requests.get(url, params=params, timeout=30)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        # No bloquea el análisis: algunos vídeos tienen comentarios deshabilitados o hay restricciones.
        return []
    data = r.json() or {}
    out: list[dict[str, Any]] = []
    for it in data.get("items") or []:
        sn = (((it or {}).get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
        text = sn.get("textDisplay") or sn.get("textOriginal") or ""
        if not text:
            continue
        out.append(
            {
                "author": sn.get("authorDisplayName") or "",
                "text": text,
                "like_count": sn.get("likeCount") or 0,
            }
        )
    return out


def fetch_transcript(video_id: str, *, lang: str = "es") -> tuple[str | None, str]:
    """
    Devuelve (lang_detected, transcript_text). Si no hay transcript, lang_detected=None y texto vacío.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Falta dependencia `youtube-transcript-api`. Instala requirements.txt en tu venv."
        ) from e

    langs = []
    if lang:
        langs.append(lang)
    # fallbacks típicos
    for x in ("es", "en"):
        if x not in langs:
            langs.append(x)
    try:
        rows = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
    except Exception:
        return None, ""
    text = "\n".join((r.get("text") or "").strip() for r in rows if (r.get("text") or "").strip())
    return (langs[0] if text else None), text.strip()


def _llm_provider() -> str:
    return (os.environ.get("VIDEOMAKER_LLM_PROVIDER") or "openai").lower().strip() or "openai"


def llm_chat(system: str, user: str, *, model: str | None = None) -> str:
    selected = _llm_provider()
    if selected == "ollama":
        from videomaker.llm.providers.ollama import ollama_chat

        return ollama_chat(system=system, user=user, model=model or os.environ.get("OLLAMA_MODEL", "llama3.2:latest")).strip()
    if selected == "openai":
        from videomaker.llm.providers.openai_compat import openai_compat_chat

        return openai_compat_chat(system=system, user=user, model=model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")).strip()
    raise ValueError(f"Proveedor LLM no soportado: {selected}")


def build_analysis_report(
    *,
    url: str,
    video_id: str,
    metadata: dict[str, Any],
    transcript: str,
    top_comments: list[dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    sys = (
        "Eres un analista experto de vídeos de YouTube y guionista.\n"
        "Tu tarea: analizar el vídeo y devolver SOLO JSON válido (sin markdown)."
    )
    user = {
        "video": {
            "url": url,
            "video_id": video_id,
            "lang_hint": lang,
            "metadata": {
                "title": metadata.get("title", ""),
                "channel": metadata.get("channel", ""),
                "description": (metadata.get("description", "") or "")[:4000],
                "duration_s": metadata.get("duration_s"),
                "tags": metadata.get("tags", [])[:50],
            },
        },
        "transcript_excerpt": transcript[:8000],
        "top_comments": top_comments[:20],
        "output_schema": {
            "hookPattern": "string (1-3 frases)",
            "sectionOutline": ["string"],
            "pacingNotes": ["string"],
            "suggestedBrollThemes": ["string"],
            "CTAStyle": "string",
            "keywordOpportunities": ["string"],
        },
        "constraints": [
            "No inventes datos del vídeo: si no hay transcript, dilo.",
            "Sé concreto y accionable para alimentar una pipeline de creación.",
        ],
    }
    raw = llm_chat(sys, "INPUT:\n" + json.dumps(user, ensure_ascii=False) + "\n\nOUTPUT: JSON únicamente.")
    try:
        j = json.loads(raw)
        if isinstance(j, dict):
            return j
    except Exception:
        pass
    return {"raw": raw}


def analyze_youtube(inputs: YoutubeAnalyzeInputs) -> tuple[dict[str, Any], str]:
    """
    Ejecuta análisis completo y devuelve (report, log_text).
    """
    logs: list[str] = []
    vid = extract_video_id(inputs.url)
    logs.append(f"video_id={vid}")
    md = fetch_metadata(vid)
    logs.append("metadata: ok" if md else "metadata: empty")
    lang_detected, transcript = fetch_transcript(vid, lang=inputs.lang)
    logs.append(f"transcript: {'ok' if transcript else 'missing'}")
    comments = fetch_top_comments(vid, max_comments=inputs.max_comments)
    logs.append(f"comments: {len(comments)}")
    insights = build_analysis_report(
        url=inputs.url,
        video_id=vid,
        metadata=md,
        transcript=transcript,
        top_comments=comments,
        lang=inputs.lang,
    )
    report = {
        "video_id": vid,
        "url": inputs.url,
        "title": md.get("title") or "",
        "channel": md.get("channel") or "",
        "duration_s": md.get("duration_s"),
        "transcript_lang": lang_detected,
        "top_comments": comments,
        "insights": insights,
    }
    return report, "\n".join(logs)

