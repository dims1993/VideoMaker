"""Generación de guion vía Anthropic (capa creativa)."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Callable

_LOG = logging.getLogger(__name__)

ProgressFn = Callable[[str], None]

from videomaker.core.models import Locale, ScriptBlueprint
from videomaker.llm.script_writer_voice import (
    prepare_script_writer_system_prompt,
    prepare_script_writer_user_prompt,
)
from videomaker.llm.script_pipeline_format import (
    build_session_user_prompt,
    technical_pipeline_format_addon,
)

_PROMPT_ADDON_TITLE = "--- Instrucciones adicionales (plantilla / editor) ---"


def _script_min_words_default() -> int:
    raw = os.environ.get("VIDEOMAKER_SCRIPT_MIN_WORDS", "1500").strip()
    try:
        v = int(raw)
    except ValueError:
        v = 1500
    return max(200, min(v, 5000))


def _wpm_default() -> int:
    raw = (os.environ.get("VIDEOMAKER_SCRIPT_WORDS_PER_MINUTE", "") or "").strip() or "150"
    try:
        v = int(raw)
    except ValueError:
        v = 150
    return max(80, min(v, 240))


def _target_words_for_minutes(target_minutes: float, *, per_fragment: bool = False) -> int:
    """
    Palabras narrables objetivo aproximadas (≈ VIDEOMAKER_SCRIPT_WORDS_PER_MINUTE, por defecto 150/min).

    - Guion completo: respeta el suelo VIDEOMAKER_SCRIPT_MIN_WORDS (compatibilidad).
    - Fragmento suelto (`per_fragment=True`): solo proporcional al tiempo del segmento, sin imponer 1500+ palabras por trozo.
    """
    try:
        tm = float(target_minutes)
    except (TypeError, ValueError):
        tm = 10.0
    tm = max(1.0, min(tm, 120.0))
    wpm = _wpm_default()
    words = int(tm * wpm)
    if per_fragment:
        frag_min = int(os.environ.get("VIDEOMAKER_FRAGMENT_MIN_WORDS", "80"))
        frag_max = int(os.environ.get("VIDEOMAKER_FRAGMENT_MAX_WORDS", "15000"))
        frag_min = max(40, min(frag_min, 4000))
        frag_max = max(frag_min + 1, min(frag_max, 50000))
        return max(frag_min, min(words, frag_max))
    base = _script_min_words_default()
    return max(base, words)


def segment_word_target(target_minutes: float) -> int:
    """Objetivo de palabras para un solo fragmento en modo secuencial (proporcional a los minutos del segmento)."""
    return _target_words_for_minutes(target_minutes, per_fragment=True)


def _staged_enabled(target_minutes: float) -> bool:
    raw = (os.environ.get("VIDEOMAKER_SCRIPT_STAGED", "") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    # Auto: si el guion es "largo", activamos el método por etapas.
    try:
        return float(target_minutes) >= 14.0
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class _StagePlan:
    blocks: list[str]
    target_words: int


def _stage_plan_from_extras(target_minutes: float, *, system_extra: str, user_extra: str) -> _StagePlan:
    """
    Decide la estructura por etapas en función de overlays del catálogo (Script Writer template).

    Nota: el prompt maestro por defecto habla de 5 bloques; si el template pide 4 actos,
    el modo staged fuerza 4 bloques para mejorar coherencia en guiones largos.
    """
    blob = f"{system_extra}\n{user_extra}".lower()
    wants_four_act = bool(re.search(r"\bfour_act\b|cuatro\s+actos", blob))
    if wants_four_act:
        blocks = ["Hook", "Acto 2 · Promesa", "Acto 3 · Desarrollo", "Acto 4 · Cierre"]
    else:
        blocks = ["Introducción", "Pilar 1", "Pilar 2", "Pilar 3", "Cierre"]
    return _StagePlan(blocks=blocks, target_words=_target_words_for_minutes(target_minutes, per_fragment=False))


def _extract_reference_keyword_line(full_text: str) -> str:
    """
    Intenta extraer la última línea de keywords separadas por coma.
    Si no existe, devuelve vacío.
    """
    t = (full_text or "").strip()
    if not t:
        return ""
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if not lines:
        return ""
    last = lines[-1]
    # Heurística: keywords suelen ser "word, word, word"
    if "," in last and len(last) <= 180:
        return last
    return ""


def _staged_outline_prompt(user: str, plan: _StagePlan) -> str:
    titles = ", ".join(f"«{b}»" for b in plan.blocks)
    return (
        user.rstrip()
        + "\n\n"
        + _PROMPT_ADDON_TITLE
        + "\n\n"
        + f"Modo etapas: devuelve **solo** OUTLINE (sin GUIÓN). {len(plan.blocks)} bloques: {titles}.\n"
        + "Texto plano; una línea por sección + 2–3 beats concretos (escena/objeto, no eslogan).\n"
        + "OUTLINE\n"
    )


def _staged_block_prompt(*, outline: str, block_title: str, prior_tail: str, target_words_block: int, include_broll: bool = True) -> str:
    tail = (prior_tail or "").strip()
    tail = tail[-2200:] if len(tail) > 2200 else tail
    broll_line = (
        "- `[B-ROLL: …]` cada ~2 frases, formato exacto.\n"
        if include_broll
        else "- Sin `[B-ROLL]`.\n"
    )
    return (
        f"Escribe solo el bloque «{block_title}». Empieza con `[CATEGORIA: {block_title}]`.\n"
        + "Texto plano. Escena concreta > frase que suena importante.\n"
        + broll_line
        + f"Mínimo ~{target_words_block} palabras narrables.\n\n"
        + "OUTLINE:\n"
        + outline.strip()
        + "\n\n"
        + (f"Continúa desde:\n{tail}\n\n" if tail else "")
        + f"Bloque: {block_title}\n"
    )


def _max_repairs() -> int:
    raw = (os.environ.get("VIDEOMAKER_SCRIPT_MAX_REPAIRS", "") or "").strip()
    if raw:
        try:
            v = int(raw)
        except ValueError:
            v = 2
        return max(0, min(v, 8))
    return 4


def _generate_script_staged(
    blueprint: ScriptBlueprint,
    *,
    provider: str | None = None,
    model: str | None = None,
    system_extra: str = "",
    user_extra: str = "",
    include_broll: bool = True,
    on_progress: ProgressFn | None = None,
) -> str:
    system, user = compose_messages(
        blueprint,
        system_extra=system_extra,
        user_extra=user_extra,
        include_broll=include_broll,
    )
    from videomaker.llm.llm_routing import call_creative_llm

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)
        _LOG.info("script staged: %s", msg)

    def call_llm(user_prompt: str) -> str:
        return call_creative_llm(system=system, user=user_prompt, model=model)

    plan = _stage_plan_from_extras(
        blueprint.target_minutes,
        system_extra=system_extra,
        user_extra=user_extra,
    )

    _progress("Claude: outline…")
    outline = call_llm(_staged_outline_prompt(user, plan))
    # Limpieza mínima: nos quedamos desde OUTLINE si el modelo añadió texto antes.
    m = re.search(r"(?im)^\s*OUTLINE\s*$", outline or "")
    if m:
        outline = "OUTLINE\n" + (outline[m.end() :].strip() or "")
    outline = outline.strip()

    # Reparto de palabras por bloque.
    total = max(900, plan.target_words)
    if len(plan.blocks) == 4:
        weights = [0.18, 0.22, 0.40, 0.20]  # Hook, Promesa, Desarrollo, Cierre
    else:
        weights = [0.14, 0.24, 0.24, 0.24, 0.14]
    per_block = [max(220, int(total * w)) for w in weights]

    blocks_text: list[str] = []
    prior_tail = ""
    for idx, title in enumerate(plan.blocks):
        _progress(f"Claude: bloque {idx + 1}/{len(plan.blocks)} — {title}…")
        block = call_llm(
            _staged_block_prompt(
                outline=outline,
                block_title=title,
                prior_tail=prior_tail,
                target_words_block=per_block[idx],
                include_broll=include_broll,
            )
        ).strip()
        # Asegura encabezado de categoría por compatibilidad con TTS/producción.
        if not re.search(r"(?im)^\s*\[CATEGORIA\s*:", block):
            block = f"[CATEGORIA: {title}]\n" + block
        blocks_text.append(block.strip())
        prior_tail = "\n\n".join(blocks_text)[-3500:]

    guion = "\n\n".join(blocks_text).strip()

    # Keywords finales: si el modelo no las dio, pedimos una línea barata.
    kw = _extract_reference_keyword_line(guion)
    if not kw:
        _progress("Claude: keywords visuales…")
        kw = call_llm(
            "Devuelve SOLO una línea con 8–12 keywords en inglés, separadas por comas, como referencia visual "
            "(moodboard / equipo de imagen / IA). No añadas nada más."
        ).strip()
        kw = kw.splitlines()[-1].strip() if kw else ""

    full = f"{outline}\n\nGUIÓN\n{guion}\n\n{kw}".strip()

    # Reparación global: en modo staged el guion ya se armó por bloques; 1 paso ligero como máximo.
    min_words = _target_words_for_minutes(blueprint.target_minutes)
    max_repairs = min(1, _max_repairs())
    draft = full
    for attempt in range(max_repairs + 1):
        issues = _script_issues(draft, min_words=min_words, include_broll=include_broll)
        if not issues:
            return draft.strip()
        if attempt >= max_repairs:
            _LOG.warning(
                "script staged: skipping further repairs (%d issues remain)", len(issues)
            )
            return draft.strip()
        _progress(f"Claude: ajuste final ({attempt + 1})…")
        repair_instructions = "\n".join(issues)
        draft = call_llm(
            user.rstrip()
            + "\n\n"
            + _PROMPT_ADDON_TITLE
            + "\n\n"
            + "Corrige el borrador completo. Falta:\n"
            + repair_instructions
            + "\nMantén voz y tema. OUTLINE + GUIÓN + KEYWORDS. Solo [CATEGORIA] y [B-ROLL].\n"
            + "\n\n"
            + "BORRADOR ANTERIOR (para corregir/expandir):\n"
            + draft.strip()
        )

    return draft.strip()


def _count_narrable_words(text: str) -> int:
    from videomaker.core.script_clean import count_narrable_words

    return count_narrable_words(text)


def _count_broll_tags(text: str) -> int:
    return len(re.findall(r"(?i)\[B-ROLL\s*:?[^\]]*\]", text or ""))


def _count_sentences_narrable(text: str) -> int:
    """
    Conteo aproximado de oraciones para verificar: 1 [B-ROLL] cada 2 oraciones.
    """
    from videomaker.core.script_clean import narrable_plain_text

    t = narrable_plain_text(text)
    parts = re.split(r"[.!?]+(?:\s+|$)", t)
    return len([p for p in parts if re.search(r"\w", p)])


def _script_issues(text: str, *, min_words: int, include_broll: bool = True) -> list[str]:
    issues: list[str] = []
    words = _count_narrable_words(text)
    if words < min_words:
        issues.append(
            f"- Longitud insuficiente: {words} palabras narrables (mínimo {min_words}, sin contar etiquetas)."
        )
    broll = _count_broll_tags(text)
    if include_broll:
        sentences = _count_sentences_narrable(text)
        need = max(0, sentences // 2)
        if broll < need:
            issues.append(
                f"- Faltan etiquetas [B-ROLL: …]: hay {broll} y se necesitan al menos ~{need} "
                f"(aprox. una cada dos oraciones narrables; ~{sentences} oraciones detectadas)."
            )
    else:
        if broll > 0:
            issues.append(
                f"- El guion contiene etiquetas B-ROLL ({broll}) y no debe incluirlas en modo visual estático. Eliminalas."
            )
    return issues


def compose_messages(
    blueprint: ScriptBlueprint,
    *,
    system_extra: str = "",
    user_extra: str = "",
    include_broll: bool = True,
) -> tuple[str, str]:
    """
    Ensambla system/user para el LLM.

    - La **base narrativa** son las plantillas del Catálogo Prompt (+ overlay Script Writer), pasadas como `system_extra` / `user_extra`.
    - Este archivo solo añade datos de sesión y el bloque técnico `technical_pipeline_format_addon` (etiquetas TTS/B-roll),
      visible también cuando no hay plantilla (para que no exista un «prompt oculto» fuera de la app).
    """
    dm = (
        float(blueprint.prompt_duration_minutes)
        if blueprint.prompt_duration_minutes is not None
        else float(blueprint.target_minutes)
    )
    fmt = technical_pipeline_format_addon(blueprint.locale, dm, include_broll=include_broll)
    se = prepare_script_writer_system_prompt((system_extra or "").strip())
    if se:
        system = (se + "\n\n" + fmt) if se else fmt
    else:
        system = (
            fmt
            + "\n\n--- Plantilla de Prompt ---\n"
            "No hay plantilla del Catálogo Prompt cargada en esta ejecución. "
            "En la app: paso **Prompt** → elige una plantilla (voz, tono, arquitectura del guion). "
            "Lo anterior solo fija el contrato técnico de etiquetas; la coherencia narrativa debe venir de esa plantilla.\n"
        )
    user = build_session_user_prompt(blueprint)
    ue = (user_extra or "").strip()
    if ue:
        user = user.rstrip() + f"\n\n{_PROMPT_ADDON_TITLE}\n\n" + ue
    user = prepare_script_writer_user_prompt(
        user, locale=blueprint.locale.value, language_code=blueprint.locale.value
    )
    return system, user


def prompt_builder_preview_payload(blueprint: ScriptBlueprint) -> dict[str, str]:
    """Serializable: vista previa sin LLM (sin plantillas = solo sesión + contrato técnico)."""
    system, user = compose_messages(blueprint, system_extra="", user_extra="")
    return {"system": system, "user": user}


def generate_script(
    blueprint: ScriptBlueprint,
    *,
    provider: str | None = None,
    model: str | None = None,
    system_extra: str = "",
    user_extra: str = "",
    force_single_pass: bool = False,
    per_fragment_segment: bool = False,
    include_broll: bool = True,
    on_progress: ProgressFn | None = None,
) -> str:
    """
    Genera el guion vía **Anthropic** (capa creativa). `provider` de sesión se ignora;
    usa `model` si se indica, si no `ANTHROPIC_MODEL` del entorno.
    """
    if not force_single_pass and _staged_enabled(blueprint.target_minutes):
        if on_progress:
            on_progress(
                f"Guion largo (~{blueprint.target_minutes:.0f} min): generación por etapas con Claude…"
            )
        return _generate_script_staged(
            blueprint,
            provider=provider,
            model=model,
            system_extra=system_extra,
            user_extra=user_extra,
            include_broll=include_broll,
            on_progress=on_progress,
        )

    system, user = compose_messages(
        blueprint,
        system_extra=system_extra,
        user_extra=user_extra,
        include_broll=include_broll,
    )
    from videomaker.llm.llm_routing import call_creative_llm

    def call_llm(user_prompt: str) -> str:
        return call_creative_llm(system=system, user=user_prompt, model=model)

    if on_progress:
        on_progress("Claude: generando guion (paso único)…")

    min_words = _target_words_for_minutes(blueprint.target_minutes, per_fragment=per_fragment_segment)
    max_repairs = 2

    draft = call_llm(user)
    for attempt in range(max_repairs + 1):
        issues = _script_issues(draft, min_words=min_words, include_broll=include_broll)
        if not issues:
            return draft.strip()
        if attempt >= max_repairs:
            return draft.strip()

        repair_instructions = "\n".join(issues)
        repair_prompt = (
            user.rstrip()
            + "\n\n"
            + _PROMPT_ADDON_TITLE
            + "\n\n"
            + "Corrige el borrador completo. Falta:\n"
            + repair_instructions
            + "\nMantén voz y tema. OUTLINE + GUIÓN + KEYWORDS."
            + (" [B-ROLL] cada ~2 frases." if include_broll else " Sin [B-ROLL].")
            + "\n\nBORRADOR:\n"
            + draft.strip()
        )

        draft = call_llm(repair_prompt)

    return draft.strip()


def dry_run_prompt(
    blueprint: ScriptBlueprint,
    *,
    system_extra: str = "",
    user_extra: str = "",
) -> str:
    """Útil para la pantalla de 'previsualizar / editar prompt' sin gastar tokens."""
    system, user = compose_messages(
        blueprint,
        system_extra=system_extra,
        user_extra=user_extra,
    )
    return f"--- SYSTEM ---\n{system}\n\n--- USER ---\n{user}\n"


def split_script_into_segments(
    full_text: str,
    max_chars: int = 900,
    on_chunk: Callable[[int, str], None] | None = None,
) -> list[str]:
    """
    Trocea por párrafos para TTS por fragmentos (menos RAM / reintentos más baratos).
    """
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for p in paragraphs:
        if size + len(p) > max_chars and buf:
            chunk = "\n\n".join(buf)
            chunks.append(chunk)
            if on_chunk:
                on_chunk(len(chunks) - 1, chunk)
            buf = []
            size = 0
        buf.append(p)
        size += len(p) + 2
    if buf:
        chunk = "\n\n".join(buf)
        chunks.append(chunk)
        if on_chunk:
            on_chunk(len(chunks) - 1, chunk)
    return chunks
