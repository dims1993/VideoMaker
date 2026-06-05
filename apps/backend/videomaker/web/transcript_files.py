"""Extracción de texto desde archivos de transcripción."""

from __future__ import annotations

import io
import json
import re
from typing import Any

_ALLOWED_SUFFIXES = (".txt", ".pdf", ".json", ".srt", ".vtt")


def extract_transcripts_from_json(data: Any) -> str:
    """Normaliza JSON de export del canal (videos con transcript y status ok)."""
    videos: list[Any] | None = None
    if isinstance(data, dict) and isinstance(data.get("videos"), list):
        videos = data["videos"]
    elif isinstance(data, list):
        videos = data
    if not videos:
        raise ValueError("JSON sin lista «videos» reconocible")

    blocks: list[str] = []
    for v in videos:
        if not isinstance(v, dict):
            continue
        status = v.get("status")
        transcript = str(v.get("transcript") or "").strip()
        if not transcript:
            continue
        if status is not None and status != "ok":
            continue
        title = str(v.get("title") or v.get("video_id") or "Sin título").strip()
        dur = v.get("duration_s")
        mins: int | None = None
        if isinstance(dur, (int, float)) and dur:
            mins = round(float(dur) / 60)
        header = f"=== VÍDEO: {title} ({mins} min) ===" if mins is not None else f"=== VÍDEO: {title} ==="
        blocks.append(f"{header}\n{transcript}")

    if not blocks:
        raise ValueError("JSON sin transcripciones con status ok")
    return "\n\n".join(blocks)


def parse_subtitle_text(content: str, *, filename: str = "") -> str:
    """Extrae texto legible de subtítulos .srt / .vtt."""
    low = (filename or "").lower()
    lines: list[str] = []
    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue
        if low.endswith(".vtt"):
            if s == "WEBVTT" or s.startswith("NOTE"):
                continue
            s = re.sub(r"<[^>]+>", "", s).strip()
            if not s:
                continue
        if re.fullmatch(r"\d+", s):
            continue
        if "-->" in s:
            continue
        lines.append(s)
    text = "\n".join(lines).strip()
    if not text:
        raise ValueError(f"El subtítulo no contiene texto extraíble: {filename or 'upload'}")
    return text


def extract_transcript_text(content: bytes, filename: str) -> str:
    name = (filename or "upload").strip().lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError(
                "Falta pypdf en el venv. Instala con: python -m pip install pypdf"
            ) from e
        reader = PdfReader(io.BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            parts.append((page.extract_text() or "").strip())
        text = "\n\n".join(p for p in parts if p).strip()
        if not text:
            raise ValueError(f"El PDF no contiene texto extraíble: {filename}")
        return text

    raw = content.decode("utf-8", errors="replace").strip()
    if not raw:
        raise ValueError(f"Archivo vacío: {filename}")

    if name.endswith(".json"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido: {filename}") from e
        return extract_transcripts_from_json(data)

    if name.endswith(".srt") or name.endswith(".vtt"):
        return parse_subtitle_text(raw, filename=filename)

    if name.endswith(".txt"):
        return raw

    raise ValueError(
        f"Formato no soportado: {filename}. Usa {', '.join(_ALLOWED_SUFFIXES)}"
    )


def combine_transcript_documents(documents: list[tuple[str, str]]) -> str:
    """Une varios documentos con separadores legibles para el LLM."""
    blocks: list[str] = []
    for filename, text in documents:
        body = (text or "").strip()
        if not body:
            continue
        blocks.append(f"--- {filename} ---\n{body}")
    return "\n\n".join(blocks).strip()
