"""Ritmo visual alineado al ritmo narrativo (duración variable por plano)."""

from __future__ import annotations

import re
from typing import Any

RhythmTier = str  # fast | medium | slow

_HOOK_TENSION_PURPOSES = frozenset(
    {
        "curiosity",
        "contradiction",
        "emotional_escalation",
        "pattern_interrupt",
        "tension_rise",
    }
)
_HOOK_SLOW_PURPOSES = frozenset({"payoff_release", "breathing_room", "payoff_promise"})
_HOOK_FAST_PACING = frozenset(
    {"tension_rise", "stimulus_beat", "hook_open", "pattern_interrupt", "tension_peak"}
)
_HOOK_SLOW_PACING = frozenset({"payoff_release", "breathing_room", "narrative_hold"})
_HOOK_FAST_EMOTIONS = frozenset(
    {"fear", "tension", "confusion", "urgency", "shock", "anxiety", "panic"}
)

_BODY_FAST_MARKERS = re.compile(
    r"\b(suddenly|pero entonces|however|wait|shock|panic|crisis|deuda|debt|"
    r"no puedes|can't|urgent|ahora mismo|right now|¿sabías|did you know)\b",
    re.I,
)
_BODY_SLOW_MARKERS = re.compile(
    r"\b(finalmente|finally|en conclusión|in conclusion|la verdad es|the truth is|"
    r"recuerda|remember|imagina|imagine|years later|años después|silence|silencio|"
    r"respira|breathe|weight|peso|soledad|alone)\b",
    re.I,
)


def default_rhythm_plan() -> dict[str, Any]:
    return {
        "principle": "visual cut length follows narration tension, not fixed 3s/7s grids",
        "hook_seconds": {"fast": "1–2", "medium": "2–3.5", "slow": "4–5"},
        "body_seconds": {"fast": "2–3.5", "medium": "4–6", "slow": "5–8"},
        "fast_when": "tension, confusion, pattern_interrupt, high intensity",
        "slow_when": "revelation, contrast_world, emotional weight, breathing_room",
    }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def hook_rhythm_tier(beat: dict[str, Any]) -> RhythmTier:
    hier = str(beat.get("shot_hierarchy") or "").strip().lower()
    if hier == "anchor":
        return "slow"
    if hier == "afterglow":
        return "slow"
    if hier == "support_build":
        return "fast"
    block = str(beat.get("sequence_block") or "").strip().lower()
    purpose = str(beat.get("purpose") or "").strip().lower()
    pacing = str(beat.get("pacing_role") or "").strip().lower()
    emotion = str(beat.get("emotion") or "").strip().lower()
    try:
        intensity = int(beat.get("intensity") or 50)
    except (TypeError, ValueError):
        intensity = 50

    if block == "contrast_world":
        return "slow"
    if block == "intimate_weight" and intensity < 72:
        return "slow"
    if purpose in _HOOK_SLOW_PURPOSES or pacing in _HOOK_SLOW_PACING:
        return "slow"
    if (
        purpose in _HOOK_TENSION_PURPOSES
        or pacing in _HOOK_FAST_PACING
        or emotion in _HOOK_FAST_EMOTIONS
        or intensity >= 78
    ):
        return "fast"
    if block == "intimate_close" and intensity >= 70:
        return "fast"
    if block == "medium_space" and purpose in ("curiosity", "contradiction"):
        return "medium"
    return "medium"


def body_rhythm_tier(beat: dict[str, Any]) -> RhythmTier:
    if beat.get("is_anchor_shot") or str(beat.get("shot_hierarchy") or "") == "anchor":
        return "slow"
    if str(beat.get("shot_hierarchy") or "") == "afterglow":
        return "slow"
    anchor = str(beat.get("text_anchor") or "")
    purpose = str(beat.get("purpose") or "").strip().lower()
    pacing = str(beat.get("pacing_role") or "").strip().lower()
    try:
        intensity = int(beat.get("intensity") or 0)
    except (TypeError, ValueError):
        intensity = 0

    if purpose in _HOOK_SLOW_PURPOSES or pacing in _HOOK_SLOW_PACING:
        return "slow"
    if purpose in _HOOK_TENSION_PURPOSES or pacing in _HOOK_FAST_PACING or intensity >= 80:
        return "fast"
    if _BODY_SLOW_MARKERS.search(anchor):
        return "slow"
    if _BODY_FAST_MARKERS.search(anchor) and not _BODY_SLOW_MARKERS.search(anchor):
        return "fast"
    wc = len(re.findall(r"\w+", anchor))
    if wc <= 8:
        return "fast"
    if wc >= 28:
        return "slow"
    return "medium"


def duration_s_for_tier(
    tier: RhythmTier,
    *,
    section: str,
    beat: dict[str, Any] | None = None,
) -> float:
    """Duración objetivo en segundos antes de normalizar al pool de audio."""
    try:
        intensity = int((beat or {}).get("intensity") or 50)
    except (TypeError, ValueError):
        intensity = 50
    t = (tier or "medium").strip().lower()
    if section == "hook":
        hier = str((beat or {}).get("shot_hierarchy") or "").strip().lower()
        if hier == "anchor":
            return 5.25
        if hier == "afterglow":
            return _clamp(4.25 + (60 - min(intensity, 60)) / 40.0, 4.0, 5.0)
        if t == "fast":
            return _clamp(2.0 - (intensity - 50) / 80.0, 1.0, 2.0)
        if t == "slow":
            return _clamp(4.0 + (70 - min(intensity, 70)) / 35.0, 4.0, 5.0)
        return _clamp(2.75 + (intensity % 20) / 40.0, 2.0, 3.5)
    # body — estabilidad visual para argumento denso (4–6s soporte, 5–8s ancla)
    hier = str((beat or {}).get("shot_hierarchy") or "").strip().lower()
    if (beat or {}).get("is_anchor_shot") or hier == "anchor":
        return _clamp(6.5 + (55 - min(intensity, 55)) / 40.0, 5.5, 8.0)
    if hier == "afterglow":
        return _clamp(5.0 + (50 - min(intensity, 50)) / 35.0, 4.5, 6.5)
    if t == "fast":
        return _clamp(4.0 - (intensity - 50) / 120.0, 3.5, 4.5)
    if t == "slow":
        return _clamp(5.5 + (60 - min(intensity, 60)) / 30.0, 5.0, 7.5)
    return _clamp(5.0 + (intensity % 12) / 25.0, 4.0, 6.0)


def rhythm_max_hold_s(
    tier: RhythmTier,
    plan_max_hold: float,
    *,
    section: str = "body",
) -> float:
    """Umbral de split: tensión → cortes más cortos; peso emocional → aguanta planos largos."""
    base = float(plan_max_hold or 8.0)
    t = (tier or "medium").strip().lower()
    if section == "hook":
        if t == "fast":
            return max(1.8, base * 0.55)
        if t == "slow":
            return min(5.5, base * 1.15)
        return base * 0.85
    if t == "fast":
        return max(2.5, base * 0.55)
    if t == "slow":
        return min(11.0, base * 1.4)
    return base


def _normalize_timeline(
    beats: list[dict[str, Any]],
    pool_s: float,
    *,
    section: str,
    min_s: float,
    max_s: float,
) -> list[dict[str, Any]]:
    if not beats or pool_s <= 0:
        return beats
    raw: list[float] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        tier = str(b.get("rhythm_tier") or "").strip().lower()
        if tier not in ("fast", "medium", "slow"):
            tier = hook_rhythm_tier(b) if section == "hook" else body_rhythm_tier(b)
        raw.append(
            _clamp(duration_s_for_tier(tier, section=section, beat=b), min_s, max_s)
        )
    if not raw:
        return beats
    total_raw = sum(raw)
    scale = pool_s / total_raw if total_raw > 0 else 1.0
    t = 0.0
    out: list[dict[str, Any]] = []
    for b, d in zip(beats, raw):
        if not isinstance(b, dict):
            continue
        row = dict(b)
        dur = _clamp(d * scale, min_s, max_s)
        row["start_sec"] = round(t, 3)
        row["end_sec"] = round(t + dur, 3)
        row["duration_sec"] = round(dur, 3)
        row["hold_s"] = round(dur, 3)
        row["weight"] = dur
        row["rhythm_normalized"] = True
        t += dur
        out.append(row)
    if out and abs(t - pool_s) > 0.05:
        drift = pool_s - t
        last = out[-1]
        nd = max(min_s, float(last["duration_sec"]) + drift)
        last["duration_sec"] = round(nd, 3)
        last["hold_s"] = round(nd, 3)
        last["weight"] = nd
        last["end_sec"] = round(float(last["start_sec"]) + nd, 3)
    return out


def apply_hook_narrative_rhythm(
    beats: list[dict[str, Any]],
    hook_pool_s: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Timeline del gancho: cortes 1–2s en tensión, 4–5s en revelación/peso."""
    tiered: list[dict[str, Any]] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        row = dict(b)
        tier = hook_rhythm_tier(row)
        row["rhythm_tier"] = tier
        row["rhythm_note"] = {
            "fast": "narrative tension — quick cut",
            "medium": "narrative hold",
            "slow": "revelation or emotional weight — let shot breathe",
        }.get(tier, tier)
        tiered.append(row)
    out = _normalize_timeline(tiered, float(hook_pool_s or 0), section="hook", min_s=0.9, max_s=5.5)
    summary = {
        "hook_pool_s": round(float(hook_pool_s or 0), 2),
        "beat_count": len(out),
        "tier_counts": {
            t: sum(1 for x in out if x.get("rhythm_tier") == t) for t in ("fast", "medium", "slow")
        },
        "duration_range_s": [
            round(min((x.get("duration_sec") or 0) for x in out), 2) if out else 0,
            round(max((x.get("duration_sec") or 0) for x in out), 2) if out else 0,
        ],
    }
    return out, summary


def apply_body_narrative_rhythm(
    beats: list[dict[str, Any]],
    body_pool_s: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pesos/duración del cuerpo: el reparto de audio sigue tensión vs respiración."""
    tiered: list[dict[str, Any]] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        row = dict(b)
        tier = body_rhythm_tier(row)
        row["rhythm_tier"] = tier
        d = duration_s_for_tier(tier, section="body", beat=row)
        row["hold_s"] = round(d, 3)
        row["weight"] = d
        tiered.append(row)
    if body_pool_s > 0 and tiered:
        total_w = sum(float(x.get("weight") or 1) for x in tiered)
        scale = body_pool_s / total_w if total_w > 0 else 1.0
        for row in tiered:
            w = _clamp(float(row.get("weight") or 1) * scale, 1.5, 9.0)
            row["weight"] = round(w, 3)
            row["hold_s"] = round(w, 3)
            row["duration_sec"] = round(w, 3)
            row["rhythm_normalized"] = True
    summary = {
        "body_pool_s": round(float(body_pool_s or 0), 2),
        "beat_count": len(tiered),
        "tier_counts": {
            t: sum(1 for x in tiered if x.get("rhythm_tier") == t)
            for t in ("fast", "medium", "slow")
        },
    }
    return tiered, summary
