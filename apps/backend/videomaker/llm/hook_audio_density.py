"""Densifica micro_beats del gancho según duración de audio (más cortes = más retención)."""

from __future__ import annotations

import copy
import re
from typing import Any

from videomaker.llm.hook_retention_router import (
    PLATFORM_PRESETS,
    _split_hook_into_phrases,
    build_beats_rule_based,
    classify_hook_class,
    compute_viral_intensity_curve,
)
from videomaker.llm.section_density_plan import SectionDensityPlan


def _beat_duration(b: dict[str, Any]) -> float:
    try:
        return max(0.1, float(b.get("end_sec") or 0) - float(b.get("start_sec") or 0))
    except (TypeError, ValueError):
        return 1.0


def _split_longest_hook_beat(beats: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    if len(beats) < 1:
        return None
    idx = max(range(len(beats)), key=lambda i: _beat_duration(beats[i]))
    b = beats[idx]
    dur = _beat_duration(b)
    if dur < 2.0:
        return None
    start = float(b.get("start_sec") or 0)
    end = float(b.get("end_sec") or start + dur)
    mid = start + dur / 2.0
    left = copy.deepcopy(b)
    right = copy.deepcopy(b)
    left["end_sec"] = round(mid, 3)
    right["start_sec"] = round(mid, 3)
    right["index"] = int(b.get("index", idx)) + 1
    out = beats[:idx] + [left, right] + beats[idx + 1 :]
    for i, row in enumerate(out):
        row["index"] = i
    return out


def densify_hook_micro_beats(
    micro_beats: list[dict[str, Any]],
    hook_text: str,
    plan: SectionDensityPlan,
    *,
    platform: str,
    visual_energy: str,
) -> list[dict[str, Any]]:
    """Aumenta micro_beats hasta ``plan.hook_target_images`` (cortes ~3.5s)."""
    target = plan.hook_target_images
    beats = [b for b in micro_beats if isinstance(b, dict)]
    if len(beats) >= target:
        return beats

    phrases = _split_hook_into_phrases(hook_text)
    if len(phrases) >= target:
        hook_class = classify_hook_class(hook_text)
        preset = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["youtube"])
        beat_sec = plan.hook_target_hold_s
        n = min(len(phrases), target)
        curve = compute_viral_intensity_curve(n, visual_energy, platform=platform)
        from videomaker.llm.hook_retention_router import _default_beat

        rebuilt: list[dict[str, Any]] = []
        t = 0.0
        for i, phrase in enumerate(phrases[:n]):
            end = t + beat_sec
            rebuilt.append(
                _default_beat(
                    index=i,
                    start=t,
                    end=end,
                    phrase=phrase,
                    hook_class=hook_class,
                    platform=platform,
                    energy=visual_energy,
                    intensity=curve[i] if i < len(curve) else 70,
                    n_beats=n,
                )
            )
            t = end
        return rebuilt

    beats = build_beats_rule_based(
        hook_text,
        platform=platform,
        visual_energy=visual_energy,
        max_beats=min(target, max(len(phrases), len(beats) + 4)),
    )
    guard = 0
    while len(beats) < target and guard < 80:
        guard += 1
        next_beats = _split_longest_hook_beat(beats)
        if not next_beats or len(next_beats) <= len(beats):
            break
        beats = next_beats
    return beats
