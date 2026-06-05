"""Ajustes visuales del Scene Editor — estilo base + protagonista (Nano Banana 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARTIFACT = "scene_visual_settings.json"

_DEFAULT_BASE_STYLE = (
    "Cinematic documentary still, editorial photography, muted warm palette, "
    "natural motivated lighting, shallow depth of field, subtle 35mm film grain, 16:9"
)

_DEFAULT_PROTAGONIST = (
    "The viewer's stand-in: a person in their early 30s experiencing the financial moment "
    "described in the narration — shown in medium shot, over-the-shoulder, or close-up on hands "
    "when the scene is object-focused (phone, calculator, app screen)."
)

_DEFAULT_PROTAGONIST_WARDROBE = (
    "messy dark brown hair, warm light-tan skin, black long-sleeve shirt, "
    "bare head with no hat cap hood or beanie"
)

_DEFAULT_AVOID = (
    "stock photo feel, generic office, cartoon, watermark, text overlays unless specified, "
    "extra fingers, blurry, oversaturated colors"
)

_DEFAULT_PROTAGONIST_ACTION_RULES = (
    "POSE & ACTION (every block):\n"
    "- Give the protagonist a SPECIFIC physical action from the narration "
    "(flipping a document page, marking a form, scrolling a phone, walking, handing papers, "
    "comparing printouts, pointing at a prop when narration requires it).\n"
    "- NEVER repeat the same action or pose as the PREVIOUS block — vary gesture even if narration is similar.\n"
    "- Vary body pose and camera every block: full-body side view, over-shoulder, hands close-up, "
    "walking mid-step, reaching.\n"
    "- BANNED without narration support: hand on chin, Rodin thinker, arms crossed staring, idle center observer.\n"
    "- Montage blocks: protagonist ACTS on props; screens/whiteboards/papers are all OK when narration names them.\n"
    "- Prefer concrete verbs over mood words: avoid thoughtful, contemplative, gazing reflectively, pensive."
)

_DEFAULT_PROTAGONIST_EXPRESSIONS = (
    "neutral: calm circular eyes, relaxed mouth line, attentive but composed\n"
    "concerned: slightly furrowed cartoon brows, worried circular eyes, tight small mouth\n"
    "shocked: circular eyes widened, small round open mouth, raised brows in surprise\n"
    "skeptical: one raised brow, flat unimpressed mouth, sideways doubtful glance\n"
    "frustrated: brows angled down, pressed lips, tense jaw in simple cartoon lines\n"
    "hopeful: soft slight smile, bright circular eyes, lifted cheeks with blush\n"
    "realization: eyes widened with insight, small o-shaped mouth, brows raised in discovery\n"
    "determined: focused straight-on gaze, firm set mouth, forward-leaning energy\n"
    "dismissive: half-lidded circular eyes, flat mouth, unimpressed look\n"
    "curious: head slightly tilted, one brow raised, interested open circular eyes\n"
    "relieved: soft exhale smile, relaxed brows, eased shoulders\n"
    "overwhelmed: wide stressed eyes, wavy mouth line, subtle sweat drop in cartoon style"
)


def _path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / ARTIFACT


def default_settings() -> dict[str, Any]:
    return {
        "version": 1,
        "target_generator": "nano_banana",
        "base_style_en": _DEFAULT_BASE_STYLE,
        "protagonist_en": _DEFAULT_PROTAGONIST,
        "protagonist_wardrobe_en": _DEFAULT_PROTAGONIST_WARDROBE,
        "protagonist_action_rules_en": _DEFAULT_PROTAGONIST_ACTION_RULES,
        "protagonist_expressions_en": _DEFAULT_PROTAGONIST_EXPRESSIONS,
        "avoid_en": _DEFAULT_AVOID,
        "planner_extra_rules_en": "",
        "gemini_continuity_prefix_en": "",
        "auto_avoid_supplement_en": "",
        "aspect_ratio": "16:9",
        "output_spec": "2K output",
    }


def read_scene_visual_settings(work_dir: Path) -> dict[str, Any]:
    p = _path(work_dir)
    if not p.is_file():
        return default_settings()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return default_settings()
        out = default_settings()
        out.update({k: v for k, v in raw.items() if v is not None})
        return out
    except Exception:
        return default_settings()


def _field_from_payload(data: dict[str, Any], key: str, fallback: str) -> str:
    if key in data:
        return str(data.get(key) or "").strip()
    return str(fallback or "").strip()


def write_scene_visual_settings(work_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    base = default_settings()
    payload = {
        "version": 1,
        "target_generator": "nano_banana",
        "base_style_en": _field_from_payload(data, "base_style_en", base["base_style_en"]),
        "protagonist_en": _field_from_payload(data, "protagonist_en", base["protagonist_en"]),
        "protagonist_wardrobe_en": _field_from_payload(
            data, "protagonist_wardrobe_en", base["protagonist_wardrobe_en"]
        ),
        "protagonist_action_rules_en": _field_from_payload(
            data, "protagonist_action_rules_en", base["protagonist_action_rules_en"]
        ),
        "protagonist_expressions_en": _field_from_payload(
            data, "protagonist_expressions_en", base["protagonist_expressions_en"]
        ),
        "avoid_en": _field_from_payload(data, "avoid_en", base["avoid_en"]),
        "planner_extra_rules_en": _field_from_payload(
            data, "planner_extra_rules_en", base["planner_extra_rules_en"]
        ),
        "gemini_continuity_prefix_en": _field_from_payload(
            data, "gemini_continuity_prefix_en", base["gemini_continuity_prefix_en"]
        ),
        "auto_avoid_supplement_en": _field_from_payload(
            data, "auto_avoid_supplement_en", base["auto_avoid_supplement_en"]
        ),
        "aspect_ratio": _field_from_payload(data, "aspect_ratio", "16:9") or "16:9",
        "output_spec": _field_from_payload(data, "output_spec", "2K output") or "2K output",
    }
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    _path(work_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
