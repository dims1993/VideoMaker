"""Tests lenguaje visual del body."""

from __future__ import annotations

from videomaker.llm.body_visual_language import (
    PILLAR_IDS,
    apply_body_visual_pipeline,
    apply_per_pillar_anchor_hierarchy,
    assign_visual_pillars,
    infer_visual_pillar,
)


def test_pillar_from_act():
    assert infer_visual_pillar("acto_2", 0, 10) == "pillar_1"
    assert infer_visual_pillar("acto_3", 5, 10) == "pillar_2"
    assert infer_visual_pillar("acto_4", 9, 10) == "pillar_3"


def test_one_anchor_per_pillar():
    beats = [
        {"index": i, "act": f"acto_{2 + i // 4}", "text_anchor": f"beat {i}", "track": "insert"}
        for i in range(12)
    ]
    beats[2]["text_anchor"] = "older woman in fleece vest warm kitchen"
    beats[6]["text_anchor"] = "alone at screen small apartment night"
    beats[10]["text_anchor"] = "two worlds contrast unfair truth"
    tiered = assign_visual_pillars(beats)
    out, meta = apply_per_pillar_anchor_hierarchy(tiered)
    anchors = [b for b in out if b.get("is_anchor_shot")]
    assert len(anchors) == len(PILLAR_IDS)
    assert meta["anchor_count"] == 3


def test_pipeline_enriches_prompts_with_color():
    beats = [
        {"index": 0, "act": "acto_2", "track": "insert", "text_anchor": "outline point one"},
        {"index": 1, "act": "acto_2", "track": "insert", "text_anchor": "fleece vest woman suburban"},
    ]
    out, plan = apply_body_visual_pipeline(beats, body_pool_s=120.0)
    assert plan.get("pillar_counts")
    insert = [b for b in out if b.get("track") == "insert"]
    assert all("warm amber" in str(b.get("ai_prompt") or "").lower() or "cool blue" in str(b.get("ai_prompt") or "").lower() for b in insert)
    anchor = next(b for b in out if b.get("is_anchor_shot"))
    assert "ANCHOR" in anchor["ai_prompt"] or "fleece" in anchor["ai_prompt"].lower()
