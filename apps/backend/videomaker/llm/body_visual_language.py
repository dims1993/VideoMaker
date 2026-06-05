"""Lenguaje visual del body: pilares, anclas, subtexto, composición, color, ritmo."""

from __future__ import annotations

import re
from typing import Any

PILLAR_IDS = ("pillar_1", "pillar_2", "pillar_3")

PILLAR_SPEC: dict[str, dict[str, Any]] = {
    "pillar_1": {
        "label": "Domestic suburban comfort",
        "visual_zone": "domestic interiors, warm suburban comfort, older people at ease",
        "color_temperature": "warm",
        "light_phrase": "warm amber interior, natural golden window light, soft tungsten",
        "palette": ["warm amber", "honey gold", "cream walls", "soft sage green", "fleece earth tones"],
        "composition_for_animation": "subject on right third, warm window or doorway left — room to pull back",
        "camera_motion": "slow_pull_out",
        "subtext_lens": "generational ease, material comfort, stability — never illustrate spoken dollar amounts literally",
        "forbidden": "cold phone glow, cramped night apartment, harsh fluorescent isolation",
    },
    "pillar_2": {
        "label": "Functional solitude",
        "visual_zone": "screens, small spaces, artificial light, functional solitude",
        "color_temperature": "cool",
        "light_phrase": "cool blue artificial light, screen glow, flat fluorescent, deep shadows",
        "palette": ["cool blue", "cyan screen cast", "slate grey", "charcoal shadow", "muted steel"],
        "composition_for_animation": "subject low center or left third, negative space above for slow push-in",
        "camera_motion": "slow_push_in",
        "subtext_lens": "quiet exhaustion, mental load, alone with systems — not literal app names from narration",
        "forbidden": "suburban warmth, older couples at tea, golden hour porches",
    },
    "pillar_3": {
        "label": "Two worlds in tension",
        "visual_zone": "both worlds colliding — hard cut, no dissolve, visual argument",
        "color_temperature": "split",
        "light_phrase": "warm amber left frame vs cool blue right frame, chromatic clash, no smooth blend",
        "palette": ["warm amber vs cool blue", "split lighting", "high contrast", "visual tension"],
        "composition_for_animation": "diptych or split frame — warm domestic vs cold screen, static or subtle push",
        "camera_motion": "static",
        "subtext_lens": "structural unfairness visible in the frame — contrast without narrating the thesis aloud",
        "forbidden": "single neutral palette, illustrative stock office, happy family montage",
    },
}

_PILLAR1_ANCHOR = re.compile(
    r"\b(fleece|forro polar|polar|older woman|mujer mayor|parents|padres|suburban|"
    r"chaleco|porch|jardín|garden|warm kitchen|cozy)\b",
    re.I,
)
_PILLAR2_ANCHOR = re.compile(
    r"\b(alone|sola|screen|pantalla|apartment|apartamento|small kitchen|spreadsheet|"
    r"calculator|calculadora|overdraft|deuda|night|noche|fluorescent)\b",
    re.I,
)
_PILLAR3_ANCHOR = re.compile(
    r"\b(two worlds|dos mundos|contrast|contraste|while they|mientras ellos|"
    r"generational|generación|unfair|injusto|that's why|por eso|the truth|la verdad)\b",
    re.I,
)
_EMOTION_FROM_TEXT = [
    (re.compile(r"\b(fear|miedo|panic|ansiedad|anxiety|worry)\b", re.I), "quiet anxiety"),
    (re.compile(r"\b(anger|rabia|frustrat|injust)\b", re.I), "controlled frustration"),
    (re.compile(r"\b(hope|esperanza|relief|alivio)\b", re.I), "cautious relief"),
    (re.compile(r"\b(truth|verdad|realize|entiend)\b", re.I), "dawning clarity"),
    (re.compile(r"\b(alone|sola|silence|silencio)\b", re.I), "functional solitude"),
    (re.compile(r"\b(comfort|calor|cálido|warm|cozy)\b", re.I), "material ease"),
]


def body_visual_system_addon() -> str:
    zones = "\n".join(
        f"- {pid}: {PILLAR_SPEC[pid]['visual_zone']} · color: {PILLAR_SPEC[pid]['light_phrase']}"
        for pid in PILLAR_IDS
    )
    return f"""
BODY VISUAL LANGUAGE (mandatory — all six rules, no exceptions):

1) VISUAL ZONES BY PILLAR (define BEFORE any image; every beat gets visual_pillar):
{zones}
- pillar_1 → acto_2 / first third of body
- pillar_2 → acto_3 / middle third
- pillar_3 → acto_4+ / final third — hard cut tension between worlds

2) SHOT HIERARCHY: exactly ONE anchor per pillar (is_anchor_shot=true, shot_hierarchy=anchor).
   Support beats: clean neutral prompts. Anchor beats: rich, specific, memorable (e.g. woman in fleece vest).

3) EMOTIONAL SUBTEXT — dual channel: NEVER illustrate narration nouns literally.
   Provide emotional_state + visual_subtext per beat; ai_prompt shows felt truth, not spoken props.

4) COMPOSITION FOR ANIMATION: composition_for_animation + subject_position (left_third|right_third|center_low|center_high).

5) COLOR: every ai_prompt MUST include pillar light_phrase / color_temperature.

6) BODY RHYTHM: holds 4–6s support, 5–8s anchor — stability for intellectual argument; do NOT over-split beats.

Root JSON must include:
"body_visual_plan": {{
  "pillars": {{"pillar_1": {{...}}, "pillar_2": {{...}}, "pillar_3": {{...}}}},
  "rules": ["zones", "anchor_per_pillar", "subtext_not_literal", "composition_for_animation", "color", "slow_rhythm"]
}}

Each macro_beat MUST include:
visual_pillar, color_temperature, light_quality, color_palette[], emotional_state, visual_subtext,
shot_hierarchy (support|support_build|anchor|afterglow), is_anchor_shot, composition_for_animation,
subject_position, camera_motion, rhythm_tier (medium|slow; slow for anchor)
"""


def default_body_visual_plan() -> dict[str, Any]:
    return {
        "pillars": {pid: {k: v for k, v in spec.items() if k != "forbidden"} for pid, spec in PILLAR_SPEC.items()},
        "rules": [
            "visual_zones_by_pillar",
            "anchor_vs_support_hierarchy",
            "narrative_rhythm_slow",
            "emotional_subtext_not_literal",
            "composition_for_animation",
            "consistent_color_per_zone",
        ],
        "body_hold_target_s": "4–6 support · 5–8 anchor",
    }


def infer_visual_pillar(act: str, beat_index: int, total: int) -> str:
    act_l = (act or "").strip().lower()
    if "2" in act_l or act_l in ("intro", "introduction"):
        return "pillar_1"
    if "3" in act_l:
        return "pillar_2"
    if any(x in act_l for x in ("4", "5", "cta", "cierre", "outro")):
        return "pillar_3"
    if total <= 0:
        return "pillar_1"
    t = beat_index / max(total - 1, 1)
    if t < 0.34:
        return "pillar_1"
    if t < 0.67:
        return "pillar_2"
    return "pillar_3"


def _infer_emotional_state(anchor: str) -> str:
    for pat, label in _EMOTION_FROM_TEXT:
        if pat.search(anchor):
            return label
    return "quiet cognitive tension"


def _pillar_anchor_score(beat: dict[str, Any], pillar: str) -> int:
    anchor = str(beat.get("text_anchor") or "")
    score = len(re.findall(r"\w+", anchor)) // 3
    try:
        score += int(beat.get("intensity") or 0) // 4
    except (TypeError, ValueError):
        pass
    markers = {
        "pillar_1": _PILLAR1_ANCHOR,
        "pillar_2": _PILLAR2_ANCHOR,
        "pillar_3": _PILLAR3_ANCHOR,
    }
    if markers.get(pillar) and markers[pillar].search(anchor):
        score += 50
    if str(beat.get("composition_hint") or "").strip():
        score += 5
    return score


def _build_support_prompt(beat: dict[str, Any], spec: dict[str, Any]) -> str:
    subtext = str(beat.get("visual_subtext") or spec["subtext_lens"])[:120]
    comp = str(beat.get("composition_for_animation") or spec["composition_for_animation"])
    pos = str(beat.get("subject_position") or "right_third")
    light = spec["light_phrase"]
    emotion = str(beat.get("emotional_state") or "quiet tension")
    return (
        f"Editorial documentary still, {spec['visual_zone']}, emotional subtext: {emotion} — {subtext}, "
        f"subject {pos.replace('_', ' ')}, {comp}, {light}, "
        f"clean support frame, shallow DOF, not literal illustration of narration, 35mm"
    )[:900]


def _build_anchor_prompt(beat: dict[str, Any], spec: dict[str, Any]) -> str:
    anchor = str(beat.get("text_anchor") or "")[:200]
    emotion = str(beat.get("emotional_state") or "memorable clarity")
    light = spec["light_phrase"]
    comp = str(beat.get("composition_for_animation") or spec["composition_for_animation"])
    pos = str(beat.get("subject_position") or "center_low")
    motif = str(beat.get("anchor_motif") or "").strip()
    if not motif and spec["label"] == "Domestic suburban comfort":
        motif = (
            "older woman in fleece vest in warm suburban kitchen, natural window light, "
            "quiet material comfort, specific wardrobe texture, memorable anchor portrait"
        )
    elif not motif:
        motif = f"defining {spec['label']} image the viewer remembers"
    return (
        f"ANCHOR SHOT — rich cinematic still: {motif}, felt truth: {emotion}, "
        f"narrative cue (subtext only): {anchor[:80]}, subject {pos.replace('_', ' ')}, "
        f"{comp}, {light}, maximum specificity, static framing, shallow DOF, photorealistic, "
        f"dual channel — do not illustrate spoken nouns literally"
    )[:900]


def assign_visual_pillars(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    n = len(beats)
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(beats):
        if not isinstance(raw, dict):
            continue
        b = dict(raw)
        pillar = str(b.get("visual_pillar") or "").strip().lower()
        if pillar not in PILLAR_IDS:
            pillar = infer_visual_pillar(str(b.get("act") or "body"), i, n)
        spec = PILLAR_SPEC[pillar]
        b["visual_pillar"] = pillar
        b["visual_zone"] = spec["visual_zone"]
        b["color_temperature"] = spec["color_temperature"]
        b["light_quality"] = spec["light_phrase"]
        b["color_palette"] = list(spec["palette"])
        b["emotional_state"] = str(b.get("emotional_state") or "").strip() or _infer_emotional_state(
            str(b.get("text_anchor") or "")
        )
        b["visual_subtext"] = str(b.get("visual_subtext") or spec["subtext_lens"])[:200]
        b["composition_for_animation"] = str(
            b.get("composition_for_animation") or spec["composition_for_animation"]
        )
        b["subject_position"] = str(b.get("subject_position") or "right_third")
        if not str(b.get("camera_motion") or "").strip():
            b["camera_motion"] = spec["camera_motion"]
        out.append(b)
    return out


def apply_per_pillar_anchor_hierarchy(beats: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Un plano ancla por pilar; soporte vs afterglow dentro de cada bloque."""
    by_pillar: dict[str, list[int]] = {p: [] for p in PILLAR_IDS}
    for i, b in enumerate(beats):
        if isinstance(b, dict):
            by_pillar.setdefault(str(b.get("visual_pillar") or "pillar_1"), []).append(i)

    anchor_indices: dict[str, int] = {}
    for pillar, idxs in by_pillar.items():
        if not idxs:
            continue
        best = max(idxs, key=lambda i: _pillar_anchor_score(beats[i], pillar))
        anchor_indices[pillar] = best

    out: list[dict[str, Any]] = []
    for i, raw in enumerate(beats):
        if not isinstance(raw, dict):
            continue
        b = dict(raw)
        pillar = str(b.get("visual_pillar") or "pillar_1")
        anchor_i = anchor_indices.get(pillar)
        if anchor_i is None:
            b["shot_hierarchy"] = "support"
            b["is_anchor_shot"] = False
        elif i == anchor_i:
            b["shot_hierarchy"] = "anchor"
            b["is_anchor_shot"] = True
            b["rhythm_tier"] = "slow"
            b["camera_motion"] = "static"
            b["camera_motion_direction"] = "none"
        elif i > anchor_i:
            b["shot_hierarchy"] = "afterglow"
            b["is_anchor_shot"] = False
            b["rhythm_tier"] = "slow"
            b["camera_motion"] = "slow_pull_out"
        else:
            b["shot_hierarchy"] = "support_build" if anchor_i - i <= 2 else "support"
            b["is_anchor_shot"] = False
        out.append(b)

    return out, {
        "anchor_by_pillar": {p: anchor_indices.get(p) for p in PILLAR_IDS},
        "anchor_count": len(anchor_indices),
    }


def enrich_body_beat_prompts(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in beats:
        if not isinstance(raw, dict):
            continue
        b = dict(raw)
        if str(b.get("track") or "").lower() != "insert":
            out.append(b)
            continue
        pillar = str(b.get("visual_pillar") or "pillar_1")
        spec = PILLAR_SPEC.get(pillar, PILLAR_SPEC["pillar_1"])
        if b.get("is_anchor_shot"):
            b["ai_prompt"] = _build_anchor_prompt(b, spec)
        else:
            b["ai_prompt"] = _build_support_prompt(b, spec)
        b["prompt_style"] = "body_subtext" if not b.get("is_anchor_shot") else "body_anchor"
        out.append(b)
    return out


def apply_body_visual_pipeline(
    beats: list[dict[str, Any]],
    *,
    body_pool_s: float = 0.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aplica las 6 reglas visuales del body en orden."""
    if not beats:
        return beats, {"applied": False}

    out = assign_visual_pillars(beats)
    out, anchor_meta = apply_per_pillar_anchor_hierarchy(out)
    out = enrich_body_beat_prompts(out)

    from videomaker.llm.narrative_visual_rhythm import apply_body_narrative_rhythm

    out, rhythm_summary = apply_body_narrative_rhythm(out, body_pool_s)

    plan = {
        **default_body_visual_plan(),
        "anchor_shots": anchor_meta,
        "narrative_rhythm": rhythm_summary,
        "beat_count": len(out),
        "pillar_counts": {p: sum(1 for x in out if x.get("visual_pillar") == p) for p in PILLAR_IDS},
    }
    return out, plan


def merge_llm_visual_fields(beats: list[dict[str, Any]], llm_beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preserva campos visuales del LLM cuando existen."""
    if not llm_beats:
        return beats
    by_anchor: dict[str, dict[str, Any]] = {}
    for lb in llm_beats:
        if isinstance(lb, dict):
            key = str(lb.get("text_anchor") or "")[:120].strip().lower()
            if key:
                by_anchor[key] = lb
    out: list[dict[str, Any]] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        row = dict(b)
        key = str(row.get("text_anchor") or "")[:120].strip().lower()
        llm = by_anchor.get(key) or {}
        for field in (
            "visual_pillar",
            "emotional_state",
            "visual_subtext",
            "composition_for_animation",
            "subject_position",
            "anchor_motif",
            "ai_prompt",
            "is_anchor_shot",
        ):
            if llm.get(field) not in (None, "", []):
                row[field] = llm[field]
        out.append(row)
    return out
