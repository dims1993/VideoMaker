"""Endpoints Scene Editor — parse guion, TTS por chunk."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from videomaker.scene_editor.audio_service import (
    export_chunks_to_narration_wav,
    generate_all_chunks_audio,
    generate_chunk_audio,
    resolve_chunk_audio_file,
)
from videomaker.scene_editor.models import (
    BatchChunkError,
    Chunk,
    ExportNarrationRequest,
    ExportNarrationResponse,
    GenerateAllChunksRequest,
    GenerateAllChunksResponse,
    GenerateChunkRequest,
    GenerateChunkResponse,
    ParseScriptRequest,
    ParseScriptResponse,
    SaveChunksRequest,
    SaveChunksResponse,
)
from videomaker.scene_editor.parser import parse_script_to_chunks
from videomaker.scene_editor.section_mapping import ensure_chunk_sections, load_script_text
from videomaker.scene_editor.store import read_chunks, write_chunks
from videomaker.tts.elevenlabs_client import ElevenLabsError, list_voices, tts_config_public
from videomaker.web.io_util import safe_work_dir

router = APIRouter(tags=["scene-editor"])


def _load_script_text(work_dir: Path) -> str:
    return load_script_text(work_dir)


@router.post("/script/parse", response_model=ParseScriptResponse)
async def api_script_parse(body: ParseScriptRequest) -> ParseScriptResponse:
    text = (body.text or "").strip()
    work_dir: Path | None = None
    if body.work:
        try:
            work_dir = safe_work_dir(body.work)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if not text and work_dir is not None:
        text = _load_script_text(work_dir).strip()
    if not text:
        raise HTTPException(status_code=400, detail="No hay texto de guion para parsear.")
    chunks = parse_script_to_chunks(text)
    if work_dir is not None:
        write_chunks(work_dir, chunks)
    return ParseScriptResponse(chunks=chunks)


@router.get("/scene-editor/chunks", response_model=ParseScriptResponse)
def api_scene_editor_chunks_get(work: str = Query("output/ui_session")) -> ParseScriptResponse:
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    chunks = read_chunks(work_dir)
    if chunks:
        chunks = ensure_chunk_sections(work_dir, chunks, persist=True)
    return ParseScriptResponse(chunks=chunks or [])


@router.put("/scene-editor/chunks", response_model=SaveChunksResponse)
def api_scene_editor_chunks_put(body: SaveChunksRequest) -> SaveChunksResponse:
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    write_chunks(work_dir, body.chunks)
    return SaveChunksResponse(chunks=body.chunks)


@router.post("/audio/generate-chunk", response_model=GenerateChunkResponse)
async def api_audio_generate_chunk(body: GenerateChunkRequest) -> GenerateChunkResponse:
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    chunks = read_chunks(work_dir) or []
    idx = next((i for i, c in enumerate(chunks) if c.id == body.chunk_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Chunk no encontrado; parsea el guion primero.")

    base = chunks[idx]
    try:
        updated = await generate_chunk_audio(
            work_dir=work_dir,
            chunk=base,
            narration_text=body.narration_text or base.narration_text,
            work_slug=body.work,
            voice_id=(body.voice_id or "").strip() or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ElevenLabsError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    chunks[idx] = updated
    write_chunks(work_dir, chunks)
    return GenerateChunkResponse(chunk=updated)


@router.post("/audio/generate-all-chunks", response_model=GenerateAllChunksResponse)
async def api_audio_generate_all_chunks(body: GenerateAllChunksRequest) -> GenerateAllChunksResponse:
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    chunks = read_chunks(work_dir) or []
    if not chunks:
        raise HTTPException(status_code=400, detail="No hay bloques; parsea el guion primero.")

    voice_id = (body.voice_id or "").strip() or None

    def _persist(updated: list[Chunk]) -> None:
        write_chunks(work_dir, updated)

    try:
        updated, generated, skipped, failed, errors = await generate_all_chunks_audio(
            work_dir=work_dir,
            chunks=chunks,
            work_slug=body.work,
            voice_id=voice_id,
            skip_with_audio=body.skip_with_audio,
            regenerate_all=body.regenerate_all,
            on_progress=_persist,
        )
    except ElevenLabsError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    write_chunks(work_dir, updated)
    return GenerateAllChunksResponse(
        chunks=updated,
        generated=generated,
        skipped=skipped,
        failed=failed,
        errors=[BatchChunkError(chunk_id=e["chunk_id"], detail=e["detail"]) for e in errors],
    )


@router.post("/audio/export-narration", response_model=ExportNarrationResponse)
def api_audio_export_narration(body: ExportNarrationRequest) -> ExportNarrationResponse:
    """Une los audios por bloque (scene_audio/) en un solo narracion.wav para el render."""
    import json

    from videomaker.web.io_util import finalize_new_narration

    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    chunks = read_chunks(work_dir) or []
    if not chunks:
        raise HTTPException(status_code=400, detail="No hay bloques; abre el Scene Editor y carga el guion.")

    try:
        result = export_chunks_to_narration_wav(
            work_dir,
            chunks,
            chunk_gap_ms=body.chunk_gap_ms,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    finalize_new_narration(work_dir)
    pipeline = work_dir / "pipeline"
    pipeline.mkdir(parents=True, exist_ok=True)
    vo_path = pipeline / "voiceovers.json"
    vo_path.write_text(
        json.dumps(
            {
                "wav": "narracion.wav",
                "duration_s": result["duration_s"],
                "source": "scene_editor_chunks",
                "chunks_used": result["chunks_used"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    from videomaker.pipeline.runner import _set_step

    missing = result.get("chunks_missing") or []
    miss_note = f"; {len(missing)} bloques sin audio" if missing else ""
    _set_step(
        work_dir,
        "voiceovers_generation",
        state="done",
        detail=f"narracion.wav ({result['chunks_used']} bloques Scene Editor{miss_note})",
    )

    try:
        from videomaker.llm.image_prompt_timing_reconcile import (
            reconcile_image_prompts_with_audio,
            reconcile_manifest_from_prompts,
        )

        if (work_dir / "pipeline" / "image_prompts.json").is_file():
            reconcile_image_prompts_with_audio(work_dir)
            reconcile_manifest_from_prompts(work_dir)
    except ValueError:
        pass

    return ExportNarrationResponse(
        path=str(result["path"]),
        duration_s=float(result["duration_s"]),
        chunks_used=int(result["chunks_used"]),
        chunks_missing=list(missing) if isinstance(missing, list) else [],
    )


@router.get("/audio/tts-config")
def api_audio_tts_config() -> dict:
    return tts_config_public()


@router.get("/audio/elevenlabs-voices")
def api_audio_elevenlabs_voices():
    try:
        voices = list_voices()
    except ElevenLabsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"voices": voices}


@router.get("/audio/chunk-file")
def api_audio_chunk_file(
    work: str = Query("output/ui_session"),
    chunk_id: str = Query(...),
):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = resolve_chunk_audio_file(work_dir, chunk_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Audio del chunk no encontrado.")
    media = "audio/mpeg" if p.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(str(p), media_type=media)
