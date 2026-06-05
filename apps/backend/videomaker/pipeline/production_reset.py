"""Reset parcial de artefactos de producción (mismo work, «nuevo proyecto» visual/audio/imágenes)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Literal

from videomaker.scene_editor.models import Chunk, VisualShot
from videomaker.scene_editor.store import artifact_path as scene_editor_path
from videomaker.scene_editor.store import read_chunks, scene_audio_dir, write_chunks

ProductionResetScope = Literal[
    "scene_editor_visual",
    "image_prompts",
    "voiceovers",
    "images_generation",
]

_VISUAL_CHUNK_CLEAR = {
    "visual_status": "idle",
    "situation_es": None,
    "scene_prompt_en": None,
    "protagonist_expression_key": None,
    "protagonist_expression_en": None,
    "ai_prompt": None,
    "negative_prompt": None,
    "visual_shots": [],
    "visual_rhythm_ok": None,
    "visual_rhythm_warning": None,
}

_AUDIO_CHUNK_CLEAR = {
    "audio_url": None,
    "duration_ms": None,
    "status": "idle",
}


def _pipeline_dir(work_dir: Path) -> Path:
    return work_dir / "pipeline"


def _strip_shot_visual(shot: VisualShot) -> VisualShot:
    return shot.model_copy(
        update={
            "director_note": shot.director_note,
            "situation_es": None,
            "scene_prompt_en": None,
            "protagonist_expression_key": None,
            "protagonist_expression_en": None,
            "ai_prompt": None,
            "negative_prompt": None,
        }
    )


def strip_chunk_visual_fields(chunk: Chunk) -> Chunk:
    updated = chunk.model_copy(update=_VISUAL_CHUNK_CLEAR)
    if updated.visual_shots:
        updated = updated.model_copy(
            update={"visual_shots": [_strip_shot_visual(s) for s in updated.visual_shots]}
        )
    return updated


def strip_chunk_audio_fields(chunk: Chunk) -> Chunk:
    return chunk.model_copy(update=_AUDIO_CHUNK_CLEAR)


def _read_image_prompts_source(work_dir: Path) -> str | None:
    p = _pipeline_dir(work_dir) / "image_prompts.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        src = data.get("source")
        return str(src) if src else None
    return None


def _unlink_if_file(path: Path, cleared: list[str]) -> None:
    if path.is_file():
        path.unlink(missing_ok=True)
        cleared.append(path.name)


def _rmtree_if_dir(path: Path, cleared: list[str]) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        cleared.append(f"{path.name}/")


def _reset_pipeline_steps(work_dir: Path, step_ids: list[str], *, detail: str) -> None:
    from videomaker.pipeline.runner import _set_step

    for sid in step_ids:
        _set_step(work_dir, sid, state="idle", detail=detail)


def reset_scene_editor_visuals(work_dir: Path) -> dict[str, Any]:
    """Quita prompts visuales de los bloques; conserva narración y audio."""
    cleared: list[str] = []
    chunks = read_chunks(work_dir)
    if not chunks:
        return {"ok": True, "chunks_updated": 0, "cleared": cleared}

    updated: list[Chunk] = []
    n = 0
    for c in chunks:
        stripped = strip_chunk_visual_fields(c)
        if stripped.model_dump() != c.model_dump():
            n += 1
        updated.append(stripped)
    if n:
        write_chunks(work_dir, updated)
        cleared.append("scene_editor.json (prompts visuales)")
    return {"ok": True, "chunks_updated": n, "cleared": cleared}


def _clear_narration_files(work_dir: Path, cleared: list[str]) -> None:
    from videomaker.web.io_util import NARRATION_MANIFEST_FILE, write_narration_manifest

    _unlink_if_file(work_dir / "narracion.wav", cleared)
    for p in work_dir.glob("narracion_*.wav"):
        p.unlink(missing_ok=True)
        cleared.append(p.name)
    man = work_dir / NARRATION_MANIFEST_FILE
    if man.is_file():
        man.unlink(missing_ok=True)
        cleared.append(man.name)
    write_narration_manifest(work_dir, None)


def _clear_scene_audio(work_dir: Path, cleared: list[str]) -> None:
    d = scene_audio_dir(work_dir)
    for p in d.glob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)
            cleared.append(f"scene_audio/{p.name}")


def _maybe_clear_legacy_image_prompts(work_dir: Path, cleared: list[str]) -> None:
    src = _read_image_prompts_source(work_dir)
    if src == "scene_editor_visual_planner":
        _unlink_if_file(_pipeline_dir(work_dir) / "image_prompts.json", cleared)
        _reset_pipeline_steps(
            work_dir,
            ["image_prompt_writer", "images_generation"],
            detail="Pendiente — image_prompts legacy borrado.",
        )


def reset_image_prompts_workflow(work_dir: Path, *, clear_images: bool = True) -> dict[str, Any]:
    cleared: list[str] = []
    _unlink_if_file(_pipeline_dir(work_dir) / "image_prompts.json", cleared)
    steps = ["image_prompt_writer"]
    if clear_images:
        reset_images_generation_workflow(work_dir, cleared=cleared, reset_step=False)
        steps.append("images_generation")
    _reset_pipeline_steps(work_dir, steps, detail="Pendiente — nuevo plan de prompts.")
    return {"ok": True, "cleared": cleared}


def reset_images_generation_workflow(
    work_dir: Path,
    *,
    cleared: list[str] | None = None,
    reset_step: bool = True,
) -> dict[str, Any]:
    out = cleared if cleared is not None else []
    pipe = _pipeline_dir(work_dir)
    _unlink_if_file(pipe / "images_generation.json", out)
    _unlink_if_file(pipe / "gemini_web_job.json", out)
    _rmtree_if_dir(pipe / "images", out)
    try:
        from videomaker.engines.gemini_web_batch import request_cancel

        request_cancel(work_dir)
    except Exception:
        pass
    if reset_step:
        _reset_pipeline_steps(
            work_dir,
            ["images_generation"],
            detail="Pendiente — manifest de imágenes reiniciado.",
        )
    return {"ok": True, "cleared": out}


def reset_voiceovers_workflow(work_dir: Path) -> dict[str, Any]:
    """Visual + audio por bloque, narración unificada y export legacy a IPW si aplica."""
    cleared: list[str] = []
    chunks = read_chunks(work_dir) or []
    chunks_touched = 0
    if chunks:
        merged: list[Chunk] = []
        for c in chunks:
            next_c = strip_chunk_audio_fields(strip_chunk_visual_fields(c))
            if next_c.model_dump() != c.model_dump():
                chunks_touched += 1
            merged.append(next_c)
        if chunks_touched:
            write_chunks(work_dir, merged)
            cleared.append("scene_editor.json (audio y visual)")

    _clear_scene_audio(work_dir, cleared)
    _clear_narration_files(work_dir, cleared)
    _unlink_if_file(_pipeline_dir(work_dir) / "voiceovers.json", cleared)
    _unlink_if_file(_pipeline_dir(work_dir) / "audio_timeline.json", cleared)
    _maybe_clear_legacy_image_prompts(work_dir, cleared)
    _reset_pipeline_steps(
        work_dir,
        ["voiceovers_generation"],
        detail="Pendiente — nueva pasada de voiceovers.",
    )
    return {
        "ok": True,
        "chunks_updated": chunks_touched,
        "cleared": cleared,
    }


def run_production_reset(work_dir: Path, scope: ProductionResetScope) -> dict[str, Any]:
    if scope == "scene_editor_visual":
        result = reset_scene_editor_visuals(work_dir)
    elif scope == "image_prompts":
        result = reset_image_prompts_workflow(work_dir)
    elif scope == "voiceovers":
        result = reset_voiceovers_workflow(work_dir)
    elif scope == "images_generation":
        result = reset_images_generation_workflow(work_dir)
    else:
        raise ValueError(f"scope desconocido: {scope}")
    result["scope"] = scope
    result["has_scene_editor"] = scene_editor_path(work_dir).is_file()
    return result
