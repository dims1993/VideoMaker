"""Brief mínimo del Script Writer — guionista humano, sin conciencia editorial."""

from __future__ import annotations

import re

WRITER_VOICE_HEADER_EN = "## Writer"
WRITER_VOICE_HEADER_ES = "## Guionista"

# ~6 líneas. Sin métricas, sin marcas de estilo premium.
WRITER_VOICE_BLOCK_EN = f"""{WRITER_VOICE_HEADER_EN}
Write like a person talking, not a premium explainer brand.
**Scenes beat slogans.** ("She closed the payment tab" > "This is not a market, it is a mechanism.")
Avoid: Vox/Moon/essay voice, aphorism pairs ("not X — Y"), mechanism metaphors, sounding important.
Channel notes below = topic/tone only — not a checklist."""

WRITER_VOICE_BLOCK_ES = f"""{WRITER_VOICE_HEADER_ES}
Escribe como alguien hablando, no como marca de vídeo premium.
**La escena gana al eslogan.** ("Cerró la pestaña del pago" > "Esto no es un mercado, es un mecanismo.")
Evita: tono Vox/ensayo, parejas "no es X — es Y", metáforas de mecanismo, sonar importante.
Notas de canal abajo = tema/tono — no checklist."""

_STRIP_SECTION_PREFIXES: tuple[str, ...] = (
    "## Creative looseness",
    "## Holgura creativa",
    "## Script governance",
    "## Gobernanza del guion",
    "## Priority order",
    "## Orden de prioridad",
    "## Retention discipline",
    "## Disciplina de retención",
    "## Write visually",
    "## Escribe en visual",
    "## Pattern interrupt",
    "## Pattern Interrupt",
    "## Grounded realism",
    "## Realismo vivido",
    "## Truth claims",
    "## Verdad",
    "## Visual pacing architecture",
    "## Arquitectura de ritmo visual",
    "## Anti editorial bloat",
    "## Anti-hinchazón editorial",
    "## Estructura de salida",
    "## Script output structure",
    "## Script Writer output",
    "## TTS / spoken",
    "## TTS / guion hablado",
)

_NARRATIVE_MARKERS = (
    "\n\n---\n\n## Channel narrative guidelines\n\n",
    "\n\n---\n\n## Instrucciones narrativas (canal)\n\n",
)

_MAX_NARRATIVE_CHARS = 1200


def _language_is_spanish(lang: str) -> bool:
    code = (lang or "").strip().lower().replace("_", "-")
    return code.startswith("es") or code == "es"


def writer_voice_brief(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return WRITER_VOICE_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return WRITER_VOICE_BLOCK_EN
    return WRITER_VOICE_BLOCK_ES


def has_writer_voice(text: str) -> bool:
    t = text or ""
    return WRITER_VOICE_HEADER_EN in t or WRITER_VOICE_HEADER_ES in t


def strip_editorial_governance_sections(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw

    parts = re.split(r"(?m)^(?=## )", raw)
    if len(parts) <= 1 and not raw.lstrip().startswith("## "):
        return _strip_inline_governance_paragraphs(raw)

    kept: list[str] = []
    for i, part in enumerate(parts):
        chunk = part.strip()
        if not chunk:
            continue
        if i == 0 and not chunk.startswith("## "):
            kept.append(_strip_inline_governance_paragraphs(chunk))
            continue
        first_line = chunk.split("\n", 1)[0].strip()
        if any(first_line.startswith(prefix) for prefix in _STRIP_SECTION_PREFIXES):
            continue
        if first_line.startswith("## Tema del vídeo") or first_line.startswith("## Video topic"):
            continue
        kept.append(chunk)
    return "\n\n".join(k for k in kept if k).strip()


def _strip_inline_governance_paragraphs(text: str) -> str:
    lines: list[str] = []
    skip_block = False
    skip_tokens = (
        "retention",
        "retención",
        "pacing",
        "ritmo visual",
        "hook density",
        "beat ",
        "editorial",
        "análisis editorial",
        "mechanism",
        "mecanismo",
        "pattern interrupt",
        "scroll-stop",
        "energy curve",
        "visual density",
        "spine;",
    )
    for line in text.splitlines():
        low = line.lower()
        if any(token in low for token in skip_tokens):
            skip_block = True
            continue
        if skip_block and not line.strip():
            skip_block = False
            continue
        if skip_block and line.startswith(("-", "*", "•")):
            continue
        skip_block = False
        lines.append(line)
    return "\n".join(lines).strip()


def _cap_narrative_section(text: str, max_chars: int) -> str:
    raw = (text or "").strip()
    if len(raw) <= max_chars:
        return raw
    for marker in _NARRATIVE_MARKERS:
        idx = raw.find(marker)
        if idx < 0:
            continue
        head = raw[: idx + len(marker)]
        narrative = raw[idx + len(marker) :].strip()
        if len(narrative) <= max_chars:
            return raw
        trimmed = narrative[:max_chars].rsplit("\n", 1)[0].strip()
        return f"{head}{trimmed}\n\n[… guía de canal recortada para el borrador …]"
    if len(raw) > max_chars + 400:
        return raw[:max_chars].rsplit("\n", 1)[0].strip() + "\n\n[… instrucciones recortadas …]"
    return raw


def compact_script_writer_instructions(text: str, *, max_narrative_chars: int = _MAX_NARRATIVE_CHARS) -> str:
    cleaned = strip_editorial_governance_sections(text)
    return _cap_narrative_section(cleaned, max_narrative_chars)


def prepare_script_writer_user_prompt(
    text: str,
    *,
    language_code: str = "",
    locale: str = "",
) -> str:
    cleaned = compact_script_writer_instructions(text)
    brief = writer_voice_brief(language_code=language_code, locale=locale)
    if has_writer_voice(cleaned):
        return cleaned.strip()
    if cleaned:
        return f"{brief}\n\n{cleaned}".strip()
    return brief.strip()


def prepare_script_writer_system_prompt(text: str) -> str:
    return compact_script_writer_instructions(text, max_narrative_chars=800)
