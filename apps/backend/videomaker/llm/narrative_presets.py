"""Presets de reparto temporal por categoría narrativa (4 actos). Orientativo; editable por plantilla."""

from __future__ import annotations

from typing import Any, TypedDict


class NarrativePreset(TypedDict):
    id: str
    name: str
    weights: tuple[float, float, float, float]
    descriptions: tuple[str, str, str, str]


# Pesos = fracción del tiempo total del pipeline (suman 1). Solo aplica a structure_preset four_act.
NARRATIVE_PRESETS: dict[str, NarrativePreset] = {
    "finanzas": {
        "id": "finanzas",
        "name": "Finanzas / Documental",
        "weights": (0.15, 0.25, 0.45, 0.15),
        "descriptions": (
            "Hook & Contraste",
            "El Mapa / La Empatía",
            "El Núcleo (La Carne)",
            "Cierre & Identidad",
        ),
    },
    "entretenimiento": {
        "id": "entretenimiento",
        "name": "Entretenimiento / Viral",
        "weights": (0.25, 0.20, 0.40, 0.15),
        "descriptions": ("Hyper-Hook", "Contexto rápido", "Clímax / Giro", "Salida"),
    },
    "tutorial": {
        "id": "tutorial",
        "name": "Tutorial / Técnico",
        "weights": (0.10, 0.15, 0.65, 0.10),
        "descriptions": ("Promesa", "Preparación", "Paso a paso", "Resultado"),
    },
    "ventas": {
        "id": "ventas",
        "name": "Marketing / Ventas (VSL)",
        "weights": (0.20, 0.30, 0.30, 0.20),
        "descriptions": ("Dolor", "Agitación", "Solución / Prueba", "CTA / Urgencia"),
    },
}


def list_narrative_presets() -> list[NarrativePreset]:
    return list(NARRATIVE_PRESETS.values())


def weights_for_narrative_preset(preset_id: str | None) -> list[float] | None:
    if not preset_id:
        return None
    key = str(preset_id).strip().lower()
    p = NARRATIVE_PRESETS.get(key)
    if not p:
        return None
    return list(p["weights"])
