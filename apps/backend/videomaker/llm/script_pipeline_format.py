"""
Contrato técnico común del pipeline de guion (etiquetas TTS/B-roll).

La **voz, ritmo y arquitectura narrativa** las define la plantilla del paso **Prompt**
(y el overlay de Script Writer), editable en la app. Este módulo solo asegura salida
parseable y compatible con el resto del sistema — sin imponer «tres pilares» ni
«cinco bloques» ocultos fuera de las plantillas.
"""

from __future__ import annotations

from textwrap import dedent

from videomaker.core.models import Locale, ScriptBlueprint


def build_session_user_prompt(blueprint: ScriptBlueprint) -> str:
    """Solo datos de sesión (keywords, contexto, duración). Sin mandatos narrativos ocultos."""
    dm = (
        float(blueprint.prompt_duration_minutes)
        if blueprint.prompt_duration_minutes is not None
        else float(blueprint.target_minutes)
    )
    kw = ", ".join(blueprint.keywords) if blueprint.keywords else "(sin palabras clave)"
    ctx = blueprint.extra_context.strip() or "(sin contexto adicional)"
    parts = [
        "Datos de la sesión del pipeline:",
        f"- Palabras clave / tema: {kw}",
        f"- Contexto adicional del creador: {ctx}",
        f"- Duración orientativa total de narración: ~{dm:.1f} min.",
    ]
    if blueprint.categories:
        parts.extend(["", "Secciones opcionales (beats definidos en código):"])
        for c in blueprint.categories:
            beats = "\n".join(f"  - {b}" for b in c.beats)
            parts.append(f"### {c.title}\n{beats}")
    parts.extend(
        [
            "",
            "La narrativa (cuántas partes, tono, profundidad) la marca la plantilla del Catálogo Prompt "
            "en la app; este bloque solo aporta tema y contexto de sesión.",
        ]
    )
    return "\n".join(parts).strip()


def technical_pipeline_format_addon(locale: Locale, target_minutes: float) -> str:
    """Reglas de formato compartidas (salida que el pipeline puede procesar)."""
    dm = float(target_minutes)
    if locale == Locale.EN:
        return _technical_en(dm)
    return _technical_es(dm)


def _technical_es(dm: float) -> str:
    return dedent(
        f"""
        Formato de salida Videomaker (obligatorio para el pipeline):
        - Primero un OUTLINE con tiempos orientativos por parte, coherente con las instrucciones de tu plantilla de Prompt / Script Writer.
        - Luego el GUIÓN con `[CATEGORIA: …]` al inicio de cada bloque según esa misma arquitectura (no impongas desde aquí un número fijo de secciones).
        - Inserta `[B-ROLL: descripción concreta]` aproximadamente cada dos frases narrables, en el punto donde debe cambiar la imagen (no al final del párrafo ni del guion). El TTS no lee estas etiquetas.
        - Al final, una línea con 8–12 keywords en inglés separadas por comas como referencia visual (moodboard / equipo de imagen).
        - Referencia de duración total hablada del vídeo: ~{dm:.1f} min (orientativo).
        - Evita Markdown decorativo dentro del texto hablado si puede interferir con el TTS.
        """
    ).strip()


def _technical_en(dm: float) -> str:
    return dedent(
        f"""
        Videomaker output format (required for the pipeline):
        - Start with an OUTLINE with rough timings per section, aligned with your Prompt / Script Writer template.
        - Then the script with `[CATEGORIA: …]` at the start of each block following that architecture (do not impose a fixed section count from here).
        - Insert `[B-ROLL: concrete description]` roughly every two spoken sentences, where the cut should happen (not bunched at paragraph end). TTS does not read these tags.
        - End with one line: 8–12 English keywords comma-separated as visual reference for the team or image generation.
        - Target spoken length reference: ~{dm:.1f} min (orientative).
        """
    ).strip()

