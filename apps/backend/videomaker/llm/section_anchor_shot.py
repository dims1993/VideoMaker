"""Plano ancla por sección: jerarquía support → anchor → afterglow."""

from __future__ import annotations

import re
from typing import Any

ShotHierarchy = str  # support_build | support | anchor | afterglow

_HOOK_ANCHOR_CLOSE = re.compile(
    r"\b(close|closes|closing|closed|swipe|lock\s*screen|screen\s*off|"
    r"app\s*minimized|minimize|thumb.*home|shut\s*laptop|lid\s*close|"
    r"screen\s*goes\s*dark|turns?\s*off\s*phone)\b",
    re.I,
)

_DEFAULT_HOOK_ANCHOR_VISUAL = (
    "extreme close-up thumb pressing home or power on phone, banking app closing, "
    "cool blue screen flicker then darkness, quiet decisive gesture, shallow DOF"
)

_DEFAULT_HOOK_ANCHOR_LAYER = (
    "decisive closure — app or screen goes dark; the hook's remembered image"
)


def default_hook_anchor_plan() -> dict[str, Any]:
    return {
        "section": "hook",
        "principle": "one anchor shot per section; most beats are support building toward it",
        "default_motif": "person closes banking app / screen goes dark",
        "preferred_block": "intimate_weight",
        "anchor_visual_seed": _DEFAULT_HOOK_ANCHOR_VISUAL,
        "after_anchor": "let following shots breathe (slow, static, emotional release)",
    }


def default_body_anchor_plan() -> dict[str, Any]:
    return {
        "section": "body",
        "principle": "one punch image per body section amid support B-roll",
        "anchor_ratio": "roughly 1 anchor per 12–18 support beats",
    }


def _beat_index(beat: dict[str, Any], fallback: int) -> int:
    try:
        return int(beat.get("index", fallback))
    except (TypeError, ValueError):
        return fallback


def infer_hook_anchor_beat_index(
    beats: list[dict[str, Any]],
    parsed_plan: dict[str, Any] | None = None,
) -> int:
    """Elige el beat ancla del gancho (por defecto cierre de app en intimate_weight)."""
    n = len(beats)
    if n == 0:
        return 0
    if isinstance(parsed_plan, dict):
        raw = parsed_plan.get("anchor_beat_index")
        if raw is None and isinstance(parsed_plan.get("anchor_shot"), dict):
            raw = parsed_plan["anchor_shot"].get("beat_index")
        try:
            idx = int(raw)
            if 0 <= idx < n:
                return idx
        except (TypeError, ValueError):
            pass

    weight_idxs = [
        i for i, b in enumerate(beats) if str(b.get("sequence_block") or "") == "intimate_weight"
    ]
    if not weight_idxs:
        weight_idxs = list(range(max(0, n - max(3, n // 5)), n))

    for i in weight_idxs:
        blob = " ".join(
            str(beats[i].get(k) or "")
            for k in (
                "visual_description",
                "image_prompt_seed",
                "new_information_layer",
                "text_overlay_content",
            )
        )
        if _HOOK_ANCHOR_CLOSE.search(blob):
            return i

    return max(
        weight_idxs,
        key=lambda i: (
            int(beats[i].get("intensity") or 0),
            i,
        ),
    )


def _hierarchy_for_position(i: int, anchor_i: int) -> ShotHierarchy:
    if i == anchor_i:
        return "anchor"
    if i > anchor_i:
        return "afterglow"
    if i >= max(0, anchor_i - 3):
        return "support_build"
    return "support"


def apply_hook_anchor_hierarchy(
    beats: list[dict[str, Any]],
    parsed_plan: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Marca jerarquía visual: soporte → construcción → ancla → respiración.
    Enriquece el beat ancla (cierre de app por defecto).
    """
    n = len(beats)
    if n == 0:
        return beats, {"applied": False}

    anchor_i = infer_hook_anchor_beat_index(beats, parsed_plan)
    plan_anchor = (
        parsed_plan.get("anchor_shot")
        if isinstance(parsed_plan, dict) and isinstance(parsed_plan.get("anchor_shot"), dict)
        else {}
    )
    motif = str(plan_anchor.get("motif") or parsed_plan.get("anchor_motif") or "").strip() if isinstance(
        parsed_plan, dict
    ) else ""
    if not motif:
        motif = default_hook_anchor_plan()["default_motif"]

    out: list[dict[str, Any]] = []
    for i, raw in enumerate(beats):
        if not isinstance(raw, dict):
            continue
        b = dict(raw)
        hier = _hierarchy_for_position(i, anchor_i)
        b["shot_hierarchy"] = hier
        b["builds_to_anchor"] = i < anchor_i
        b["shot_weight"] = {
            "support": "low",
            "support_build": "rising",
            "anchor": "anchor",
            "afterglow": "release",
        }.get(hier, "low")

        if hier == "anchor":
            b["is_anchor_shot"] = True
            b["purpose"] = str(b.get("purpose") or "payoff_promise")
            b["pacing_role"] = str(b.get("pacing_role") or "payoff_release")
            b["sequence_block"] = str(b.get("sequence_block") or "intimate_weight")
            b["new_information_layer"] = (
                str(b.get("new_information_layer") or "").strip() or _DEFAULT_HOOK_ANCHOR_LAYER
            )
            vis = str(b.get("visual_description") or b.get("image_prompt_seed") or "").strip()
            if not vis or not _HOOK_ANCHOR_CLOSE.search(vis):
                b["visual_description"] = _DEFAULT_HOOK_ANCHOR_VISUAL
                b["image_prompt_seed"] = _DEFAULT_HOOK_ANCHOR_VISUAL
            b["camera_motion"] = "static"
            b["camera_motion_direction"] = "none"
            b["camera_motion_note"] = "locked frame on decisive close — the remembered hook image"
            cam = b.get("camera") if isinstance(b.get("camera"), dict) else {}
            cam = dict(cam)
            cam["motion"] = "static"
            b["camera"] = cam
            try:
                b["intensity"] = max(int(b.get("intensity") or 0), 88)
            except (TypeError, ValueError):
                b["intensity"] = 88
        elif hier == "afterglow":
            b["is_anchor_shot"] = False
            b["purpose"] = str(b.get("purpose") or "breathing_room")
            b["pacing_role"] = str(b.get("pacing_role") or "breathing_room")
            if str(b.get("camera_motion") or "") not in ("static", "slow_pull_out"):
                b["camera_motion"] = "slow_pull_out"
                b["camera_motion_direction"] = "out"
        else:
            b["is_anchor_shot"] = False

        out.append(b)

    summary = {
        **default_hook_anchor_plan(),
        "anchor_beat_index": anchor_i,
        "anchor_motif": motif,
        "support_count": sum(1 for x in out if x.get("shot_hierarchy") in ("support", "support_build")),
        "afterglow_count": sum(1 for x in out if x.get("shot_hierarchy") == "afterglow"),
    }
    return out, summary


_BODY_ANCHOR_MARKERS = re.compile(
    r"\b(verdad|truth|finally|ahora entiendes|now you see|el problema es|the problem is|"
    r"nadie te dice|no one tells|por eso|that's why|la clave|the key)\b",
    re.I,
)


def infer_body_anchor_beat_index(beats: list[dict[str, Any]]) -> int:
    n = len(beats)
    if n <= 2:
        return max(0, n - 1)
    lo = int(n * 0.45)
    hi = max(lo + 1, int(n * 0.78))
    window = range(lo, min(hi + 1, n))
    best_i = window.start or 0
    best_score = -1
    for i in window:
        anchor = str(beats[i].get("text_anchor") or "")
        score = len(re.findall(r"\w+", anchor))
        if _BODY_ANCHOR_MARKERS.search(anchor):
            score += 40
        try:
            score += int(beats[i].get("intensity") or 0) // 5
        except (TypeError, ValueError):
            pass
        if score > best_score:
            best_score = score
            best_i = i
    return best_i


def apply_body_anchor_hierarchy(
    beats: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Un plano ancla en el cuerpo (~mitad narrativa); el resto soporte."""
    n = len(beats)
    if n == 0:
        return beats, {"applied": False}
    anchor_i = infer_body_anchor_beat_index(beats)
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(beats):
        if not isinstance(raw, dict):
            continue
        b = dict(raw)
        hier = _hierarchy_for_position(i, anchor_i)
        b["shot_hierarchy"] = hier
        b["is_anchor_shot"] = hier == "anchor"
        b["shot_weight"] = "anchor" if hier == "anchor" else ("release" if hier == "afterglow" else "low")
        if hier == "anchor":
            b["rhythm_tier"] = "slow"
            b["hold_s"] = max(float(b.get("hold_s") or 6), 6.5)
            b["weight"] = b["hold_s"]
        out.append(b)
    return out, {
        **default_body_anchor_plan(),
        "anchor_beat_index": anchor_i,
        "beat_count": n,
    }
