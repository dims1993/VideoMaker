"""Texto de plantillas incluidas en Videomaker (referencia única, psicología narrativa mínima)."""

from __future__ import annotations

from videomaker.llm.prompt_writer_contract import bundled_prompt_narrative_extra

# Plantilla 1 · Psicología y finanzas
YOUTUBE_PSYCH_FINANCE_USER_EXTRA = bundled_prompt_narrative_extra(
    language_code="es",
    channel_hint=(
        "Canal reflexivo psicología + finanzas: el espectador llega con culpa o comparación; "
        "el vídeo debe devolver agencia sin sermón motivacional."
    ),
)

# Plantilla 2 · Reflexivo ~10 min
REFLECTIVE_10MIN_USER_EXTRA = bundled_prompt_narrative_extra(
    language_code="es",
    channel_hint=(
        "Vídeo reflexivo ~10 min: ritmo calmado, imagen mental concreta, cierre con pregunta abierta — "
        "no resumen tipo clase."
    ),
)
