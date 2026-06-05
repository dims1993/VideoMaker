"""Resolución de idioma de salida para LLM (temas, plantilla prompt, etc.)."""

from __future__ import annotations

import json
import re
from pathlib import Path

_SUPPORTED = frozenset({"en", "es"})

# Alineado con el selector «Idioma de salida» del Topic Generator (UI).
PIPELINE_DEFAULT_LANGUAGE = "en"


def normalize_language_code(raw: str | None) -> str | None:
    if not raw:
        return None
    low = str(raw).strip().lower()
    if low in ("en", "en-us", "en-gb", "english"):
        return "en"
    if low in ("es", "es-es", "es-mx", "spanish", "español", "espanol"):
        return "es"
    if low.startswith("en-"):
        return "en"
    if low.startswith("es-"):
        return "es"
    return None


def detect_language_from_text(text: str, *, sample_chars: int = 8000) -> str:
    """Heurística simple en→es si no hay idioma de canal."""
    sample = (text or "")[:sample_chars].lower()
    if len(sample) < 80:
        return "es"
    es_hits = len(
        re.findall(
            r"\b(el|la|los|las|de|que|en|un|una|por|con|para|es|son|está|esta)\b",
            sample,
        )
    )
    en_hits = len(
        re.findall(
            r"\b(the|and|you|your|is|are|was|with|for|this|that|have|from|not)\b",
            sample,
        )
    )
    return "en" if en_hits > es_hits * 1.15 else "es"


def resolve_output_language(
    *,
    explicit: str | None = None,
    channel_language: str | None = None,
    transcript_text: str = "",
) -> str:
    """
    Prioridad: parámetro explícito → language del canal guardado → detección en texto.
    """
    for candidate in (explicit, channel_language):
        code = normalize_language_code(candidate)
        if code in _SUPPORTED:
            return code
    return detect_language_from_text(transcript_text)


def language_label(code: str) -> str:
    return "English" if code == "en" else "Spanish"


def read_topic_generator_output_language(work_dir: Path) -> str | None:
    """Lee ``output_language`` de ``pipeline/topic_generator.json`` (fuente canónica Create)."""
    p = work_dir / "pipeline" / "topic_generator.json"
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    code = normalize_language_code(str(raw.get("output_language") or ""))
    return code if code in _SUPPORTED else None


def resolve_pipeline_lang(
    work_dir: Path,
    *,
    request_lang: str | None = None,
) -> str:
    """
    Idioma efectivo para todos los pasos Create.

    Prioridad: ``topic_generator.json`` → ``request_lang`` (UI) → ``prompt.json`` → EN.
    """
    topic = read_topic_generator_output_language(work_dir)
    if topic:
        return topic
    req = normalize_language_code(request_lang)
    if req:
        return req
    pj = work_dir / "pipeline" / "prompt.json"
    if pj.is_file():
        try:
            raw = json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                stored = normalize_language_code(str(raw.get("lang") or ""))
                if stored:
                    return stored
        except Exception:
            pass
    return PIPELINE_DEFAULT_LANGUAGE
