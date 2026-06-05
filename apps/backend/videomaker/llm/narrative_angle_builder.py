"""Narrative Angle Builder — tema → tesis emocional + mecanismo + conflicto humano (mínimo)."""

from __future__ import annotations

import json
import re
from typing import Any

from videomaker.llm.llm_routing import call_creative_llm
from videomaker.llm.output_language import language_label, resolve_output_language

_ANGLE_KEYS = (
    "core_tension",
    "central_question",
    "main_mechanism",
    "emotional_arc",
    "viewer_transformation",
    "narrative_promise",
    "primary_symbol",
    "forbidden_directions",
)

_LEGACY_KEY_MAP = {
    "tension": "core_tension",
    "emotional_promise": "narrative_promise",
}


def _system(lang: str) -> str:
    label = language_label(lang)
    return f"""You transform a video TOPIC into a short narrative angle. Output language: {label} ({lang}).

You receive ONLY: topic, audience, channel_style, constraints (duration, tone).
Do NOT ask for pacing rules, hooks, retention, B-roll, or storytelling systems.

Return ONLY valid JSON with EXACTLY these keys (no extras):
{{
  "core_tension": "one sentence — human conflict under the topic (not a slogan)",
  "central_question": "one sentence — the question the video answers",
  "main_mechanism": "one sentence — how the system/incentives actually work",
  "emotional_arc": ["5 short labels", "e.g. self-blame", "confusion", "clarity"],
  "viewer_transformation": "one sentence — what shifts in the viewer's self-understanding",
  "narrative_promise": "one sentence — what this video will deliver (specific, not hype)",
  "primary_symbol": "few words — one visual metaphor prop/scene",
  "forbidden_directions": ["3-5 short labels", "what NOT to do tonally"]
}}

Rules:
- Write like a human story lens, not a YouTube optimization doc.
- No script lines, no outline, no hook copy, no retention/pacing notes.
- emotional_arc: 4-6 items, each 1-4 words.
- forbidden_directions: 3-5 items, concrete tonal traps to avoid.
- Prefer plain scenes over aphorisms ("locked house" > "this is not a market, it is a mechanism")."""


def _as_str_list(val: Any, *, max_items: int = 8) -> list[str]:
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()][:max_items]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def normalize_narrative_angle(data: dict[str, Any]) -> dict[str, Any]:
    """Unifica JSON nuevo o legacy (tension / emotional_promise)."""
    out: dict[str, Any] = {}
    for key in _ANGLE_KEYS:
        if key in data and data[key] not in (None, ""):
            out[key] = data[key]
    for old, new in _LEGACY_KEY_MAP.items():
        if new not in out or not out.get(new):
            legacy = data.get(old)
            if legacy:
                out[new] = legacy
    if isinstance(out.get("emotional_arc"), str):
        out["emotional_arc"] = [s.strip() for s in out["emotional_arc"].split(",") if s.strip()]
    out["emotional_arc"] = _as_str_list(out.get("emotional_arc"), max_items=6)
    out["forbidden_directions"] = _as_str_list(out.get("forbidden_directions"), max_items=6)
    for key in ("core_tension", "central_question", "main_mechanism", "viewer_transformation", "narrative_promise", "primary_symbol"):
        out[key] = str(out.get(key) or "").strip()
    return out


def build_narrative_angle_input(
    *,
    topic: str,
    audience: str = "",
    channel_style: str = "",
    duration_minutes: float | None = None,
    tone: str = "",
) -> dict[str, Any]:
    """Payload mínimo que recibe el builder (y se guarda en el artefacto)."""
    constraints: dict[str, Any] = {}
    if duration_minutes is not None and duration_minutes > 0:
        constraints["duration"] = round(float(duration_minutes), 1)
    if tone.strip():
        constraints["tone"] = tone.strip()
    return {
        "topic": topic.strip(),
        "audience": (audience or "").strip() or "—",
        "channel_style": (channel_style or "").strip() or "—",
        "constraints": constraints,
    }


def build_narrative_angle(
    angle_input: dict[str, Any],
    *,
    output_language: str | None = None,
    channel_language: str | None = None,
) -> dict[str, Any]:
    """
    `angle_input` = build_narrative_angle_input(...) — solo topic/audience/channel_style/constraints.
  """
    topic = str(angle_input.get("topic") or "").strip()
    if not topic:
        raise ValueError("Narrative angle requires a topic title.")

    lang = resolve_output_language(
        explicit=output_language,
        channel_language=channel_language,
        transcript_text=topic,
    )
    user = json.dumps(angle_input, ensure_ascii=False, indent=2)
    raw = call_creative_llm(
        system=_system(lang),
        user=f"Input:\n{user}\n\nReturn the narrative angle JSON only.",
        temperature=0.35,
    )
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Narrative angle must be a JSON object")

    angle = normalize_narrative_angle(data)
    if not any(angle.get(k) for k in ("core_tension", "central_question", "main_mechanism", "narrative_promise")):
        raise ValueError("Narrative angle JSON is empty")

    return {
        "input": angle_input,
        **angle,
        "output_language": lang,
        "source_topic_title": topic,
    }


def narrative_angle_context_text(na: dict[str, Any]) -> str:
    """Texto compacto para Script Writer / prompt (sin reglas editoriales)."""
    if not na:
        return ""
    norm = normalize_narrative_angle(na)
    lines: list[str] = []
    if norm.get("core_tension"):
        lines.append(f"Tensión: {norm['core_tension']}")
    if norm.get("central_question"):
        lines.append(f"Pregunta: {norm['central_question']}")
    if norm.get("main_mechanism"):
        lines.append(f"Mecanismo: {norm['main_mechanism']}")
    arc = norm.get("emotional_arc") or []
    if arc:
        lines.append("Arco: " + " → ".join(arc))
    if norm.get("viewer_transformation"):
        lines.append(f"Transformación: {norm['viewer_transformation']}")
    if norm.get("narrative_promise"):
        lines.append(f"Promesa: {norm['narrative_promise']}")
    if norm.get("primary_symbol"):
        lines.append(f"Símbolo: {norm['primary_symbol']}")
    forb = norm.get("forbidden_directions") or []
    if forb:
        lines.append("Evitar: " + ", ".join(forb))
    return "\n".join(lines)
