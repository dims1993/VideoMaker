"""Hook Scene Router v2: retención, micro-beats y plan visual para el gancho (Acto 1)."""

from __future__ import annotations

import os
import re
from typing import Any

from videomaker.llm.output_language import language_label, normalize_language_code
from videomaker.pipeline.models import PipelineInputs

HOOK_CLASSES = frozenset(
    {
        "curiosity",
        "contradiction",
        "shock",
        "fear",
        "fast_payoff",
        "story",
        "data",
        "invitation",
        "mixed",
    }
)

RETENTION_PATTERNS = frozenset(
    {
        "curiosity_gap",
        "contradiction",
        "shock",
        "fear",
        "fast_payoff",
        "stakes",
        "social_proof",
        "pattern_interrupt",
    }
)

PLATFORM_PRESETS: dict[str, dict[str, Any]] = {
    "tiktok": {
        "label": "TikTok",
        "pacing_profile": "hyper_short",
        "default_beat_sec": 1.4,
        "max_beats": 12,
        "visual_energy_default": "high",
        "cut_style": "hyper_fast",
        "talking_head_after_sec": 18,
        "intensity_peak_cap": 95,
        "max_intensity_step_up": 22,
        "breath_beats_enabled": False,
        "tension_release_cycles": False,
        "preferred_transitions": ("whip_pan", "hard_cut", "flash", "speed_ramp"),
        "cognitive_load_cap": 75,
        "escalation_style": "aggressive_instant",
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "pacing_profile": "short_vertical",
        "default_beat_sec": 1.75,
        "max_beats": 10,
        "visual_energy_default": "high",
        "cut_style": "fast",
        "talking_head_after_sec": 20,
        "intensity_peak_cap": 92,
        "max_intensity_step_up": 18,
        "breath_beats_enabled": False,
        "tension_release_cycles": False,
        "preferred_transitions": ("whip_pan", "hard_cut", "zoom_cut", "speed_ramp"),
        "cognitive_load_cap": 72,
        "escalation_style": "fast",
    },
    "reels": {
        "label": "Instagram Reels",
        "pacing_profile": "short_vertical",
        "default_beat_sec": 1.5,
        "max_beats": 10,
        "visual_energy_default": "high",
        "cut_style": "fast",
        "talking_head_after_sec": 20,
        "intensity_peak_cap": 93,
        "max_intensity_step_up": 20,
        "breath_beats_enabled": False,
        "tension_release_cycles": False,
        "preferred_transitions": ("blur", "whip_pan", "hard_cut", "flash"),
        "cognitive_load_cap": 74,
        "escalation_style": "fast",
    },
    "youtube": {
        "label": "YouTube (long-form hook)",
        "pacing_profile": "narrative_long",
        "default_beat_sec": 3.5,
        "max_beats": 32,
        "visual_energy_default": "medium",
        "cut_style": "narrative",
        "talking_head_after_sec": 30,
        "intensity_peak_cap": 84,
        "max_intensity_step_up": 10,
        "breath_beats_enabled": True,
        "breath_interval": 2,
        "tension_release_cycles": True,
        "preferred_transitions": ("dissolve", "match_cut", "slow_zoom", "hard_cut"),
        "cognitive_load_cap": 68,
        "escalation_style": "slow_with_breathing_room",
    },
}


def platform_pacing_profile(platform: str) -> dict[str, Any]:
    """Perfil de pacing resuelto para la plataforma."""
    plat = normalize_platform(platform)
    preset = PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"])
    return {
        "platform": plat,
        "label": preset.get("label"),
        "pacing_profile": preset.get("pacing_profile", "short_vertical"),
        "escalation_style": preset.get("escalation_style", "fast"),
        "beat_duration_sec": preset.get("default_beat_sec"),
        "cut_style": preset.get("cut_style"),
        "breathing_room": bool(preset.get("breath_beats_enabled")),
        "tension_release_cycles": bool(preset.get("tension_release_cycles")),
        "intensity_peak_cap": int(preset.get("intensity_peak_cap", 90)),
        "talking_head_after_sec": int(preset.get("talking_head_after_sec", 25)),
        "guidance": _platform_pacing_guidance(plat),
    }


def _platform_pacing_guidance(platform: str) -> str:
    plat = normalize_platform(platform)
    if plat == "youtube":
        return (
            "YouTube long-form hook: breathing room between beats, tension-release cycles "
            "(rise → brief dip → rise), slower escalation, holds 3-4s, dissolves/match cuts, "
            "never TikTok-style hyper strobe pacing."
        )
    if plat == "tiktok":
        return (
            "TikTok: instant hook, 1-1.5s beats, aggressive escalation, whip pans and hard cuts, "
            "no breathing dips, maximum stimulus from beat one."
        )
    if plat == "reels":
        return (
            "Reels: fast vertical pacing like TikTok, 1.5s beats, high energy, pattern interrupts, "
            "minimal hold frames."
        )
    return (
        "YouTube Shorts: fast vertical 1.5-2s beats, high energy, quick escalation to payoff, "
        "no long holds — distinct from long-form YouTube."
    )

HOOK_PRE_NARRATOR_SCENE_TYPES = frozenset(
    {"broll", "motion_graphic", "text_card", "split_screen", "stock", "data_ui", "cinematic_broll"}
)

VALID_TRANSITION_TYPES = frozenset(
    {
        "hard_cut",
        "match_cut",
        "whip_pan",
        "blur",
        "speed_ramp",
        "zoom_cut",
        "flash",
        "dissolve",
        "hold",
    }
)

VISUAL_ENERGY_PROFILES: dict[str, dict[str, str]] = {
    "high": {
        "cuts": "1-2s beats, aggressive text, zooms, pattern interrupts",
        "motion": "fast push-ins, whip pans, kinetic typography",
        "overlay": "large bold text, high contrast",
    },
    "medium": {
        "cuts": "2-3s beats, clean B-roll, motion graphics",
        "motion": "smooth pans, subtle zooms",
        "overlay": "readable subtitles, lower-third stats",
    },
    "low": {
        "cuts": "3-5s beats, cinematic holds",
        "motion": "slow dolly, minimal cuts",
        "overlay": "minimal text, mood-first",
    },
}

# Plantillas cinematográficas (sujeto + espacio + luz + gesto) — modo reglas y referencia implícita para IA.
_CINEMATIC_BEAT_TEMPLATES: dict[str, list[str]] = {
    "curiosity": [
        "tight close-up, person's eyes narrowing at phone screen glow in dark room, cool blue light, shallow depth of field",
        "over-shoulder shot, finger hovering over banking app transfer button, warm desk lamp, tense stillness",
    ],
    "tension": [
        "young woman alone at kitchen table staring at banking app, soft warm light, subtle jaw tension, shallow focus on screen",
        "close-up hands gripping coffee mug, overdue bill papers blurred in background, muted morning grey light",
    ],
    "fear": [
        "extreme close-up red negative balance on phone, face half in shadow, harsh overhead fluorescent, shallow DOF",
        "wide shot empty apartment, single person on floor with laptop, cold blue hour through window, isolation",
    ],
    "shock": [
        "snap-zoom framing on bold statistic reflected in glasses, high contrast, sharp rim light, frozen expression",
        "macro shot calculator display flipping digits, hands frozen mid-air, dramatic side light, dust in beam",
    ],
    "hope": [
        "young woman alone at kitchen table staring at banking app, soft warm light, subtle smile of relief, shallow focus",
        "golden hour through window on face, shoulders dropping, phone showing green checkmark, gentle lens flare",
    ],
    "urgency": [
        "handheld close-up thumb racing across phone timer, motion blur on edges, harsh kitchen practicals, sweat on temple",
        "split-second whip-pan to wall clock, shallow focus, cool tones, subject mid-turn toward camera",
    ],
    "success": [
        "medium shot confident walk past floor-to-ceiling windows at dusk, city bokeh, tailored silhouette, calm power",
        "tabletop macro growing chart on tablet, manicured hand placing coin, warm key light, crisp shadows",
    ],
}

_GENERIC_VISUAL_BANS = (
    "b-roll of people",
    "people celebrating",
    "financial milestones",
    "stock footage",
    "generic office",
    "happy family",
    "success montage",
    "discussing finances",
    "discussing money",
    "talking about money",
    "having a conversation",
    "business people",
    "professional looking",
)

# Patrones típicos de prompts Shutterstock / stock (no identidad ni lugar).
_STOCK_FOOTAGE_RE: list[str] = [
    r"\bdiscussing\b",
    r"\btalking about\b",
    r"\bconversation about\b",
    r"\b(concept|photo|image|footage)\s+of\b",
    r"\bgroup of people\b",
    r"\b(diverse|happy)\s+(people|friends|couple)\b",
    r"\bbeautiful\s+(young\s+)?(woman|man)\b",
    r"\bprofessional\s+(woman|man|person)\b",
    r"\bbusiness\s+meeting\b",
    r"\btwo\s+(friends|people|colleagues)\s+(discussing|talking|sitting)\b",
    r"\bperson\s+using\s+(laptop|phone)\b",
]

_CLASSIFIER_RULES: list[tuple[str, list[str]]] = [
    ("curiosity", [r"nobody tells", r"secret", r"why\s+", r"what if", r"nadie te dice", r"por qué"]),
    ("contradiction", [r"more than", r"worth more", r"but\s+", r"sin embargo", r"paradox"]),
    ("shock", [r"millionaire", r"90%", r"most people", r"la mayoría", r"millonarios"]),
    ("fear", [r"stuck", r"wasting", r"can't save", r"atascado", r"pierdes", r"error"]),
    ("fast_payoff", [r"in \d+ seconds", r"en \d+ segundos", r"you'll understand", r"entenderás"]),
    ("data", [r"\d+%", r"\d+\s*percent", r"data", r"dato", r"estadística"]),
    ("story", [r"at \d+", r"years old", r"cuando tenía", r"él tenía"]),
    ("invitation", [r"imagine", r"picture this", r"imagina", r"tú puedes"]),
]


def normalize_platform(raw: str | None, metadata_platform: str | None = None) -> str:
    for candidate in (raw, metadata_platform):
        p = (candidate or "").strip().lower()
        if p in PLATFORM_PRESETS:
            return p
        if p in ("shorts", "short"):
            return "youtube_shorts"
        if p in ("youtube_long", "long_form", "longform", "long"):
            return "youtube"
        if p == "reel":
            return "reels"
    return "youtube_shorts"


def resolve_talking_head_after_sec(platform: str, settings_value: Any = None) -> int:
    """Segundos sin narrator visible (solo b-roll / motion / gráficos)."""
    if settings_value is not None and str(settings_value).strip().lower() not in ("", "auto"):
        try:
            return min(120, max(0, int(float(settings_value))))
        except (TypeError, ValueError):
            pass
    env = (os.environ.get("VIDEOMAKER_HOOK_TALKING_HEAD_AFTER_SEC") or "").strip()
    if env:
        try:
            return min(120, max(0, int(float(env))))
        except ValueError:
            pass
    preset = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["youtube_shorts"])
    return int(preset.get("talking_head_after_sec", 25))


def _replacement_scene_type(
    *,
    index: int,
    purpose: str,
    hook_class: str,
) -> str:
    if hook_class in ("data", "contradiction", "shock", "fast_payoff") or purpose == "contradiction":
        return "motion_graphic" if index % 2 else "text_card"
    if index % 3 == 0:
        return "broll"
    if index % 3 == 1:
        return "motion_graphic"
    return "text_card"


def apply_narrator_visibility_policy(
    beats: list[dict[str, Any]],
    *,
    talking_head_after_sec: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Nunca talking_head antes de talking_head_after_sec (p. ej. 20–30 s).
    Sustituye por b-roll / infográficos / motion graphics.
    """
    threshold = max(0, talking_head_after_sec)
    hook_dur = float(beats[-1]["end_sec"]) if beats else 0.0
    entire_broll_only = hook_dur < threshold
    effective_threshold = threshold if not entire_broll_only else hook_dur + 1.0
    allowed = sorted(HOOK_PRE_NARRATOR_SCENE_TYPES)
    out: list[dict[str, Any]] = []
    replacements = 0
    for i, beat in enumerate(beats):
        b = dict(beat)
        start = float(b.get("start_sec", 0) or 0)
        st = str(b.get("scene_type") or "broll").strip().lower()
        purpose = str(b.get("purpose") or "")
        hook_class = str(b.get("hook_class") or "mixed")
        if st == "talking_head" and start < effective_threshold:
            b["scene_type"] = _replacement_scene_type(
                index=i, purpose=purpose, hook_class=hook_class
            )
            b["narrator_visible"] = False
            b["scene_type_original"] = "talking_head"
            replacements += 1
        elif st == "talking_head":
            b["narrator_visible"] = True
        else:
            b["narrator_visible"] = False
            if st not in HOOK_PRE_NARRATOR_SCENE_TYPES and start < effective_threshold:
                b["scene_type"] = _replacement_scene_type(
                    index=i, purpose=purpose, hook_class=hook_class
                )
                replacements += 1
        out.append(b)
    policy = {
        "talking_head_allowed_after_sec": threshold,
        "hook_duration_sec": round(hook_dur, 2),
        "entire_hook_visual_only": entire_broll_only,
        "allowed_scene_types_before_narrator": allowed,
        "replacements_applied": replacements,
        "note": (
            "Modern hook: cinematic b-roll, infographics and motion graphics only until "
            f"{threshold}s; no on-camera narrator before that."
        ),
    }
    return out, policy


def _normalize_transition(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    t = str(raw.get("type") or "").strip().lower()
    if t not in VALID_TRANSITION_TYPES:
        return None
    try:
        frames = int(raw.get("duration_frames", 0) or 0)
    except (TypeError, ValueError):
        frames = 0
    if t == "hold":
        return {"type": "hold", "duration_frames": 0}
    if frames <= 0:
        frames = _default_transition_frames(t)
    return {
        "type": t,
        "duration_frames": min(24, max(2, frames)),
        "sync_audio_impact": bool(raw.get("sync_audio_impact", t in ("whip_pan", "flash", "speed_ramp"))),
    }


def _default_transition_frames(transition_type: str) -> int:
    return {
        "hard_cut": 3,
        "match_cut": 6,
        "whip_pan": 8,
        "blur": 10,
        "speed_ramp": 12,
        "zoom_cut": 6,
        "flash": 4,
        "dissolve": 14,
        "hold": 0,
    }.get(transition_type, 6)


def _rule_transition_to_next(
    *,
    index: int,
    n_beats: int,
    purpose: str,
    next_purpose: str | None,
    intensity: int,
    next_intensity: int | None,
    visual_energy: str,
    scene_type: str,
    next_scene_type: str | None,
    platform: str = "youtube_shorts",
) -> dict[str, Any] | None:
    if index >= n_beats - 1:
        return None
    ni = next_intensity if next_intensity is not None else intensity
    jump = ni - intensity
    high = visual_energy == "high"
    plat = normalize_platform(platform)
    preset = PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"])
    profile = str(preset.get("pacing_profile") or "short_vertical")
    narrative_long = profile == "narrative_long"

    if purpose == "breathing_room" or next_purpose == "breathing_room":
        return {"type": "dissolve", "duration_frames": 18, "sync_audio_impact": False}
    if jump < 0 and narrative_long:
        return {"type": "dissolve", "duration_frames": 14, "sync_audio_impact": False}

    if purpose == "payoff_promise":
        return {
            "type": "speed_ramp" if high else "flash",
            "duration_frames": 12 if high else 5,
            "sync_audio_impact": True,
        }
    if purpose == "payoff_release" or next_purpose == "payoff_release":
        return {"type": "dissolve", "duration_frames": 14, "sync_audio_impact": False}
    if jump >= 15 or (purpose == "contradiction" and high and not narrative_long):
        return {"type": "whip_pan", "duration_frames": 8 if high else 6, "sync_audio_impact": True}
    if jump >= 8 or purpose == "emotional_escalation":
        if narrative_long and jump < 14:
            return {"type": "match_cut", "duration_frames": 8, "sync_audio_impact": False}
        return {"type": "speed_ramp", "duration_frames": 10 if high else 8, "sync_audio_impact": True}
    if scene_type == next_scene_type and scene_type in ("broll", "cinematic_broll"):
        return {"type": "match_cut", "duration_frames": 6, "sync_audio_impact": False}
    if purpose == "curiosity":
        return {"type": "hard_cut", "duration_frames": 3, "sync_audio_impact": False}
    if ni >= 85:
        return {"type": "zoom_cut", "duration_frames": 6, "sync_audio_impact": True}
    if high and index % 2 == 1:
        return {"type": "blur", "duration_frames": 8, "sync_audio_impact": False}
    return {"type": "hard_cut", "duration_frames": 4, "sync_audio_impact": False}


def apply_beat_transitions(
    beats: list[dict[str, Any]],
    *,
    visual_energy: str,
    platform: str = "youtube_shorts",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    n = len(beats)
    out: list[dict[str, Any]] = []
    type_counts: dict[str, int] = {}
    for i, beat in enumerate(beats):
        b = dict(beat)
        next_b = beats[i + 1] if i + 1 < n else None
        existing = _normalize_transition(b.get("transition_to_next"))
        if existing and existing.get("type") != "hold":
            trans = existing
        elif i < n - 1 and next_b:
            trans = _rule_transition_to_next(
                index=i,
                n_beats=n,
                purpose=str(b.get("purpose") or ""),
                next_purpose=str(next_b.get("purpose") or ""),
                intensity=int(b.get("intensity") or 70),
                next_intensity=int(next_b.get("intensity") or 70),
                visual_energy=visual_energy,
                scene_type=str(b.get("scene_type") or "broll"),
                next_scene_type=str(next_b.get("scene_type") or "broll"),
                platform=platform,
            )
        else:
            trans = None
        b["transition_to_next"] = trans
        if trans:
            t = str(trans.get("type"))
            type_counts[t] = type_counts.get(t, 0) + 1
        out.append(b)
    prof = platform_pacing_profile(platform)
    summary = {
        "fps_assumption": 30,
        "transition_count": sum(type_counts.values()),
        "types_used": type_counts,
        "platform_profile": prof.get("pacing_profile"),
        "rhythm_note": prof.get("guidance"),
    }
    return out, summary


# Umbrales heurísticos para pacing (evitar dropoff por sobrecarga o aburrimiento).
_VIEWER_COGNITIVE_LOAD_DROPOFF = 78
_VIEWER_ATTENTION_BOREDOM = 52
_VIEWER_CURIOSITY_LOW = 48


def _clamp_metric(value: Any, default: int = 50) -> int:
    try:
        return min(100, max(0, int(float(value))))
    except (TypeError, ValueError):
        return default


def _valid_viewer_state(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return all(k in raw for k in ("attention", "curiosity", "cognitive_load"))


def _clamp_viewer_state(raw: dict[str, Any]) -> dict[str, int]:
    return {
        "attention": _clamp_metric(raw.get("attention"), 70),
        "curiosity": _clamp_metric(raw.get("curiosity"), 70),
        "cognitive_load": _clamp_metric(raw.get("cognitive_load"), 40),
    }


def _pacing_hint_from_viewer_state(vs: dict[str, int]) -> str | None:
    att = vs["attention"]
    cur = vs["curiosity"]
    load = vs["cognitive_load"]
    if load >= _VIEWER_COGNITIVE_LOAD_DROPOFF:
        return "dropoff_risk_reduce_cognitive_load"
    if att < _VIEWER_ATTENTION_BOREDOM:
        return "boredom_risk_boost_pattern_interrupt"
    if cur < _VIEWER_CURIOSITY_LOW:
        return "weak_curiosity_strengthen_gap"
    if load < 25 and att < 65:
        return "too_calms_increase_stimulus"
    return None


def _rule_viewer_state_for_beat(
    beat: dict[str, Any], *, platform: str = "youtube_shorts"
) -> dict[str, int]:
    purpose = str(beat.get("purpose") or "")
    hook_class = str(beat.get("hook_class") or "")
    intensity = _clamp_metric(beat.get("intensity"), 70)
    vd = beat.get("visual_density") if isinstance(beat.get("visual_density"), dict) else {}
    text_amt = str(vd.get("text_amount") or "medium").lower()
    try:
        overlays = int(vd.get("overlay_count", 1) or 1)
    except (TypeError, ValueError):
        overlays = 1
    has_text = bool(beat.get("text_overlay")) and bool(
        str(beat.get("text_overlay_content") or "").strip()
    )

    curiosity_by_purpose = {
        "curiosity": 76,
        "contradiction": 84,
        "emotional_escalation": 72,
        "payoff_promise": 64,
        "payoff_release": 48,
        "pattern_interrupt": 70,
        "breathing_room": 58,
    }
    curiosity = curiosity_by_purpose.get(purpose, 70)
    if hook_class in ("data", "shock"):
        curiosity = min(100, curiosity + 6)

    attention = int(min(98, max(48, 52 + intensity * 0.42)))
    if purpose == "payoff_promise":
        attention = min(98, attention + 6)

    cognitive_load = 28
    if text_amt == "high":
        cognitive_load += 20
    elif text_amt == "medium":
        cognitive_load += 10
    cognitive_load += min(22, overlays * 8)
    if has_text:
        cognitive_load += 8
    if purpose == "contradiction":
        cognitive_load += 14
    if purpose == "emotional_escalation":
        cognitive_load += 10
    if hook_class in ("data", "contradiction"):
        cognitive_load += 8
    if purpose == "payoff_promise":
        cognitive_load += 6
    if purpose == "payoff_release":
        cognitive_load = max(22, cognitive_load - 22)
    if purpose == "breathing_room":
        cognitive_load = max(18, cognitive_load - 18)
        attention = max(48, attention - 8)
    plat = normalize_platform(platform)
    load_cap = int(
        PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"]).get(
            "cognitive_load_cap", 78
        )
    )
    cognitive_load = min(load_cap, max(18, cognitive_load))

    return {
        "attention": attention,
        "curiosity": curiosity,
        "cognitive_load": cognitive_load,
    }


def _smooth_viewer_state_curve(states: list[dict[str, int]]) -> list[dict[str, int]]:
    """Evita saltos bruscos beat-a-beat en atención."""
    if len(states) < 2:
        return states
    out = [dict(states[0])]
    for i in range(1, len(states)):
        prev = out[-1]
        cur = dict(states[i])
        if cur["attention"] < prev["attention"] - 12 and i < len(states) - 1:
            cur["attention"] = max(cur["attention"], prev["attention"] - 8)
        out.append(cur)
    return out


def _build_viewer_state_tracking_summary(
    beats: list[dict[str, Any]],
    parsed_tracking: dict[str, Any] | None,
    *,
    platform: str = "youtube_shorts",
) -> dict[str, Any]:
    dropoff: list[int] = []
    boredom: list[int] = []
    curiosity_weak: list[int] = []
    attention_vals: list[int] = []
    load_vals: list[int] = []
    curve: list[dict[str, int]] = []
    plat = normalize_platform(platform)
    load_dropoff = int(
        PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"]).get(
            "cognitive_load_cap", _VIEWER_COGNITIVE_LOAD_DROPOFF
        )
    )

    for i, b in enumerate(beats):
        vs = b.get("viewer_state") if isinstance(b.get("viewer_state"), dict) else {}
        if not vs:
            continue
        curve.append(
            {
                "attention": int(vs.get("attention", 0)),
                "curiosity": int(vs.get("curiosity", 0)),
                "cognitive_load": int(vs.get("cognitive_load", 0)),
            }
        )
        attention_vals.append(int(vs.get("attention", 0)))
        load_vals.append(int(vs.get("cognitive_load", 0)))
        if int(vs.get("cognitive_load", 0)) >= load_dropoff:
            dropoff.append(i)
        if int(vs.get("attention", 0)) < _VIEWER_ATTENTION_BOREDOM:
            boredom.append(i)
        if int(vs.get("curiosity", 0)) < _VIEWER_CURIOSITY_LOW:
            curiosity_weak.append(i)

    peak_att_idx = attention_vals.index(max(attention_vals)) if attention_vals else 0
    peak_load = max(load_vals) if load_vals else 0

    recommendations: list[str] = []
    if dropoff:
        recommendations.append(
            "Reduce text/overlays/stats on beats "
            + ", ".join(str(x) for x in dropoff)
            + " — cognitive load risks scroll."
        )
    if boredom:
        recommendations.append(
            "Add pattern interrupt or faster cut on beats "
            + ", ".join(str(x) for x in boredom)
            + " — attention too low."
        )
    if not recommendations:
        recommendations.append(
            "Viewer state arc balanced: rising attention with controlled cognitive load."
        )

    summary: dict[str, Any] = {
        "model_version": 1,
        "attention_curve": [v["attention"] for v in curve],
        "curiosity_curve": [v["curiosity"] for v in curve],
        "cognitive_load_curve": [v["cognitive_load"] for v in curve],
        "peak_attention_beat_index": peak_att_idx,
        "peak_cognitive_load": peak_load,
        "dropoff_risk_beat_indices": dropoff,
        "boredom_risk_beat_indices": boredom,
        "weak_curiosity_beat_indices": curiosity_weak,
        "pacing_recommendations": recommendations,
    }
    if isinstance(parsed_tracking, dict):
        for key in ("narrative", "overall_dropoff_risk", "overall_boredom_risk"):
            if parsed_tracking.get(key) is not None:
                summary[key] = parsed_tracking.get(key)
    return summary


def apply_viewer_state_tracking(
    beats: list[dict[str, Any]],
    *,
    parsed_tracking: dict[str, Any] | None = None,
    platform: str = "youtube_shorts",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Modela estado del espectador por beat para pacing inteligente."""
    states: list[dict[str, int]] = []
    for b in beats:
        raw_vs = b.get("viewer_state") if isinstance(b, dict) else None
        if isinstance(raw_vs, dict) and _valid_viewer_state(raw_vs):
            states.append(_clamp_viewer_state(raw_vs))
        else:
            states.append(
                _rule_viewer_state_for_beat(
                    b if isinstance(b, dict) else {}, platform=platform
                )
            )

    states = _smooth_viewer_state_curve(states)

    out: list[dict[str, Any]] = []
    for i, beat in enumerate(beats):
        b = dict(beat)
        vs = states[i] if i < len(states) else _rule_viewer_state_for_beat(b, platform=platform)
        b["viewer_state"] = vs
        hint = _pacing_hint_from_viewer_state(vs)
        if hint:
            b["viewer_pacing_hint"] = hint
        out.append(b)

    tracking = _build_viewer_state_tracking_summary(
        out, parsed_tracking, platform=platform
    )
    return out, tracking


def normalize_visual_energy(raw: str | None, platform: str) -> str:
    e = (raw or "").strip().lower()
    if e in VISUAL_ENERGY_PROFILES:
        return e
    return str(PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["youtube_shorts"])["visual_energy_default"])


def classify_hook_class(text: str) -> str:
    t = text.lower()
    scores: dict[str, int] = {name: 0 for name, _ in _CLASSIFIER_RULES}
    for name, patterns in _CLASSIFIER_RULES:
        for pat in patterns:
            if re.search(pat, t, re.I):
                scores[name] = scores.get(name, 0) + 1
    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best
    return "curiosity"


def detect_retention_patterns(text: str) -> list[str]:
    t = text.lower()
    found: list[str] = []
    checks: list[tuple[str, list[str]]] = [
        ("curiosity_gap", [r"nobody", r"secret", r"nadie", r"what you don't"]),
        ("contradiction", [r"more than", r"but actually", r"sin embargo"]),
        ("shock", [r"most people", r"90%", r"millonarios"]),
        ("fear", [r"stuck", r"can't", r"atascado", r"waste"]),
        ("fast_payoff", [r"in \d+ second", r"en \d+ seg"]),
        ("stakes", [r"matters more", r"importa más", r"game changer"]),
        ("pattern_interrupt", [r"stop", r"wait", r"espera", r"listen"]),
    ]
    for label, pats in checks:
        if any(re.search(p, t, re.I) for p in pats):
            found.append(label)
    return found or ["curiosity_gap"]


def _split_hook_into_phrases(hook_text: str) -> list[str]:
    raw = re.sub(r"\s+", " ", hook_text.replace("\n", " ").strip())
    if not raw:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=[,;])\s+", raw)
    chunks = [p.strip() for p in parts if p.strip()]
    if len(chunks) <= 1 and len(raw) > 80:
        words = raw.split()
        size = max(6, len(words) // 6)
        chunks = []
        for i in range(0, len(words), size):
            seg = " ".join(words[i : i + size]).strip()
            if seg:
                chunks.append(seg)
    return chunks


def _has_cinematic_anchors(text: str) -> bool:
    """Señales de prompt con identidad visual (lugar, luz, encuadre)."""
    t = (text or "").lower()
    anchors = (
        "cinematic",
        "split frame",
        "shallow depth",
        "dof",
        "35mm",
        "film grain",
        "rim light",
        "practical",
        "neon",
        "kitchen table",
        "cafe",
        "night",
        "close-up",
        "macro shot",
        "over-the-shoulder",
        "ots",
        "glow",
        "chiaroscuro",
        "handheld",
    )
    return sum(1 for a in anchors if a in t) >= 2


def _is_stock_footage_prompt(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    if len(t) < 50:
        return True
    if any(ban in t for ban in _GENERIC_VISUAL_BANS):
        return True
    if any(re.search(p, t, re.I) for p in _STOCK_FOOTAGE_RE):
        if not _has_cinematic_anchors(t):
            return True
    vague = ("b-roll", "b roll", "stock photo", "stock image", "montage", "footage of", "showing success")
    if sum(1 for v in vague if v in t) >= 1 and not _has_cinematic_anchors(t):
        return True
    if re.search(r"\b(two friends|friends discussing|people discussing)\b", t, re.I):
        return not _has_cinematic_anchors(t)
    return False


def _is_generic_visual_description(text: str) -> bool:
    return _is_stock_footage_prompt(text)


def _cinematic_visual_description(
    emotion: str,
    phrase: str,
    *,
    index: int,
    energy: str,
) -> str:
    """Línea visual concreta para image models (modo reglas)."""
    templates = _CINEMATIC_BEAT_TEMPLATES.get(emotion, _CINEMATIC_BEAT_TEMPLATES["curiosity"])
    base = templates[index % len(templates)]
    hook_hint = phrase.strip()[:90]
    if hook_hint:
        return f"{base}, narrative cue: {hook_hint}"
    return base


def _synthetic_cinematic_prompt_from_beat(beat: dict[str, Any]) -> str:
    """Genera prompt anti-stock con identidad, lugar, emoción y cámara."""
    emotion = str(beat.get("emotion") or "curiosity")
    purpose = str(beat.get("purpose") or "")
    scene_type = str(beat.get("scene_type") or "broll").lower()
    index = int(beat.get("index", 0))
    phrase = str(beat.get("text_overlay_content") or "").strip()
    cam = beat.get("camera") if isinstance(beat.get("camera"), dict) else {}
    shot = str(cam.get("shot") or "medium close-up")
    block = str(beat.get("sequence_block") or "").strip().lower()
    if block:
        from videomaker.llm.hook_visual_sequence import block_color_spec

        spec = block_color_spec(block, int(beat.get("index", 0)))
        lighting = str(cam.get("lighting") or spec.get("light_source") or spec["light_phrase"])
    else:
        lighting = str(cam.get("lighting") or "cool blue artificial light, deep shadows, shallow depth of field")
    composition = str(cam.get("composition") or "off-center subject, cinematic framing")
    style = str(beat.get("visual_style") or "cinematic")

    if purpose == "contradiction" or scene_type == "split_screen":
        core = (
            "cinematic split frame diptych, two friends in dim Chicago cafe at night, "
            "left panel relaxed checking investment app with subtle green phone glow on face, "
            "right panel anxious staring at overdraft notification red screen light, "
            "wet window bokeh behind, shallow depth of field, 35mm film grain, emotional contrast"
        )
    elif scene_type in ("motion_graphic", "data_ui", "text_card"):
        core = (
            f"cinematic UI moment over real environment, bold kinetic typography space, "
            f"{_cinematic_visual_description(emotion, phrase, index=index, energy='high')}, "
            f"high contrast, not corporate stock"
        )
    else:
        core = _cinematic_visual_description(
            emotion, phrase, index=index, energy=style if style in ("high", "low", "medium") else "medium"
        )

    return (
        f"{core}, {shot}, {lighting}, {composition}, "
        f"photorealistic cinematic still, distinct characters and location, not stock footage"
    )[:900]


def resolve_image_prompt_for_beat(beat: dict[str, Any]) -> str:
    """
    Prompt final para SD/MJ/Flux: nunca devolver línea tipo Shutterstock.
    Prioridad: seed/visuales ya cinematográficos → síntesis desde metadata del beat.
    """
    for key in ("image_prompt_seed", "visual_description"):
        raw = str(beat.get(key) or "").strip()
        if raw and not _is_stock_footage_prompt(raw):
            cam = beat.get("camera") if isinstance(beat.get("camera"), dict) else {}
            if _has_cinematic_anchors(raw):
                return raw[:900]
            shot = str(cam.get("shot") or "medium close-up")
            light = str(cam.get("lighting") or "natural cinematic light")
            return f"{raw}, {shot}, {light}, shallow depth of field, 35mm, not stock photo"[:900]
    return _synthetic_cinematic_prompt_from_beat(beat)


def enrich_beats_cinematic_prompts(beats: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Asegura image_prompt_seed y visual_description cinematográficos en todos los beats."""
    out: list[dict[str, Any]] = []
    fixes = 0
    for beat in beats:
        b = dict(beat)
        prior = str(b.get("visual_description") or b.get("image_prompt_seed") or "")
        prompt = resolve_image_prompt_for_beat(b)
        if prior and _is_stock_footage_prompt(prior):
            b["visual_description_original"] = prior[:500]
            fixes += 1
        b["visual_description"] = prompt
        b["image_prompt_seed"] = prompt
        b["prompt_style"] = "cinematic_narrative"
        out.append(b)
    return out, fixes


def _energy_intensity_boost(visual_energy: str) -> int:
    return {"high": 5, "medium": 0, "low": -8}.get(visual_energy, 0)


def _intensity_curve_vertical_fast(
    n_beats: int,
    *,
    boost: int,
    peak_cap: int,
    max_step: int,
) -> list[int]:
    """TikTok / Shorts / Reels: escalada rápida, sin respiraciones."""
    if n_beats == 1:
        return [min(peak_cap, max(0, 72 + boost))]
    has_release = n_beats >= 5
    peak_idx = n_beats - 2 if has_release else n_beats - 1
    curve: list[int] = []
    for i in range(n_beats):
        if i == 0:
            v = 45
        elif i == 1:
            v = 60
        elif has_release and i == n_beats - 1:
            v = 65
        elif i == peak_idx:
            v = peak_cap
        elif i < peak_idx:
            if peak_idx <= 2:
                v = 75
            else:
                t = (i - 1) / max(1, peak_idx - 1)
                v = int(60 + t * (peak_cap - 60))
        else:
            v = 80
        curve.append(min(peak_cap, max(0, v + boost)))
    peak_at = curve.index(max(curve)) if curve else 0
    for i in range(1, peak_at + 1):
        step = curve[i] - curve[i - 1]
        if step < 0:
            curve[i] = min(peak_cap, curve[i - 1] + 5)
        elif step > max_step:
            curve[i] = min(peak_cap, curve[i - 1] + max_step)
    if has_release and len(curve) > 1 and curve[-1] >= curve[-2]:
        curve[-1] = max(55, curve[-2] - 20)
    return curve


def _intensity_curve_narrative_long(
    n_beats: int,
    *,
    boost: int,
    peak_cap: int,
    max_step: int,
    breath_interval: int = 2,
) -> list[int]:
    """
    YouTube largo: escalada lenta + ciclos tensión-release (breathing room).
    Ej. 6 beats: [42, 54, 48, 62, 56, 70, 62]
    """
    if n_beats == 1:
        return [min(peak_cap, max(0, 58 + boost))]
    has_release = n_beats >= 4
    peak_idx = n_beats - 2 if has_release else n_beats - 1
    curve: list[int] = []
    for i in range(n_beats):
        if i == 0:
            v = 40
        elif i == 1:
            v = 52
        elif has_release and i == n_beats - 1:
            v = 58
        elif i == peak_idx:
            v = peak_cap
        elif i < peak_idx:
            t = (i - 1) / max(1, peak_idx - 1)
            v = int(52 + t * (peak_cap - 52))
        else:
            v = int(peak_cap * 0.75)
        curve.append(min(peak_cap, max(0, v + boost)))
    # Tension-release: dips cada breath_interval (no en 0, pico ni release final)
    for i in range(2, n_beats - 1):
        if (i - 1) % breath_interval == 0 and i != peak_idx:
            dip = max(38, curve[i - 1] - 10)
            curve[i] = min(curve[i], dip)
    for i in range(1, n_beats):
        if i == peak_idx:
            continue
        step = curve[i] - curve[i - 1]
        if step > max_step:
            curve[i] = min(peak_cap, curve[i - 1] + max_step)
        if step < -12:
            curve[i] = max(38, curve[i - 1] - 10)
    if has_release and len(curve) > 1:
        curve[-1] = max(50, min(curve[-2] - 12, curve[-1]))
    return curve


def compute_viral_intensity_curve(
    n_beats: int,
    visual_energy: str = "medium",
    platform: str = "youtube_shorts",
) -> list[int]:
    """Curva de intensidad según plataforma (vertical rápido vs narrativo largo)."""
    if n_beats <= 0:
        return []
    plat = normalize_platform(platform)
    preset = PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"])
    boost = _energy_intensity_boost(visual_energy)
    peak_cap = int(preset.get("intensity_peak_cap", 90))
    max_step = int(preset.get("max_intensity_step_up", 18))
    profile = str(preset.get("pacing_profile") or "short_vertical")
    if profile == "narrative_long":
        return _intensity_curve_narrative_long(
            n_beats,
            boost=boost,
            peak_cap=peak_cap,
            max_step=max_step,
            breath_interval=int(preset.get("breath_interval", 2)),
        )
    return _intensity_curve_vertical_fast(
        n_beats, boost=boost, peak_cap=peak_cap, max_step=max_step
    )


def _pacing_role_for_beat(
    index: int,
    n_beats: int,
    intensity: int,
    prev_intensity: int | None,
    platform: str,
) -> str:
    plat = normalize_platform(platform)
    preset = PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"])
    if preset.get("pacing_profile") == "narrative_long":
        if index == 0:
            return "hook_open"
        if prev_intensity is not None and intensity < prev_intensity - 6:
            return "breathing_room"
        if index == n_beats - 1:
            return "payoff_release"
        if index == n_beats - 2:
            return "tension_peak"
        if intensity >= int(preset.get("intensity_peak_cap", 84)) - 5:
            return "tension_rise"
        return "narrative_hold"
    if index == 0:
        return "pattern_interrupt"
    if index == n_beats - 1:
        return "payoff_release" if n_beats >= 5 else "payoff_punch"
    return "stimulus_beat"


def apply_platform_pacing(
    beats: list[dict[str, Any]],
    intensity_curve: list[int],
    *,
    platform: str,
) -> list[dict[str, Any]]:
    """Marca roles de pacing y ajusta purpose en beats de respiración (YouTube largo)."""
    plat = normalize_platform(platform)
    profile = platform_pacing_profile(plat)
    preset = PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"])
    out: list[dict[str, Any]] = []
    prev_i: int | None = None
    for i, beat in enumerate(beats):
        b = dict(beat)
        intensity = int(
            b.get("intensity") or (intensity_curve[i] if i < len(intensity_curve) else 70)
        )
        role = _pacing_role_for_beat(i, len(beats), intensity, prev_i, plat)
        b["pacing_role"] = role
        b["platform_pacing"] = str(preset.get("pacing_profile") or "short_vertical")
        if role == "breathing_room":
            b["purpose"] = "breathing_room"
            b["motion"] = "slow_zoom"
            vd = b.get("visual_density") if isinstance(b.get("visual_density"), dict) else {}
            b["visual_density"] = {
                **vd,
                "text_amount": "low",
                "motion_intensity": "low",
                "overlay_count": max(0, int(vd.get("overlay_count", 1)) - 1),
            }
        elif profile["pacing_profile"] == "hyper_short" and i == 0:
            b["motion"] = b.get("motion") or "fast_zoom"
        out.append(b)
        prev_i = intensity
    return out


def purpose_for_arc_index(index: int, n_beats: int) -> str:
    if index == 0:
        return "curiosity"
    if index == 1:
        return "contradiction"
    if n_beats >= 5 and index == n_beats - 1:
        return "payoff_release"
    if index == n_beats - 1:
        return "payoff_promise"
    if index >= 2:
        return "emotional_escalation"
    return "pattern_interrupt"


def _motion_for_intensity(intensity: int) -> str:
    if intensity >= 88:
        return "fast_zoom"
    if intensity >= 75:
        return "whip_pan"
    if intensity >= 62:
        return "push_in"
    if intensity >= 48:
        return "handheld"
    return "slow_zoom"


def _visual_density_for_intensity(intensity: int) -> dict[str, Any]:
    if intensity >= 85:
        return {"text_amount": "high", "motion_intensity": "high", "overlay_count": 3}
    if intensity >= 70:
        return {"text_amount": "high", "motion_intensity": "medium", "overlay_count": 2}
    if intensity >= 55:
        return {"text_amount": "medium", "motion_intensity": "medium", "overlay_count": 1}
    return {"text_amount": "low", "motion_intensity": "low", "overlay_count": 1}


def apply_intensity_escalation(
    beats: list[dict[str, Any]],
    intensity_curve: list[int],
    *,
    visual_energy: str,
    platform: str = "youtube_shorts",
) -> list[dict[str, Any]]:
    """Sincroniza purpose, intensity, motion y densidad con la curva viral."""
    n = len(beats)
    curve = intensity_curve[:n]
    if len(curve) < n:
        curve = curve + compute_viral_intensity_curve(
            n - len(curve), visual_energy, platform=platform
        )
    curve = curve[:n]
    out: list[dict[str, Any]] = []
    for i, beat in enumerate(beats):
        b = dict(beat)
        intensity = int(curve[i]) if i < len(curve) else 70
        intensity = min(100, max(0, intensity))
        b["intensity"] = intensity
        b["purpose"] = purpose_for_arc_index(i, n)
        b["motion"] = _motion_for_intensity(intensity)
        b["visual_density"] = _visual_density_for_intensity(intensity)
        if intensity >= 80:
            b["visual_style"] = "kinetic" if visual_energy != "low" else b.get("visual_style", "cinematic")
        out.append(b)
    return out


def resolve_intensity_curve(
    beats: list[dict[str, Any]],
    parsed_curve: Any,
    *,
    visual_energy: str,
    platform: str = "youtube_shorts",
) -> list[int]:
    n = len(beats)
    if isinstance(parsed_curve, list) and len(parsed_curve) >= n:
        nums: list[int] = []
        for x in parsed_curve[:n]:
            try:
                nums.append(min(100, max(0, int(float(x)))))
            except (TypeError, ValueError):
                nums.append(70)
        if nums:
            return nums
    from_beats: list[int] = []
    for b in beats:
        try:
            from_beats.append(min(100, max(0, int(b.get("intensity", 0)))))
        except (TypeError, ValueError):
            from_beats.append(0)
    if len(from_beats) == n and any(v > 0 for v in from_beats):
        return from_beats
    return compute_viral_intensity_curve(n, visual_energy, platform=platform)


def intensity_arc_summary(curve: list[int], *, platform: str = "youtube_shorts") -> dict[str, Any]:
    if not curve:
        return {"shape": "empty", "peak_beat_index": 0, "peak_intensity": 0}
    peak = max(curve)
    plat = normalize_platform(platform)
    preset = PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"])
    shape = (
        "narrative_tension_release"
        if preset.get("pacing_profile") == "narrative_long"
        else "vertical_fast_escalation"
    )
    return {
        "shape": shape,
        "platform": plat,
        "pacing_profile": preset.get("pacing_profile"),
        "stages": ["curiosity", "contradiction", "emotional_escalation", "payoff_promise", "payoff_release"],
        "peak_beat_index": curve.index(peak),
        "peak_intensity": peak,
        "curve": curve,
    }


_MUSIC_ENERGY_LEVELS = frozenset(
    {"minimal", "low", "building", "rising", "peak", "release", "drop", "static"}
)

_HOOK_CLASS_SFX_PALETTE: dict[str, list[str]] = {
    "curiosity": ["soft_whoosh", "notification_ping", "subtle_room_tone"],
    "contradiction": ["record_scratch_light", "bass_sting", "clock_tick"],
    "shock": ["bass_hit", "impact_riser", "glitch_hit"],
    "fear": ["heartbeat_low", "tension_drone", "warning_beep"],
    "fast_payoff": ["riser_short", "snap", "bass_hit"],
    "data": ["cash_register", "keyboard_tap", "data_blip"],
    "story": ["paper_rustle", "soft_piano_sting", "room_tone"],
    "invitation": ["soft_chime", "breath_room", "warm_pad_hit"],
    "mixed": ["whoosh", "bass_hit", "subtle_riser"],
}


def _beat_audio_for_arc(
    *,
    index: int,
    n_beats: int,
    purpose: str,
    intensity: int,
    primary_hook_class: str,
    peak_idx: int,
    silence_before_payoff: bool,
) -> dict[str, Any]:
    palette = _HOOK_CLASS_SFX_PALETTE.get(primary_hook_class, _HOOK_CLASS_SFX_PALETTE["mixed"])
    if purpose == "curiosity":
        music = "minimal"
        sfx = [palette[0], "subtle_room_tone"]
    elif purpose == "contradiction":
        music = "building"
        sfx = [palette[1] if len(palette) > 1 else "bass_sting", "clock_tick"]
    elif purpose == "emotional_escalation":
        music = "rising"
        sfx = ["tension_riser", palette[-1], "heartbeat_tension"]
    elif purpose == "payoff_promise":
        music = "peak"
        sfx = ["bass_hit", "cash_register", "impact_sting"]
    elif purpose == "payoff_release":
        music = "release"
        sfx = ["soft_exhale", "warm_pad", "room_tone"]
    elif purpose == "breathing_room":
        music = "minimal"
        sfx = ["room_tone", "soft_exhale"]
    else:
        music = "building"
        sfx = [palette[0]]

    use_silence = (
        silence_before_payoff
        and index == peak_idx - 1
        and peak_idx > 0
        and purpose != "payoff_promise"
    )
    impact = purpose == "payoff_promise" or (intensity >= 88 and index == peak_idx)

    return {
        "music_energy": music,
        "sfx": sfx[:3],
        "silence": use_silence,
        "silence_duration_ms": 180 if use_silence else 0,
        "impact_beat": impact,
        "duck_voice": impact,
    }


def compute_hook_audio_design(
    beats: list[dict[str, Any]],
    intensity_curve: list[int],
    *,
    primary_hook_class: str = "curiosity",
    platform: str = "youtube_shorts",
) -> dict[str, Any]:
    n = len(beats)
    if n == 0:
        return {
            "music_energy": "rising",
            "sfx": [],
            "silence_before_payoff": False,
            "impact_beat_indices": [],
        }
    peak_idx = (
        intensity_curve.index(max(intensity_curve))
        if intensity_curve
        else max(0, n - 1)
    )
    plat = normalize_platform(platform)
    preset = PLATFORM_PRESETS.get(plat, PLATFORM_PRESETS["youtube_shorts"])
    narrative = preset.get("pacing_profile") == "narrative_long"
    silence_before = n >= 3 and peak_idx >= 1
    if narrative:
        silence_before = n >= 4
    palette = _HOOK_CLASS_SFX_PALETTE.get(primary_hook_class, _HOOK_CLASS_SFX_PALETTE["mixed"])
    impact_threshold = 88 if not narrative else 80
    impact_indices = [
        i
        for i, b in enumerate(beats)
        if isinstance(b, dict)
        and (
            b.get("purpose") == "payoff_promise"
            or (intensity_curve[i] if i < len(intensity_curve) else 0) >= impact_threshold
        )
        and b.get("purpose") != "breathing_room"
    ]
    if not impact_indices and peak_idx < n:
        impact_indices = [peak_idx]

    return {
        "music_energy": "building" if narrative else "rising",
        "music_profile": (
            "narrative_tension_release"
            if narrative
            else "hook_pulse_escalation_to_impact"
        ),
        "sfx": list(dict.fromkeys(palette + ["bass_hit", "riser_short"]))[:6],
        "silence_before_payoff": silence_before,
        "silence_beat_index": peak_idx - 1 if silence_before else None,
        "impact_beat_indices": impact_indices,
        "sync_to_intensity_curve": True,
    }


def _normalize_audio_design(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    me = str(raw.get("music_energy") or "rising").strip().lower()
    if me not in _MUSIC_ENERGY_LEVELS:
        me = "rising"
    sfx_raw = raw.get("sfx")
    sfx: list[str] = []
    if isinstance(sfx_raw, list):
        sfx = [str(x).strip() for x in sfx_raw if str(x).strip()][:8]
    impact = raw.get("impact_beat_indices")
    impact_idx: list[int] = []
    if isinstance(impact, list):
        for x in impact:
            try:
                impact_idx.append(int(x))
            except (TypeError, ValueError):
                continue
    silence_idx = raw.get("silence_beat_index")
    try:
        silence_beat = int(silence_idx) if silence_idx is not None else None
    except (TypeError, ValueError):
        silence_beat = None
    return {
        "music_energy": me,
        "music_profile": str(raw.get("music_profile") or "hook_pulse_escalation_to_impact").strip(),
        "sfx": sfx,
        "silence_before_payoff": bool(raw.get("silence_before_payoff", False)),
        "silence_beat_index": silence_beat,
        "impact_beat_indices": impact_idx,
        "sync_to_intensity_curve": bool(raw.get("sync_to_intensity_curve", True)),
    }


def apply_audio_design(
    beats: list[dict[str, Any]],
    intensity_curve: list[int],
    *,
    primary_hook_class: str,
    parsed_audio: dict[str, Any] | None,
    platform: str = "youtube_shorts",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    n = len(beats)
    peak_idx = (
        intensity_curve.index(max(intensity_curve))
        if intensity_curve
        else max(0, n - 1)
    )
    global_audio = parsed_audio or compute_hook_audio_design(
        beats,
        intensity_curve,
        primary_hook_class=primary_hook_class,
        platform=platform,
    )
    if not global_audio.get("sfx"):
        global_audio["sfx"] = compute_hook_audio_design(
            beats,
            intensity_curve,
            primary_hook_class=primary_hook_class,
            platform=platform,
        ).get("sfx", [])
    silence_before = bool(global_audio.get("silence_before_payoff"))
    if silence_before and global_audio.get("silence_beat_index") is None and peak_idx > 0:
        global_audio["silence_beat_index"] = peak_idx - 1

    impact_set = set(global_audio.get("impact_beat_indices") or [])

    out: list[dict[str, Any]] = []
    for i, beat in enumerate(beats):
        b = dict(beat)
        purpose = str(b.get("purpose") or purpose_for_arc_index(i, n))
        intensity = int(b.get("intensity") or (intensity_curve[i] if i < len(intensity_curve) else 70))
        existing = b.get("audio") if isinstance(b.get("audio"), dict) else {}
        rule_audio = _beat_audio_for_arc(
            index=i,
            n_beats=n,
            purpose=purpose,
            intensity=intensity,
            primary_hook_class=primary_hook_class,
            peak_idx=peak_idx,
            silence_before_payoff=silence_before,
        )
        merged = {**rule_audio, **{k: v for k, v in existing.items() if v is not None}}
        if i in impact_set:
            merged["impact_beat"] = True
        sil_idx = global_audio.get("silence_beat_index")
        if sil_idx is not None and i == sil_idx:
            merged["silence"] = True
            merged["silence_duration_ms"] = merged.get("silence_duration_ms") or 180
        b["audio"] = merged
        out.append(b)
    return out, global_audio


def _finance_style_from_hook_class(hook_class: str) -> str:
    mapping = {
        "data": "data_minimalist",
        "contradiction": "data_minimalist",
        "shock": "data_minimalist",
        "story": "deep_documentary",
        "invitation": "intimate_pov",
        "fear": "financial_noir",
        "curiosity": "financial_noir",
        "fast_payoff": "data_minimalist",
        "mixed": "deep_documentary",
    }
    return mapping.get(hook_class, "deep_documentary")


def _default_beat(
    *,
    index: int,
    start: float,
    end: float,
    phrase: str,
    hook_class: str,
    platform: str,
    energy: str,
    intensity: int,
    n_beats: int,
) -> dict[str, Any]:
    emotion = {
        "curiosity": "curiosity",
        "contradiction": "tension",
        "shock": "shock",
        "fear": "tension",
        "fast_payoff": "urgency",
        "data": "shock",
        "story": "tension",
        "invitation": "curiosity",
    }.get(hook_class, "curiosity")
    cinematic = _cinematic_visual_description(emotion, phrase, index=index, energy=energy)
    purpose = purpose_for_arc_index(index, n_beats)
    motion = _motion_for_intensity(intensity)
    vd = _visual_density_for_intensity(intensity)
    return {
        "index": index,
        "start_sec": round(start, 2),
        "end_sec": round(end, 2),
        "duration_sec": round(end - start, 2),
        "purpose": purpose,
        "hook_class": hook_class,
        "retention_pattern": "curiosity_gap" if index == 0 else "pattern_interrupt",
        "intensity": intensity,
        "scene_type": "broll" if index % 2 == 0 else "motion_graphic",
        "narrator_visible": False,
        "visual_style": "kinetic" if intensity >= 80 and energy != "low" else "cinematic",
        "motion": motion,
        "text_overlay": True,
        "text_overlay_content": phrase[:72] if intensity >= 55 else "",
        "emotion": emotion,
        "visual_description": cinematic,
        "camera": {
            "shot": "close-up" if intensity >= 75 else ("medium close-up" if index == 0 else "medium"),
            "lighting": "high contrast rim light" if intensity >= 85 else "soft warm practicals, shallow depth",
            "composition": "subject off-center, negative space for text" if index < 2 else "center weighted",
            "motion": motion,
        },
        "visual_density": vd,
        "image_prompt_seed": cinematic,
    }


def build_beats_rule_based(
    hook_text: str,
    *,
    platform: str,
    visual_energy: str,
    max_beats: int | None = None,
) -> list[dict[str, Any]]:
    preset = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["youtube_shorts"])
    beat_sec = float(preset["default_beat_sec"])
    cap = max_beats or int(preset["max_beats"])
    phrases = _split_hook_into_phrases(hook_text)
    if not phrases:
        phrases = [hook_text[:200]]
    hook_class = classify_hook_class(hook_text)
    n = min(len(phrases), cap)
    curve = compute_viral_intensity_curve(n, visual_energy, platform=platform)
    beats: list[dict[str, Any]] = []
    t = 0.0
    for i, phrase in enumerate(phrases[:cap]):
        end = t + beat_sec
        beats.append(
            _default_beat(
                index=i,
                start=t,
                end=end,
                phrase=phrase,
                hook_class=hook_class,
                platform=platform,
                energy=visual_energy,
                intensity=curve[i] if i < len(curve) else 70,
                n_beats=n,
            )
        )
        t = end
    return beats


def default_hook_router_system_prompt(
    *,
    output_lang: str,
    platform: str,
    visual_energy: str,
    talking_head_after_sec: int | None = None,
) -> str:
    """Prompt interno mostrado en UI (modo IA, system prompt automático)."""
    plat = normalize_platform(platform)
    energy = normalize_visual_energy(visual_energy, plat)
    th = talking_head_after_sec if talking_head_after_sec is not None else resolve_talking_head_after_sec(plat)
    return retention_router_system_prompt(
        output_lang=normalize_language_code(output_lang or "es"),
        platform=plat,
        visual_energy=energy,
        talking_head_after_sec=th,
    )


def retention_router_system_prompt(
    *,
    output_lang: str,
    platform: str,
    visual_energy: str,
    talking_head_after_sec: int = 25,
) -> str:
    plat = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["youtube_shorts"])
    energy = VISUAL_ENERGY_PROFILES.get(visual_energy, VISUAL_ENERGY_PROFILES["medium"])
    loc = language_label(output_lang)
    from videomaker.llm.hook_visual_sequence import documentary_sequence_system_addon

    doc_seq = documentary_sequence_system_addon()
    return f"""You are a retention-first hook director and cinematographer for short-form and long-form video.

Your job is NOT to edit video — it is to answer: "What stops the viewer from scrolling?"
You think in SHOTS, not categories. Every visual_description must be shootable in one frame.

Target platform: {plat["label"]} ({platform})
Visual energy: {visual_energy} — {energy["cuts"]}
Default beat length: variable by narrative rhythm (NOT fixed {plat["default_beat_sec"]}s every shot):
- Tension/confusion/high intensity: 1–2s quick cuts
- Revelation/contrast/emotional weight: 4–5s breathing room
- Medium beats: ~2–3.5s; timeline must sum to target_hook_duration_sec

PLATFORM-SPECIFIC PACING (mandatory — never use one universal vertical rhythm):
{_platform_pacing_guidance(platform)}
Pacing profile: {plat.get("pacing_profile", "short_vertical")} · escalation: {plat.get("escalation_style", "fast")}
Breathing room beats: {"yes — mark purpose=breathing_room on tension dips" if plat.get("breath_beats_enabled") else "no — keep intensity climbing"}
Intensity peak cap for this platform: ~{plat.get("intensity_peak_cap", 90)}

Analyze ONLY the hook narration (Act 1). Detect retention psychology:
- curiosity_gap, contradiction, shock, fear, fast_payoff, stakes, pattern_interrupt

Classify primary hook_class: curiosity | contradiction | shock | fear | fast_payoff | story | data | invitation | mixed

Output ONLY valid JSON (no markdown) with this structure:
{{
  "retention_analysis": {{
    "primary_hook_class": "string",
    "patterns_detected": ["curiosity_gap", "..."],
    "scroll_stop_rationale": "1-2 sentences: why viewer keeps watching",
    "novelty_score": 0-100,
    "emotional_intensity_score": 0-100,
    "pacing_score": 0-100
  }},
  "platform_plan": {{
    "platform": "{platform}",
    "visual_energy": "{visual_energy}",
    "target_hook_duration_sec": number,
    "beat_duration_target_sec": number,
    "cut_style": "string"
  }},
  "density_controls": {{
    "text_density": "low|medium|high",
    "cut_frequency": "low|medium|high",
    "motion_level": "low|medium|high",
    "max_overlays_per_beat": 1-3,
    "anti_fatigue_note": "string"
  }},
  "visual_sequence_plan": {{
    "arc": "intimate_close → medium_space → contrast_world → intimate_weight",
    "target_beats": number,
    "emotional_tone": "quiet exhaustion, not melodrama",
    "motif_thread": "optional sparse motif (screen glow, cold cup, closed door)",
    "rules": ["no consecutive same shot_distance+shot_angle", "each beat adds new layer"]
  }},
  "intensity_curve": [45, 60, 80, 90, 65],
  "viewer_state_tracking": {{
    "attention_curve": [70, 78, 85, 92, 80],
    "curiosity_curve": [76, 84, 72, 64, 48],
    "cognitive_load_curve": [35, 48, 58, 62, 40],
    "dropoff_risk_beat_indices": [],
    "boredom_risk_beat_indices": [],
    "pacing_recommendations": ["string"]
  }},
  "audio_design": {{
    "music_energy": "rising",
    "music_profile": "hook_pulse_escalation_to_impact",
    "sfx": ["cash_register", "bass_hit", "riser_short"],
    "silence_before_payoff": true,
    "silence_beat_index": 2,
    "impact_beat_indices": [3],
    "sync_to_intensity_curve": true
  }},
  "micro_beats": [
    {{
      "index": 0,
      "start_sec": 0,
      "end_sec": 1.5,
      "duration_sec": number,
      "rhythm_tier": "fast|medium|slow",
      "rhythm_note": "why this hold length matches narration",
      "shot_hierarchy": "support|support_build|anchor|afterglow",
      "is_anchor_shot": false,
      "purpose": "curiosity|contradiction|emotional_escalation|payoff_promise|payoff_release|pattern_interrupt|breathing_room",
      "pacing_role": "pattern_interrupt|stimulus_beat|breathing_room|tension_rise|tension_peak|payoff_release|hook_open|narrative_hold",
      "intensity": 0-100,
      "hook_class": "curiosity|...",
      "retention_pattern": "curiosity_gap|...",
      "sequence_block": "intimate_close|medium_space|contrast_world|intimate_weight",
      "shot_distance": "extreme_close|macro|close_up|medium_close|medium|medium_wide|wide|establishing",
      "shot_angle": "high|eye_level|low|profile|over_shoulder|three_quarter|wide_angle",
      "new_information_layer": "what NEW visual fact this beat adds vs the previous beat",
      "camera_motion": "slow_push_in|push_in|slow_pull_out|pull_out|static",
      "camera_motion_direction": "in|out|none",
      "camera_motion_note": "short English phrase, e.g. slow push-in toward subject",
      "color_temperature": "cool|cool_neutral|warm (warm ONLY in contrast_world block)",
      "light_quality": "specific source + temperature, e.g. cool blue phone glow, warm amber interior, harsh fluorescent",
      "color_palette": ["cool blue", "charcoal", "..."],
      "scene_type": "broll|motion_graphic|text_card|split_screen|stock|data_ui (NO talking_head before {talking_head_after_sec}s)",
      "narrator_visible": false,
      "visual_style": "cinematic|kinetic|documentary|data_ui|noir",
      "motion": "slow_zoom|fast_zoom|whip_pan|static|push_in|handheld",
      "text_overlay": true,
      "text_overlay_content": "short on-screen text in {loc}",
      "emotion": "curiosity|tension|fear|shock|hope|urgency|success",
      "visual_description": "ONE cinematic shot in English (25-45 words): who + where + action + light + emotional micro-detail",
      "camera": {{
        "shot": "close-up|medium close-up|medium|wide|macro|OTS",
        "lighting": "MUST name source + temperature (cool blue light, warm amber interior, harsh fluorescent — match sequence_block)",
        "color_temperature": "cool|cool_neutral|warm",
        "composition": "specific (e.g. shallow DOF, off-center subject, negative space for text)",
        "motion": "specific (e.g. slow push-in, handheld drift, static hold)"
      }},
      "visual_density": {{
        "text_amount": "low|medium|high",
        "motion_intensity": "low|medium|high",
        "overlay_count": 0-3
      }},
      "image_prompt_seed": "ONE cinematic English line (30-50 words) for Midjourney/Flux — MUST match visual_description quality; never stock",
      "audio": {{
        "music_energy": "minimal|building|rising|peak|release",
        "sfx": ["specific_sfx_id", "..."],
        "silence": false,
        "silence_duration_ms": 0,
        "impact_beat": false,
        "duck_voice": false
      }},
      "transition_to_next": {{
        "type": "hard_cut|match_cut|whip_pan|blur|speed_ramp|zoom_cut|flash|dissolve",
        "duration_frames": 3-14,
        "sync_audio_impact": true
      }},
      "viewer_state": {{
        "attention": 0-100,
        "curiosity": 0-100,
        "cognitive_load": 0-100
      }},
      "viewer_pacing_hint": "optional: dropoff_risk_reduce_cognitive_load | boredom_risk_boost_pattern_interrupt | ..."
    }}
  ],
  "finance_style_id": "deep_documentary|data_minimalist|financial_noir|intimate_pov",
  "bridge_summary": {{
    "ia_keywords": "comma-separated English keywords for SD/MJ",
    "typography_hint": "string",
    "color_palette": ["#hex or name", "..."]
  }}
}}

CINEMATIC visual_description (CRITICAL):
- Write like a director briefing a DP + stills photographer — NOT like a producer tagging stock footage.
- MUST include at least 4 of: specific subject (age/gender optional), exact location/props, physical action, lighting quality, lens/framing feel, emotional micro-expression or body language.
- FORBIDDEN vague phrases: "B-roll of people", "people celebrating", "financial milestones", "stock footage", "happy family", "success montage", "generic office", "inspiring moment".
- BAD: "B-roll of people celebrating financial milestones"
- GOOD: "young woman alone at kitchen table staring at banking app, soft warm light, subtle smile of relief, shallow focus on screen"
- BAD: "chart going up showing success"
- GOOD: "macro shot tablet with green upward chart, manicured hand placing coin, warm key light, crisp shadow on wood desk"
- Tie each shot to the spoken line of that beat; emotion must be visible in the frame (face, hands, light, space).
- camera.* must be specific enough to recreate the shot; avoid "natural lighting" alone — name the source (window, lamp, screen glow).
- COLOR BLOCK RULES: intimate_close + medium_space + intimate_weight = cool blue / artificial / fluorescent / shadows ONLY. contrast_world = warm amber / natural golden / tungsten ONLY. Chromatic shift carries the argument without narration.
- Every visual_description and image_prompt_seed MUST contain an explicit color-temperature phrase (cool blue light, warm amber interior, harsh fluorescent).

INTENSITY ESCALATION (CRITICAL — hooks must NOT feel flat):
- Root field intensity_curve: array of integers 0-100, one per micro_beat, same length as micro_beats.
- Arc shape: curiosity (low ~40-50) → contradiction (~55-65) → emotional_escalation (ramp ~70-85) → payoff_promise PEAK (~88-95) → optional payoff_release dip on last beat only if 5+ beats (~60-70).
- Example 5 beats: [45, 60, 80, 90, 65]. Example 4 beats: [45, 60, 80, 90].
- Each beat MUST set intensity matching intensity_curve[i]; purpose must follow the arc stage (not all "payoff").
- Higher intensity → faster motion, more overlays, tighter shots, bolder text_overlay; lower → slower, fewer overlays.
- NEVER assign similar intensity to every beat (e.g. all 70s); the curve must climb to a clear peak before any release.

AUDIO PSYCHOLOGY (CRITICAL for modern retention):
- Root audio_design + per-beat audio must reinforce the intensity curve (not flat background music).
- music_energy arc: minimal/building (curiosity) → building (contradiction) → rising (escalation) → peak (payoff) → release (optional last beat).
- sfx: concrete IDs (snake_case), 1-3 per beat — e.g. cash_register, bass_hit, riser_short, heartbeat_tension, notification_ping, record_scratch_light.
- silence_before_payoff: true → insert micro-silence (~150-250ms) on the beat BEFORE the payoff peak (set silence_beat_index); that beat's audio.silence=true.
- impact_beat: true on payoff_promise beat — hit/sting synced to visual cut (bass_hit + duck_voice).
- Match sfx to hook_class (finance: cash_register, data_blip; fear: heartbeat_low, warning_beep).
- Do NOT leave audio empty; hooks without SFX/silence/impact feel amateur on TikTok/Shorts.

NARRATOR / TALKING HEAD (CRITICAL — modern hooks):
- FORBIDDEN: scene_type "talking_head" or narrator_visible true on ANY beat with start_sec < {talking_head_after_sec}.
- Until {talking_head_after_sec}s use ONLY: cinematic broll, motion_graphic, text_card, split_screen, data_ui, stock.
- If entire hook is shorter than {talking_head_after_sec}s, NEVER use talking_head in the hook at all.
- Visible narrator too early kills novelty and visual intrigue; voice can be VO-only over b-roll during the hook.
- Prefer data_ui / motion_graphic for contradiction and data hooks; cinematic broll for story/curiosity.

TRANSITIONS (CRITICAL for rhythm — every beat except the last needs transition_to_next):
- Types: hard_cut | match_cut | whip_pan | blur | speed_ramp | zoom_cut | flash | dissolve
- duration_frames at 30fps: hard_cut 2-4, match_cut 5-7, whip_pan 6-10, blur 8-12, speed_ramp 10-14, flash 3-5, dissolve 12-16
- Arc: curiosity→contradiction often hard_cut or match_cut; escalation→payoff use whip_pan or speed_ramp; peak payoff sync_audio_impact true with flash or speed_ramp
- Last micro_beat: transition_to_next = null (omit or omit field)
- Vary types — never whip_pan on every cut; escalate transition energy with intensity_curve
- sync_audio_impact true when transition pairs with impact_beat or SFX hit

VIEWER STATE TRACKING (advanced pacing — model the imagined viewer each beat):
- Per beat viewer_state: attention, curiosity, cognitive_load (all 0-100 integers).
- attention should generally RISE toward payoff_promise then ease on release; avoid flat lines.
- curiosity peaks around contradiction / curiosity_gap; can dip slightly at payoff (answer arriving).
- cognitive_load rises with text overlays, stats, data_ui — keep mostly 35-70; above 78 = dropoff risk; below 25 with low attention = boredom risk.
- Set viewer_pacing_hint when a beat is dangerous (too much info OR too calm).
- Root viewer_state_tracking: curves arrays + dropoff_risk_beat_indices + boredom_risk_beat_indices + pacing_recommendations.

ESSAY VIDEO — VISUAL COUNTERPOINT (CRITICAL — dual channel):
- Voice carries argument; images carry emotion, subtext, or CONTRAST. Never illustrate the spoken object literally.
- If narration says "calculator / mortgage app / Zillow", the frame must NOT show that UI unless using deliberate counterpoint (e.g. voice: struggle → image: affluent suburb).
- Strategies (rotate across beats): (1) counterpoint — visual opposes or complicates the line; (2) intimate_subtext — solitude, fatigue, quiet stakes; (3) scale_escalation — intimate → systemic (street, blocks, city mood); (4) motif_echo — sparse recurrence of one motif (door, dim screen) with accumulated weight.
- visual_description / image_prompt_seed: 28-48 words, English, one still. WHO + WHERE + light + emotional micro-detail — what the voice does NOT say aloud.
- BAD (literal): "person opening mortgage calculator on phone"
- GOOD (subtext): "person alone at kitchen table late at night, dim light, still hands, quiet exhaustion, no drama, shallow DOF"

IMAGE PROMPTS — NOT STOCK FOOTAGE:
- FORBIDDEN: "two friends discussing finances", "people celebrating", "business meeting", "person using laptop", generic stock.
- REQUIRED: specific PLACE + emotion visible in frame + LIGHT + lens feel; tie to beat purpose/emotion, NOT to spoken nouns.
- image_prompt_seed MUST match visual_description (same scene, cinematic, not illustrative redundancy).

Rules:
- micro_beats: {int(plat["max_beats"])} beats max for this platform; each beat 1-3s for short-form, up to 4s for youtube long-form.
- Every beat needs distinct visual change (no duplicate framing).
- text_overlay_content in {loc} when text_overlay is true.
- finance_style_id must match hook psychology (data/contradiction/shock → data_minimalist; story/invitation → intimate_pov or deep_documentary; fear/systemic → financial_noir).
{doc_seq}
"""


def _normalize_beat(
    raw: dict[str, Any],
    *,
    index: int,
    platform: str,
    energy: str,
    phrase_hint: str = "",
) -> dict[str, Any]:
    start = float(raw.get("start_sec", raw.get("start", 0)) or 0)
    end = float(raw.get("end_sec", raw.get("end", start + 1.5)) or (start + 1.5))
    if end <= start:
        end = start + float(PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["youtube_shorts"])["default_beat_sec"])
    cam = raw.get("camera") if isinstance(raw.get("camera"), dict) else {}
    vd = raw.get("visual_density") if isinstance(raw.get("visual_density"), dict) else {}
    emotion = str(raw.get("emotion") or "curiosity").strip()
    vis = str(raw.get("visual_description") or "").strip()[:500]
    overlay = str(raw.get("text_overlay_content") or phrase_hint or "").strip()
    if _is_generic_visual_description(vis):
        vis = _cinematic_visual_description(emotion, overlay or phrase_hint, index=index, energy=energy)
    seed = str(raw.get("image_prompt_seed") or "").strip()[:800]
    if not seed or _is_stock_footage_prompt(seed):
        seed = vis[:800]
    try:
        intensity_val = int(float(raw.get("intensity", 0) or 0))
    except (TypeError, ValueError):
        intensity_val = 0
    intensity_val = min(100, max(0, intensity_val)) if intensity_val else 0
    st = str(raw.get("scene_type") or "broll").strip().lower()
    return {
        "index": int(raw.get("index", index)),
        "intensity": intensity_val,
        "scene_type": st,
        "narrator_visible": bool(raw.get("narrator_visible", st == "talking_head")),
        "start_sec": round(start, 2),
        "end_sec": round(end, 2),
        "duration_sec": round(end - start, 2),
        "purpose": str(raw.get("purpose") or "payoff").strip(),
        "hook_class": str(raw.get("hook_class") or "mixed").strip(),
        "retention_pattern": str(raw.get("retention_pattern") or "curiosity_gap").strip(),
        "visual_style": str(raw.get("visual_style") or "cinematic").strip(),
        "motion": str(raw.get("motion") or "push_in").strip(),
        "text_overlay": bool(raw.get("text_overlay", True)),
        "text_overlay_content": str(raw.get("text_overlay_content") or "").strip()[:120],
        "emotion": emotion,
        "visual_description": vis,
        "camera": {
            "shot": str(cam.get("shot") or "medium").strip(),
            "lighting": str(cam.get("lighting") or "natural").strip(),
            "composition": str(cam.get("composition") or "center framed").strip(),
            "motion": str(cam.get("motion") or cam.get("movement") or "slow zoom").strip(),
        },
        "visual_density": {
            "text_amount": str(vd.get("text_amount") or "medium").strip(),
            "motion_intensity": str(vd.get("motion_intensity") or energy).strip(),
            "overlay_count": int(vd.get("overlay_count", 1) if str(vd.get("overlay_count", "")).isdigit() else 1),
        },
        "image_prompt_seed": seed,
        "audio": raw.get("audio") if isinstance(raw.get("audio"), dict) else None,
        "transition_to_next": _normalize_transition(raw.get("transition_to_next")),
        "viewer_state": (
            _clamp_viewer_state(raw["viewer_state"])
            if isinstance(raw.get("viewer_state"), dict) and _valid_viewer_state(raw.get("viewer_state"))
            else None
        ),
        "viewer_pacing_hint": str(raw.get("viewer_pacing_hint") or "").strip() or None,
        "sequence_block": str(raw.get("sequence_block") or "").strip() or None,
        "shot_distance": str(raw.get("shot_distance") or "").strip() or None,
        "shot_angle": str(raw.get("shot_angle") or "").strip() or None,
        "new_information_layer": str(raw.get("new_information_layer") or "").strip()[:200] or None,
    }


def run_retention_router_llm(
    *,
    hook_text: str,
    inputs: PipelineInputs,
    platform: str,
    visual_energy: str,
    output_lang: str,
    metadata_context: str,
    audience_context: str,
    system_override: str,
    talking_head_after_sec: int = 25,
    target_beat_count: int | None = None,
    hook_duration_sec: float | None = None,
) -> dict[str, Any]:
    from videomaker.llm.metadata_gen import _parse_json_object, resolve_metadata_llm
    from videomaker.llm.hook_visual_sequence import sequence_arc_summary_en

    eff_lang = normalize_language_code(output_lang or "es")
    sys_prompt = (system_override.strip() or retention_router_system_prompt(
        output_lang=eff_lang,
        platform=platform,
        visual_energy=visual_energy,
        talking_head_after_sec=talking_head_after_sec,
    ))
    user_parts = [
        f"output_language_for_overlays: {eff_lang} ({language_label(eff_lang)})",
        f"platform: {platform}",
        f"visual_energy: {visual_energy}",
        f"talking_head_forbidden_before_sec: {talking_head_after_sec}",
    ]
    if audience_context.strip():
        user_parts.append(f"target_audience: {audience_context.strip()}")
    if metadata_context.strip():
        user_parts.append(f"metadata_context:\n{metadata_context.strip()}")
    tb = int(target_beat_count or 0)
    if tb > 0:
        user_parts.append(
            sequence_arc_summary_en(
                target_beats=tb,
                hook_duration_sec=float(hook_duration_sec or 90),
            )
        )
        user_parts.append(f"target_micro_beats: {tb}")
    user_parts.append(
        "hook_narration (for emotional/argument context ONLY — do NOT illustrate spoken objects literally in visuals):"
    )
    user_parts.append(hook_text.strip())
    user = "\n\n".join(user_parts)

    _, resolved_model = resolve_metadata_llm(inputs.provider, inputs.model)
    try:
        temp = float(os.environ.get("VIDEOMAKER_HOOK_ROUTER_TEMPERATURE", "0.35"))
    except ValueError:
        temp = 0.35
    json_mode = (os.environ.get("VIDEOMAKER_HOOK_ROUTER_JSON_MODE", "1")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

    def call_llm() -> str:
        from videomaker.llm.providers.openai_compat import openai_compat_chat

        return openai_compat_chat(
            system=sys_prompt,
            user=user,
            model=resolved_model,
            response_json=json_mode,
            temperature=temp,
        ).strip()

    raw = call_llm()
    return _parse_json_object(raw)


def build_retention_router_bundle(
    *,
    hook_text: str,
    inputs: PipelineInputs,
    platform: str,
    visual_energy: str,
    mode: str,
    system_override: str,
    metadata_context: str,
    audience_context: str,
    narrative_preset: str | None,
    lang: str,
    talking_head_after_sec: int | None = None,
    max_beats_cap: int | None = None,
    hook_duration_sec: float | None = None,
) -> dict[str, Any]:
    platform = normalize_platform(platform)
    visual_energy = normalize_visual_energy(visual_energy, platform)
    th_after = (
        talking_head_after_sec
        if talking_head_after_sec is not None
        else resolve_talking_head_after_sec(platform)
    )
    preset = PLATFORM_PRESETS[platform]
    hook_class_rules = classify_hook_class(hook_text)
    patterns_rules = detect_retention_patterns(hook_text)

    parsed: dict[str, Any] | None = None
    if mode == "llm":
        try:
            parsed = run_retention_router_llm(
                hook_text=hook_text,
                inputs=inputs,
                platform=platform,
                visual_energy=visual_energy,
                output_lang=lang,
                metadata_context=metadata_context,
                audience_context=audience_context,
                system_override=system_override,
                talking_head_after_sec=th_after,
                target_beat_count=int(max_beats_cap or preset["max_beats"]),
                hook_duration_sec=hook_duration_sec,
            )
        except Exception:
            parsed = None

    if parsed:
        beats_raw = parsed.get("micro_beats")
        beats_list = beats_raw if isinstance(beats_raw, list) else []
        micro_beats = [
            _normalize_beat(
                b,
                index=i,
                platform=platform,
                energy=visual_energy,
                phrase_hint=str(b.get("text_overlay_content") or "").strip(),
            )
            for i, b in enumerate(beats_list)
            if isinstance(b, dict)
        ][: int(max_beats_cap or preset["max_beats"])]
        if not micro_beats:
            micro_beats = build_beats_rule_based(
                hook_text,
                platform=platform,
                visual_energy=visual_energy,
                max_beats=max_beats_cap,
            )
        ret = parsed.get("retention_analysis") if isinstance(parsed.get("retention_analysis"), dict) else {}
        primary_class = str(ret.get("primary_hook_class") or hook_class_rules).strip()
        finance_id = str(parsed.get("finance_style_id") or _finance_style_from_hook_class(primary_class)).strip()
        bridge = parsed.get("bridge_summary") if isinstance(parsed.get("bridge_summary"), dict) else {}
        method = "retention_llm"
    else:
        micro_beats = build_beats_rule_based(
            hook_text,
            platform=platform,
            visual_energy=visual_energy,
            max_beats=max_beats_cap,
        )
        primary_class = hook_class_rules
        finance_id = _finance_style_from_hook_class(primary_class)
        bridge = {}
        ret = {}
        method = "retention_rules"

    parsed_curve = parsed.get("intensity_curve") if parsed else None
    intensity_curve = resolve_intensity_curve(
        micro_beats, parsed_curve, visual_energy=visual_energy, platform=platform
    )
    micro_beats = apply_intensity_escalation(
        micro_beats, intensity_curve, visual_energy=visual_energy, platform=platform
    )
    micro_beats = apply_platform_pacing(micro_beats, intensity_curve, platform=platform)

    parsed_audio = _normalize_audio_design(parsed.get("audio_design") if parsed else None)
    micro_beats, audio_design = apply_audio_design(
        micro_beats,
        intensity_curve,
        primary_hook_class=primary_class,
        parsed_audio=parsed_audio,
        platform=platform,
    )

    micro_beats, narrator_visibility = apply_narrator_visibility_policy(
        micro_beats, talking_head_after_sec=th_after
    )

    micro_beats, transition_rhythm = apply_beat_transitions(
        micro_beats, visual_energy=visual_energy, platform=platform
    )

    parsed_viewer = parsed.get("viewer_state_tracking") if parsed else None
    parsed_viewer_dict = parsed_viewer if isinstance(parsed_viewer, dict) else None
    micro_beats, viewer_state_tracking = apply_viewer_state_tracking(
        micro_beats, parsed_tracking=parsed_viewer_dict, platform=platform
    )

    micro_beats, cinematic_repairs = enrich_beats_cinematic_prompts(micro_beats)

    from videomaker.llm.hook_visual_sequence import finalize_hook_visual_sequence

    parsed_seq = parsed.get("visual_sequence_plan") if parsed and isinstance(parsed.get("visual_sequence_plan"), dict) else None
    micro_beats, visual_sequence_plan = finalize_hook_visual_sequence(
        micro_beats,
        target_beats=int(max_beats_cap or preset["max_beats"]),
        hook_pool_s=float(hook_duration_sec or 0) if hook_duration_sec else 0.0,
        parsed_plan=parsed_seq,
    )

    pool_s = float(hook_duration_sec or 0) if hook_duration_sec else 0.0
    if not pool_s and micro_beats:
        pool_s = float(micro_beats[-1].get("end_sec") or 0)
    from videomaker.llm.narrative_visual_rhythm import apply_hook_narrative_rhythm
    from videomaker.llm.section_anchor_shot import apply_hook_anchor_hierarchy

    micro_beats, anchor_plan = apply_hook_anchor_hierarchy(micro_beats, visual_sequence_plan)
    micro_beats, rhythm_summary = apply_hook_narrative_rhythm(micro_beats, pool_s)
    if isinstance(visual_sequence_plan, dict):
        visual_sequence_plan["narrative_rhythm"] = rhythm_summary
        visual_sequence_plan["anchor_shot"] = anchor_plan

    total_dur = micro_beats[-1]["end_sec"] if micro_beats else 0.0
    opening_arch = {
        "curiosity": "Curiosity_Hook",
        "contradiction": "Contradiction_Hook",
        "shock": "Shock_Hook",
        "fear": "Fear_Hook",
        "fast_payoff": "Fast_Payoff",
        "story": "Story_Hook",
        "data": "Data_Hook",
        "invitation": "POV_Story",
    }.get(primary_class, "Hook_Route")

    return {
        "version": 2,
        "router_kind": "retention_micro_beats",
        "narrative_preset": narrative_preset,
        "hook_character_count": len(hook_text),
        "hook_excerpt": hook_text[:2500],
        "settings_snapshot": {
            "mode": mode,
            "platform": platform,
            "visual_energy": visual_energy,
            "talking_head_after_sec": th_after,
        },
        "narrator_visibility": narrator_visibility,
        "retention_analysis": {
            "primary_hook_class": primary_class,
            "patterns_detected": ret.get("patterns_detected")
            if isinstance(ret.get("patterns_detected"), list)
            else patterns_rules,
            "scroll_stop_rationale": str(ret.get("scroll_stop_rationale") or "").strip()
            or platform_pacing_profile(platform).get("guidance", ""),
            "novelty_score": ret.get("novelty_score"),
            "emotional_intensity_score": ret.get("emotional_intensity_score"),
            "pacing_score": ret.get("pacing_score"),
        },
        "platform_pacing": platform_pacing_profile(platform),
        "platform_plan": parsed.get("platform_plan")
        if parsed and isinstance(parsed.get("platform_plan"), dict)
        else {
            "platform": platform,
            "visual_energy": visual_energy,
            "target_hook_duration_sec": total_dur,
            "beat_duration_target_sec": preset["default_beat_sec"],
            "cut_style": preset["cut_style"],
            "pacing_profile": preset.get("pacing_profile"),
        },
        "density_controls": parsed.get("density_controls")
        if parsed and isinstance(parsed.get("density_controls"), dict)
        else {
            "text_density": "high" if visual_energy == "high" else "medium",
            "cut_frequency": visual_energy,
            "motion_level": visual_energy,
            "max_overlays_per_beat": 2 if visual_energy == "high" else 1,
            "anti_fatigue_note": "Vary shot scale and overlay timing beat-to-beat.",
        },
        "intensity_curve": intensity_curve,
        "intensity_arc": intensity_arc_summary(intensity_curve, platform=platform),
        "audio_design": audio_design,
        "transition_rhythm": transition_rhythm,
        "viewer_state_tracking": viewer_state_tracking,
        "image_prompt_policy": {
            "style": "cinematic_narrative",
            "anti_stock": True,
            "repairs_applied": cinematic_repairs,
            "required_elements": [
                "place",
                "subject_emotion",
                "lighting",
                "color_temperature",
                "lens_framing",
            ],
            "documentary_sequence": True,
            "color_language": True,
        },
        "visual_sequence_plan": visual_sequence_plan,
        "narrative_rhythm": rhythm_summary,
        "anchor_shot": anchor_plan,
        "micro_beats": micro_beats,
        "classification": {
            "method": method,
            "style_resolution": method,
            "opening_architecture": opening_arch,
            "finance_style_id": finance_id,
            "primary_hook_class": primary_class,
            "psychological_impact": str(ret.get("scroll_stop_rationale") or "")[:500],
        },
        "visual_direction": {
            "label": opening_arch,
            "visual_energy": visual_energy,
            "platform": platform,
            "total_hook_duration_sec": total_dur,
            "beat_count": len(micro_beats),
        },
        "bridge_to_images": {
            "ia_keywords": str(bridge.get("ia_keywords") or "").strip()
            or ", ".join(
                dict.fromkeys(
                    b.get("emotion", "") for b in micro_beats if isinstance(b, dict) and b.get("emotion")
                )
            ),
            "prompt_tone": f"{platform} {visual_energy} retention hook",
            "beats_for_image_prompts": True,
        },
        "llm_raw": parsed if parsed else None,
    }
