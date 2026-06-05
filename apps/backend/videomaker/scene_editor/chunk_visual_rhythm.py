"""Validación de ritmo visual por chunk (audio TTS vs densidad del prompt)."""

from __future__ import annotations

import re
from pathlib import Path

from videomaker.llm.body_scene_router import plan_chunk_visual_splits_from_router
from videomaker.scene_editor.models import Chunk, VisualShot
from videomaker.scene_editor.visual_hold_policy import (
    max_visual_hold_s,
    shots_needed_for_duration,
)


def chunk_audio_duration_s(chunk: Chunk) -> float | None:
    if isinstance(chunk.duration_ms, int) and chunk.duration_ms > 0:
        return chunk.duration_ms / 1000.0
    return None


def _router_planned_body_rhythm(work_dir: Path) -> bool:
    from videomaker.llm.body_scene_router import read_body_macro_beats

    return len(read_body_macro_beats(work_dir)) >= 2


def assess_chunk_visual_rhythm(work_dir: Path, chunk: Chunk) -> dict[str, object]:
    """Diagnóstico sin mutar el chunk."""
    if _router_planned_body_rhythm(work_dir):
        return {
            "ok": True,
            "needs_split": False,
            "max_hold_s": max_visual_hold_s(work_dir, section=chunk.section),
            "duration_s": chunk_audio_duration_s(chunk),
            "shots_needed": 1,
            "shots_current": len(chunk.visual_shots or []),
            "message": "Ritmo visual del cuerpo planificado en Body Scene Router (macro_beats). Scene Editor no parte chunks automáticamente.",
        }
    max_hold = max_visual_hold_s(work_dir, section=chunk.section)
    dur = chunk_audio_duration_s(chunk)
    if dur is None:
        return {
            "ok": True,
            "needs_split": False,
            "max_hold_s": max_hold,
            "duration_s": None,
            "shots_needed": 1,
            "message": "Sin audio medido aún.",
        }
    needed = shots_needed_for_duration(dur, max_hold)
    current = len(chunk.visual_shots) if chunk.visual_shots else (1 if (chunk.ai_prompt or "").strip() else 0)
    needs = needed > 1 and current < needed
    return {
        "ok": not needs,
        "needs_split": needs,
        "max_hold_s": max_hold,
        "duration_s": round(dur, 2),
        "shots_needed": needed,
        "shots_current": max(current, 1 if (chunk.ai_prompt or "").strip() else 0),
        "message": (
            f"Audio {dur:.1f}s supera {max_hold:.1f}s/plano → se necesitan {needed} cortes visuales."
            if needs
            else f"Ritmo OK ({dur:.1f}s ≤ {max_hold:.1f}s/plano o ya hay {current} planos)."
        ),
    }


def _split_narration_slices(text: str, n: int) -> list[str]:
    t = (text or "").strip()
    if not t or n <= 1:
        return [t] if t else [""]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", t) if s.strip()]
    if len(sentences) >= n:
        buckets: list[list[str]] = [[] for _ in range(n)]
        for i, sent in enumerate(sentences):
            buckets[i % n].append(sent)
        return [" ".join(b).strip() for b in buckets if " ".join(b).strip()]
    words = t.split()
    size = max(1, len(words) // n)
    slices: list[str] = []
    i = 0
    while i < len(words) and len(slices) < n - 1:
        slices.append(" ".join(words[i : i + size]).strip())
        i += size
    slices.append(" ".join(words[i:]).strip())
    while len(slices) < n:
        slices.append("")
    return slices[:n]


def build_visual_shots_for_chunk(
    work_dir: Path,
    chunk: Chunk,
    *,
    shots_needed: int,
) -> list[VisualShot]:
    """Crea sub-planos con pistas del Body Scene Router (sin LLM de imagen aún)."""
    briefs = plan_chunk_visual_splits_from_router(work_dir, chunk, shots_needed)
    slices = _split_narration_slices(chunk.narration_text, shots_needed)
    shots: list[VisualShot] = []
    for i in range(shots_needed):
        brief = briefs[i] if i < len(briefs) else briefs[-1] if briefs else "B-roll cutaway"
        excerpt = slices[i] if i < len(slices) else ""
        shots.append(
            VisualShot(
                id=f"{Path(chunk.id).name}-v{i + 1}",
                order=i,
                shot_type=brief.get("shot_type") if isinstance(brief, dict) else None,
                director_note=str(brief.get("director_note") if isinstance(brief, dict) else brief),
                narration_excerpt=excerpt,
            )
        )
    return shots


def ensure_visual_shots_for_rhythm(work_dir: Path, chunk: Chunk) -> Chunk:
    """
    Si el audio excede el máximo por plano, crea ``visual_shots`` (pistas del body router).
    """
    diag = assess_chunk_visual_rhythm(work_dir, chunk)
    if not diag.get("needs_split"):
        return chunk.model_copy(
            update={
                "visual_rhythm_ok": True,
                "visual_rhythm_warning": None,
            }
        )
    needed = int(diag.get("shots_needed") or 2)
    existing = list(chunk.visual_shots or [])
    if len(existing) >= needed and all((s.ai_prompt or "").strip() for s in existing):
        return chunk.model_copy(update={"visual_rhythm_ok": True, "visual_rhythm_warning": None})

    if len(existing) >= needed:
        warning = str(diag.get("message") or "")
        return chunk.model_copy(
            update={"visual_rhythm_ok": False, "visual_rhythm_warning": warning}
        )

    shots = build_visual_shots_for_chunk(work_dir, chunk, shots_needed=needed)
    warning = str(diag.get("message") or "")
    return chunk.model_copy(
        update={
            "visual_shots": shots,
            "visual_rhythm_ok": False,
            "visual_rhythm_warning": warning,
            "visual_status": "idle",
        }
    )


async def plan_visual_shots_for_chunk(
    work_dir: Path,
    chunk: Chunk,
    *,
    index: int,
    total: int,
    recent_situations: list[str],
    recent_scenes: list[str],
    recent_expression_keys: list[str],
) -> Chunk:
    """Planifica cada sub-plano con el Visual Planner (misma voz, varios planos)."""
    from videomaker.scene_editor.visual_planner_service import plan_chunk_visual

    shots = list(chunk.visual_shots or [])
    if not shots:
        return await plan_chunk_visual(
            work_dir=work_dir,
            chunk=chunk,
            index=index,
            total=total,
            recent_situations=recent_situations,
            recent_scenes=recent_scenes,
            recent_expression_keys=recent_expression_keys,
        )

    updated_shots: list[VisualShot] = []
    sit = list(recent_situations)
    scenes = list(recent_scenes)
    expr_keys = list(recent_expression_keys)

    for si, shot in enumerate(shots):
        excerpt = (shot.narration_excerpt or chunk.narration_text or "").strip()
        note = (shot.director_note or "").strip()
        director = f"[Body Scene Router · {shot.shot_type or 'cut'}] {note}".strip()
        temp = Chunk(
            id=f"{chunk.id}::{shot.id}",
            narration_text=excerpt or chunk.narration_text,
            section=chunk.section,
            director_note=director,
        )
        planned = await plan_chunk_visual(
            work_dir=work_dir,
            chunk=temp,
            index=index,
            total=total,
            recent_situations=sit,
            recent_scenes=scenes,
            recent_expression_keys=expr_keys,
        )
        updated_shots.append(
            shot.model_copy(
                update={
                    "situation_es": planned.situation_es,
                    "scene_prompt_en": planned.scene_prompt_en,
                    "protagonist_expression_key": planned.protagonist_expression_key,
                    "protagonist_expression_en": planned.protagonist_expression_en,
                    "ai_prompt": planned.ai_prompt,
                    "negative_prompt": planned.negative_prompt,
                }
            )
        )
        if planned.situation_es:
            sit.append(planned.situation_es)
        from videomaker.scene_editor.scene_visual_settings_store import read_scene_visual_settings
        from videomaker.scene_editor.visual_planner_service import _chunk_scene_for_continuity

        base_style = str(read_scene_visual_settings(work_dir).get("base_style_en") or "")
        sc = _chunk_scene_for_continuity(planned, base_style)
        if sc:
            scenes.append(sc)
        if planned.protagonist_expression_key:
            expr_keys.append(planned.protagonist_expression_key)

    return chunk.model_copy(
        update={
            "visual_shots": updated_shots,
            "visual_status": "done",
            "visual_rhythm_ok": True,
            "visual_rhythm_warning": None,
            "situation_es": updated_shots[0].situation_es if updated_shots else chunk.situation_es,
            "scene_prompt_en": updated_shots[0].scene_prompt_en if updated_shots else chunk.scene_prompt_en,
            "ai_prompt": updated_shots[0].ai_prompt if updated_shots else chunk.ai_prompt,
        }
    )

