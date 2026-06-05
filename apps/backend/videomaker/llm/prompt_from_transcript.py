"""Inferencia de plantilla Prompt a partir de transcripciones del canal."""

from __future__ import annotations

import json
import re
from typing import Any

from videomaker.llm.output_language import language_label, resolve_output_language
from videomaker.llm.prompt_instruction_contract import split_user_instructions
from videomaker.llm.prompt_writer_contract import (
    PROMPT_WRITER_ROLE_EN,
    PROMPT_WRITER_ROLE_ES,
    compress_narrative_if_long,
    derigidify_narrative,
    golden_rule_reminder,
    prompt_writer_narrative_skeleton,
)

_PROMPT_SYSTEM_TEMPLATE = """
You are a narrative compression engine and creative director for YouTube channels — NOT a copywriter or "prompt enhancer".

{role}

Your task: read channel transcripts and produce a prompt template JSON for a later **Script Writer**.
Describe psychology, tension, movement, worldview, realism, and narrative gravity — NOT wording formulas, transitions, or rhetorical templates.

## Design principles

### Compression
Distill the channel into the 10 narrative sections below (2–5 lines each; bullets OK). No essay lists of 50 rules.

### Derigidification — NEVER output:
- Literal commands ("Use…", "Say…", "Insert…", "Open with…")
- Retention/hook/B-roll/OUTLINE/GUIÓN/TTS rules (section 11 is ONLY in the app's output_structure — do not put it in user_instructions_narrative)
- Visible storytelling formulas ("Section A", "five pillars", metronome pacing)

GOLDEN RULE examples:
- BAD: "Use rhetorical questions." → GOOD: "The viewer should feel internally conflicted before major realizations."
- BAD: "Use a nobody tells you moment." → GOOD: "Include at least one reframing where the mechanism works differently than assumed."
- BAD: "Use conversational asides." → GOOD: "The narration should occasionally feel personally observed rather than formally presented."

### Direction (sections 1–10)
Fill user_instructions_narrative using EXACTLY these headers (replace parenthetical hints with inferred channel-specific content):

{skeleton}

Section notes:
1. **Creative north star** — emotional aboutness, viewer feeling, intellectual shift (very short).
2. **Core mechanism** — the real engine (critical; without it scripts become opinion/monologue).
3. **Viewer psychology** — starting belief, entry emotion, narrative shift, emotional movement chain.
4. **Tone profile** — emotional ratios, not stylistic commands; optional one-line JSON sliders 0–1.
5. **Narrative movement** — revelation progression + pacing feel; do NOT prescribe exact script sections.
6. **Visual world** — recurring physical reality for cinematic/B-roll cohesion.
7. **Human texture** — mundane grounding; anti-trailer/poetic drift.
8. **Intellectual standard** — cumulative reasoning; anti fake-smart certainty.
9. **Naturalness constraint** — naturalness overrides optimization (mandatory substance, not empty header).
10. **Forbidden patterns** — explicit drift traps (meta-hooks, guru, doomposting, etc.).

## Field policy
- system_instructions: channel voice + permanent role rules + ## {identity_heading} (psychology labels for tono/gancho/estilo_visual — no quoted catchphrases).
- user_instructions_narrative: sections 1–10 only (~4000 characters max).
- params_json.target_audience: viewer profile from transcripts.
- params_json.narrative_structure: tone / hook_type / cta_type as **psychological summaries** (one short phrase each), never imperative copy.
- Do NOT return language_context or target_duration_minutes.
- All strings in {output_language_label} ({lang}).

Return ONLY valid JSON:
{{
  "name": "<short template name>",
  "system_instructions": "<voice + ## {identity_heading}>",
  "user_instructions_narrative": "<sections 1–10 filled>",
  "params_json": {{
    "target_audience": "<who watches — psychology>",
    "narrative_structure": {{
      "tone": "<tone profile summary>",
      "hook_type": "<opening psychology — not a phrase>",
      "cta_type": "<closure psychology — not a script>"
    }}
  }}
}}
""".strip()


def _prompt_system(output_language: str) -> str:
    code = output_language if output_language in ("en", "es") else "es"
    heading = "channel_identity" if code == "en" else "identidad_del_canal"
    role = PROMPT_WRITER_ROLE_EN if code == "en" else PROMPT_WRITER_ROLE_ES
    return _PROMPT_SYSTEM_TEMPLATE.format(
        role=role,
        output_language_label=language_label(code),
        lang=code,
        identity_heading=heading,
        skeleton=prompt_writer_narrative_skeleton(language_code=code),
    )


def generate_prompt_template_from_transcript(
    *,
    transcript_text: str,
    output_language: str | None = None,
    channel_language: str | None = None,
    provider: str = "anthropic",
    model: str = "",
) -> dict[str, Any]:
    """Analiza transcripciones y devuelve el JSON de plantilla inferida."""
    from videomaker.llm.avatar_prompt_writer import _call_llm

    text = (transcript_text or "").strip()
    if len(text) < 50:
        raise ValueError("Se necesita más texto de transcripciones (mín. ~50 caracteres)")
    lang = resolve_output_language(
        explicit=output_language,
        channel_language=channel_language,
        transcript_text=text,
    )

    user_msg = (
        f"Analyze these channel transcripts. Output language: {language_label(lang)} ({lang}).\n\n"
        + text[:40_000]
        + "\n\n"
        + golden_rule_reminder(language_code=lang)
        + "\n\nProduce the JSON template. Sections 1–10 only in user_instructions_narrative."
    )

    from videomaker.llm.llm_routing import CREATIVE_PROVIDER, resolve_creative_model

    raw = _call_llm(
        system=_prompt_system(lang),
        user=user_msg,
        provider=CREATIVE_PROVIDER,
        model=resolve_creative_model(model),
        temperature=0.4,
    )

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    result = json.loads(cleaned)
    if not isinstance(result, dict):
        raise ValueError("LLM JSON must be an object")
    if not str(result.get("user_instructions_narrative") or "").strip():
        legacy = str(result.get("user_instructions") or "").strip()
        if legacy:
            result["user_instructions_narrative"] = legacy
    raw_narr = str(result.get("user_instructions_narrative") or "").strip()
    if raw_narr:
        raw_narr = derigidify_narrative(raw_narr)
        raw_narr = compress_narrative_if_long(raw_narr)
        _out_part, narr_only = split_user_instructions(raw_narr)
        result["user_instructions_narrative"] = narr_only
    pj = result.get("params_json")
    if isinstance(pj, dict):
        pj.pop("channel_expressions", None)
        ns = pj.get("narrative_structure")
        if isinstance(ns, dict):
            for key in ("tone", "hook_type", "cta_type"):
                val = str(ns.get(key) or "").strip()
                if val:
                    ns[key] = derigidify_narrative(val) or val
    result["output_language"] = lang
    return result
