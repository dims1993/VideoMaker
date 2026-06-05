"""Image Prompt Writer basado en Hook + Body routers (sin rejilla secs_per_image)."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from videomaker.llm.body_scene_router import read_body_macro_beats
from videomaker.llm.image_prompt_hybrid import (
    _beat_duration_estimated,
    _insert_prompt_from_beat,
    _narrator_visible_on_beat,
    _router_context,
    _timing_relative_from_beats,
)


def router_driven_ipw_enabled(work_dir: Path) -> bool:
    raw = (os.environ.get("VIDEOMAKER_IPW_ROUTER_DRIVEN") or "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    hr = work_dir / "pipeline" / "hook_scene_router.json"
    br = work_dir / "pipeline" / "body_scene_router.json"
    return hr.is_file() and br.is_file()


def _beat_weight(beat: dict[str, Any]) -> float:
    """Peso uniforme por beat → reparto equitativo del audio del cuerpo al reconciliar."""
    raw = (os.environ.get("VIDEOMAKER_BODY_EQUAL_BEAT_WEIGHTS") or "1").strip().lower()
    if raw not in ("0", "false", "no", "off"):
        return 1.0
    w = beat.get("weight")
    if isinstance(w, (int, float)) and float(w) > 0:
        return float(w)
    from videomaker.llm.body_macro_beats import _estimated_duration_s

    return _estimated_duration_s(str(beat.get("text_anchor") or ""))


def _timing_relative_body(
    beat_index: int,
    weights: list[float],
) -> dict[str, Any]:
    wsum = sum(weights) or 1.0
    before = sum(weights[:beat_index])
    w = weights[beat_index] if beat_index < len(weights) else 1.0
    rel_start = before / wsum
    rel_end = (before + w) / wsum
    est = w
    return {
        "mode": "relative_body",
        "body_beat_index": beat_index,
        "relative_start": round(rel_start, 5),
        "relative_end": round(rel_end, 5),
        "weight": round(w / wsum, 5),
        "duration_sec_estimated": round(est, 3),
        "reconciled": False,
    }


def _macro_beat_to_prompt_row(
    beat: dict[str, Any],
    *,
    beat_index: int,
    weights: list[float],
    order: int,
    ia_kw: str,
    label: str,
) -> dict[str, Any]:
    idx = int(beat.get("index", beat_index))
    track = str(beat.get("track") or "avatar").strip().lower()
    act = str(beat.get("act") or "body").strip() or "body"
    anchor = str(beat.get("text_anchor") or "").strip()
    timing = _timing_relative_body(beat_index, weights)
    dur_s = timing.get("duration_sec_estimated") or 2.0
    duration_ms = int(float(dur_s) * 1000)

    if track == "insert":
        from videomaker.llm.body_macro_beats import _insert_prompt_from_anchor

        sc = beat.get("style_consistency") if isinstance(beat.get("style_consistency"), dict) else {}
        lighting = str(sc.get("lighting") or "cinematic").strip()
        cinematic = str(beat.get("ai_prompt") or "").strip() or _insert_prompt_from_anchor(
            anchor, ia_kw=ia_kw, lighting=lighting or label
        )
        comp = str(beat.get("composition_hint") or "").strip()
        if comp and comp not in cinematic:
            cinematic = f"{cinematic} Composition: {comp}"
        hold = beat.get("hold_s") or beat.get("weight") or dur_s
        return {
            "id": f"body_insert_{idx}",
            "order": order,
            "track": "insert",
            "act": act,
            "role": f"body_beat_{idx}",
            "layer": "body_macro_beat",
            "timing": timing,
            "duration_hint_s": max(1, int(round(float(hold)))),
            "duration_ms": duration_ms,
            "text_anchor": anchor[:500],
            "narrator_visible": False,
            "ai_prompt": cinematic,
            "text": cinematic,
            "negative_prompt": "person, human face, talking head, presenter, avatar",
            "segment_text": anchor[:200],
            "composition_hint": comp or None,
            "visual_pillar": beat.get("visual_pillar"),
            "shot_hierarchy": beat.get("shot_hierarchy"),
            "is_anchor_shot": beat.get("is_anchor_shot"),
            "color_temperature": beat.get("color_temperature"),
            "light_quality": beat.get("light_quality"),
            "camera_motion": beat.get("camera_motion"),
            "composition_for_animation": beat.get("composition_for_animation"),
            "subject_position": beat.get("subject_position"),
            "emotional_state": beat.get("emotional_state"),
            "rhythm_tier": beat.get("rhythm_tier"),
            "hold_s": beat.get("hold_s"),
        }

    comp = str(beat.get("composition_hint") or "").strip()
    situation = anchor[:300]
    if comp:
        situation = f"{situation} Encuadre: {comp}"[:500]
    return {
        "id": f"body_avatar_{idx}",
        "order": order,
        "track": "avatar",
        "act": act,
        "role": f"body_beat_{idx}",
        "layer": "body_macro_beat",
        "timing": timing,
        "duration_hint_s": max(1, int(round(float(dur_s)))),
        "duration_ms": duration_ms,
        "text_anchor": anchor[:500],
        "narrator_visible": True,
        "segment_text": anchor[:500],
        "situation": situation,
        "expression": "explaining",
        "composition_hint": comp or None,
        "_needs_avatar_llm": True,
    }


def build_hook_prompt_rows(work_dir: Path, *, use_avatar: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filas del gancho desde micro_beats (avatar + insert, sin secs_per_image)."""
    hr = work_dir / "pipeline" / "hook_scene_router.json"
    if not hr.is_file():
        raise ValueError("Falta pipeline/hook_scene_router.json.")
    router = json.loads(hr.read_text(encoding="utf-8"))
    if not isinstance(router, dict):
        raise ValueError("hook_scene_router.json inválido.")

    ia_kw, label = _router_context(router)
    beats_raw = router.get("micro_beats")
    beat_dicts = [b for b in (beats_raw or []) if isinstance(b, dict)]
    if not beat_dicts:
        raise ValueError("hook_scene_router.json sin micro_beats.")

    hook_weights = [_beat_duration_estimated(b) for b in beat_dicts]
    rows: list[dict[str, Any]] = []
    for beat_index, beat in enumerate(beat_dicts):
        idx = int(beat.get("index", beat_index))
        timing = _timing_relative_from_beats(beat, beat_index=beat_index, weights=hook_weights)
        dur_s = timing.get("duration_sec_estimated") or 2.0
        duration_ms = int(float(dur_s) * 1000)
        anchor = str(beat.get("visual_description") or beat.get("purpose") or "")[:300]

        if use_avatar and _narrator_visible_on_beat(beat):
            rows.append(
                {
                    "id": f"hook_avatar_{idx}",
                    "order": beat_index + 1,
                    "track": "avatar",
                    "act": "hook",
                    "role": f"hook_beat_{idx}",
                    "layer": "hook_micro_beat",
                    "timing": timing,
                    "duration_hint_s": max(1, int(round(float(dur_s)))),
                    "duration_ms": duration_ms,
                    "narrator_visible": True,
                    "text_anchor": anchor,
                    "segment_text": anchor,
                    "expression": "explaining",
                    "_needs_avatar_llm": True,
                }
            )
        else:
            ins = _insert_prompt_from_beat(
                beat,
                router=router,
                ia_kw=ia_kw,
                label=label,
                order=beat_index + 1,
                beat_index=beat_index,
                hook_weights=hook_weights,
            )
            rows.append(ins)
    return rows, router


def append_body_prompts_to_bundle(
    work_dir: Path,
    *,
    existing: dict[str, Any] | None = None,
    hook_prompts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    beats = read_body_macro_beats(work_dir)
    if not beats:
        raise ValueError(
            "body_scene_router.json sin macro_beats. Ejecuta Body Scene Router (Start step)."
        )

    br_path = work_dir / "pipeline" / "body_scene_router.json"
    router: dict[str, Any] = {}
    if br_path.is_file():
        try:
            router = json.loads(br_path.read_text(encoding="utf-8"))
        except Exception:
            router = {}

    ia_kw = ""
    raw_kw = router.get("ia_keywords_body")
    if isinstance(raw_kw, list):
        ia_kw = ", ".join(str(x).strip() for x in raw_kw[:6] if str(x).strip())
    elif isinstance(raw_kw, str):
        ia_kw = raw_kw.strip()
    label = str(router.get("visual_style_inherited") or "").strip()

    weights = [_beat_weight(b) for b in beats]
    body_rows: list[dict[str, Any]] = []
    for i, beat in enumerate(beats):
        body_rows.append(
            _macro_beat_to_prompt_row(
                beat,
                beat_index=i,
                weights=weights,
                order=i + 1,
                ia_kw=ia_kw,
                label=label,
            )
        )

    bundle = deepcopy(existing) if isinstance(existing, dict) else {"prompts": []}
    if hook_prompts is not None:
        hook_rows = hook_prompts
        other: list[dict[str, Any]] = []
    else:
        prompts = bundle.get("prompts") if isinstance(bundle.get("prompts"), list) else []
        hook_rows = [p for p in prompts if isinstance(p, dict) and str(p.get("act") or "") == "hook"]
        other = [
            p
            for p in prompts
            if isinstance(p, dict)
            and str(p.get("act") or "") != "hook"
            and str(p.get("layer") or "") != "body_macro_beat"
        ]
    merged = hook_rows + body_rows + other
    for oi, row in enumerate(merged, start=1):
        if isinstance(row, dict):
            row["order"] = oi
    bundle["prompts"] = merged
    bundle["body_macro_beat_count"] = len(body_rows)
    bundle["source"] = bundle.get("source") or "router_driven"
    out = work_dir / "pipeline" / "image_prompts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": "pipeline/image_prompts.json",
        "prompt_count": len(merged),
        "body_beat_count": len(body_rows),
    }


def _enrich_avatar_prompt_rows(
    work_dir: Path,
    prompts: list[dict[str, Any]],
    *,
    avatar_description: str,
    scene_visual_settings: dict[str, Any] | None,
    target_generator: str,
    provider: str | None,
    model: str | None,
) -> None:
    from videomaker.llm.avatar_prompt_writer import (
        _build_system_prompt,
        _call_llm,
        _parse_llm_array,
    )

    indices = [
        i
        for i, p in enumerate(prompts)
        if isinstance(p, dict)
        and p.get("track") == "avatar"
        and p.get("_needs_avatar_llm")
    ]
    if not indices:
        return

    try:
        temp = float(os.environ.get("VIDEOMAKER_AVATAR_PROMPT_TEMPERATURE", "0.6"))
    except ValueError:
        temp = 0.6

    resolved_provider = (provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER", "openai")).lower()
    resolved_model = model or (
        os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
        if resolved_provider == "ollama"
        else os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    )
    system_prompt = _build_system_prompt(
        avatar_description,
        target_generator,
        scene_visual_settings=scene_visual_settings,
    )

    BATCH = 12
    for batch_start in range(0, len(indices), BATCH):
        batch_idx = indices[batch_start : batch_start + BATCH]
        segments = [
            str(prompts[i].get("text_anchor") or prompts[i].get("segment_text") or "")[:500]
            for i in batch_idx
        ]
        numbered = "\n\n".join(f"[{j + 1}] {seg}" for j, seg in enumerate(segments))
        user_msg = (
            f"Genera prompts de imagen del AVATAR para estos {len(segments)} fragmentos narrados:\n\n"
            f"{numbered}"
        )
        try:
            raw = _call_llm(
                system=system_prompt,
                user=user_msg,
                provider=resolved_provider,
                model=resolved_model,
                temperature=temp,
            )
            items = _parse_llm_array(raw)
        except Exception:
            items = []

        for j, i in enumerate(batch_idx):
            row = prompts[i]
            row.pop("_needs_avatar_llm", None)
            item = items[j] if j < len(items) and isinstance(items[j], dict) else {}
            row["ai_prompt"] = str(item.get("ai_prompt") or row.get("ai_prompt") or "").strip()
            row["expression"] = item.get("expression") or row.get("expression") or "explaining"
            row["situation"] = item.get("situation") or row.get("situation") or ""
            row["negative_prompt"] = item.get(
                "negative_prompt",
                "realistic, photorealistic, 3D render, photo, blurry",
            )
            if not row.get("ai_prompt"):
                row["ai_prompt"] = (
                    f"{avatar_description}, explaining, educational flat 2D cartoon, "
                    f"context: {(row.get('text_anchor') or '')[:120]} --ar 16:9"
                )


def build_image_prompts_from_routers(
    work_dir: Path,
    *,
    use_avatar: bool = True,
    avatar_description: str = "",
    scene_visual_settings: dict[str, Any] | None = None,
    intro_enabled: bool = False,
    intro_character_name: str = "",
    outro_enabled: bool = False,
    outro_character_name: str = "",
    target_generator: str = "midjourney",
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Rejilla definitiva: Hook micro_beats + Body macro_beats.
    Avatar LLM solo en filas ``track: avatar``; inserts usan ai_prompt del router.
    """
    from videomaker.llm.avatar_prompt_writer import (
        AVATAR_DEFAULT_DESCRIPTION,
        _generate_intro_segment,
        _generate_outro_segment,
    )

    hook_rows, hook_router = build_hook_prompt_rows(work_dir, use_avatar=use_avatar)

    from videomaker.core.image_prompt_writer_settings_store import read_image_prompt_writer_settings
    from videomaker.llm.hook_visual_counterpoint import enrich_hook_image_prompt_rows

    ipw_st = read_image_prompt_writer_settings(work_dir)
    counterpoint_meta: dict[str, Any] = {}
    if ipw_st.get("hook_essay_counterpoint", True):
        hook_rows, counterpoint_meta = enrich_hook_image_prompt_rows(
            hook_rows,
            hook_router,
            provider=provider,
            model=model,
        )

    body_info = append_body_prompts_to_bundle(
        work_dir, hook_prompts=hook_rows, existing={"prompts": hook_rows}
    )
    ip_path = work_dir / "pipeline" / "image_prompts.json"
    bundle = json.loads(ip_path.read_text(encoding="utf-8"))
    bundle["router_ref"] = "pipeline/hook_scene_router.json"
    bundle["classification"] = hook_router.get("classification") if isinstance(hook_router, dict) else {}
    bundle["retention_analysis"] = hook_router.get("retention_analysis")
    bundle["micro_beat_count"] = len(hook_rows)
    if counterpoint_meta:
        bundle["hook_counterpoint"] = counterpoint_meta

    desc = (avatar_description or AVATAR_DEFAULT_DESCRIPTION).strip()
    if use_avatar:
        _enrich_avatar_prompt_rows(
            work_dir,
            bundle.get("prompts") or [],
            avatar_description=desc,
            scene_visual_settings=scene_visual_settings,
            target_generator=target_generator,
            provider=provider,
            model=model,
        )

    prompts = bundle.get("prompts") if isinstance(bundle.get("prompts"), list) else []
    intro_outro: list[dict[str, Any]] = []
    if use_avatar and intro_enabled and intro_character_name:
        try:
            intro_outro.append(
                _generate_intro_segment(
                    script_text="",
                    character_name=intro_character_name,
                    avatar_description=desc,
                    target_generator=target_generator,
                    provider=provider or "openai",
                    model=model or "",
                    temperature=0.6,
                )
            )
        except Exception:
            pass
    if use_avatar and outro_enabled and outro_character_name:
        try:
            intro_outro.append(
                _generate_outro_segment(
                    script_text="",
                    character_name=outro_character_name,
                    avatar_description=desc,
                    target_generator=target_generator,
                    provider=provider or "openai",
                    model=model or "",
                    temperature=0.6,
                )
            )
        except Exception:
            pass
    if intro_outro:
        hook_part = [p for p in prompts if isinstance(p, dict) and str(p.get("act")) == "hook"]
        rest = [p for p in prompts if isinstance(p, dict) and str(p.get("act")) != "hook"]
        prompts = intro_outro[:1] + hook_part + rest + intro_outro[1:]
        bundle["prompts"] = prompts

    bundle["version"] = 4
    bundle["source"] = "router_driven"
    bundle["hybrid_mode"] = True
    bundle["routing"] = {
        "hook": "hook_scene_router.json",
        "body": "body_scene_router.json",
        "avatar_secs_per_image": False,
    }
    bundle["total_prompts"] = len(prompts)
    ip_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "path": "pipeline/image_prompts.json",
        "prompt_count": len(prompts),
        "hook_prompt_count": len(hook_rows),
        "body_beat_count": body_info.get("body_beat_count"),
    }
