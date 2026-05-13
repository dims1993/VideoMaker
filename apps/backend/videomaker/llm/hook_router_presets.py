"""Plantillas visuales predefinidas (gancho finanzas / educación)."""

from __future__ import annotations

from typing import Any

# IDs estables para UI y JSON
FINANCE_STYLE_IDS = (
    "deep_documentary",
    "data_minimalist",
    "financial_noir",
    "intimate_pov",
)

FINANCE_VISUAL_STYLES: dict[str, dict[str, Any]] = {
    "deep_documentary": {
        "id": "deep_documentary",
        "label": 'The "Deep Documentary" (Nick Invests)',
        "opening_architecture_hint": "Hiperconcreto / documental introspectivo",
        "lighting": "Claroscuro, luz lateral (rembrandt), sombras profundas.",
        "composition": (
            "Planos detalle (macro) de objetos cotidianos (café, teclado, reloj). "
            "Profundidad de campo muy baja (fondo desenfocado)."
        ),
        "color_palette": ["tierra", "azul medianoche", "negro mate", "madera"],
        "ia_keywords": (
            "Cinematic, moody lighting, shot on 35mm, shallow depth of field, "
            "realistic textures, grainy film look"
        ),
        "typography_hint": "Serif clásica (Times / Playfair Display), pequeña y elegante.",
        "editing_fps_hint": 24,
    },
    "data_minimalist": {
        "id": "data_minimalist",
        "label": 'The "Data Minimalist"',
        "opening_architecture_hint": "Paradoja estadística / dato contundente",
        "lighting": "Blanca, neutra, estilo estudio Apple. Sin sombras agresivas.",
        "composition": (
            "Espacio negativo amplio. Gráficos vectoriales limpios sobre fondos sólidos "
            "o texturas papel premium."
        ),
        "color_palette": ["blanco roto", "gris ceniza", "verde esmeralda", "naranja quemado"],
        "ia_keywords": (
            "Clean, minimal, high-end vector, paper texture, soft shadows, isometric, 4k, "
            "architectural photography"
        ),
        "typography_hint": "Sans geométrica (Montserrat / Inter), negrita, muy legible.",
        "editing_fps_hint": 30,
    },
    "financial_noir": {
        "id": "financial_noir",
        "label": 'The "Financial Noir"',
        "opening_architecture_hint": "Coste silencioso / mercados / sistema global",
        "lighting": "Fría, luces de ciudad, neones lejanos, reflejos en cristal, lluvia.",
        "composition": (
            "Planos generales (wide) de ciudades, aeropuertos o centros financieros; "
            "ángulos bajos (poder)."
        ),
        "color_palette": ["azul eléctrico", "gris metálico", "cian"],
        "ia_keywords": (
            "Cyberpunk corporate, rainy city streets, glass reflections, drone shot, "
            "blue hour, high contrast, sharp details"
        ),
        "typography_hint": "Monospace (Roboto Mono), estilo terminal / ticker.",
        "editing_fps_hint": 24,
    },
    "intimate_pov": {
        "id": "intimate_pov",
        "label": 'The "Intimate POV"',
        "opening_architecture_hint": "Invitación mental / identificación (Piensa en…)",
        "lighting": "Cálida, luz natural ventana, golden hour.",
        "composition": (
            "Primera persona o over-the-shoulder; handheld ligero (realismo)."
        ),
        "color_palette": ["cálidos", "naranja", "crema", "orgánicos"],
        "ia_keywords": (
            "POV, lifestyle photography, warm sunlight, authentic moment, handheld camera, "
            "soft focus, morning vibes"
        ),
        "typography_hint": "Typewriter o cursiva muy limpia.",
        "editing_fps_hint": 30,
    },
}
