"""Tests ritmo visual vs narrativo."""

from __future__ import annotations

from videomaker.llm.narrative_visual_rhythm import (
    apply_hook_narrative_rhythm,
    body_rhythm_tier,
    hook_rhythm_tier,
)


def test_hook_fast_on_tension():
    beat = {"purpose": "contradiction", "emotion": "fear", "intensity": 85}
    assert hook_rhythm_tier(beat) == "fast"


def test_hook_slow_on_contrast_block():
    beat = {"sequence_block": "contrast_world", "purpose": "curiosity"}
    assert hook_rhythm_tier(beat) == "slow"


def test_hook_timeline_sums_to_pool():
    beats = [
        {"index": i, "purpose": "contradiction" if i < 4 else "payoff_release", "intensity": 80}
        for i in range(8)
    ]
    out, summary = apply_hook_narrative_rhythm(beats, 90.0)
    total = sum(float(b["duration_sec"]) for b in out)
    assert abs(total - 90.0) < 0.2
    assert summary["tier_counts"].get("fast", 0) >= 1
    assert summary["tier_counts"].get("slow", 0) >= 1
    assert summary["duration_range_s"][0] < summary["duration_range_s"][1]


def test_body_slow_on_reflective_anchor():
    beat = {"text_anchor": "Finally, the truth is that silence weighs more than debt."}
    assert body_rhythm_tier(beat) == "slow"
