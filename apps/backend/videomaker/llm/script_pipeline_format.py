"""
Contrato técnico mínimo del Script Writer (etiquetas parseables).
Voz y tema: plantilla Prompt + sesión. Sin reglas editoriales aquí.
"""

from __future__ import annotations

from videomaker.core.models import Locale, ScriptBlueprint
from videomaker.llm.script_output_contract import script_writer_format_block


def build_session_user_prompt(blueprint: ScriptBlueprint) -> str:
    dm = (
        float(blueprint.prompt_duration_minutes)
        if blueprint.prompt_duration_minutes is not None
        else float(blueprint.target_minutes)
    )
    kw = ", ".join(blueprint.keywords) if blueprint.keywords else "—"
    ctx = blueprint.extra_context.strip() or "—"
    return f"Tema: {kw}\nContexto: {ctx}\nDuración ~{dm:.0f} min."


def technical_pipeline_format_addon(
    locale: Locale, target_minutes: float, *, include_broll: bool = True
) -> str:
    dm = float(target_minutes)
    lang = "en" if locale == Locale.EN else "es"
    fmt = script_writer_format_block(locale=lang)
    broll = "" if include_broll else ("\nSin etiquetas [B-ROLL]." if lang == "es" else "\nNo [B-ROLL] tags.")
    return f"~{dm:.0f} min hablados.{broll}\n{fmt}"
