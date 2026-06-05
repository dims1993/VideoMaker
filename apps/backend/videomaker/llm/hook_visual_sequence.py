"""Arco de secuencia documental para el gancho (distancia focal + bloques narrativos)."""

from __future__ import annotations

import re
from typing import Any

# Bloques del arco: cerrado → medio → contraste → cerrado con peso
BLOCK_IDS = ("intimate_close", "medium_space", "contrast_world", "intimate_weight")

BLOCK_GUIDANCE: dict[str, str] = {
    "intimate_close": (
        "Block 1 — INTIMATE CLOSE: extreme close / macro / detail. Fingers, screens, partial face, "
        "forgotten cup. Viewer does not know where yet. Quiet exhaustion, not drama."
    ),
    "medium_space": (
        "Block 2 — MEDIUM SPACE: reveal where they are. Small apartment, night kitchen, window to "
        "buildings (not gardens), work clothes on chair. Camera pulls back — medium / medium-wide."
    ),
    "contrast_world": (
        "Block 3 — CONTRAST CUT: opposite world without narration naming it. Suburban house warm at "
        "night, new car in driveway, older hands with tea — visual argument via contrast."
    ),
    "intimate_weight": (
        "Block 4 — INTIMATE WEIGHT: return close but heavier. Same motifs as block 1 transformed "
        "(screen closed, still hands, dark window, city unchanged). Emotional cost visible."
    ),
}

# Rotación de distancia/ángulo por bloque (nunca repetir par consecutivo)
_DISTANCE_BY_BLOCK: dict[str, list[str]] = {
    "intimate_close": ["extreme_close", "macro", "close_up", "close_up", "extreme_close"],
    "medium_space": ["medium", "medium_wide", "medium", "wide", "medium"],
    "contrast_world": ["wide", "establishing", "medium_wide", "medium", "wide"],
    "intimate_weight": ["close_up", "extreme_close", "medium_close", "close_up", "extreme_close"],
}
_ANGLE_BY_BLOCK: dict[str, list[str]] = {
    "intimate_close": ["high", "eye_level", "profile", "over_shoulder", "low"],
    "medium_space": ["eye_level", "three_quarter", "wide_angle", "eye_level", "slightly_high"],
    "contrast_world": ["eye_level", "low", "three_quarter", "establishing", "eye_level"],
    "intimate_weight": ["profile", "eye_level", "high", "over_shoulder", "low"],
}

_SHOT_MAP = {
    "extreme_close": "extreme close-up",
    "macro": "macro",
    "close_up": "close-up",
    "medium_close": "medium close-up",
    "medium": "medium",
    "medium_wide": "medium wide",
    "wide": "wide",
    "establishing": "wide establishing",
    "wide_angle": "wide",
}

# Color y luz como lenguaje: define paleta ANTES de generar (contraste cromático = argumento visual)
BLOCK_COLOR_LANGUAGE: dict[str, dict[str, Any]] = {
    "intimate_close": {
        "world": "protagonist_alone",
        "color_temperature": "cool",
        "light_phrase": "cool blue artificial light, phone screen glow, deep shadows",
        "palette": ["cool blue", "cyan screen cast", "charcoal shadow", "muted steel grey"],
        "light_sources": [
            "cool blue phone glow on fingers",
            "harsh fluorescent spill in darkness",
            "cold laptop screen cast on partial face",
            "dim monitor blue wash, heavy shadow falloff",
        ],
    },
    "medium_space": {
        "world": "protagonist_alone",
        "color_temperature": "cool_neutral",
        "light_phrase": "cool blue night interior, sparse artificial lamps, flat fluorescent kitchen",
        "palette": ["slate blue", "cool grey walls", "muted tungsten spill", "city cyan through glass"],
        "light_sources": [
            "flat overhead fluorescent, cool greenish cast",
            "single warm lamp fighting cool ambient blue",
            "window spill: cool city sodium and blue dusk",
            "under-cabinet fluorescent, sterile cool tone on small kitchen",
        ],
    },
    "contrast_world": {
        "world": "parents_suburban_comfort",
        "color_temperature": "warm",
        "light_phrase": "warm amber interior, natural golden light, soft tungsten glow",
        "palette": ["warm amber", "honey gold", "cream walls", "soft sage suburban green"],
        "light_sources": [
            "warm amber interior lamps, golden practicals",
            "natural window light, honey afternoon glow on suburban home",
            "soft tungsten dining light, older hands holding tea",
            "driveway dusk with warm porch lights, new car gleam",
        ],
    },
    "intimate_weight": {
        "world": "protagonist_alone",
        "color_temperature": "cool",
        "light_phrase": "return to cool blue artificial light, heavier shadows, dim screen afterglow",
        "palette": ["cool blue", "deep navy shadow", "desaturated skin", "cold grey negative space"],
        "light_sources": [
            "screen closing — last cool blue flicker then shadow",
            "harsh fluorescent now feels colder, still hands on table",
            "dark window, unchanged cool city glow outside",
            "single cool practical, emotional weight in shadow pools",
        ],
    },
}

# Movimiento de cámara (Ken Burns en render): tensión → push-in; revelación/contraste → pull-out/static
_MOTION_IN_PURPOSES = frozenset(
    {
        "curiosity",
        "contradiction",
        "emotional_escalation",
        "pattern_interrupt",
        "tension_rise",
    }
)
_MOTION_OUT_PURPOSES = frozenset({"payoff_release", "breathing_room"})
_MOTION_IN_PACING = frozenset(
    {"tension_rise", "stimulus_beat", "hook_open", "pattern_interrupt", "tension_peak"}
)
_MOTION_OUT_PACING = frozenset({"payoff_release", "breathing_room", "narrative_hold"})
_MOTION_IN_EMOTIONS = frozenset(
    {"fear", "tension", "confusion", "urgency", "shock", "anxiety", "panic"}
)

_CAMERA_MOTION_LABELS: dict[str, str] = {
    "slow_push_in": "slow push-in toward subject, creeping zoom in",
    "push_in": "push-in, camera moves inward",
    "slow_pull_out": "slow pull-out, camera reveals wider space",
    "pull_out": "pull-back, widening frame",
    "static": "locked-off static frame, no camera drift",
}

_COLOR_MARKERS = re.compile(
    r"\b(cool blue|warm amber|harsh fluorescent|tungsten|golden hour|"
    r"color temperature|cyan cast|amber glow|fluorescent|screen glow)\b",
    re.I,
)


def default_camera_motion_plan() -> dict[str, Any]:
    return {
        "tension_confusion": "slow_push_in (inward) — confusion, stakes, isolation",
        "revelation_contrast": "pull_out or static — contrast block, payoff release, breathing room",
        "rule": "never two consecutive beats with the same camera_motion_direction (in/out)",
        "render_zoom_default": 1.06,
    }


def _motion_direction(motion: str) -> str:
    m = (motion or "").strip().lower()
    if m in ("static", "none", "locked"):
        return "none"
    if m in ("pull_out", "slow_pull_out", "pull_back", "out"):
        return "out"
    return "in"


def default_camera_motion_for_beat(beat: dict[str, Any], block_id: str) -> str:
    """Etiqueta de momento → movimiento de cámara para vídeo (~3s por plano)."""
    purpose = str(beat.get("purpose") or "").strip().lower()
    pacing = str(beat.get("pacing_role") or "").strip().lower()
    emotion = str(beat.get("emotion") or "").strip().lower()

    if block_id == "contrast_world":
        return "slow_pull_out"
    if purpose in _MOTION_OUT_PURPOSES or pacing in _MOTION_OUT_PACING:
        return "static" if pacing == "breathing_room" else "slow_pull_out"
    if block_id == "medium_space" and pacing in ("narrative_hold", "payoff_release"):
        return "slow_pull_out"
    if (
        purpose in _MOTION_IN_PURPOSES
        or pacing in _MOTION_IN_PACING
        or emotion in _MOTION_IN_EMOTIONS
        or block_id in ("intimate_close", "intimate_weight")
    ):
        return "slow_push_in"
    legacy = str(beat.get("motion") or "").strip().lower()
    if legacy in ("push_in", "slow_zoom", "fast_zoom"):
        return "slow_push_in" if "slow" in legacy or legacy == "push_in" else "push_in"
    if legacy in ("static", "hold"):
        return "static"
    if legacy in ("whip_pan",):
        return "push_in"
    return "slow_push_in"


def apply_camera_motion_to_beat(beat: dict[str, Any], block_id: str) -> dict[str, Any]:
    b = dict(beat)
    motion = str(b.get("camera_motion") or "").strip().lower()
    if motion not in _CAMERA_MOTION_LABELS:
        motion = default_camera_motion_for_beat(b, block_id)
    b["camera_motion"] = motion
    b["camera_motion_direction"] = _motion_direction(motion)
    b["camera_motion_note"] = _CAMERA_MOTION_LABELS.get(motion, motion)
    cam = b.get("camera") if isinstance(b.get("camera"), dict) else {}
    cam = dict(cam)
    cam["motion"] = motion
    b["camera"] = cam
    b["motion"] = motion
    return b


def _alternate_consecutive_motion_directions(beats: list[dict[str, Any]]) -> int:
    """Nunca dos planos seguidos con la misma dirección in/out."""
    fixes = 0
    prev_dir: str | None = None
    for b in beats:
        if not isinstance(b, dict):
            continue
        d = str(b.get("camera_motion_direction") or "none")
        if prev_dir and d == prev_dir and d != "none":
            if d == "in":
                b["camera_motion"] = "slow_pull_out"
                b["camera_motion_direction"] = "out"
            else:
                b["camera_motion"] = "slow_push_in"
                b["camera_motion_direction"] = "in"
            b["camera_motion_note"] = _CAMERA_MOTION_LABELS.get(
                str(b["camera_motion"]), str(b["camera_motion"])
            )
            cam = b.get("camera") if isinstance(b.get("camera"), dict) else {}
            cam = dict(cam)
            cam["motion"] = b["camera_motion"]
            b["camera"] = cam
            b["motion"] = b["camera_motion"]
            fixes += 1
            d = str(b["camera_motion_direction"])
        prev_dir = d
    return fixes


def default_color_language_plan() -> dict[str, Any]:
    """Paleta raíz del gancho — fijar antes de generar beats o prompts."""
    return {
        "protagonist_world": {
            "blocks": ["intimate_close", "medium_space", "intimate_weight"],
            "color_temperature": "cool",
            "palette": BLOCK_COLOR_LANGUAGE["intimate_close"]["palette"],
            "light_language": "cool blue artificial light, shadows, screens — quiet exhaustion",
        },
        "contrast_world": {
            "blocks": ["contrast_world"],
            "color_temperature": "warm",
            "palette": BLOCK_COLOR_LANGUAGE["contrast_world"]["palette"],
            "light_language": "warm amber interior, natural light — suburban comfort without narration",
        },
        "chromatic_argument": (
            "Cool blue protagonist isolation vs warm amber parents/suburb contrast; "
            "color temperature shift IS the visual thesis."
        ),
        "required_in_every_prompt": [
            "explicit color temperature phrase (e.g. cool blue light, warm amber interior, harsh fluorescent)",
        ],
    }


def block_color_spec(block_id: str, beat_index: int = 0) -> dict[str, Any]:
    spec = dict(BLOCK_COLOR_LANGUAGE.get(block_id, BLOCK_COLOR_LANGUAGE["intimate_close"]))
    sources = spec.get("light_sources") or []
    if sources:
        spec = {**spec, "light_source": sources[beat_index % len(sources)]}
    return spec


def apply_color_language_to_beat(beat: dict[str, Any], block_id: str, beat_index: int) -> dict[str, Any]:
    """Asigna color_temperature, light_quality y camera.lighting por bloque."""
    spec = block_color_spec(block_id, beat_index)
    b = dict(beat)
    b["color_temperature"] = spec["color_temperature"]
    b["light_quality"] = spec.get("light_source") or spec["light_phrase"]
    b["color_palette"] = list(spec.get("palette") or [])
    cam = b.get("camera") if isinstance(b.get("camera"), dict) else {}
    cam = dict(cam)
    cam["lighting"] = spec.get("light_source") or spec["light_phrase"]
    cam["color_temperature"] = spec["color_temperature"]
    b["camera"] = cam
    return b


def prompt_has_color_language(text: str) -> bool:
    return bool(_COLOR_MARKERS.search(text or ""))


def merge_color_language_into_prompt(text: str, block_id: str, *, beat_index: int = 0) -> str:
    """Asegura frase de temperatura de color en cada prompt de imagen."""
    base = (text or "").strip()
    if prompt_has_color_language(base):
        return base[:900]
    spec = block_color_spec(block_id, beat_index)
    phrase = str(spec.get("light_source") or spec["light_phrase"])
    if not base:
        return phrase[:900]
    return f"{base}, {phrase}"[:900]


def block_quotas(n: int) -> list[int]:
    """Cuántos beats por bloque (suma = n)."""
    if n <= 0:
        return []
    if n <= 4:
        return [1] * n + [0] * (4 - n)
    base = n // 4
    rem = n % 4
    counts = [base + (1 if i < rem else 0) for i in range(4)]
    return counts


def block_id_for_beat_index(beat_index: int, total: int) -> str:
    if total <= 0:
        return BLOCK_IDS[0]
    counts = block_quotas(total)
    cursor = 0
    for bid, cnt in zip(BLOCK_IDS, counts, strict=True):
        if beat_index < cursor + cnt:
            return bid
        cursor += cnt
    return BLOCK_IDS[-1]


def sequence_arc_summary_en(*, target_beats: int, hook_duration_sec: float) -> str:
    dur = max(30.0, float(hook_duration_sec or 90))
    return (
        f"Design ONE coherent {target_beats}-shot sequence (~{dur:.0f}s hook), not {target_beats} unrelated stills. "
        f"Arc: intimate_close ({block_quotas(target_beats)[0]} shots) → medium_space ({block_quotas(target_beats)[1]}) → "
        f"contrast_world ({block_quotas(target_beats)[2]}) → intimate_weight ({block_quotas(target_beats)[3]}). "
        "Never two consecutive shots with the same shot_distance AND shot_angle. "
        "Each beat must add a NEW information layer (do not repeat the previous subject/framing). "
        "Voice carries argument; images carry emotion/subtext/contrast — do not illustrate spoken nouns literally. "
        "Chromatic arc: protagonist world = cool blue artificial light; contrast block = warm amber natural light."
    )


def documentary_sequence_system_addon() -> str:
    blocks = "\n".join(f"- {bid}: {BLOCK_GUIDANCE[bid]}" for bid in BLOCK_IDS)
    return f"""
DOCUMENTARY SHOT SEQUENCE (CRITICAL — design the FULL hook as one sequence):
{blocks}

Arc shape (mandatory): intimate_close → medium_space → contrast_world → intimate_weight
- Assign each micro_beat exactly one sequence_block from the four above, in order across the timeline.
- shot_distance: extreme_close | macro | close_up | medium_close | medium | medium_wide | wide | establishing
- shot_angle: high | eye_level | low | profile | over_shoulder | three_quarter | wide_angle | slightly_high
- new_information_layer: one short phrase — what NEW thing the viewer learns vs the previous beat (not repetition).
- NEVER use the same shot_distance AND shot_angle on two consecutive beats.
- camera.shot must match shot_distance; vary composition and subject every beat.
- visual_description must reflect the block (block 3 = suburban contrast, not more apartment unless contrast).

COLOR & LIGHT LANGUAGE (define palette BEFORE shots — chromatic contrast = visual argument):
- Protagonist world (intimate_close, medium_space, intimate_weight): cool blue, artificial light, harsh fluorescent, deep shadows, screen glow. NEVER warm amber here.
- Contrast world (contrast_world / parents-suburb): warm amber interior, natural golden light, soft tungsten — NEVER cool blue phone glow here.
- EVERY micro_beat MUST set: color_temperature (cool | cool_neutral | warm), light_quality (specific source phrase), color_palette (3-4 color names).
- EVERY visual_description and image_prompt_seed MUST include an explicit temperature phrase, e.g. "cool blue light", "warm amber interior", "harsh fluorescent".
- camera.lighting must name source + temperature; forbid vague "natural lighting" alone.

CAMERA MOVEMENT (for 3s stills → Ken Burns in video render):
- Tension / confusion / escalation (purpose, pacing_role, emotion): camera_motion = slow_push_in or push_in (direction: in).
- Revelation / contrast (contrast_world block, payoff_release, breathing_room): camera_motion = slow_pull_out or static (direction: out or none).
- NEVER two consecutive beats with the same camera_motion_direction (in vs out).
- Each beat: camera_motion, camera_motion_direction (in|out|none), camera_motion_note (short English phrase for editors).

ANCHOR SHOT (one remembered image per hook — hierarchy, not equal weight):
- Exactly ONE beat must be shot_hierarchy=anchor, is_anchor_shot=true (default motif: closes banking app / screen dark in intimate_weight).
- Beats before anchor: support or support_build (construct the turn); after anchor: afterglow (breathe, release).
- Anchor beat: static camera, slow hold, highest emotional weight; do NOT dilute with 30 equal shots.

NARRATIVE RHYTHM (duration must follow narration, NOT fixed 3s per shot):
- Tension/confusion/high intensity → rhythm_tier fast, duration_sec ~1–2
- Revelation/contrast_world/emotional weight → rhythm_tier slow, duration_sec ~4–5
- Medium beats ~2–3.5s; start_sec/end_sec must sum to target hook audio length

Root JSON must include:
"visual_sequence_plan": {{
  "arc": "intimate_close → medium_space → contrast_world → intimate_weight",
  "target_beats": number,
  "emotional_tone": "e.g. quiet exhaustion, not melodrama",
  "motif_thread": "optional recurring motif (door, screen glow, cold cup) sparse in blocks 1 and 4",
  "color_language": {{
    "protagonist_world": {{ "color_temperature": "cool", "light_language": "cool blue artificial, shadows" }},
    "contrast_world": {{ "color_temperature": "warm", "light_language": "warm amber, natural golden light" }},
    "chromatic_argument": "cool isolation vs warm suburban comfort"
  }},
  "rules": ["no consecutive same distance+angle", "each beat new layer", "dual channel vs narration", "color temperature per block"],
  "camera_motion_plan": {{ "tension": "push_in", "revelation": "pull_out_or_static", "no_consecutive_same_direction": true }}
}}
"""


def _distance_angle_for_beat(beat_index: int, block_id: str, prev_key: tuple[str, str] | None) -> tuple[str, str]:
    dists = _DISTANCE_BY_BLOCK.get(block_id, _DISTANCE_BY_BLOCK["intimate_close"])
    angles = _ANGLE_BY_BLOCK.get(block_id, _ANGLE_BY_BLOCK["intimate_close"])
    d = dists[beat_index % len(dists)]
    a = angles[beat_index % len(angles)]
    key = (d, a)
    guard = 0
    while prev_key and key == prev_key and guard < 12:
        guard += 1
        d = dists[(beat_index + guard) % len(dists)]
        a = angles[(beat_index + guard) % len(angles)]
        key = (d, a)
    return d, a


def _overlap_ratio(a: str, b: str) -> float:
    wa = set(re.findall(r"[a-z]{4,}", (a or "").lower()))
    wb = set(re.findall(r"[a-z]{4,}", (b or "").lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def finalize_hook_visual_sequence(
    beats: list[dict[str, Any]],
    *,
    target_beats: int | None = None,
    hook_pool_s: float = 0.0,
    parsed_plan: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Asegura sequence_block, shot_distance, shot_angle y camera.shot en cada micro_beat.
    Corrige violaciones consecutivas distance+angle cuando el LLM no las cumplió.
    """
    n = len(beats)
    if n == 0:
        return beats, {"applied": False}

    target = max(n, int(target_beats or n))
    out: list[dict[str, Any]] = []
    prev_key: tuple[str, str] | None = None
    violations_fixed = 0
    motion_direction_fixes = 0
    layer_warnings: list[int] = []

    for i, raw in enumerate(beats):
        if not isinstance(raw, dict):
            continue
        b = dict(raw)
        block_id = str(b.get("sequence_block") or "").strip().lower()
        if block_id not in BLOCK_IDS:
            block_id = block_id_for_beat_index(i, n)

        dist, ang = _distance_angle_for_beat(i, block_id, prev_key)
        llm_dist = str(b.get("shot_distance") or "").strip().lower()
        llm_ang = str(b.get("shot_angle") or "").strip().lower()
        if llm_dist and llm_ang:
            candidate = (llm_dist, llm_ang)
            if prev_key is None or candidate != prev_key:
                dist, ang = llm_dist, llm_ang
            else:
                violations_fixed += 1
        else:
            violations_fixed += 1

        prev_key = (dist, ang)
        shot_label = _SHOT_MAP.get(dist, dist.replace("_", " "))
        cam = b.get("camera") if isinstance(b.get("camera"), dict) else {}
        cam = dict(cam)
        cam["shot"] = shot_label
        cam.setdefault("angle", ang.replace("_", " "))
        b["sequence_block"] = block_id
        b["shot_distance"] = dist
        b["shot_angle"] = ang
        b = apply_color_language_to_beat(b, block_id, i)
        b = apply_camera_motion_to_beat(b, block_id)
        cam = b.get("camera") if isinstance(b.get("camera"), dict) else {}
        cam = dict(cam)
        cam["shot"] = shot_label
        cam.setdefault("angle", ang.replace("_", " "))
        b["camera"] = cam
        if not str(b.get("new_information_layer") or "").strip():
            b["new_information_layer"] = BLOCK_GUIDANCE[block_id][:120]

        for key in ("visual_description", "image_prompt_seed"):
            raw = str(b.get(key) or "").strip()
            if raw:
                b[key] = merge_color_language_into_prompt(raw, block_id, beat_index=i)

        if i > 0 and out:
            prev_vis = str(out[-1].get("visual_description") or "")
            cur_vis = str(b.get("visual_description") or "")
            if cur_vis and _overlap_ratio(prev_vis, cur_vis) > 0.55:
                layer_warnings.append(i)

        out.append(b)

    motion_direction_fixes = _alternate_consecutive_motion_directions(out)

    plan: dict[str, Any] = {
        "arc": "intimate_close → medium_space → contrast_world → intimate_weight",
        "target_beats": target,
        "hook_duration_sec_est": round(hook_pool_s, 1) if hook_pool_s else None,
        "beat_count": n,
        "block_counts": {
            bid: sum(1 for x in out if x.get("sequence_block") == bid) for bid in BLOCK_IDS
        },
        "violations_fixed": violations_fixed,
        "layer_overlap_warnings": layer_warnings,
        "motion_direction_fixes": motion_direction_fixes,
    }
    plan["color_language"] = default_color_language_plan()
    plan["camera_motion_plan"] = default_camera_motion_plan()
    if isinstance(parsed_plan, dict):
        for k in ("emotional_tone", "motif_thread", "rules", "color_language"):
            if parsed_plan.get(k):
                plan[k] = parsed_plan[k]

    return out, plan


def sequence_context_for_counterpoint(
    beats: list[dict[str, Any]],
    plan: dict[str, Any] | None,
) -> str:
    """Texto compacto para el LLM de contrapunto (secuencia completa, sin narración)."""
    lines = [
        sequence_arc_summary_en(
            target_beats=len(beats),
            hook_duration_sec=float((plan or {}).get("hook_duration_sec_est") or 90),
        ),
    ]
    if plan:
        tone = plan.get("emotional_tone")
        if tone:
            lines.append(f"Emotional tone: {tone}")
        motif = plan.get("motif_thread")
        if motif:
            lines.append(f"Sparse motif: {motif}")
        color = plan.get("color_language")
        if isinstance(color, dict):
            chrom = color.get("chromatic_argument")
            if chrom:
                lines.append(f"Color arc: {chrom}")
            pw = color.get("protagonist_world") if isinstance(color.get("protagonist_world"), dict) else {}
            cw = color.get("contrast_world") if isinstance(color.get("contrast_world"), dict) else {}
            if pw.get("light_language"):
                lines.append(f"Protagonist light: {pw['light_language']}")
            if cw.get("light_language"):
                lines.append(f"Contrast world light: {cw['light_language']}")
    lines.append("Shots in order:")
    lines.extend(_shot_lines_for_beats(beats))
    return "\n".join(lines)


def _shot_lines_for_beats(beats: list[dict[str, Any]], *, indices: list[int] | None = None) -> list[str]:
    lines: list[str] = []
    for pos, b in enumerate(beats):
        if not isinstance(b, dict):
            continue
        if indices is not None and pos not in indices:
            continue
        i = b.get("index", pos)
        light = str(b.get("light_quality") or (b.get("camera") or {}).get("lighting") or "")[:60]
        mov = str(b.get("camera_motion") or b.get("motion") or "")[:24]
        hier = str(b.get("shot_hierarchy") or "")
        anchor_flag = " ANCHOR" if b.get("is_anchor_shot") else ""
        lines.append(
            f"  #{i} [{b.get('sequence_block')}] {b.get('shot_distance')}/{b.get('shot_angle')} "
            f"({b.get('color_temperature') or '?'} · {light}) cam={mov}{anchor_flag}"
            f"{f' [{hier}]' if hier else ''}: "
            f"{str(b.get('new_information_layer') or '')[:50]}"
        )
    return lines


def sequence_context_for_counterpoint_batch(
    beats: list[dict[str, Any]],
    plan: dict[str, Any] | None,
    *,
    batch_start: int,
    batch_end: int,
    prior_prompts: list[str] | None = None,
) -> str:
    """
    Contexto por lote: arco completo + continuidad (beats previos + prompts ya escritos)
    + plan de shots del lote actual. Usar en cada llamada LLM del contrapunto, no solo el lote 1.
    """
    n = len(beats)
    batch_start = max(0, min(batch_start, n))
    batch_end = max(batch_start, min(batch_end, n))
    lines = [
        sequence_arc_summary_en(
            target_beats=n,
            hook_duration_sec=float((plan or {}).get("hook_duration_sec_est") or 90),
        ),
    ]
    if plan:
        tone = plan.get("emotional_tone")
        if tone:
            lines.append(f"Emotional tone: {tone}")
        motif = plan.get("motif_thread")
        if motif:
            lines.append(f"Sparse motif: {motif}")

    if batch_start > 0:
        lookback = beats[max(0, batch_start - 3) : batch_start]
        lines.append("Continuity — shots immediately before this batch:")
        lines.extend(_shot_lines_for_beats(lookback))
        if prior_prompts:
            recent = [p.strip()[:120] for p in prior_prompts[-3:] if p and p.strip()]
            if recent:
                lines.append("Continuity — image prompts already written (do not repeat subjects/framing):")
                for j, p in enumerate(recent):
                    lines.append(f"  prior[{batch_start - len(recent) + j}]: {p}")

    lines.append(f"Write prompts ONLY for beats {batch_start}–{batch_end - 1} (inclusive), in order:")
    lines.extend(_shot_lines_for_beats(beats[batch_start:batch_end]))

    if batch_end < n:
        lookahead = beats[batch_end : min(n, batch_end + 2)]
        lines.append("Coming next (for arc awareness, do not illustrate yet):")
        lines.extend(_shot_lines_for_beats(lookahead))

    return "\n".join(lines)
