"""Contrato mínimo de salida del Script Writer."""

from __future__ import annotations

_SCRIPT_FORMAT_ES = """Formato (solo esto en la respuesta):
OUTLINE → GUIÓN con `[CATEGORIA: …]` y `[B-ROLL: …]` inline → KEYWORDS (1 línea, inglés, comas).
Sin análisis editorial. TTS no lee etiquetas. Texto hablado sin Markdown decorativo."""

_SCRIPT_FORMAT_EN = """Format (return only):
OUTLINE → SCRIPT with `[CATEGORIA: …]` and inline `[B-ROLL: …]` → KEYWORDS (one English comma line).
No editorial analysis. TTS skips tags. No decorative Markdown in spoken lines."""


def script_writer_format_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip().lower()
    if lang.startswith("en") or lang == "en":
        return _SCRIPT_FORMAT_EN
    return _SCRIPT_FORMAT_ES
