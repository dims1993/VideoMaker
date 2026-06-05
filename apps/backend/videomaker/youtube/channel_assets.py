"""Generación de assets (ZIP) por canal en almacenamiento local.

Nota: para producción esto puede migrar a S3/GCS; aquí guardamos en disco y devolvemos paths.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import requests

from videomaker import config


def channel_assets_dir(channel_id: str) -> Path:
    d = config.OUTPUT_DIR / "channels" / channel_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def delete_channel_assets(channel_id: str) -> None:
    d = config.OUTPUT_DIR / "channels" / channel_id
    if not d.exists():
        return
    # Seguridad: solo dentro de output/channels
    try:
        d = d.resolve()
        root = (config.OUTPUT_DIR / "channels").resolve()
        if not d.is_relative_to(root):
            return
    except Exception:
        return
    import shutil

    shutil.rmtree(d, ignore_errors=True)


def _safe_name(s: str) -> str:
    keep = []
    for ch in (s or ""):
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        elif ch.isspace():
            keep.append("_")
    out = "".join(keep).strip("_")
    return out or "item"


def build_thumbnails_zip(channel_id: str, videos: list[dict[str, Any]]) -> Path:
    """
    Genera thumbnails.zip. Cada vídeo debe traer `video_id` y opcionalmente `thumbnail_url`.
    """
    out = channel_assets_dir(channel_id) / "thumbnails.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        manifest = {"channel_id": channel_id, "count": len(videos)}
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for v in videos:
            vid = v.get("video_id") or ""
            url = v.get("thumbnail_url") or ""
            if not (vid and url):
                continue
            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                z.writestr(f"{_safe_name(vid)}.jpg", r.content)
            except Exception:
                continue
    return out


def build_scripts_zip(channel_id: str, videos: list[dict[str, Any]]) -> Path:
    """
    Genera scripts.zip con insights por vídeo (MVP). Más adelante: transcript completo o guion extraído.
    """
    out = channel_assets_dir(channel_id) / "scripts.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        manifest = {"channel_id": channel_id, "count": len(videos)}
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for v in videos:
            vid = v.get("video_id") or ""
            title = v.get("title") or vid
            insights = v.get("insights") or {}
            if not vid:
                continue
            payload = {"video_id": vid, "title": title, "insights": insights}
            z.writestr(f"{_safe_name(title)}_{_safe_name(vid)}.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return out


def build_transcripts_zip(channel_id: str, videos: list[dict[str, Any]], *, lang: str = "es") -> Path:
    """scripts.zip con transcripciones (YouTube Data API captions por defecto)."""
    from videomaker.youtube.transcript_fetch import fetch_video_transcript

    out = channel_assets_dir(channel_id) / "scripts.zip"

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        manifest = {"channel_id": channel_id, "count": len(videos), "lang": lang}
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for v in videos:
            vid = v.get("video_id") or ""
            title = v.get("title") or vid
            if not vid:
                continue
            text, _err, _method = fetch_video_transcript(vid, lang=lang)
            if not text:
                continue
            z.writestr(f"{_safe_name(title)}_{_safe_name(vid)}.txt", text)
    return out

