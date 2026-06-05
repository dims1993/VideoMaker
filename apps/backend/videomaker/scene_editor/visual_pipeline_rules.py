"""Reglas del pipeline visual: defaults del servidor y resolución desde settings."""

from __future__ import annotations

from typing import Any

from videomaker.scene_editor.scene_visual_settings_store import default_settings

PLANNER_BUILTIN_RULES_EN = """PRIORITY (strict):
1. NARRATION = what the viewer hears — this is your ONLY story source (no separate editor/B-roll hints).
2. Each block MUST look visually different from previous blocks (new setting, props, composition, body pose, and action).

Rules:
- Include concrete nouns FROM THE NARRATION (degree, job, retirement, influencer, article, etc.).
- Follow PROTAGONIST ACTION & POSE rules above — never default to hand-on-chin thinker or idle center observer.
- NEVER repeat the same action verb or pose as the previous block — vary gesture even when narration is similar (screens and whiteboards are OK if narration needs them).
- If narration contrasts two ideas → split/diptych frame showing BOTH sides.
- If narration lists several achievements → montage in one 16:9 frame covering ALL items.
- The recurring character MUST match PROTAGONIST FACE + WARDROBE above — always bare head, no hat/cap/hood/beanie unless narration explicitly says so.
- Van life, influencers, or couples in the narration: show them in vignettes/screens only; the protagonist keeps black shirt + messy brown hair + cartoon face.
- Object-focused scenes (phone screen, calculator): still mention the protagonist's hands/face/wardrobe from PROTAGONIST.
- No filler: inviting atmosphere, gentle shadows, sense of accomplishment, wooden table budget app (unless narration is about budgeting).
- Do NOT repeat base style, Avoid, 16:9, 2K, or the full PROTAGONIST block in scene_prompt_en — embed traits naturally in the action.
- Read NARRATION emotional tone and set protagonist_expression_key accordingly — vary expression across blocks as the story shifts."""

GEMINI_CONTINUITY_PREFIX_DEFAULT = (
    "Same illustration style and same protagonist design as described below — "
    "COMPLETELY DIFFERENT scene (new location, props, camera angle, body pose, and action — not a repeat). "
    "Do NOT reuse thinker pose (hand on chin), idle center observer, or seated contemplation. Scene:"
)

AUTO_AVOID_SUPPLEMENT_DEFAULT = (
    "hat, cap, beanie, hood, headwear, baseball cap, "
    "hand on chin, thinker pose, idle standing center, arms crossed staring"
)

SCENE_VALIDATION_RULES_ES = [
    "Frases de pose prohibidas en escena: mano en barbilla, thinker pose, brazos cruzados mirando, observador pasivo en el centro.",
    "Palabras de ánimo pasivo sin acción: thoughtful, contemplative, pensive, gazing reflectively.",
    "Relleno genérico prohibido: inviting atmosphere, wooden table budget app, gentle shadows (salvo que la narración lo pida).",
    "Cada escena necesita verbo de acción física o encuadre de manos / over-shoulder / POV.",
]

EXTRA_STYLE_FIELD_KEYS = (
    "planner_extra_rules_en",
    "gemini_continuity_prefix_en",
    "auto_avoid_supplement_en",
)


def resolved_planner_extra_rules(settings: dict[str, Any]) -> str:
    custom = str(settings.get("planner_extra_rules_en") or "").strip()
    return custom or PLANNER_BUILTIN_RULES_EN


def resolved_gemini_continuity_prefix(settings: dict[str, Any]) -> str:
    custom = str(settings.get("gemini_continuity_prefix_en") or "").strip()
    return custom or GEMINI_CONTINUITY_PREFIX_DEFAULT


def resolved_auto_avoid_supplement(settings: dict[str, Any]) -> str:
    custom = str(settings.get("auto_avoid_supplement_en") or "").strip()
    if custom:
        return custom
    return AUTO_AVOID_SUPPLEMENT_DEFAULT


def effective_rules_preview(settings: dict[str, Any]) -> dict[str, Any]:
    """Qué reglas aplicará el motor con los ajustes actuales (para la UI)."""
    from videomaker.scene_editor.protagonist_expressions import expressions_catalog_from_settings
    from videomaker.scene_editor.scene_visual_settings_store import (
        _DEFAULT_PROTAGONIST,
        _DEFAULT_PROTAGONIST_ACTION_RULES,
        _DEFAULT_PROTAGONIST_EXPRESSIONS,
        _DEFAULT_PROTAGONIST_WARDROBE,
        _DEFAULT_AVOID,
        _DEFAULT_BASE_STYLE,
    )
    from videomaker.scene_editor.visual_prompt_compose import effective_avoid_en

    defaults = default_settings()
    fallback_used: dict[str, str] = {}
    for key, fallback in (
        ("base_style_en", _DEFAULT_BASE_STYLE),
        ("protagonist_en", _DEFAULT_PROTAGONIST),
        ("protagonist_wardrobe_en", _DEFAULT_PROTAGONIST_WARDROBE),
        ("protagonist_action_rules_en", _DEFAULT_PROTAGONIST_ACTION_RULES),
        ("protagonist_expressions_en", _DEFAULT_PROTAGONIST_EXPRESSIONS),
        ("avoid_en", _DEFAULT_AVOID),
    ):
        if not str(settings.get(key) or "").strip():
            fallback_used[key] = fallback

    return {
        "fallback_used_when_empty": fallback_used,
        "effective_avoid_en": effective_avoid_en(settings),
        "planner_extra_rules_en": resolved_planner_extra_rules(settings),
        "planner_extra_rules_is_custom": bool(
            str(settings.get("planner_extra_rules_en") or "").strip()
        ),
        "gemini_continuity_prefix_en": resolved_gemini_continuity_prefix(settings),
        "gemini_continuity_prefix_is_custom": bool(
            str(settings.get("gemini_continuity_prefix_en") or "").strip()
        ),
        "auto_avoid_supplement_en": resolved_auto_avoid_supplement(settings),
        "auto_avoid_supplement_is_custom": bool(
            str(settings.get("auto_avoid_supplement_en") or "").strip()
        ),
        "expression_catalog_count": len(expressions_catalog_from_settings(settings)),
        "scene_validation_rules_es": SCENE_VALIDATION_RULES_ES,
        "builtin_defaults": {
            "planner_extra_rules_en": PLANNER_BUILTIN_RULES_EN,
            "gemini_continuity_prefix_en": GEMINI_CONTINUITY_PREFIX_DEFAULT,
            "auto_avoid_supplement_en": AUTO_AVOID_SUPPLEMENT_DEFAULT,
            **{k: defaults[k] for k in defaults if k.endswith("_en")},
        },
    }
