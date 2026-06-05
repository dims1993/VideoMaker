"""
Contrato del Prompt Writer — motor de compresión narrativa (no copy enhancer).

Secciones 1–10 → user_instructions_narrative (psicología creativa).
Sección 11 (OUTPUT SPEC) → solo params_json.output_structure en la app — nunca mezclar aquí.
"""

from __future__ import annotations

import re

PROMPT_WRITER_ROLE_EN = (
    "The Prompt Writer compresses narrative psychology, removes rigidity, "
    "and stabilizes realism — it is a creative director, not a wording template."
)
PROMPT_WRITER_ROLE_ES = (
    "El Prompt Writer comprime psicología narrativa, quita rigidez y estabiliza realismo — "
    "es director creativo, no plantilla de frases."
)

NATURALNESS_SECTION_EN = """## Naturalness constraint
Naturalness overrides optimization.
Do not force retention tricks, emotional reversals, rhetorical questions, transition phrases, or motivational cadence.
If a moment already works emotionally, do not artificially intensify it.
The script should feel observed and spoken — not engineered."""

NATURALNESS_SECTION_ES = """## Restricción de naturalidad
La naturalidad anula la optimización.
No fuerces trucos de retención, reversiones emocionales, preguntas retóricas, frases puente ni cadencia motivacional.
Si un momento ya funciona emocionalmente, no lo intensifiques artificialmente.
El guion debe sentirse observado y hablado — no ingenierizado."""

# Headers required in inferred narrative (sections 1–10).
NARRATIVE_SECTION_HEADERS_EN = (
    "## Creative north star",
    "## Core mechanism",
    "## Viewer psychology",
    "## Tone profile",
    "## Narrative movement",
    "## Visual world",
    "## Human texture",
    "## Intellectual standard",
    "## Naturalness constraint",
    "## Forbidden patterns",
)

NARRATIVE_SECTION_HEADERS_ES = (
    "## Estrella creativa",
    "## Mecanismo central",
    "## Psicología del espectador",
    "## Perfil de tono",
    "## Movimiento narrativo",
    "## Mundo visual",
    "## Textura humana",
    "## Estándar intelectual",
    "## Restricción de naturalidad",
    "## Patrones prohibidos",
)

_SURFACE_COPY_RE = re.compile(
    r"(?im)^\s*(?:use|usa|inserta|insert|always|siempre|never|nunca|must|debes|"
    r"include|incluye|say|di|open with|abre con)\s+[`\"']?.+[`\"']?\s*$"
)

_RETENTION_CLICHE_RE = re.compile(
    r"(?i)(stay with me|quédate conmigo|deep breath|respira profundamente|"
    r"nobody tells you|lo que nadie te cuenta|pattern interrupt|hook every|"
    r"retention cadence|cadencia de retención|here'?s the thing|aquí va la cosa|"
    r"the truth is|la verdad es)"
)


def _lang_code(language_code: str) -> str:
    code = (language_code or "").strip().lower()
    if code.startswith("en") or code == "en":
        return "en"
    return "es"


def prompt_writer_narrative_skeleton(*, language_code: str = "") -> str:
    """Plantilla markdown secciones 1–10 (el LLM sustituye paréntesis por contenido inferido)."""
    if _lang_code(language_code) == "en":
        return """## Creative north star
(very short: what the video is emotionally about; what the viewer should feel; what intellectual shift happens — 2–4 sentences, no hooks)

## Core mechanism
(the hidden engine: incentives/system that drive the story — 1–3 sentences; must be specific)

## Viewer psychology
(starting belief; emotional entry state; narrative shift; desired emotional movement as short arrow chain)

## Tone profile
(emotional ratios / energy balance as bullets — analytical vs emotional, serious vs apocalyptic, etc.; optional 0–1 sliders in JSON line if useful)

## Narrative movement
(progression of revelation as bullets — intimate → contradiction → mechanism → human examples → systemic view → closure; do NOT prescribe exact [CATEGORY] sections)

## Visual world
(recurring filmable physical reality — 6–12 concrete images/objects/lights for B-roll cohesion)

## Human texture
(ordinary physical details to prefer; cinematic/poetic/trailer habits to avoid)

## Intellectual standard
(how arguments should accumulate: math, timelines, incentives; what counts as fake-smart)

## Naturalness constraint
(naturalness overrides optimization; do not force tricks when the moment already works)

## Forbidden patterns
(explicit list: meta-hooks, guru tone, doomposting, visible formulas — channel-specific)"""
    return """## Estrella creativa
(muy breve: de qué va emocionalmente el vídeo; qué debe sentir el espectador; qué cambio intelectual — 2–4 frases, sin ganchos)

## Mecanismo central
(motor oculto: incentivos/sistema que mueven la historia — 1–3 frases; debe ser concreto)

## Psicología del espectador
(creencia inicial; estado emocional de entrada; giro narrativo; movimiento emocional deseado en cadena corta)

## Perfil de tono
(ratios emocionales / balance de energía en viñetas — analítico vs emocional, serio vs apocalíptico, etc.; opcional línea JSON 0–1 si ayuda)

## Movimiento narrativo
(progresión de la revelación en viñetas — íntimo → contradicción → mecanismo → ejemplos humanos → sistema → cierre; NO prescribir secciones [CATEGORIA] exactas)

## Mundo visual
(realidad física recurrente y filmable — 6–12 imágenes/objetos/luces para cohesión de B-roll)

## Textura humana
(detalle físico ordinario a preferir; hábitos cinematográficos/poéticos/tráiler a evitar)

## Estándar intelectual
(cómo deben acumularse los argumentos: datos, timelines, incentivos; qué es “falso inteligente”)

## Restricción de naturalidad
(la naturalidad anula la optimización; no forzar trucos si el momento ya funciona)

## Patrones prohibidos
(lista explícita: meta-ganchos, tono gurú, doomposting, fórmulas visibles — específico del canal)"""


def golden_rule_reminder(*, language_code: str = "") -> str:
    if _lang_code(language_code) == "en":
        return (
            "GOLDEN RULE: describe psychology and movement, not wording formulas. "
            'BAD: "Use rhetorical questions." '
            'GOOD: "The viewer should feel internally conflicted before major realizations."'
        )
    return (
        "REGLA DE ORO: describe psicología y movimiento, no fórmulas de redacción. "
            'MAL: "Usa preguntas retóricas." '
            'BIEN: "El espectador debe sentirse en conflicto interno antes de las revelaciones grandes."'
    )


def bundled_prompt_narrative_extra(*, language_code: str = "", channel_hint: str = "") -> str:
    """Overlay corto para plantillas empaquetadas (psicología, no esqueleto vacío)."""
    hint = (channel_hint or "").strip()
    gr = golden_rule_reminder(language_code=language_code)
    parts = [PROMPT_WRITER_ROLE_ES if _lang_code(language_code) != "en" else PROMPT_WRITER_ROLE_EN]
    if hint:
        parts.append(hint)
    parts.append(gr)
    parts.append(
        "Sections 1–10 live in narrative instructions. "
        "Output format (OUTLINE/GUIÓN/B-ROLL/TTS) is technical — only in the app base model."
        if _lang_code(language_code) == "en"
        else "Las secciones 1–10 van en instrucciones narrativas. "
        "El formato de salida (OUTLINE/GUIÓN/B-ROLL/TTS) es técnico — solo en el modelo base de la app."
    )
    return "\n\n".join(parts)


def derigidify_narrative(text: str) -> str:
    lines: list[str] = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw:
            lines.append(line)
            continue
        if _SURFACE_COPY_RE.match(raw):
            continue
        if _RETENTION_CLICHE_RE.search(raw) and len(raw) < 140:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def compress_narrative_if_long(text: str, *, max_chars: int = 4500) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars].rsplit("\n", 1)[0].strip() + "\n\n[… recortado …]"
