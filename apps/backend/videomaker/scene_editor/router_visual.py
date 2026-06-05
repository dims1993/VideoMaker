"""Endpoints Visual Planner — estilo base + prompts Nano Banana 2."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from videomaker.scene_editor.models import (
    BatchChunkError,
    Chunk,
    ExpandVisualRhythmRequest,
    ExpandVisualRhythmResponse,
    ExportImagePromptsRequest,
    ExportImagePromptsResponse,
    PlanAllVisualRequest,
    PlanAllVisualResponse,
    PlanVisualChunkRequest,
    PlanVisualChunkResponse,
)
from videomaker.scene_editor.chunk_visual_rhythm import (
    assess_chunk_visual_rhythm,
    ensure_visual_shots_for_rhythm,
    plan_visual_shots_for_chunk,
)
from videomaker.scene_editor.scene_visual_settings_store import (
    read_scene_visual_settings,
    write_scene_visual_settings,
)
from videomaker.scene_editor.store import read_chunks, write_chunks
from videomaker.scene_editor.scene_visual_settings_store import read_scene_visual_settings
from videomaker.scene_editor.visual_planner_service import (
    export_chunks_to_image_prompts,
    plan_all_chunks_visual,
    plan_chunk_visual,
)
from videomaker.scene_editor.visual_prompt_compose import extract_scene_from_full_prompt
from videomaker.web.io_util import safe_work_dir

router = APIRouter(tags=["scene-editor-visual"])


class SceneVisualSettingsBody(BaseModel):
    work: str = Field(default="output/ui_session")
    base_style_en: str = ""
    protagonist_en: str = ""
    protagonist_wardrobe_en: str = ""
    protagonist_action_rules_en: str = ""
    protagonist_expressions_en: str = ""
    avoid_en: str = ""
    planner_extra_rules_en: str = ""
    gemini_continuity_prefix_en: str = ""
    auto_avoid_supplement_en: str = ""
    aspect_ratio: str = "16:9"
    output_spec: str = "2K output"


@router.get("/visual/style-settings")
def api_visual_style_settings_get(work: str = "output/ui_session") -> dict:
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return read_scene_visual_settings(work_dir)


@router.put("/visual/style-settings")
def api_visual_style_settings_put(body: SceneVisualSettingsBody) -> dict:
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return write_scene_visual_settings(work_dir, body.model_dump(exclude={"work"}))


@router.get("/visual/effective-rules")
def api_visual_effective_rules(work: str = "output/ui_session") -> dict:
    from videomaker.scene_editor.visual_pipeline_rules import effective_rules_preview

    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    settings = read_scene_visual_settings(work_dir)
    return effective_rules_preview(settings)


@router.get("/visual/planner-config")
def api_visual_planner_config(work: str = "output/ui_session") -> dict:
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    settings = read_scene_visual_settings(work_dir)
    has_style = bool((settings.get("base_style_en") or "").strip())
    return {
        "target_generator": "nano_banana",
        "has_style_settings": has_style,
        "has_protagonist": bool((settings.get("protagonist_en") or "").strip()),
        "has_action_pose_rules": bool(
            (settings.get("protagonist_action_rules_en") or "").strip()
        ),
        "has_expression_catalog": bool(
            (settings.get("protagonist_expressions_en") or "").strip()
        ),
        "planner_injects": [
            "base_style_en → prompt final (1.ª imagen Gemini)",
            "protagonist_en + protagonist_wardrobe_en → Character lock",
            "protagonist_expressions_en → expresión facial por bloque (desde narración)",
            "protagonist_action_rules_en → Visual Planner + cola Gemini",
            "avoid_en + auto_avoid_supplement_en → Avoid efectivo",
            "planner_extra_rules_en → reglas del Visual Planner (vacío = builtin del servidor)",
            "gemini_continuity_prefix_en → prefijo imágenes 2+ en cola Gemini",
        ],
    }


@router.post("/visual/plan-chunk", response_model=PlanVisualChunkResponse)
async def api_visual_plan_chunk(body: PlanVisualChunkRequest) -> PlanVisualChunkResponse:
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    chunks = read_chunks(work_dir) or []
    idx = next((i for i, c in enumerate(chunks) if c.id == body.chunk_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Chunk no encontrado.")

    base = chunks[idx]
    chunk_input = base.model_copy(
        update={
            "narration_text": body.narration_text or base.narration_text,
            "director_note": body.director_note if body.director_note is not None else base.director_note,
            "visual_status": "planning",
            "ai_prompt": None,
            "scene_prompt_en": None,
            "situation_es": None,
            "protagonist_expression_key": None,
            "protagonist_expression_en": None,
        }
    )
    chunks[idx] = chunk_input
    write_chunks(work_dir, chunks)

    settings = read_scene_visual_settings(work_dir)
    base_style = str(settings.get("base_style_en") or "")
    window = chunks[max(0, idx - 5) : idx]
    recent = [(c.situation_es or "").strip() for c in window if (c.situation_es or "").strip()]
    recent_scenes: list[str] = []
    recent_expression_keys: list[str] = []
    for c in window:
        scene = (c.scene_prompt_en or "").strip()
        if not scene and (c.ai_prompt or "").strip():
            scene = extract_scene_from_full_prompt(str(c.ai_prompt), base_style)
        if scene:
            recent_scenes.append(scene)
        if c.protagonist_expression_key:
            recent_expression_keys.append(c.protagonist_expression_key)

    try:
        rhythm_chunk = ensure_visual_shots_for_rhythm(work_dir, chunk_input)
        if rhythm_chunk.visual_shots:
            updated = await plan_visual_shots_for_chunk(
                work_dir,
                rhythm_chunk,
                index=idx,
                total=len(chunks),
                recent_situations=recent,
                recent_scenes=recent_scenes,
                recent_expression_keys=recent_expression_keys,
            )
        else:
            updated = await plan_chunk_visual(
                work_dir=work_dir,
                chunk=rhythm_chunk,
                index=idx,
                total=len(chunks),
                recent_situations=recent,
                recent_scenes=recent_scenes,
                recent_expression_keys=recent_expression_keys,
            )
    except ValueError as e:
        chunks[idx] = base.model_copy(update={"visual_status": "error"})
        write_chunks(work_dir, chunks)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        chunks[idx] = base.model_copy(update={"visual_status": "error"})
        write_chunks(work_dir, chunks)
        raise HTTPException(status_code=502, detail=str(e)) from e

    chunks[idx] = updated
    write_chunks(work_dir, chunks)
    return PlanVisualChunkResponse(chunk=updated)


@router.post("/visual/plan-all-chunks", response_model=PlanAllVisualResponse)
async def api_visual_plan_all_chunks(body: PlanAllVisualRequest) -> PlanAllVisualResponse:
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    chunks = read_chunks(work_dir) or []
    if not chunks:
        raise HTTPException(status_code=400, detail="No hay bloques; parsea el guion primero.")

    def _persist(updated: list[Chunk]) -> None:
        write_chunks(work_dir, updated)

    try:
        updated, planned, skipped, failed, errors = await plan_all_chunks_visual(
            work_dir=work_dir,
            chunks=chunks,
            skip_with_prompt=body.skip_with_prompt,
            regenerate_all=body.regenerate_all,
            chunk_ids=body.chunk_ids,
            on_progress=_persist,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    write_chunks(work_dir, updated)
    return PlanAllVisualResponse(
        chunks=updated,
        planned=planned,
        skipped=skipped,
        failed=failed,
        errors=[BatchChunkError(chunk_id=e["chunk_id"], detail=e["detail"]) for e in errors],
    )


@router.post("/visual/expand-rhythm", response_model=ExpandVisualRhythmResponse)
async def api_visual_expand_rhythm(body: ExpandVisualRhythmRequest) -> ExpandVisualRhythmResponse:
    """Divide un bloque largo en sub-planos (Body Router) y opcionalmente planifica visuales."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    chunks = read_chunks(work_dir) or []
    idx = next((i for i, c in enumerate(chunks) if c.id == body.chunk_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Chunk no encontrado.")

    base = chunks[idx]
    assessment = assess_chunk_visual_rhythm(work_dir, base)
    expanded = ensure_visual_shots_for_rhythm(work_dir, base)

    if body.auto_plan and expanded.visual_shots:
        settings = read_scene_visual_settings(work_dir)
        base_style = str(settings.get("base_style_en") or "")
        window = chunks[max(0, idx - 5) : idx]
        recent = [(c.situation_es or "").strip() for c in window if (c.situation_es or "").strip()]
        recent_scenes: list[str] = []
        recent_expr: list[str] = []
        for c in window:
            scene = (c.scene_prompt_en or "").strip()
            if not scene and (c.ai_prompt or "").strip():
                scene = extract_scene_from_full_prompt(str(c.ai_prompt), base_style)
            if scene:
                recent_scenes.append(scene)
            if c.protagonist_expression_key:
                recent_expr.append(c.protagonist_expression_key)
        try:
            expanded = await plan_visual_shots_for_chunk(
                work_dir,
                expanded,
                index=idx,
                total=len(chunks),
                recent_situations=recent,
                recent_scenes=recent_scenes,
                recent_expression_keys=recent_expr,
            )
        except (ValueError, Exception) as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

    chunks[idx] = expanded
    write_chunks(work_dir, chunks)
    return ExpandVisualRhythmResponse(
        chunk=expanded,
        assessment=assessment,
    )


@router.get("/visual/rhythm-assessment")
def api_visual_rhythm_assessment(
    work: str = "output/ui_session",
    chunk_id: str = "",
) -> dict:
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    chunks = read_chunks(work_dir) or []
    chunk = next((c for c in chunks if c.id == chunk_id), None)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk no encontrado.")
    return assess_chunk_visual_rhythm(work_dir, chunk)


@router.post("/visual/export-image-prompts", response_model=ExportImagePromptsResponse)
def api_visual_export_image_prompts(body: ExportImagePromptsRequest) -> ExportImagePromptsResponse:
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    chunks = read_chunks(work_dir) or []
    if not chunks:
        raise HTTPException(status_code=400, detail="No hay bloques en el Scene Editor.")

    try:
        info = export_chunks_to_image_prompts(work_dir, chunks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return ExportImagePromptsResponse(path=info["path"], prompt_count=info["prompt_count"])
