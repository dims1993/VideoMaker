"""Máximo de segundos por plano según ``visual_density`` del prompt (scroll-stop)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from videomaker.core import config
from videomaker.scene_editor.section_mapping import section_to_act


def _env_max_hold_override() -> float | None:
    raw = (os.environ.get("VIDEOMAKER_MAX_VISUAL_HOLD_S") or "").strip()
    if not raw:
        return None
    try:
        v = float(raw)
        return v if v >= 2.0 else None
    except ValueError:
        return None


def _label_to_max_s(label: str) -> float:
    t = (label or "").strip().lower()
    if not t:
        return (config.CLIP_DURATION_MIN_S + config.CLIP_DURATION_MAX_S) / 2.0
    if "high" in t or "alta" in t:
        return config.CLIP_DURATION_MIN_S
    if "low" in t or "baja" in t or "intimate" in t:
        return config.CLIP_DURATION_MAX_S
    if "medium" in t or "media" in t:
        return (config.CLIP_DURATION_MIN_S + config.CLIP_DURATION_MAX_S) / 2.0
    return (config.CLIP_DURATION_MIN_S + config.CLIP_DURATION_MAX_S) / 2.0


def _read_prompt_visual_density(work_dir: Path) -> dict[str, str]:
    p = work_dir / "pipeline" / "prompt.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    vd = raw.get("visual_density") if isinstance(raw, dict) else None
    if not isinstance(vd, dict):
        return {}
    return {str(k): str(v) for k, v in vd.items() if str(k).strip()}


def max_visual_hold_s(work_dir: Path, *, section: str | None = None) -> float:
    """
    Segundos máximos con un solo plano antes de exigir corte visual.

    Prioridad: ``VIDEOMAKER_MAX_VISUAL_HOLD_S`` → ``visual_density`` por acto/sección.
    """
    override = _env_max_hold_override()
    if override is not None:
        return override

    vd = _read_prompt_visual_density(work_dir)
    act = section_to_act(section)
    if act in ("hook", "intro"):
        return _label_to_max_s(vd.get("hook", "high"))
    if act in ("outro", "cierre", "closing"):
        return _label_to_max_s(vd.get("emotional_reveal", "low + intimate"))
    return _label_to_max_s(vd.get("middle_explanation", "medium"))


def shots_needed_for_duration(duration_s: float, max_hold_s: float) -> int:
    if duration_s <= 0 or max_hold_s <= 0:
        return 1
    if duration_s <= max_hold_s + 0.25:
        return 1
    import math

    return min(8, max(2, int(math.ceil(duration_s / max_hold_s))))
