"""Avatar híbrido (A/B tracks): fusiona prompts de avatar con inserts del Hook Scene Router."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from videomaker.llm.hook_scene_router import _beat_image_prompt_text


def _narrator_visible_on_beat(beat: dict[str, Any]) -> bool:
    if "narrator_visible" in beat:
        return bool(beat.get("narrator_visible"))
    scene = str(beat.get("scene_type") or "").strip().lower()
    return scene in ("talking_head", "avatar", "presenter")


def _router_context(router: dict[str, Any]) -> tuple[str, str]:
    bridge = router.get("bridge_to_images") if isinstance(router, dict) else None
    ia_kw = ""
    if isinstance(bridge, dict):
        ia_kw = str(bridge.get("ia_keywords") or "").strip()
    vd = router.get("visual_direction") if isinstance(router, dict) else None
    label = ""
    if isinstance(vd, dict):
        label = str(vd.get("label") or "").strip()
    return ia_kw, label


def _beat_duration_estimated(beat: dict[str, Any]) -> float:
    dur = beat.get("duration_sec")
    if isinstance(dur, (int, float)) and float(dur) > 0:
        return float(dur)
    start = beat.get("start_sec")
    end = beat.get("end_sec")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and float(end) > float(start):
        return float(end) - float(start)
    return 2.0


def _timing_relative_from_beats(
    beat: dict[str, Any],
    *,
    beat_index: int,
    weights: list[float],
) -> dict[str, Any]:
    """Posición en el gancho como fracción 0–1 (no segundos absolutos de TTS)."""
    wsum = sum(weights) or 1.0
    before = sum(weights[:beat_index])
    w = weights[beat_index] if beat_index < len(weights) else 1.0
    rel_start = before / wsum
    rel_end = (before + w) / wsum
    est = _beat_duration_estimated(beat)
    return {
        "mode": "relative_hook",
        "hook_beat_index": int(beat.get("index", beat_index)),
        "relative_start": round(rel_start, 5),
        "relative_end": round(rel_end, 5),
        "weight": round(w / wsum, 5),
        "duration_sec_estimated": round(est, 3),
        "start_sec_estimated": beat.get("start_sec"),
        "end_sec_estimated": beat.get("end_sec"),
        "reconciled": False,
    }


def _insert_prompt_from_beat(
    beat: dict[str, Any],
    *,
    router: dict[str, Any],
    ia_kw: str,
    label: str,
    order: int,
    beat_index: int,
    hook_weights: list[float],
) -> dict[str, Any]:
    idx = int(beat.get("index", beat_index))
    cinematic = _beat_image_prompt_text(beat, global_kw=ia_kw, label=label)
    timing = _timing_relative_from_beats(beat, beat_index=beat_index, weights=hook_weights)
    dur_s = timing.get("duration_sec_estimated") or _beat_duration_estimated(beat)
    duration_ms = int(float(dur_s) * 1000) if isinstance(dur_s, (int, float)) else None
    return {
        "id": f"hook_insert_{idx}",
        "order": order,
        "track": "insert",
        "act": "hook",
        "role": f"hook_beat_{idx}",
        "layer": "hook_micro_beat",
        "timing": timing,
        "duration_hint_s": max(
            1,
            int(round(float(beat.get("hold_s") or beat.get("duration_sec") or dur_s))),
        )
        if isinstance(dur_s, (int, float)) or beat.get("hold_s")
        else 2,
        **({"duration_ms": duration_ms} if duration_ms else {}),
        "purpose": beat.get("purpose"),
        "pacing_role": beat.get("pacing_role"),
        "sequence_block": beat.get("sequence_block"),
        "intensity": beat.get("intensity"),
        "scene_type": beat.get("scene_type"),
        "camera_motion": beat.get("camera_motion"),
        "camera_motion_direction": beat.get("camera_motion_direction"),
        "camera_motion_note": beat.get("camera_motion_note"),
        "rhythm_tier": beat.get("rhythm_tier"),
        "hold_s": beat.get("hold_s"),
        "shot_hierarchy": beat.get("shot_hierarchy"),
        "is_anchor_shot": beat.get("is_anchor_shot"),
        "visual_pillar": beat.get("visual_pillar"),
        "emotional_state": beat.get("emotional_state"),
        "composition_for_animation": beat.get("composition_for_animation"),
        "subject_position": beat.get("subject_position"),
        "narrator_visible": False,
        "ai_prompt": cinematic,
        "text": cinematic,
        "negative_prompt": "person, human face, talking head, presenter, avatar, cartoon character",
        "prompt_style": beat.get("prompt_style") or "cinematic_narrative",
        "text_metadata": {
            "emotion": beat.get("emotion"),
            "scene_type": beat.get("scene_type"),
            "intensity": beat.get("intensity"),
        },
    }


def _avatar_prompt_for_beat(
    avatar: dict[str, Any],
    beat: dict[str, Any],
    *,
    order: int,
    beat_index: int,
    hook_weights: list[float],
) -> dict[str, Any]:
    out = deepcopy(avatar)
    timing = _timing_relative_from_beats(beat, beat_index=beat_index, weights=hook_weights)
    dur_s = timing.get("duration_sec_estimated") or _beat_duration_estimated(beat)
    out.update(
        {
            "order": order,
            "track": "avatar",
            "act": out.get("act") or "hook",
            "layer": "hook_micro_beat",
            "timing": timing,
            "narrator_visible": True,
        }
    )
    if isinstance(dur_s, (int, float)):
        out["duration_hint_s"] = max(1, int(round(float(dur_s))))
        out["duration_ms"] = int(float(dur_s) * 1000)
    return out


def _tag_avatar_only(bundle: dict[str, Any]) -> dict[str, Any]:
    prompts = bundle.get("prompts")
    if not isinstance(prompts, list):
        return bundle
    tagged: list[dict[str, Any]] = []
    for i, p in enumerate(prompts):
        if not isinstance(p, dict):
            continue
        row = deepcopy(p)
        if row.get("id") not in ("intro", "outro"):
            row.setdefault("track", "avatar")
        row.setdefault("order", i + 1)
        tagged.append(row)
    out = deepcopy(bundle)
    out["prompts"] = tagged
    out["hybrid_mode"] = False
    return out


def merge_avatar_hybrid_with_hook(
    work_dir: Path,
    *,
    avatar_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Intercala beats del hook: track avatar (personaje) vs track insert (B-roll sin avatar).

    Requiere `image_prompts.json` del avatar writer (o bundle pasado). Si existe
    `hook_scene_router.json`, el gancho sigue la línea de tiempo de `micro_beats`.
    """
    if avatar_bundle is None:
        ip_path = work_dir / "pipeline" / "image_prompts.json"
        if not ip_path.is_file():
            raise ValueError(
                "Falta pipeline/image_prompts.json. Genera prompts de avatar antes de fusionar el hook."
            )
        try:
            avatar_bundle = json.loads(ip_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"No se pudo leer image_prompts.json: {e}") from e

    if not isinstance(avatar_bundle, dict):
        raise ValueError("image_prompts.json inválido.")

    hr_path = work_dir / "pipeline" / "hook_scene_router.json"
    if not hr_path.is_file():
        bundle = _tag_avatar_only(avatar_bundle)
        _write_bundle(work_dir, bundle)
        n = len(bundle.get("prompts") or [])
        return {
            "path": "pipeline/image_prompts.json",
            "prompt_count": n,
            "hybrid": False,
            "avatar_count": n,
            "insert_count": 0,
        }

    try:
        router = json.loads(hr_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"No se pudo leer hook_scene_router.json: {e}") from e

    beats_raw = router.get("micro_beats") if isinstance(router, dict) else None
    beats: list[dict[str, Any]] = [
        b for b in (beats_raw or []) if isinstance(b, dict)
    ]
    if not beats:
        bundle = _tag_avatar_only(avatar_bundle)
        _write_bundle(work_dir, bundle)
        n = len(bundle.get("prompts") or [])
        return {
            "path": "pipeline/image_prompts.json",
            "prompt_count": n,
            "hybrid": False,
            "avatar_count": n,
            "insert_count": 0,
        }

    beats = sorted(
        beats,
        key=lambda b: (
            float(b["start_sec"])
            if isinstance(b.get("start_sec"), (int, float))
            else float(b.get("index") or 0),
        ),
    )
    hook_weights = [_beat_duration_estimated(b) for b in beats]
    for b in beats:
        b["_hook_weights"] = hook_weights

    prompts_raw = avatar_bundle.get("prompts")
    if not isinstance(prompts_raw, list):
        raise ValueError("El bundle de avatar no contiene prompts[].")

    intro_items: list[dict[str, Any]] = []
    outro_items: list[dict[str, Any]] = []
    hook_avatars: list[dict[str, Any]] = []
    body_avatars: list[dict[str, Any]] = []

    for p in prompts_raw:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "")
        if pid == "intro":
            intro_items.append(deepcopy(p))
        elif pid == "outro":
            outro_items.append(deepcopy(p))
        elif str(p.get("act") or "").strip().lower() == "hook":
            hook_avatars.append(deepcopy(p))
        else:
            body_avatars.append(deepcopy(p))

    ia_kw, label = _router_context(router)
    merged: list[dict[str, Any]] = []
    order = 1
    h_idx = 0
    insert_count = 0

    for beat_index, beat in enumerate(beats):
        if _narrator_visible_on_beat(beat) and h_idx < len(hook_avatars):
            merged.append(
                _avatar_prompt_for_beat(
                    hook_avatars[h_idx],
                    beat,
                    order=order,
                    beat_index=beat_index,
                    hook_weights=hook_weights,
                )
            )
            h_idx += 1
        else:
            merged.append(
                _insert_prompt_from_beat(
                    beat,
                    router=router,
                    ia_kw=ia_kw,
                    label=label,
                    order=order,
                    beat_index=beat_index,
                    hook_weights=hook_weights,
                )
            )
            insert_count += 1
        order += 1

    for item in intro_items:
        row = deepcopy(item)
        row["track"] = "avatar"
        row["order"] = order
        merged.append(row)
        order += 1

    for item in body_avatars:
        row = deepcopy(item)
        row.setdefault("track", "avatar")
        row["order"] = order
        merged.append(row)
        order += 1

    for item in outro_items:
        row = deepcopy(item)
        row["track"] = "avatar"
        row["order"] = order
        merged.append(row)
        order += 1

    # Re-numerar ids numéricos en orden final (preservar intro/outro/hook_insert_*)
    num = 1
    for row in merged:
        rid = str(row.get("id") or "")
        if rid in ("intro", "outro") or rid.startswith("hook_insert_"):
            continue
        row["id"] = str(num)
        num += 1

    avatar_count = sum(1 for r in merged if r.get("track") == "avatar")
    bundle: dict[str, Any] = {
        "version": 3,
        "source": "avatar_hybrid",
        "hybrid_mode": True,
        "hybrid_tracks": {"avatar": avatar_count, "insert": insert_count},
        "router_ref": "pipeline/hook_scene_router.json",
        "avatar_source": str(avatar_bundle.get("source") or "avatar_prompt_writer"),
        "avatar_description": avatar_bundle.get("avatar_description"),
        "intro_enabled": avatar_bundle.get("intro_enabled"),
        "intro_character_name": avatar_bundle.get("intro_character_name"),
        "outro_enabled": avatar_bundle.get("outro_enabled"),
        "outro_character_name": avatar_bundle.get("outro_character_name"),
        "target_generator": avatar_bundle.get("target_generator"),
        "secs_per_image": avatar_bundle.get("secs_per_image"),
        "total_prompts": len(merged),
        "global_style": avatar_bundle.get("global_style")
        if isinstance(avatar_bundle.get("global_style"), dict)
        else {},
        "prompts": merged,
        "classification": router.get("classification") if isinstance(router, dict) else {},
        "retention_analysis": router.get("retention_analysis")
        if isinstance(router, dict)
        else None,
        "micro_beat_count": len(beats),
        "timing_semantics": "relative_hook",
    }

    for b in beats:
        b.pop("_hook_weights", None)

    _write_bundle(work_dir, bundle)
    return {
        "path": "pipeline/image_prompts.json",
        "prompt_count": len(merged),
        "hybrid": True,
        "avatar_count": avatar_count,
        "insert_count": insert_count,
    }


def _write_bundle(work_dir: Path, bundle: dict[str, Any]) -> None:
    out = work_dir / "pipeline" / "image_prompts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
