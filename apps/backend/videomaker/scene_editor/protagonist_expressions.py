"""Expresiones faciales del protagonista — catálogo + inferencia desde narración."""

from __future__ import annotations

import re
from typing import Any

# Formato en settings: una línea por expresión → key: descripción visual en inglés
_DEFAULT_EXPRESSIONS_CATALOG: dict[str, str] = {
    "neutral": "calm circular eyes, relaxed mouth line, attentive but composed",
    "concerned": "slightly furrowed cartoon brows, worried circular eyes, tight small mouth",
    "shocked": "circular eyes widened, small round open mouth, raised brows in surprise",
    "skeptical": "one raised brow, flat unimpressed mouth, sideways doubtful glance",
    "frustrated": "brows angled down, pressed lips, tense jaw in simple cartoon lines",
    "hopeful": "soft slight smile, bright circular eyes, lifted cheeks with blush",
    "realization": "eyes widened with insight, small o-shaped mouth, brows raised in discovery",
    "determined": "focused straight-on gaze, firm set mouth, forward-leaning energy",
    "dismissive": "half-lidded circular eyes, flat mouth, unimpressed look",
    "curious": "head slightly tilted, one brow raised, interested open circular eyes",
    "relieved": "soft exhale smile, relaxed brows, eased shoulders",
    "overwhelmed": "wide stressed eyes, wavy mouth line, subtle sweat drop in cartoon style",
}

_DEFAULT_EXPRESSIONS_LINES = "\n".join(f"{k}: {v}" for k, v in _DEFAULT_EXPRESSIONS_CATALOG.items())

_EMOTION_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("shocked", ("reject", "denied", "impossible", "four minutes", "can't believe", "shock", "surprised")),
    ("frustrated", ("can't", "cannot", "stuck", "harder", "sacrifice", "unfair", "wrong with you")),
    ("skeptical", ("doubt", "question", "advice", "influencer", "really?", "sure about")),
    ("concerned", ("worry", "afford", "manageable", "pressure", "struggling", "anxious", "risk")),
    ("realization", ("threshold", "rose", "snapped", "noticing", "realize", "what changed", "that's when")),
    ("curious", ("ask", "what changed", "different question", "start noticing", "wonder")),
    ("hopeful", ("approved", "manageable", "possible", "opportunity", "chance")),
    ("determined", ("must", "need to", "decide", "commit", "fix")),
    ("overwhelmed", ("too much", "everywhere", "piling up", "all at once")),
    ("relieved", ("approved", "finally", "works out", "got it")),
    ("dismissive", ("doesn't make", "ignore", "whatever", "not your fault")),
]


def default_expressions_catalog_text() -> str:
    return _DEFAULT_EXPRESSIONS_LINES


def parse_expressions_catalog(text: str) -> dict[str, str]:
    out = dict(_DEFAULT_EXPRESSIONS_CATALOG)
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, desc = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        desc = desc.strip()
        if key and desc:
            out[key] = desc
    return out


def expressions_catalog_from_settings(settings: dict[str, Any]) -> dict[str, str]:
    raw = str(settings.get("protagonist_expressions_en") or "").strip()
    return parse_expressions_catalog(raw) if raw else dict(_DEFAULT_EXPRESSIONS_CATALOG)


def expression_en_for_key(key: str, catalog: dict[str, str]) -> str:
    k = (key or "").strip().lower().replace(" ", "_")
    return catalog.get(k) or catalog.get("neutral", _DEFAULT_EXPRESSIONS_CATALOG["neutral"])


def infer_expression_from_narration(narration: str, catalog: dict[str, str] | None = None) -> str:
    """Heurística EN/ES sobre el tono emocional del voiceover."""
    _ = catalog
    low = (narration or "").lower()
    if not low.strip():
        return "neutral"
    scores: dict[str, int] = {}
    for key, hints in _EMOTION_HINTS:
        scores[key] = sum(1 for h in hints if h in low)
    best = max(scores.items(), key=lambda x: x[1])
    if best[1] >= 1:
        return best[0]
    if "?" in narration:
        return "curious"
    if any(w in low for w in ("but ", "however", "yet ", "still ")):
        return "concerned"
    return "neutral"


def resolve_protagonist_expression(
    *,
    narration: str,
    llm_key: str | None,
    catalog: dict[str, str],
) -> tuple[str, str]:
    key = (llm_key or "").strip().lower().replace(" ", "_")
    if key not in catalog:
        key = infer_expression_from_narration(narration, catalog)
    if key not in catalog:
        key = "neutral"
    return key, expression_en_for_key(key, catalog)


def expressions_planner_block(catalog: dict[str, str]) -> str:
    lines = "\n".join(f"  - {k}: {v}" for k, v in catalog.items())
    return (
        "PROTAGONIST FACIAL EXPRESSIONS (pick ONE key per block from NARRATION emotion — vary across blocks):\n"
        f"{lines}\n"
        "Match the voiceover tone: shock at rejection, concern about affordability, skepticism about advice, "
        "realization at a turning point, etc. Never default to neutral if narration carries clear emotion."
    )


def scene_has_expression_described(scene: str) -> bool:
    low = (scene or "").lower()
    return bool(
        re.search(
            r"\b(expression|facial|brows|mouth|smile|frown|worried|shocked|surprised|concerned)\b",
            low,
        )
    )


def apply_protagonist_expression(scene: str, expression_en: str) -> str:
    base = (scene or "").strip().rstrip(".")
    expr = (expression_en or "").strip().rstrip(".")
    if not base or not expr:
        return scene or ""
    if scene_has_expression_described(base):
        return base + ("." if not base.endswith(".") else "")
    return f"{base}. Protagonist facial expression: {expr}."
