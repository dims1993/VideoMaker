"""Editorial Analyzer — diagnóstico sobre guion terminado (no creación)."""

from __future__ import annotations

import json
import re
from typing import Any

from videomaker.llm.llm_routing import call_creative_llm
from videomaker.llm.output_language import language_label, resolve_output_language
from videomaker.llm.prompt_instruction_contract import editorial_governance_block


def _system(lang: str) -> str:
    label = language_label(lang)
    governance = editorial_governance_block(language_code=lang, locale=lang)
    return f"""You are an editorial analyst for YouTube scripts. Output language: {label} ({lang}).

{governance}

You receive a FINISHED script. Do NOT rewrite it. Diagnose only.

Return ONLY valid JSON:
{{
  "pacing_notes": ["bullet", "..."],
  "retention_notes": ["bullet", "..."],
  "emotional_arcs": "short paragraph on emotional movement",
  "density_problems": ["where explanation stacks without breathing room"],
  "visual_strategy": ["how B-roll / visuals support or fail the story"],
  "cta_analysis": "how the close / CTA lands (or if missing)"
}}

Be concrete. Reference moments or sections. No generic YouTube advice."""

def analyze_script(
    script_text: str,
    *,
    topic_title: str = "",
    narrative_context: str = "",
    target_minutes: float | None = None,
    output_language: str | None = None,
) -> dict[str, Any]:
    text = (script_text or "").strip()
    if len(text) < 200:
        raise ValueError("Se necesita un guion más largo para analizar (mín. ~200 caracteres).")
    lang = resolve_output_language(explicit=output_language, transcript_text=text)
    parts = [
        f"Topic: {topic_title.strip() or '(not provided)'}",
        f"Target duration (min): {target_minutes if target_minutes else '(not provided)'}",
    ]
    if narrative_context.strip():
        parts.extend(["", "Narrative angle context:", narrative_context.strip()])
    parts.extend(["", "--- SCRIPT ---", text[:80_000]])
    raw = call_creative_llm(system=_system(lang), user="\n".join(parts), temperature=0.25)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Editorial analysis must be a JSON object")
    return {
        "pacing_notes": _as_str_list(data.get("pacing_notes")),
        "retention_notes": _as_str_list(data.get("retention_notes")),
        "emotional_arcs": str(data.get("emotional_arcs") or "").strip(),
        "density_problems": _as_str_list(data.get("density_problems")),
        "visual_strategy": _as_str_list(data.get("visual_strategy")),
        "cta_analysis": str(data.get("cta_analysis") or "").strip(),
        "output_language": lang,
    }


def _as_str_list(val: Any) -> list[str]:
    if not isinstance(val, list):
        return []
    return [str(x).strip() for x in val if str(x).strip()][:20]
