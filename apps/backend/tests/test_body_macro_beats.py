"""Tests para preservación de track y suplemento de macro_beats."""

from __future__ import annotations

from videomaker.llm.body_macro_beats import (
    contextual_composition_hint,
    expand_block_with_max_hold,
    extract_outline_bullets,
    finalize_macro_beats,
    normalize_macro_beats,
    supplement_macro_beats_from_script,
)


def test_avatar_parent_never_splits():
    anchor = (
        "A homeowner checks Zillow and sees their house appreciated forty-seven "
        "thousand dollars this year—more than they earned from their actual job."
    )
    rows = expand_block_with_max_hold(
        anchor,
        max_hold_s=5.0,
        parent_track="avatar",
    )
    assert len(rows) == 1
    assert rows[0]["track"] == "avatar"
    assert "split_reason" not in rows[0]
    assert rows[0]["text_anchor"] == anchor


def test_insert_parent_stays_insert_on_split():
    anchor = (
        "A homeowner checks Zillow and sees their house appreciated forty-seven "
        "thousand dollars this year—more than they earned from their actual job. "
        "Retirement calculator showing net worth disparity."
    )
    rows = expand_block_with_max_hold(
        anchor,
        max_hold_s=4.0,
        parent_track="insert",
        parent_ai_prompt="Close-up Zillow UI, cinematic.",
    )
    assert len(rows) >= 2
    assert all(r["track"] == "insert" for r in rows)
    assert all(r.get("ai_prompt") for r in rows)


def test_finalize_preserves_llm_insert_track():
    llm_beats = [
        {
            "act": "acto_2",
            "text_anchor": "City council meeting with yard sign testimony against duplex.",
            "track": "insert",
            "ai_prompt": "Council room B-roll.",
        },
        {
            "act": "acto_4",
            "text_anchor": "Parent offers down payment help while house gained value.",
            "track": "avatar",
        },
    ]
    bundle = {
        "style_consistency": {"lighting": "cinematic", "composition": "desk macro"},
        "llm_enrichment": {"macro_beats": llm_beats},
    }
    body = """
**PILLAR 1**
- A homeowner checks Zillow and sees appreciation
- Retirement calculator net worth chart
- City council meeting yard sign testimony
"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        (work / "pipeline").mkdir()
        out = finalize_macro_beats(work, bundle, body)
    beats = out["macro_beats"]
    tracks = [b["track"] for b in beats]
    assert "avatar" in tracks
    assert tracks.count("avatar") >= 1
    assert tracks.count("insert") >= 2
    assert not any(
        b.get("split_reason") == "max_hold" and b["track"] == "avatar"
        for b in beats
    )


def test_outline_bullets_extracted():
    text = """
**PILLAR 1 — wealth**
- First bullet about Zillow and home prices today.
- Second bullet about retirement calculator numbers.
"""
    bullets = extract_outline_bullets(text)
    assert len(bullets) >= 2


def test_supplement_adds_missing_outline():
    existing = normalize_macro_beats(
        [
            {
                "act": "acto_2",
                "text_anchor": "Only one beat about money.",
                "track": "insert",
            }
        ]
    )
    body = """
**PILLAR 1**
- Unique bullet about teacher budget spreadsheet savings.
- Another bullet about Reddit homeowners from 2008.
- Third bullet about financial advice article assumptions.
"""
    more = supplement_macro_beats_from_script(existing, body)
    assert len(more) >= 3


def test_contextual_composition_not_desk_for_civic():
    hint = contextual_composition_hint(
        "City council meeting yard sign duplex",
        "desk macro keyboard",
    )
    assert "teclado" in hint.lower() or "escritorio" in hint.lower() or "cívico" in hint.lower()


def test_target_beat_count_from_script():
    from pathlib import Path
    import tempfile
    from videomaker.llm.body_audio_density import target_macro_beat_count

    body = "word " * 3000  # ~20 min speech est
    with tempfile.TemporaryDirectory() as td:
        n = target_macro_beat_count(Path(td), body)
    assert n >= 12


def test_split_oversized_prompt_assignments():
    from pathlib import Path
    import tempfile
    from videomaker.llm.body_audio_density import split_oversized_prompt_assignments

    p = {"id": "body_1", "text_anchor": "A long anchor. " * 20, "track": "insert"}
    with tempfile.TemporaryDirectory() as td:
        out_p, out_ms = split_oversized_prompt_assignments(
            Path(td), [p], [120_000], section="body"
        )
    assert len(out_p) >= 2
    assert sum(out_ms) == 120_000
