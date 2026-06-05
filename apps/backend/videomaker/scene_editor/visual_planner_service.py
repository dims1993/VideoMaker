"""Visual Planner: estilo base + escena narrativa por bloque → prompt Nano Banana 2."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from videomaker.llm.llm_routing import call_production_llm
from videomaker.scene_editor.protagonist_expressions import (
    apply_protagonist_expression,
    expressions_catalog_from_settings,
    resolve_protagonist_expression,
)
from videomaker.pipeline.runner import save_manual_image_prompts_bundle
from videomaker.scene_editor.models import Chunk
from videomaker.scene_editor.scene_visual_settings_store import read_scene_visual_settings
from videomaker.scene_editor.section_mapping import ensure_chunk_sections, section_to_act
from videomaker.scene_editor.visual_prompt_compose import (
    assemble_nano_banana_prompt,
    effective_avoid_en,
    enrich_scene_prompt,
    extract_scene_from_full_prompt,
    gesture_retry_hint,
    infer_narration_visual_strategy,
    protagonist_wardrobe_from_settings,
    settings_block,
    strategy_instruction,
    validate_full_prompt,
    validate_scene_prompt,
)

_DEFAULT_NEGATIVE = "stock photo, watermark, blurry, cartoon, extra fingers"
_CONTINUITY_WINDOW = 5


def _batch_delay_sec() -> float:
    raw = (os.environ.get("VISUAL_PLANNER_BATCH_DELAY_MS") or "400").strip()
    try:
        return max(0, int(raw)) / 1000.0
    except ValueError:
        return 0.4


def _build_system_prompt(settings: dict[str, Any]) -> str:
    from videomaker.scene_editor.visual_pipeline_rules import resolved_planner_extra_rules

    planner_rules = resolved_planner_extra_rules(settings)
    return f"""You write image prompts for Google Nano Banana 2 (Gemini image generation).

Write clear English PROSE — not Midjourney tags or comma-keyword lists.

{settings_block(settings)}

{planner_rules}

Output JSON:
{{
  "situation_es": "one Spanish sentence: what this image adds to the story",
  "protagonist_expression_key": "one key from PROTAGONIST FACIAL EXPRESSIONS (e.g. concerned, shocked, skeptical)",
  "scene_prompt_en": "45-90 words, scene only — include the emotional beat in the protagonist's face/body language"
}}
"""


def _build_user_prompt(
    chunk: Chunk,
    *,
    index: int,
    total: int,
    recent_situations: list[str],
    recent_scenes: list[str],
    visual_strategy: str,
    recent_expression_keys: list[str] | None = None,
) -> str:
    narration = (chunk.narration_text or "").strip() or "(none)"
    section = (chunk.section or "").strip() or section_to_act(None)
    dur = ""
    if chunk.duration_ms and chunk.duration_ms > 0:
        dur = f"\nVoiceover: ~{chunk.duration_ms / 1000:.1f}s"

    continuity = ""
    if recent_situations or recent_scenes:
        lines: list[str] = []
        if recent_situations:
            lines.append("Story beats already shown (do NOT repeat same setup):")
            lines.extend(f"- {s}" for s in recent_situations[-_CONTINUITY_WINDOW:])
        if recent_scenes:
            lines.append("Recent compositions to AVOID repeating:")
            for sc in recent_scenes[-3:]:
                lines.append(f"- {sc[:160]}…" if len(sc) > 160 else f"- {sc}")
        continuity = "\n" + "\n".join(lines)

    expr_block = ""
    if recent_expression_keys:
        recent_expr = ", ".join(recent_expression_keys[-4:])
        expr_block = (
            f"\nRecent expression keys used (pick a DIFFERENT key if this block's emotion changed): {recent_expr}\n"
        )

    director = (chunk.director_note or "").strip()
    director_block = ""
    if director:
        director_block = f"\n=== DIRECTOR / ROUTER (secondary) ===\n{director[:800]}\n"

    return f"""Block {index + 1} of {total} · Section: {section}{dur}

{strategy_instruction(visual_strategy)}
{director_block}
=== NARRATION (PRIMARY — illustrate THIS) ===
{narration[:1400]}
=== END NARRATION ===
{expr_block}{continuity}
"""


def _parse_llm_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    data = json.loads(text)
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError("Respuesta LLM inválida.")
    return data


def _normalize_scene(raw_scene: str, full_fallback: str, base_style: str) -> str:
    scene = (raw_scene or "").strip()
    if scene.lower().startswith(base_style.lower()[:30]):
        scene = extract_scene_from_full_prompt(scene, base_style)
    if not scene and full_fallback:
        scene = extract_scene_from_full_prompt(full_fallback, base_style)
    return scene.strip()


def _finalize_chunk_prompts(
    chunk: Chunk,
    *,
    situation: str,
    scene: str,
    settings: dict[str, Any],
    expression_key: str,
    expression_en: str,
) -> Chunk:
    base_style = str(settings.get("base_style_en") or "")
    wardrobe = protagonist_wardrobe_from_settings(settings)
    scene_clean = enrich_scene_prompt(
        scene,
        director_note=None,
        protagonist_en=str(settings.get("protagonist_en") or ""),
        wardrobe_en=wardrobe,
    )
    full = assemble_nano_banana_prompt(
        base_style_en=base_style,
        scene_prompt_en=scene_clean,
        avoid_en=effective_avoid_en(settings),
        aspect_ratio=str(settings.get("aspect_ratio") or "16:9"),
        output_spec=str(settings.get("output_spec") or "2K output"),
    )
    return chunk.model_copy(
        update={
            "visual_status": "done",
            "situation_es": situation or None,
            "scene_prompt_en": scene_clean,
            "protagonist_expression_key": expression_key or None,
            "protagonist_expression_en": expression_en or None,
            "ai_prompt": full,
            "negative_prompt": str(settings.get("avoid_en") or _DEFAULT_NEGATIVE),
        }
    )


def _plan_chunk_sync(
    chunk: Chunk,
    *,
    index: int,
    total: int,
    settings: dict[str, Any],
    recent_situations: list[str],
    recent_scenes: list[str],
    recent_expression_keys: list[str] | None = None,
) -> Chunk:
    if not (settings.get("base_style_en") or "").strip():
        raise ValueError("Define un estilo base antes de planificar visuales.")

    narration = (chunk.narration_text or "").strip()
    if not narration:
        raise ValueError("El bloque no tiene texto narrable.")

    base_style = str(settings.get("base_style_en") or "")
    protagonist = str(settings.get("protagonist_en") or "")
    wardrobe = protagonist_wardrobe_from_settings(settings)
    avoid = effective_avoid_en(settings)
    expr_catalog = expressions_catalog_from_settings(settings)
    visual_strategy = infer_narration_visual_strategy(narration)
    system = _build_system_prompt(settings)
    last_err = ""
    situation = ""
    expression_key = ""
    expression_en = ""

    for attempt in range(6):
        user = _build_user_prompt(
            chunk,
            index=index,
            total=total,
            recent_situations=recent_situations,
            recent_scenes=recent_scenes,
            visual_strategy=visual_strategy,
            recent_expression_keys=recent_expression_keys,
        )
        if attempt > 0:
            err_low = last_err.lower()
            if "parecida" in err_low:
                retry_hint = "Use a DIFFERENT location, camera angle, and props than recent blocks."
            elif any(k in err_low for k in ("postura", "estático", "estatico", "acción", "accion", "pose")):
                retry_hint = gesture_retry_hint(attempt, recent_scenes)
            elif any(
                k in err_low
                for k in (
                    "pantalla", "pizarra", "gesto", "señalando", "senalando",
                    "repetición", "repeticion", "repetid", "misma acción", "misma pose", "verbo",
                )
            ):
                retry_hint = gesture_retry_hint(attempt, recent_scenes)
            elif "genérico" in err_low or "generico" in err_low:
                retry_hint = (
                    "Replace vague atmosphere with CONCRETE props from NARRATION "
                    "(documents, numbers, screens, places). Max one lighting phrase."
                )
            elif "narración" in err_low or "voiceover" in err_low:
                retry_hint = "Illustrate the NARRATION text literally — name its nouns and actions."
            else:
                retry_hint = "Rewrite from NARRATION only. Different location/props than previous blocks."
            user = (
                f"RETRY {attempt} — rejected: {last_err}\n"
                f"{retry_hint}\n\n"
                f"{user}"
            )

        raw = call_production_llm(
            system=system,
            user=user,
            temperature=0.45 if attempt == 0 else 0.3,
        )
        parsed = _parse_llm_object(raw)

        situation = str(parsed.get("situation_es") or "").strip()
        llm_expr_key = str(parsed.get("protagonist_expression_key") or "").strip()
        expression_key, expression_en = resolve_protagonist_expression(
            narration=narration,
            llm_key=llm_expr_key,
            catalog=expr_catalog,
        )
        raw_scene = str(parsed.get("scene_prompt_en") or "").strip()
        raw_full = str(parsed.get("ai_prompt") or "").strip()
        scene = _normalize_scene(raw_scene, raw_full, base_style)
        scene = apply_protagonist_expression(scene, expression_en)
        scene = enrich_scene_prompt(
            scene,
            director_note=None,
            protagonist_en=protagonist,
            wardrobe_en=wardrobe,
        )

        ok, reason = validate_scene_prompt(
            scene,
            narration=narration,
            director_note=None,
            recent_scenes=recent_scenes,
            protagonist_en=protagonist,
            wardrobe_en=wardrobe,
        )
        if not ok:
            last_err = reason
            continue

        full = assemble_nano_banana_prompt(
            base_style_en=base_style,
            scene_prompt_en=scene,
            avoid_en=avoid,
            aspect_ratio=str(settings.get("aspect_ratio") or "16:9"),
            output_spec=str(settings.get("output_spec") or "2K output"),
        )

        ok_full, reason_full = validate_full_prompt(full, base_style=base_style)
        if ok_full:
            return _finalize_chunk_prompts(
                chunk,
                situation=situation,
                scene=scene,
                settings=settings,
                expression_key=expression_key,
                expression_en=expression_en,
            )
        last_err = reason_full

    raise ValueError(f"No se pudo generar prompt válido: {last_err}")


async def plan_chunk_visual(
    *,
    work_dir: Path,
    chunk: Chunk,
    index: int,
    total: int,
    settings: dict[str, Any] | None = None,
    recent_situations: list[str] | None = None,
    recent_scenes: list[str] | None = None,
    recent_expression_keys: list[str] | None = None,
) -> Chunk:
    cfg = settings if settings is not None else read_scene_visual_settings(work_dir)
    return await asyncio.to_thread(
        _plan_chunk_sync,
        chunk,
        index=index,
        total=total,
        settings=cfg,
        recent_situations=recent_situations or [],
        recent_scenes=recent_scenes or [],
        recent_expression_keys=recent_expression_keys or [],
    )


def _should_skip_visual(chunk: Chunk, *, skip_with_prompt: bool, regenerate_all: bool) -> bool:
    if regenerate_all or not skip_with_prompt:
        return False
    if chunk.visual_status in ("error", "planning"):
        return False
    if not (chunk.ai_prompt or "").strip():
        return False
    # Prompts legacy sin scene_prompt_en → replanificar
    if not (chunk.scene_prompt_en or "").strip():
        return False
    return chunk.visual_status == "done"


def _chunk_scene_for_continuity(chunk: Chunk, base_style: str) -> str:
    scene = (chunk.scene_prompt_en or "").strip()
    if scene:
        return scene
    full = (chunk.ai_prompt or "").strip()
    if full:
        return extract_scene_from_full_prompt(full, base_style)
    return ""


async def plan_all_chunks_visual(
    *,
    work_dir: Path,
    chunks: list[Chunk],
    skip_with_prompt: bool = True,
    regenerate_all: bool = False,
    chunk_ids: list[str] | None = None,
    on_progress: Callable[[list[Chunk]], None] | None = None,
) -> tuple[list[Chunk], int, int, int, list[dict[str, str]]]:
    out = [c.model_copy() for c in chunks]
    settings = read_scene_visual_settings(work_dir)
    base_style = str(settings.get("base_style_en") or "")
    if not base_style.strip():
        raise ValueError("Guarda un estilo base en Visual Planner antes de planificar.")

    wanted_ids = set(chunk_ids) if chunk_ids else None
    planned = skipped = failed = 0
    errors: list[dict[str, str]] = []
    delay = _batch_delay_sec()
    recent_situations: list[str] = []
    recent_scenes: list[str] = []
    recent_expression_keys: list[str] = []

    for i, chunk in enumerate(out):
        if wanted_ids is not None and chunk.id not in wanted_ids:
            if chunk.situation_es:
                recent_situations.append(chunk.situation_es)
            sc = _chunk_scene_for_continuity(chunk, base_style)
            if sc:
                recent_scenes.append(sc)
            if chunk.protagonist_expression_key:
                recent_expression_keys.append(chunk.protagonist_expression_key)
            continue

        if not (chunk.narration_text or "").strip():
            skipped += 1
            continue
        force_regen = regenerate_all or (wanted_ids is not None and chunk.id in wanted_ids)
        if not force_regen and _should_skip_visual(
            chunk, skip_with_prompt=skip_with_prompt, regenerate_all=regenerate_all
        ):
            skipped += 1
            if chunk.situation_es:
                recent_situations.append(chunk.situation_es)
            sc = _chunk_scene_for_continuity(chunk, base_style)
            if sc:
                recent_scenes.append(sc)
            if chunk.protagonist_expression_key:
                recent_expression_keys.append(chunk.protagonist_expression_key)
            continue

        out[i] = chunk.model_copy(
            update={
                "visual_status": "planning",
                "ai_prompt": None,
                "scene_prompt_en": None,
                "situation_es": None,
                "protagonist_expression_key": None,
                "protagonist_expression_en": None,
            }
        )
        if on_progress:
            on_progress(out)

        did_call = False
        try:
            from videomaker.scene_editor.chunk_visual_rhythm import (
                ensure_visual_shots_for_rhythm,
                plan_visual_shots_for_chunk,
            )

            rhythm_chunk = ensure_visual_shots_for_rhythm(work_dir, out[i])
            if rhythm_chunk.visual_shots:
                updated = await plan_visual_shots_for_chunk(
                    work_dir,
                    rhythm_chunk,
                    index=i,
                    total=len(out),
                    recent_situations=recent_situations,
                    recent_scenes=recent_scenes,
                    recent_expression_keys=recent_expression_keys,
                )
            else:
                updated = await plan_chunk_visual(
                    work_dir=work_dir,
                    chunk=rhythm_chunk,
                    index=i,
                    total=len(out),
                    settings=settings,
                    recent_situations=recent_situations,
                    recent_scenes=recent_scenes,
                    recent_expression_keys=recent_expression_keys,
                )
            out[i] = updated
            if updated.situation_es:
                recent_situations.append(updated.situation_es)
            sc = _chunk_scene_for_continuity(updated, base_style)
            if sc:
                recent_scenes.append(sc)
            if updated.protagonist_expression_key:
                recent_expression_keys.append(updated.protagonist_expression_key)
            planned += 1
            did_call = True
        except Exception as e:
            out[i] = chunk.model_copy(update={"visual_status": "error", "ai_prompt": None, "scene_prompt_en": None})
            failed += 1
            errors.append({"chunk_id": chunk.id, "detail": str(e)})

        if on_progress:
            on_progress(out)
        if delay > 0 and did_call:
            await asyncio.sleep(delay)

    return out, planned, skipped, failed, errors


def _export_one_visual_prompt(
    *,
    work_dir: Path,
    chunk: Chunk,
    settings: dict[str, Any],
    base_style: str,
    order: int,
    prompt: str,
    scene_only: str,
    expr_en: str,
    segment_text: str,
    shot: Any | None,
    duration_hint_s: float | None,
) -> dict[str, Any]:
    section = (chunk.section or "").strip() or None
    act = section_to_act(section)
    wardrobe = protagonist_wardrobe_from_settings(settings)
    scene_only = enrich_scene_prompt(
        scene_only,
        director_note=None,
        protagonist_en=str(settings.get("protagonist_en") or ""),
        wardrobe_en=wardrobe,
    ).rstrip(".")
    export_prompt = assemble_nano_banana_prompt(
        base_style_en=base_style,
        scene_prompt_en=scene_only,
        avoid_en=effective_avoid_en(settings),
        aspect_ratio=str(settings.get("aspect_ratio") or "16:9"),
        output_spec=str(settings.get("output_spec") or "2K output"),
    )
    shot_id = getattr(shot, "id", None) if shot is not None else None
    pid = str(shot_id or Path(chunk.id).name)
    return {
        "id": pid,
        "order": order,
        "act": act,
        "section": section,
        "role": "scene_shot" if shot is not None else "scene_chunk",
        "segment_text": segment_text[:400],
        "situation": (getattr(shot, "situation_es", None) or chunk.situation_es or "").strip()
        if shot is not None
        else (chunk.situation_es or "").strip(),
        "expression": (
            (getattr(shot, "protagonist_expression_key", None) or chunk.protagonist_expression_key or "")
            .strip()
            or None
        ),
        "protagonist_expression_en": expr_en or None,
        "scene_prompt_en": scene_only or None,
        "ai_prompt": export_prompt,
        "negative_prompt": (
            getattr(shot, "negative_prompt", None) or chunk.negative_prompt or settings.get("avoid_en")
        ),
        "duration_ms": chunk.duration_ms,
        "duration_hint_s": duration_hint_s,
        "chunk_id": chunk.id,
        "parent_chunk_id": chunk.id if shot is not None else None,
        "shot_type": getattr(shot, "shot_type", None) if shot is not None else None,
    }


def export_chunks_to_image_prompts(work_dir: Path, chunks: list[Chunk]) -> dict[str, Any]:
    settings = read_scene_visual_settings(work_dir)
    base_style = str(settings.get("base_style_en") or "")
    chunks = ensure_chunk_sections(work_dir, chunks, persist=True)
    prompts: list[dict[str, Any]] = []
    order = 0
    for chunk in chunks:
        shots = [s for s in (chunk.visual_shots or []) if (s.ai_prompt or "").strip()]
        if shots:
            total_ms = chunk.duration_ms if isinstance(chunk.duration_ms, int) and chunk.duration_ms > 0 else 0
            per_s = (total_ms / 1000.0 / len(shots)) if total_ms else None
            for shot in sorted(shots, key=lambda s: s.order):
                prompt = (shot.ai_prompt or "").strip()
                scene_only = (shot.scene_prompt_en or "").strip()
                if not scene_only:
                    scene_only = extract_scene_from_full_prompt(prompt, base_style)
                expr_en = (shot.protagonist_expression_en or "").strip()
                if expr_en:
                    scene_only = apply_protagonist_expression(scene_only, expr_en)
                prompts.append(
                    _export_one_visual_prompt(
                        work_dir=work_dir,
                        chunk=chunk,
                        settings=settings,
                        base_style=base_style,
                        order=order,
                        prompt=prompt,
                        scene_only=scene_only,
                        expr_en=expr_en,
                        segment_text=(shot.narration_excerpt or chunk.narration_text or ""),
                        shot=shot,
                        duration_hint_s=per_s,
                    )
                )
                order += 1
            continue

        prompt = (chunk.ai_prompt or "").strip()
        if not prompt:
            continue
        scene_only = (chunk.scene_prompt_en or "").strip()
        if not scene_only:
            scene_only = extract_scene_from_full_prompt(prompt, base_style)
        expr_en = (chunk.protagonist_expression_en or "").strip()
        if expr_en:
            scene_only = apply_protagonist_expression(scene_only, expr_en)
        prompts.append(
            _export_one_visual_prompt(
                work_dir=work_dir,
                chunk=chunk,
                settings=settings,
                base_style=base_style,
                order=order,
                prompt=prompt,
                scene_only=scene_only,
                expr_en=expr_en,
                segment_text=chunk.narration_text or "",
                shot=None,
                duration_hint_s=None,
            )
        )
        order += 1

    if not prompts:
        raise ValueError("Ningún bloque tiene prompt visual.")

    bundle: dict[str, Any] = {
        "version": 2,
        "source": "scene_editor_visual_planner",
        "target_generator": "nano_banana",
        "total_prompts": len(prompts),
        "global_style": {
            "base_style_en": settings.get("base_style_en"),
            "protagonist_en": settings.get("protagonist_en"),
            "avoid_en": settings.get("avoid_en"),
            "aspect_ratio": settings.get("aspect_ratio"),
            "output_spec": settings.get("output_spec"),
        },
        "prompts": prompts,
    }
    save_manual_image_prompts_bundle(work_dir, bundle)
    return {"path": "pipeline/image_prompts.json", "prompt_count": len(prompts)}
