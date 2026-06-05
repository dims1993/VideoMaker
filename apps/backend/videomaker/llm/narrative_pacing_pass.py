"""Narrative Pacing Pass — ritmo, duración objetivo y directrices del autor."""

from __future__ import annotations

import json
from typing import Any

from videomaker.llm.llm_routing import call_creative_llm
from videomaker.llm.output_language import language_label, resolve_output_language
from videomaker.llm.prompt_instruction_contract import editorial_governance_block
from videomaker.llm.script_output_contract import script_writer_format_block


def _count_narrable_words(text: str) -> int:
    from videomaker.llm.script_gen import _count_narrable_words

    return _count_narrable_words(text)


def _target_words_for_minutes(target_minutes: float) -> int:
    from videomaker.llm.script_gen import _target_words_for_minutes

    return _target_words_for_minutes(target_minutes, per_fragment=False)


def _estimated_minutes_from_words(words: int) -> float:
    from videomaker.llm.script_gen import _wpm_default

    wpm = _wpm_default()
    return round(words / wpm, 1) if wpm > 0 else 0.0


def _system(lang: str, *, trim_to_duration: bool) -> str:
    label = language_label(lang)
    fmt = script_writer_format_block(locale=lang)
    governance = editorial_governance_block(language_code=lang, locale=lang)
    trim_block = ""
    if trim_to_duration:
        trim_block = """
DURATION (mandatory when current draft exceeds target):
- If the draft is longer than the target minutes/word budget, SHORTEN it: cut redundancy, tighten pillars, merge repetitive beats.
- Preserve OUTLINE + act structure, [CATEGORIA] headers, and every [B-ROLL] tag that remains narratively necessary.
- Do not delete whole acts unless the author explicitly asked; prefer compression inside sections.
- After trimming, narrable word count must fall within ~95–108% of the target word budget (not above).
"""
    return f"""You are the **editor / development pass** on a finished draft — not the screenwriter.
Shape retention, pacing, breathing, and density using the analysis and author notes below.
Output language: {label} ({lang}).

{governance}

Apply ALL of the following that apply:
- loosen dense blocks (mundane detail, shorter sentences, breathing) where still too dense AFTER any trim
- add humanity (without meta-commentary) where the draft feels cold
- preserve facts, structure, and [CATEGORIA] / [B-ROLL] tags
{trim_block}
Do NOT add EDITORIAL ANALYSIS or production notes.

{fmt}

Return the full revised document in the same creation format (OUTLINE + GUIÓN/SCRIPT + KEYWORDS)."""


def apply_narrative_pacing_pass(
    script_text: str,
    editorial_analysis: dict[str, Any] | None = None,
    *,
    topic_title: str = "",
    output_language: str | None = None,
    target_minutes: float | None = None,
    trim_to_duration: bool = True,
    user_directives: str = "",
) -> tuple[str, dict[str, Any]]:
    """
    Reescribe el guion. Devuelve (texto, meta con conteos antes/después).
    """
    text = (script_text or "").strip()
    if len(text) < 200:
        raise ValueError("Guion demasiado corto para pacing pass.")

    lang = resolve_output_language(explicit=output_language, transcript_text=text)
    words_before = _count_narrable_words(text)
    min_before = _estimated_minutes_from_words(words_before)

    target_m = float(target_minutes) if target_minutes and target_minutes > 0 else None
    target_words: int | None = None
    if target_m:
        target_words = _target_words_for_minutes(target_m)

    analysis_blob = ""
    if editorial_analysis:
        analysis_blob = json.dumps(editorial_analysis, ensure_ascii=False, indent=2)

    duration_section = ["--- DURATION TARGET ---"]
    if target_m and target_words:
        duration_section.append(f"Target spoken duration: {target_m:.1f} minutes")
        duration_section.append(f"Target narrable words: ~{target_words} (approximate, exclude tags)")
        duration_section.append(f"Current draft: ~{min_before} min, {words_before} narrable words")
        if trim_to_duration and words_before > int(target_words * 1.05):
            duration_section.append(
                "ACTION: Shorten the draft to fit the target. Cut length first, then improve pacing."
            )
        elif words_before < int(target_words * 0.85):
            duration_section.append(
                "Draft is under target; you may expand slightly while improving pacing (do not pad)."
            )
        else:
            duration_section.append(
                "Draft is near target length; focus on pacing and clarity without major length change."
            )
    else:
        duration_section.append("(no minute target — pacing and clarity only)")

    author_block = ""
    ud = (user_directives or "").strip()
    if ud:
        author_block = "\n".join(
            [
                "--- AUTHOR DIRECTIVES (mandatory — apply precisely) ---",
                ud,
            ]
        )

    user = "\n".join(
        [
            f"Topic: {topic_title.strip() or '(not provided)'}",
            "",
            "\n".join(duration_section),
            "",
            author_block,
            "",
            "--- EDITORIAL ANALYSIS (apply fixes, do not copy into output) ---",
            analysis_blob or "(none — run Editorial Analyzer for richer notes)",
            "",
            "--- SCRIPT TO REVISE ---",
            text[:80_000],
        ]
    ).strip()

    revised = call_creative_llm(
        system=_system(lang, trim_to_duration=bool(trim_to_duration and target_m)),
        user=user,
        temperature=0.45,
    ).strip()

    words_after = _count_narrable_words(revised)
    meta = {
        "words_before": words_before,
        "words_after": words_after,
        "minutes_before_est": min_before,
        "minutes_after_est": _estimated_minutes_from_words(words_after),
        "target_minutes": target_m,
        "target_words": target_words,
        "trim_to_duration": bool(trim_to_duration and target_m),
        "had_user_directives": bool(ud),
        "had_editorial_analysis": bool(editorial_analysis),
    }
    return revised, meta
