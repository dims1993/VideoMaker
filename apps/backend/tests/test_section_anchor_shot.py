"""Tests plano ancla por sección."""

from __future__ import annotations

from videomaker.llm.section_anchor_shot import (
    apply_hook_anchor_hierarchy,
    infer_hook_anchor_beat_index,
)


def test_anchor_lands_in_intimate_weight_block():
    beats = [
        {"index": i, "sequence_block": b, "intensity": 50 + i}
        for i, b in enumerate(
            ["intimate_close"] * 4
            + ["medium_space"] * 4
            + ["contrast_world"] * 4
            + ["intimate_weight"] * 4
        )
    ]
    idx = infer_hook_anchor_beat_index(beats)
    assert beats[idx]["sequence_block"] == "intimate_weight"


def test_exactly_one_anchor_shot():
    beats = [{"index": i, "sequence_block": "intimate_close", "intensity": i * 5} for i in range(12)]
    beats[-3]["sequence_block"] = "intimate_weight"
    beats[-2]["visual_description"] = "thumb closes banking app, screen goes dark"
    out, plan = apply_hook_anchor_hierarchy(beats)
    anchors = [b for b in out if b.get("is_anchor_shot")]
    assert len(anchors) == 1
    assert plan["anchor_beat_index"] == anchors[0]["index"]
    assert sum(1 for b in out if b.get("shot_hierarchy") == "afterglow") >= 1
    assert sum(1 for b in out if b.get("shot_hierarchy") in ("support", "support_build")) >= 4
