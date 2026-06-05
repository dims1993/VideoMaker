"""Tests para arco de secuencia documental del gancho."""

from __future__ import annotations

from videomaker.llm.hook_visual_sequence import (
    BLOCK_IDS,
    apply_camera_motion_to_beat,
    block_id_for_beat_index,
    block_quotas,
    default_camera_motion_for_beat,
    finalize_hook_visual_sequence,
    merge_color_language_into_prompt,
    prompt_has_color_language,
    sequence_context_for_counterpoint,
    sequence_context_for_counterpoint_batch,
)


def test_block_quotas_sum_to_n():
    for n in (1, 4, 7, 30, 31):
        counts = block_quotas(n)
        assert len(counts) == 4
        assert sum(counts) == n


def test_block_id_follows_arc_order():
    n = 12
    ids = [block_id_for_beat_index(i, n) for i in range(n)]
    assert ids[0] == "intimate_close"
    assert "contrast_world" in ids
    assert ids[-1] == "intimate_weight"


def test_finalize_no_consecutive_same_distance_angle():
    beats = [{"index": i, "visual_description": f"scene {i} unique subject {i}"} for i in range(8)]
    out, plan = finalize_hook_visual_sequence(beats, target_beats=8)
    assert plan.get("beat_count") == 8
    assert len(out) == 8
    prev = None
    for b in out:
        key = (b["shot_distance"], b["shot_angle"])
        assert key != prev
        assert b["sequence_block"] in BLOCK_IDS
        assert b.get("camera", {}).get("shot")
        prev = key


def test_finalize_fixes_duplicate_llm_pair():
    beats = [
        {
            "index": 0,
            "sequence_block": "intimate_close",
            "shot_distance": "close_up",
            "shot_angle": "eye_level",
        },
        {
            "index": 1,
            "sequence_block": "intimate_close",
            "shot_distance": "close_up",
            "shot_angle": "eye_level",
        },
    ]
    out, plan = finalize_hook_visual_sequence(beats)
    assert (out[0]["shot_distance"], out[0]["shot_angle"]) != (
        out[1]["shot_distance"],
        out[1]["shot_angle"],
    )
    assert int(plan.get("violations_fixed") or 0) >= 1


def test_sequence_context_lists_shots():
    beats, _ = finalize_hook_visual_sequence(
        [{"index": i} for i in range(4)],
        target_beats=4,
    )
    ctx = sequence_context_for_counterpoint(beats, {"emotional_tone": "quiet exhaustion"})
    assert "intimate_close" in ctx
    assert "Shots in order:" in ctx
    assert "quiet exhaustion" in ctx


def test_finalize_assigns_cool_vs_warm_by_block():
    beats = [{"index": i, "visual_description": f"person in scene {i}"} for i in range(12)]
    out, plan = finalize_hook_visual_sequence(beats, target_beats=12)
    cool_blocks = {"intimate_close", "medium_space", "intimate_weight"}
    for b in out:
        block = b["sequence_block"]
        vis = str(b.get("visual_description") or "").lower()
        if block in cool_blocks:
            assert b.get("color_temperature") in ("cool", "cool_neutral")
            assert "warm amber" not in vis
        if block == "contrast_world":
            assert b.get("color_temperature") == "warm"
            assert "warm" in vis or "amber" in vis or "golden" in vis or "tungsten" in vis
    assert plan.get("color_language", {}).get("chromatic_argument")


def test_merge_color_adds_phrase_when_missing():
    p = merge_color_language_into_prompt("lonely kitchen at night", "intimate_close")
    assert prompt_has_color_language(p)


def test_contrast_block_gets_pull_out_motion():
    beat = {"purpose": "curiosity", "emotion": "tension", "pacing_role": "tension_rise"}
    assert default_camera_motion_for_beat(beat, "contrast_world") == "slow_pull_out"
    b = apply_camera_motion_to_beat(beat, "contrast_world")
    assert b["camera_motion_direction"] == "out"


def test_finalize_alternates_motion_direction():
    beats = [
        {"index": i, "purpose": "curiosity", "emotion": "tension", "visual_description": f"scene {i}"}
        for i in range(6)
    ]
    out, plan = finalize_hook_visual_sequence(beats)
    dirs = [b["camera_motion_direction"] for b in out]
    for a, b in zip(dirs, dirs[1:]):
        if a != "none" and b != "none":
            assert a != b
    assert plan.get("motion_direction_fixes") is not None


def test_batch_context_includes_continuity_and_slice():
    beats, _ = finalize_hook_visual_sequence([{"index": i} for i in range(12)], target_beats=12)
    ctx = sequence_context_for_counterpoint_batch(
        beats,
        {"emotional_tone": "quiet exhaustion"},
        batch_start=10,
        batch_end=12,
        prior_prompts=["prior shot A", "prior shot B"],
    )
    assert "beats 10–11" in ctx
    assert "Continuity" in ctx
    assert "prior shot" in ctx
    assert "quiet exhaustion" in ctx
