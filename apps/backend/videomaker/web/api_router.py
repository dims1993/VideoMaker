"""API JSON para la SPA (React). Las rutas HTML clásicas siguen en `app.py`."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from videomaker.core.models import ScriptBlueprint
from videomaker.llm.prompt_presets_store import (
    create_preset,
    delete_preset,
    get_preset,
    get_selected_id,
    list_presets,
    set_selected_id,
    update_preset,
)
from videomaker.llm.prompt_templates_store import (
    create_prompt_template,
    delete_prompt_template,
    get_prompt_template,
    list_prompt_templates,
    update_prompt_template,
)
from videomaker.llm.script_writer_templates_store import (
    create_script_writer_template,
    delete_script_writer_template,
    get_script_writer_template,
    list_script_writer_templates,
    update_script_writer_template,
)
from videomaker.core.hook_router_settings_store import (
    read_hook_router_settings,
    write_hook_router_settings,
)
from videomaker.core.image_prompt_writer_settings_store import (
    read_image_prompt_writer_settings,
    write_image_prompt_writer_settings,
)
from videomaker.core.metadata_settings_store import (
    read_metadata_settings,
    write_metadata_settings,
)
from videomaker.core.script_bundle import build_script_bundle, read_script_bundle, write_script_bundle
from videomaker.llm.script_gen import compose_messages
from videomaker.tts.voice_reference import REFERENCE_SUFFIXES, normalize_reference_for_xtts
from videomaker.youtube.channel_store import (
    delete_channel,
    get_channel,
    list_channel_videos,
    list_channel_videos_detail,
    list_channels,
    list_channels_opportunities,
    mark_channel_pearl,
    set_channel_internal_fields,
    upsert_channel,
 )

from . import jobs
from .io_util import (
    build_session_state,
    delete_narration_archive,
    parse_locale,
    read_status,
    read_tts_reference,
    safe_preview_voice_name,
    safe_work_dir,
    select_narration_archive,
    write_tts_reference,
)

router = APIRouter(prefix="/api", tags=["api"])

from videomaker.scene_editor.router_audio import router as scene_editor_router  # noqa: E402
from videomaker.scene_editor.router_visual import router as scene_editor_visual_router  # noqa: E402

router.include_router(scene_editor_router)
router.include_router(scene_editor_visual_router)

_CLONE_UPLOAD_MAX_BYTES = 25 * 1024 * 1024


class WorkModel(BaseModel):
    work: str = Field(default="output/ui_session", description="Carpeta relativa al proyecto")


class VoicePreviewBody(WorkModel):
    preset: str = "xtts_v2_es"
    text: str = "Hola, esta es una prueba de voz antes de narrar el vídeo."


class GenerateScriptBody(WorkModel):
    keywords: str = "motivación, hábitos, enfoque"
    context: str = ""
    lang: str = "es"
    minutes: float = 10.0
    provider: str = ""
    model: str = ""
    system_extra: str = ""
    user_extra: str = ""


class SpeakScriptBody(WorkModel):
    preset: str = "xtts_v2_es"
    max_chars: int = 900
    max_segments: int = 0


class RenderDraftBody(WorkModel):
    no_music: bool = False


class RenderPreviewBody(WorkModel):
    no_music: bool = True
    max_segments: int = 12
    max_duration_s: float = 120.0


class PromptPreviewBody(WorkModel):
    keywords: str = "motivación, hábitos, enfoque"
    context: str = ""
    lang: str = "es"
    minutes: float = 10.0
    system_extra: str = ""
    user_extra: str = ""


class AnalyzeYoutubeBody(WorkModel):
    url: str = Field(..., min_length=6, description="URL o ID de YouTube")
    lang: str = "es"

class AnalyzeChannelBody(WorkModel):
    channel: str = Field(..., min_length=2, description="@handle, URL del canal o nombre")
    lang: str = "es"
    max_videos: int = 10


class ChannelBackfillBody(WorkModel):
    limit: int = 200


class ChannelTranscriptsJsonBody(WorkModel):
    video_ids: list[str] = Field(default_factory=list, description="Si vacío: usa los últimos N vídeos guardados")
    limit: int = 50
    lang: str = "es"


class PipelineStartBody(WorkModel):
    keywords: str = "motivación, hábitos, enfoque"
    context: str = ""
    lang: str = "es"
    minutes: float = 10.0
    provider: str = ""
    model: str = ""
    prompt_template_id: str | None = None
    prompt_topic: str | None = None
    prompt_video_restrictions: str | None = None
    script_writer_template_id: str | None = None
    script_fragment_index: int | None = None
    render_no_music: bool = False


class PipelineRerunBody(WorkModel):
    step_id: str = Field(..., min_length=2)
    prompt_template_id: str | None = None
    prompt_topic: str | None = None
    prompt_video_restrictions: str | None = None
    script_writer_template_id: str | None = None
    keywords: str | None = None
    context: str | None = None
    lang: str | None = None
    minutes: float | None = None
    provider: str | None = None
    model: str | None = None
    script_fragment_index: int | None = None
    render_no_music: bool | None = None
    topic_generator_transcript: str | None = None
    topic_generator_niche_trends: str | None = None
    topic_generator_topic_count: int | None = Field(default=None, ge=3, le=20)


class TopicGeneratorGenerateBody(WorkModel):
    transcript_text: str = ""
    niche_trends: str = ""
    topic_count: int = Field(default=8, ge=3, le=20)
    output_language: Literal["en", "es"] | None = None
    provider: str = "anthropic"
    model: str = ""
    use_session: bool = False
    detail_level: Literal["fast", "full"] = "fast"


class TranscriptsSessionAnalyzeBody(WorkModel):
    niche_trends: str = ""
    topic_count: int = Field(default=8, ge=3, le=20)
    """Idioma de salida del LLM (temas + plantilla Prompt). Prioridad sobre idioma del canal."""
    output_language: str = Field(default="en", pattern="^(en|es)$")
    provider: str = "anthropic"
    model: str = ""


class TranscriptsSessionImportBody(WorkModel):
    """JSON exportado de /channels/.../transcripts.json (o solo { videos: [...] })."""
    payload: dict[str, Any] = Field(default_factory=dict)
    source_channel_id: str = ""


class TopicGeneratorSelectBody(WorkModel):
    selected_index: int = Field(..., ge=0)


class TopicGeneratorEnrichBody(WorkModel):
    selected_index: int = Field(..., ge=0)
    provider: str = "anthropic"
    model: str = ""


class ScriptFragmentationPatchBody(WorkModel):
    index: int = Field(..., ge=0)
    complete: bool = True


class ScriptUpdateBody(WorkModel):
    text: str = Field(default="", description="Contenido completo de guion.txt")
    only_disk: bool = Field(
        default=False,
        description="Si true, solo escribe guion/script.json sin marcar Script Writer como done",
    )


class ScriptLintBody(BaseModel):
    work: str | None = Field(
        default=None,
        description="Sesión; si text está vacío, lee guion.txt / pipeline/script.txt",
    )
    text: str | None = Field(default=None, description="Guion a analizar (prioridad sobre work)")
    target_minutes: float | None = Field(default=None, ge=0.5, le=120)
    persist: bool = Field(default=False, description="Si work está definido, guarda pipeline/script_quality.json")


class TtsReferenceBody(WorkModel):
    mode: Literal["auto", "clone", "builtin", "preview"]
    preview_filename: str | None = None


class NarrationSelectBody(WorkModel):
    name: str = Field(..., description="Archivo narracion_*.wav del historial")


class PromptPresetCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    system_extra: str = ""
    user_extra: str = ""


class PromptPresetUpdateBody(BaseModel):
    id: str = Field(..., min_length=8)
    name: str | None = Field(None, max_length=120)
    system_extra: str | None = None
    user_extra: str | None = None


class PromptPresetSelectBody(BaseModel):
    id: str | None = None


class PromptTemplateBody(BaseModel):
    name: str = ""
    hook_style: str = ""
    visual_style: str = ""
    tone: str = ""
    system_instructions: str = ""
    user_instructions: str = ""
    params_json: dict = Field(default_factory=dict)


class ScriptWriterTemplateBody(BaseModel):
    name: str = ""
    system_instructions: str = ""
    user_instructions: str = ""
    params_json: dict = Field(default_factory=dict)


@router.get("/session")
def api_session(work: str = "output/ui_session"):
    try:
        from videomaker.web.server_boot import SERVER_BOOT_AT, SERVER_BOOT_ID

        state = build_session_state(work)
        if isinstance(state, dict):
            state["server_boot_id"] = SERVER_BOOT_ID
            state["server_boot_at"] = SERVER_BOOT_AT
        return state
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _ollama_tags_payload() -> dict:
    """Lista modelos instalados vía GET {OLLAMA_BASE_URL}/api/tags."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{base}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        models_out: list[dict] = []
        for m in data.get("models") or []:
            name = m.get("name") or m.get("model")
            if isinstance(name, str) and name.strip():
                models_out.append(
                    {
                        "name": name.strip(),
                        "size": m.get("size"),
                        "modified_at": m.get("modified_at"),
                    }
                )
        return {"ok": True, "models": models_out}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "models": [], "error": str(e)}


@router.get("/llm/defaults")
def api_llm_defaults():
    """Valores por defecto del servidor (.env) para inicializar la UI."""
    from videomaker.llm.llm_routing import (
        CREATIVE_PROVIDER,
        PRODUCTION_PROVIDER,
        default_creative_model,
        default_production_model,
    )

    return {
        "llm_provider": os.environ.get("VIDEOMAKER_LLM_PROVIDER", ""),
        "creative_provider": CREATIVE_PROVIDER,
        "creative_model": default_creative_model(),
        "production_provider": PRODUCTION_PROVIDER,
        "openai_model": default_production_model(),
        "anthropic_model": default_creative_model(),
        "ollama_model": os.environ.get("OLLAMA_MODEL", ""),
    }


@router.get("/ollama/models")
def api_ollama_models():
    return _ollama_tags_payload()


@router.get("/status")
def api_status(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
        return read_status(work_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/script")
def api_script(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    guion = work_dir / "guion.txt"
    pipe = work_dir / "pipeline" / "script.txt"
    text = ""
    if guion.is_file() and guion.stat().st_size > 0:
        text = guion.read_text(encoding="utf-8")
    elif pipe.is_file():
        text = pipe.read_text(encoding="utf-8")
    has_script = guion.is_file() or pipe.is_file()
    structured = read_script_bundle(work_dir)
    if structured is None and text.strip():
        structured = build_script_bundle(text)
    quality = None
    if text.strip():
        from videomaker.llm.script_lint import lint_script, persist_script_quality

        quality = lint_script(text, work_dir=work_dir).to_dict()
        try:
            persist_script_quality(work_dir, text)
        except Exception:
            pass
    return {"text": text, "has_script": has_script, "structured": structured, "quality": quality}


@router.post("/script-lint")
def api_script_lint(body: ScriptLintBody):
    from videomaker.llm.script_lint import lint_script, persist_script_quality

    work_dir: Path | None = None
    if body.work:
        try:
            work_dir = safe_work_dir(body.work)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    text = (body.text or "").strip()
    if not text and work_dir is not None:
        guion = work_dir / "guion.txt"
        pipe = work_dir / "pipeline" / "script.txt"
        if guion.is_file() and guion.stat().st_size > 0:
            text = guion.read_text(encoding="utf-8")
        elif pipe.is_file():
            text = pipe.read_text(encoding="utf-8")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No hay texto de guion para analizar.")

    report = lint_script(
        text,
        target_minutes=body.target_minutes,
        work_dir=work_dir,
    )
    if body.persist and work_dir is not None:
        persist_script_quality(work_dir, text, target_minutes=body.target_minutes)
    return report.to_dict()


@router.put("/script")
def api_put_script(body: ScriptUpdateBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if body.only_disk:
        from videomaker.core.saved_guiones_store import write_guion_to_session_work_dir

        write_guion_to_session_work_dir(work_dir, body.text)
        return {"ok": True, "only_disk": True}
    from videomaker.pipeline.runner import apply_imported_guion_to_work

    apply_imported_guion_to_work(work_dir, body.text, detail="Guion guardado desde el editor.")
    return {"ok": True}


class WorkDirRevealBody(WorkModel):
    highlight: str | None = Field(
        default="guion.txt",
        description="Archivo dentro de la sesión a resaltar en el explorador (solo nombre base).",
    )


@router.get("/work-dir")
def api_work_dir(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    guion = work_dir / "guion.txt"
    pipe = work_dir / "pipeline" / "script.txt"
    return {
        "work": work.strip(),
        "absolute_path": str(work_dir),
        "guion_relative": "guion.txt",
        "guion_absolute": str(guion.resolve()),
        "guion_exists": guion.is_file(),
        "script_pipeline_relative": "pipeline/script.txt",
        "script_pipeline_exists": pipe.is_file(),
    }


@router.post("/work-dir/reveal")
def api_work_dir_reveal(body: WorkDirRevealBody):
    import platform
    import subprocess

    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir
    if body.highlight:
        safe_name = Path(body.highlight.strip()).name
        if safe_name:
            candidate = work_dir / safe_name
            if candidate.is_file():
                target = candidate
    system = platform.system()
    try:
        if system == "Darwin":
            if target.is_file():
                subprocess.run(["open", "-R", str(target)], check=True)
            else:
                subprocess.run(["open", str(work_dir)], check=True)
        elif system == "Windows":
            if target.is_file():
                subprocess.run(["explorer", "/select,", str(target.resolve())], check=True)
            else:
                subprocess.run(["explorer", str(work_dir.resolve())], check=True)
        else:
            subprocess.run(["xdg-open", str(work_dir)], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo abrir el explorador de archivos: {e}",
        ) from e
    return {"ok": True, "opened": str(target)}


@router.post("/voice-preview", status_code=202)
def api_voice_preview(background: BackgroundTasks, body: VoicePreviewBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    background.add_task(jobs.run_voice_preview, body.work, body.preset, body.text)
    return {"started": True, "step": "voice_preview"}


@router.post("/generate-script", status_code=202)
def api_generate_script(background: BackgroundTasks, body: GenerateScriptBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    background.add_task(
        jobs.run_generate_script,
        body.work,
        keywords=body.keywords,
        context=body.context,
        lang=body.lang,
        minutes=body.minutes,
        provider=(body.provider.strip() or None),
        model=(body.model or None),
        system_extra=body.system_extra or "",
        user_extra=body.user_extra or "",
    )
    return {"started": True, "step": "script"}


@router.post("/speak-script", status_code=202)
def api_speak_script(background: BackgroundTasks, body: SpeakScriptBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not (work_dir / "guion.txt").is_file():
        raise HTTPException(status_code=400, detail="No existe guion.txt en esta sesión.")
    background.add_task(
        jobs.run_speak_script,
        body.work,
        preset=body.preset,
        max_chars=body.max_chars,
        max_segments=body.max_segments,
    )
    return {"started": True, "step": "tts"}


@router.post("/render-draft", status_code=202)
def api_render_draft(background: BackgroundTasks, body: RenderDraftBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not (work_dir / "narracion.wav").is_file():
        raise HTTPException(status_code=400, detail="Falta narracion.wav.")
    background.add_task(jobs.run_render_draft, body.work, no_music=body.no_music)
    return {"started": True, "step": "render"}


@router.get("/pipeline/render-progress")
def api_pipeline_render_progress(work: str = "output/ui_session"):
    """Progreso del render en curso (preview MP4 o draft)."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.video.render_progress import read_render_progress

    progress = read_render_progress(work_dir)
    if progress is None:
        return {"exists": False, "progress": None}
    return {"exists": True, "progress": progress}


@router.get("/pipeline/render-preview/timeline")
def api_render_preview_timeline(work: str = "output/ui_session"):
    """Timeline imagen+audio por bloque para preview en navegador (sin codificar)."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.video.render import build_render_preview_timeline

    return build_render_preview_timeline(work_dir, work)


@router.post("/render-preview", status_code=202)
def api_render_preview(background: BackgroundTasks, body: RenderPreviewBody):
    """MP4 corto (720p, ultrafast) → preview_draft.mp4."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not (work_dir / "narracion.wav").is_file():
        raise HTTPException(status_code=400, detail="Falta narracion.wav.")
    max_seg = max(1, min(int(body.max_segments), 40))
    max_dur = max(15.0, min(float(body.max_duration_s), 600.0))
    background.add_task(
        jobs.run_render_preview,
        body.work,
        no_music=body.no_music,
        max_segments=max_seg,
        max_duration_s=max_dur,
    )
    return {
        "started": True,
        "step": "render",
        "output_file": "preview_draft.mp4",
        "max_segments": max_seg,
        "max_duration_s": max_dur,
    }


@router.post("/prompt-preview")
def api_prompt_preview(body: PromptPreviewBody):
    bp = ScriptBlueprint(
        keywords=[k.strip() for k in body.keywords.split(",") if k.strip()],
        extra_context=body.context or "",
        locale=parse_locale(body.lang),
        target_minutes=float(body.minutes),
    )
    system, user = compose_messages(
        bp,
        system_extra=body.system_extra or "",
        user_extra=body.user_extra or "",
    )
    return {"system": system, "user": user}


@router.post("/analyze/youtube", status_code=202)
def api_analyze_youtube(background: BackgroundTasks, body: AnalyzeYoutubeBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    background.add_task(jobs.run_analyze_youtube, body.work, url=body.url, lang=body.lang)
    return {"started": True, "step": "analyze"}

@router.post("/analyze/channel", status_code=202)
def api_analyze_channel(background: BackgroundTasks, body: AnalyzeChannelBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    background.add_task(
        jobs.run_analyze_channel,
        body.work,
        channel=body.channel,
        lang=body.lang,
        max_videos=int(body.max_videos),
    )
    return {"started": True, "step": "analyze_channel"}


@router.get("/analyze/result")
def api_analyze_result(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    report_path = work_dir / "analyze_youtube.json"
    log_path = work_dir / "analyze_youtube.log"
    report = None
    if report_path.is_file():
        try:
            import json

            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            report = None
    log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    return {"report": report, "log": log}


@router.get("/analyze/channel-result")
def api_analyze_channel_result(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    report_path = work_dir / "analyze_channel.json"
    log_path = work_dir / "analyze_channel.log"
    report = None
    if report_path.is_file():
        try:
            import json

            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            report = None
    log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    return {"report": report, "log": log}


@router.get("/channels/search")
def api_channels_search(
    q: str = "",
    min_subs: int = 0,
    min_views: int = 0,
    category: str = "",
    language: str = "",
    sort: str = "subs",
    limit: int = 10,
):
    """
    Busca canales en YouTube por `q` y enriquece con estadísticas.
    Nota: monetización/RPM se estima en UI (editable en directorio).
    """
    from videomaker.youtube.youtube_analyze import enrich_channels_stats, search_channels

    base = search_channels(q, max_results=min(int(limit), 25))
    stats = enrich_channels_stats([b["channel_id"] for b in base])
    lang_f = (language or "").strip().lower()
    cat_f = (category or "").strip()
    internal: dict[str, dict] = {}
    if cat_f or lang_f:
        try:
            from videomaker.youtube.channel_store import get_channels_internal_fields

            internal = get_channels_internal_fields([b["channel_id"] for b in base])
        except Exception:
            internal = {}
    out = []
    for b in base:
        cid = b["channel_id"]
        s = stats.get(cid) or {}
        subs = int(s.get("subscribers") or 0)
        views = int(s.get("total_views") or 0)
        if int(min_subs) and subs < int(min_subs):
            continue
        if int(min_views) and views < int(min_views):
            continue
        if cat_f or lang_f:
            meta = internal.get(cid) or {}
            if cat_f and (meta.get("internal_category") or "") != cat_f:
                continue
            if lang_f and (meta.get("language") or "").lower() != lang_f:
                continue
        out.append({**b, **s, "subscribers": subs, "total_views": views})

    def _views_per_video(x: dict) -> float:
        views = float(int(x.get("total_views") or 0))
        vc = float(int(x.get("video_count") or 0))
        return views / max(1.0, vc)

    def _views_per_sub(x: dict) -> float:
        views = float(int(x.get("total_views") or 0))
        subs = float(int(x.get("subscribers") or 0))
        return views / max(1.0, subs)

    key = (sort or "subs").lower().strip()
    if key == "views":
        out.sort(key=lambda x: int(x.get("total_views") or 0), reverse=True)
    elif key in ("videos", "video_count"):
        out.sort(key=lambda x: int(x.get("video_count") or 0), reverse=True)
    elif key in ("views_per_video", "views_video"):
        out.sort(key=_views_per_video, reverse=True)
    elif key in ("views_per_sub", "views_sub"):
        out.sort(key=_views_per_sub, reverse=True)
    else:
        out.sort(key=lambda x: int(x.get("subscribers") or 0), reverse=True)
    return {"channels": out[: max(1, min(int(limit), 50))]}


class ChannelSaveBody(BaseModel):
    channel_id: str = Field(..., min_length=10)
    handle: str = ""
    title: str = ""
    avatar_url: str = ""
    description: str = ""


class ChannelScanBody(WorkModel):
    channel_ids: list[str] = Field(default_factory=list)
    max_videos: int = 50


@router.post("/channels/save")
def api_channels_save(body: ChannelSaveBody):
    upsert_channel(
        channel_id=body.channel_id,
        handle=(body.handle or None),
        title=body.title or "",
        avatar_url=(body.avatar_url or None),
        description=(body.description or None),
    )
    try:
        mark_channel_pearl(body.channel_id, is_pearl=True)
    except Exception:
        pass
    return {"ok": True}


@router.post("/channels/scan", status_code=202)
def api_channels_scan(background: BackgroundTasks, body: ChannelScanBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    ids = [c.strip() for c in (body.channel_ids or []) if c and c.strip()]
    ids = [c for c in ids if c.startswith("UC")]
    ids = ids[:25]
    for cid in ids:
        background.add_task(jobs.run_channel_scan_lite, body.work, channel_id=cid, max_videos=int(body.max_videos))
    return {"started": True, "count": len(ids)}


@router.get("/channels")
def api_channels_list(
    q: str = "",
    category: str = "",
    limit: int = 50,
    sort: str = "opportunity",
    # filters
    min_subs: int | None = None,
    min_views: int | None = None,
    min_uploads_month: float | None = None,
    min_views_per_sub: float | None = None,
    min_hit_rate: float | None = None,
    # config
    window_videos: int = 50,
    hit_views_threshold: int = 50_000,
    pearls_only: bool = True,
):
    return {
        "channels": list_channels_opportunities(
            q=q,
            category=category,
            limit=limit,
            sort=sort,
            min_subs=min_subs,
            min_views=min_views,
            min_uploads_month=min_uploads_month,
            min_views_per_sub=min_views_per_sub,
            min_hit_rate=min_hit_rate,
            window_videos=window_videos,
            hit_views_threshold=hit_views_threshold,
            pearls_only=bool(pearls_only),
        )
    }


@router.post("/channels/{channel_id}/sync", status_code=202)
def api_channel_sync(background: BackgroundTasks, channel_id: str, work: str = "output/ui_session", max_videos: int = 50, lang: str = "es"):
    try:
        safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    # Preferimos Celery si REDIS_URL está configurado; fallback a BackgroundTasks.
    import os

    if os.environ.get("REDIS_URL", "").strip():
        try:
            from videomaker.workers.tasks import channel_sync_task

            res = channel_sync_task.delay(work, channel_id, int(max_videos), lang)
            return {"started": True, "task_id": res.id, "mode": "celery"}
        except Exception:
            pass
    background.add_task(jobs.run_channel_sync, work, channel_id=channel_id, max_videos=int(max_videos), lang=lang)
    return {"started": True, "mode": "background"}


@router.post("/channels/{channel_id}/backfill", status_code=202)
def api_channel_backfill(background: BackgroundTasks, channel_id: str, body: ChannelBackfillBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not get_channel(channel_id):
        raise HTTPException(status_code=404, detail="Canal no encontrado en el directorio.")
    background.add_task(jobs.run_channel_videos_backfill, body.work, channel_id=channel_id, limit=int(body.limit))
    return {"started": True, "mode": "background"}


@router.get("/tasks/{task_id}")
def api_task_status(task_id: str):
    from celery.result import AsyncResult
    from videomaker.workers.celery_app import celery_app

    r = AsyncResult(task_id, app=celery_app)
    out = {"id": task_id, "state": r.state}
    if r.successful():
        out["result"] = r.result
    if r.failed():
        out["error"] = str(r.result)
    return out


@router.get("/channels/{channel_id}")
def api_channel_get(channel_id: str, videos_limit: int = 50):
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado en el directorio.")
    vids = list_channel_videos_detail(channel_id, limit=int(videos_limit))
    return {"channel": ch, "videos": vids}


@router.get("/channels/{channel_id}/videos.json")
def api_channel_videos_json(channel_id: str, videos_limit: int = 200):
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado en el directorio.")
    vids = list_channel_videos_detail(channel_id, limit=int(videos_limit))
    import json
    from fastapi.responses import Response

    payload = {"channel": ch, "videos": vids}
    return Response(content=json.dumps(payload, ensure_ascii=False, indent=2, default=str), media_type="application/json")


class ChannelUpdateBody(BaseModel):
    internal_category: str | None = None
    notes: str | None = None
    language: str | None = None
    rpm_estimate: float | None = None
    monetization_estimate: float | None = None


@router.put("/channels/{channel_id}")
def api_channel_put(channel_id: str, body: ChannelUpdateBody):
    if not get_channel(channel_id):
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
    set_channel_internal_fields(
        channel_id,
        internal_category=body.internal_category,
        notes=body.notes,
        language=body.language,
        rpm_estimate=body.rpm_estimate,
        monetization_estimate=body.monetization_estimate,
    )
    return {"ok": True}


@router.delete("/channels/{channel_id}")
def api_channel_delete(channel_id: str):
    if not get_channel(channel_id):
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
    # Borra DB (cascade videos/insights/assets)
    delete_channel(channel_id)
    # Borra assets locales
    from videomaker.youtube.channel_assets import delete_channel_assets

    delete_channel_assets(channel_id)
    return {"ok": True}


@router.get("/channels/{channel_id}/context")
def api_channel_context(channel_id: str, videos_limit: int = 10):
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado.")
    vids = list_channel_videos(channel_id, limit=int(videos_limit))
    lines = []
    lines.append(f"CANAL: {ch.get('title','')} ({channel_id})")
    if ch.get("handle"):
        lines.append(f"HANDLE: {ch.get('handle')}")
    if ch.get("internal_category"):
        lines.append(f"CATEGORIA_INTERNA: {ch.get('internal_category')}")
    if ch.get("notes"):
        lines.append(f"NOTAS: {ch.get('notes')}")
    lines.append("")
    lines.append("VIDEOS_RECIENTES:")
    for v in vids[: int(videos_limit)]:
        hook = v.get("hook") or ""
        lines.append(f"- {v.get('title','')} ({v.get('video_id')})")
        if hook:
            lines.append(f"  Hook: {hook}")
    return {"text": "\n".join(lines).strip() + "\n"}


@router.get("/channels/{channel_id}/thumbnails.zip")
def api_channel_thumbnails_zip(channel_id: str, work: str = "output/ui_session"):
    """
    MVP: genera un ZIP desde el último JSON de sync/analyze guardado en work_dir.
    """
    from videomaker.youtube.channel_assets import build_thumbnails_zip

    work_dir = safe_work_dir(work)
    p = work_dir / f"channel_{channel_id}_sync.json"
    if not p.is_file():
        # fallback: último analyze_channel.json
        p = work_dir / "analyze_channel.json"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="No hay datos de canal para generar ZIP.")
    data = __import__("json").loads(p.read_text(encoding="utf-8"))
    videos = data.get("videos") or []
    # Por ahora no traemos thumbnail_url: se puede enriquecer en el sync siguiente.
    zip_path = build_thumbnails_zip(channel_id, videos)
    return FileResponse(str(zip_path), filename="thumbnails.zip")


@router.get("/channels/{channel_id}/scripts.zip")
def api_channel_scripts_zip(channel_id: str, work: str = "output/ui_session"):
    from videomaker.youtube.channel_assets import build_transcripts_zip

    work_dir = safe_work_dir(work)
    p = work_dir / f"channel_{channel_id}_sync.json"
    if not p.is_file():
        p = work_dir / "analyze_channel.json"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="No hay datos de canal para generar ZIP.")
    data = __import__("json").loads(p.read_text(encoding="utf-8"))
    videos = data.get("videos") or []
    zip_path = build_transcripts_zip(channel_id, videos)
    return FileResponse(str(zip_path), filename="scripts.zip")


@router.post("/channels/{channel_id}/transcripts.json")
def api_channel_transcripts_json(channel_id: str, body: ChannelTranscriptsJsonBody):
    """
    Devuelve transcripciones en JSON para vídeos seleccionados (o últimos N).
    Transcripciones: YouTube Data API v3 captions (OAuth) por defecto; ver VIDEOMAKER_TRANSCRIPT_PROVIDER.
    """
    from fastapi.responses import Response

    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from videomaker.youtube.channel_transcripts import fetch_channel_transcripts_payload

    try:
        payload = fetch_channel_transcripts_payload(
            channel_id,
            video_ids=body.video_ids,
            limit=body.limit,
            lang=body.lang or "es",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        media_type="application/json",
    )


@router.post("/channels/{channel_id}/transcripts/session")
def api_channel_transcripts_session(channel_id: str, body: ChannelTranscriptsJsonBody):
    """Descarga transcripciones, normaliza y guarda transcripts_session (sin LLM)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from videomaker.youtube.channel_transcripts import fetch_channel_transcripts_payload
    from videomaker.web.transcripts_session import (
        build_session_from_api_payload,
        session_public_view,
        write_transcripts_session,
    )

    try:
        raw = fetch_channel_transcripts_payload(
            channel_id,
            video_ids=body.video_ids,
            limit=body.limit,
            lang=body.lang or "es",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    session_data = build_session_from_api_payload(raw, source_channel_id=channel_id)
    write_transcripts_session(work_dir, session_data)
    view = session_public_view(session_data)
    view["ok"] = True
    if raw.get("youtube_ip_blocked_hint"):
        view["youtube_ip_blocked_hint"] = raw["youtube_ip_blocked_hint"]
    return view


@router.post("/session/transcripts/import")
def api_session_transcripts_import(body: TranscriptsSessionImportBody):
    """Importa transcripts desde JSON (p. ej. descargado antes del bloqueo de IP) sin llamar a YouTube."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from videomaker.web.transcripts_session import (
        build_session_from_api_payload,
        session_public_view,
        write_transcripts_session,
    )

    payload = body.payload if isinstance(body.payload, dict) else {}
    videos = payload.get("videos")
    if not isinstance(videos, list) or not videos:
        raise HTTPException(
            status_code=400,
            detail="El JSON debe incluir una lista «videos» con al menos un elemento.",
        )
    channel_id = (body.source_channel_id or payload.get("channel_id") or "").strip()
    if isinstance(payload.get("channel"), dict):
        ch = payload["channel"]
        if not channel_id and ch.get("channel_id"):
            channel_id = str(ch.get("channel_id") or "").strip()

    session_data = build_session_from_api_payload(payload, source_channel_id=channel_id)
    write_transcripts_session(work_dir, session_data)
    view = session_public_view(session_data)
    view["ok"] = True
    view["imported"] = True
    return view


@router.get("/youtube/transcripts/config")
def api_youtube_transcripts_config():
    """Estado del proveedor de transcripciones (Data API vs scrape)."""
    import os

    from videomaker.youtube.transcript_fetch import (
        data_api_ready,
        missing_oauth_message,
        provider_label,
        transcript_provider,
        worker_url_configured,
    )

    mode = transcript_provider()
    worker_ready = worker_url_configured()
    setup_hint = None
    if mode == "data_api" and not data_api_ready():
        setup_hint = missing_oauth_message()
    elif mode == "worker" and not worker_ready:
        setup_hint = (
            "Modo worker: define YOUTUBE_TRANSCRIPT_WORKER_URL (despliega workers/youtube-transcript-proxy)."
        )
    elif mode == "auto" and not data_api_ready() and not worker_ready:
        setup_hint = missing_oauth_message()

    return {
        "provider": mode,
        "provider_label": provider_label(),
        "data_api_oauth_ready": data_api_ready(),
        "worker_url_set": worker_ready,
        "youtube_api_key_set": bool(os.environ.get("YOUTUBE_API_KEY", "").strip()),
        "setup_hint": setup_hint,
    }


@router.get("/session/transcripts")
def api_session_transcripts_get(
    work: str = Query("output/ui_session"),
    include_combined_text: bool = Query(False),
):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.web.transcripts_session import read_transcripts_session, session_public_view

    data = read_transcripts_session(work_dir)
    return session_public_view(data, include_combined_text=include_combined_text)


@router.post("/session/transcripts/analyze")
def api_session_transcripts_analyze(body: TranscriptsSessionAnalyzeBody):
    """Analiza transcripts_session: Topic Generator + Prompt template en paralelo."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from videomaker.llm.prompt_from_transcript import generate_prompt_template_from_transcript
    from videomaker.llm.topic_generator import generate_topic_ideas
    from videomaker.pipeline.runner import write_topic_generator_artifact
    from videomaker.web.transcripts_session import (
        get_combined_text,
        read_transcripts_session,
        session_public_view,
        update_analyze_status,
    )

    existing = read_transcripts_session(work_dir)
    if not existing:
        raise HTTPException(
            status_code=400,
            detail="No hay transcripts en sesión. Carga transcripts desde Analyse primero.",
        )
    combined = get_combined_text(work_dir)
    if len(combined) < 50:
        raise HTTPException(
            status_code=400,
            detail="No hay transcripts válidos en sesión (mín. ~50 caracteres combinados).",
        )

    update_analyze_status(work_dir, status="analyzing", error=None)

    topic_payload: dict[str, Any] | None = None
    prompt_result: dict[str, Any] | None = None
    errors: list[str] = []

    out_lang = (body.output_language or "en").strip().lower()

    try:
        if body.provider == "mock":
            import time
            time.sleep(2)  # Simular trabajo
            topic_payload = {
                "topics": [
                    {"title": "Mock Topic 1 (Test)", "keywords": "mock, test, debug", "angle": "Este es un tema de prueba para ver si la UI funciona."},
                    {"title": "Mock Topic 2 (Fake)", "keywords": "fake, data, example", "angle": "Otro ángulo de ejemplo para rellenar la lista de temas."},
                    {"title": "Mock Topic 3", "keywords": "test, ui, flow", "angle": "Un tercer tema para asegurar que el scroll y la selección funcionan bien."},
                ],
                "selected_index": None,
            }
            prompt_result = {
                "name": "Mock Template (from Transcripts)",
                "hook_style": "Pregunta provocadora",
                "visual_style": "Animación en pizarra",
                "tone": "Educativo y cercano",
                "system_instructions": "Estas son instrucciones de sistema MOCK. El objetivo es actuar como un guionista experto en el nicho analizado, manteniendo un tono consistente.",
                "user_instructions": "Estas son instrucciones de usuario MOCK. Se centran en reglas específicas del contenido, como CTAs, temas a evitar o estructura de los pilares.",
                "params_json": { "pacing": "mixed", "data_density": "medium", "structure_preset": "default_five_blocks", "narrative_preset": "entretenimiento", "chunking": "full_pass" },
            }
        else:
            def _topics():
                return generate_topic_ideas(
                    transcript_text=combined, niche_trends=body.niche_trends, topic_count=body.topic_count,
                    output_language=out_lang, provider=body.provider, model=body.model,
                )

            def _prompt():
                return generate_prompt_template_from_transcript(
                    transcript_text=combined, output_language=out_lang, provider=body.provider, model=body.model,
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_topics = pool.submit(_topics)
                fut_prompt = pool.submit(_prompt)
                for fut in as_completed([fut_topics, fut_prompt]):
                    try:
                        res = fut.result()
                        if fut is fut_topics: topic_payload = res
                        else: prompt_result = res
                    except Exception as e: errors.append(str(e))
            if errors: raise RuntimeError(" | ".join(errors))

        if topic_payload:
            from videomaker.pipeline.runner import read_topic_generator_artifact, write_topic_generator_artifact
            from videomaker.pipeline.topic_generator_selection import apply_topic_selection, session_topic_hints

            previous = read_topic_generator_artifact(work_dir)
            kw, ctx = session_topic_hints(work_dir)
            topic_payload = apply_topic_selection(
                topic_payload,
                previous=previous,
                session_keywords=kw,
                session_context=ctx,
            )
            write_topic_generator_artifact(work_dir, topic_payload)
        from videomaker.llm.prompt_analysis_storage import slim_prompt_analysis_payload

        slim_prompt = (
            slim_prompt_analysis_payload(prompt_result)
            if isinstance(prompt_result, dict)
            else None
        )
        data = update_analyze_status(
            work_dir,
            status="completed",
            prompt_analysis=slim_prompt,
            topic_analysis=topic_payload,
            analyze_output_language=out_lang,
        )
        view = session_public_view(data)
        view["ok"] = True
        view["topics_count"] = len((topic_payload or {}).get("topics") or [])
        view["analyze_output_language"] = out_lang
        return view
    except HTTPException:
        raise
    except Exception as e:
        try:
            update_analyze_status(work_dir, status="error", error=str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/pipeline/state")
def api_pipeline_state(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_pipeline_state

    return read_pipeline_state(work_dir)


class PipelineMetadataPutBody(WorkModel):
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelinePackagingPutBody(WorkModel):
    packaging: dict[str, Any] = Field(default_factory=dict)


class PipelineImagePromptsPutBody(WorkModel):
    bundle: dict[str, Any] = Field(default_factory=dict)


class ImagePromptWriterSettingsPutBody(WorkModel):
    target_generator: str = Field(
        default="gemini",
        description="gemini | midjourney | flux | dall_e | sd | custom",
    )
    append_midjourney_suffix: bool = Field(default=True)
    export_negative_separate: bool = Field(default=True)
    notes: str = Field(default="", description="Notas internas para el equipo o futuro LLM")
    visual_mode: str = Field(
        default="animation",
        description="static | animation | combined",
    )
    use_avatar: bool = Field(default=False)
    hook_essay_counterpoint: bool = Field(
        default=True,
        description="Gancho: prompts por contrapunto emocional (no ilustración literal del guion)",
    )
    visual_style_preset_id: str = Field(
        default="",
        description="ID del preset de estilo visual (vacío = Alex por defecto si use_avatar)",
    )


class MetadataSettingsPutBody(WorkModel):
    target_platform: str = Field(default="youtube", description="youtube | tiktok | reels")
    target_keywords: str = ""
    system_prompt: str = Field(default="", description="Vacío = usar prompt por defecto del servidor al generar")
    target_keywords_source: str | None = Field(
        default=None,
        description='manual = usar target_keywords en el LLM; omitir o vacío = inferir del guion',
    )
    system_prompt_source: str | None = Field(
        default=None,
        description="manual = usar system_prompt; omitir o vacío = instrucciones compactas por defecto",
    )


class HookRouterSettingsPutBody(WorkModel):
    mode: str = Field(default="llm", description="llm = IA retención + micro-beats; template = reglas")
    finance_style: str = Field(default="auto", description="auto | deep_documentary | …")
    platform: str = Field(
        default="auto",
        description="auto | tiktok | youtube_shorts | reels | youtube",
    )
    visual_energy: str = Field(default="auto", description="auto | high | medium | low")
    system_prompt: str = Field(default="", description="Solo si system_prompt_source=manual")
    system_prompt_source: str | None = Field(
        default=None,
        description="internal = prompt interno (preview); manual = system_prompt del usuario",
    )
    talking_head_after_sec: str | int | None = Field(
        default="auto",
        description="auto | segundos (20–30) sin narrator visible en el hook",
    )


@router.get("/pipeline/hook-router-settings")
def api_hook_router_settings_get(
    work: str = "output/ui_session",
    lang: str = "es",
    preview_platform: str | None = None,
    preview_visual_energy: str | None = None,
):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.core.metadata_settings_store import read_metadata_settings
    from videomaker.llm.hook_scene_router import _metadata_target_platform, narrative_preset_from_work
    from videomaker.llm.hook_retention_router import (
        default_hook_router_system_prompt,
        normalize_platform,
        normalize_visual_energy,
        resolve_talking_head_after_sec,
    )
    from videomaker.llm.output_language import normalize_language_code

    st = read_hook_router_settings(work_dir)
    np = narrative_preset_from_work(work_dir)
    mode = str(st.get("mode") or "llm").strip().lower()
    fs = str(st.get("finance_style") or "auto").strip().lower()
    plat = str(st.get("platform") or "auto").strip().lower()
    energy = str(st.get("visual_energy") or "auto").strip().lower()
    sp = str(st.get("system_prompt") or "")
    sp_src = str(st.get("system_prompt_source") or "").strip().lower()
    if sp_src not in ("internal", "manual"):
        sp_src = "manual" if sp.strip() else "internal"
    meta_tp = _metadata_target_platform(work_dir)
    prev_plat = (preview_platform or "").strip().lower() or None
    prev_energy = (preview_visual_energy or "").strip().lower() or None
    plat_for_preview = prev_plat if prev_plat and prev_plat != "auto" else plat
    energy_for_preview = prev_energy if prev_energy and prev_energy != "auto" else energy
    resolved_platform = normalize_platform(
        None if plat_for_preview == "auto" else plat_for_preview,
        meta_tp,
    )
    resolved_energy = normalize_visual_energy(
        None if energy_for_preview == "auto" else energy_for_preview,
        resolved_platform,
    )
    eff_lang = normalize_language_code(lang)
    th_after = resolve_talking_head_after_sec(resolved_platform, st.get("talking_head_after_sec"))
    meta_st = read_metadata_settings(work_dir)
    recommended_defaults = {
        "mode": "llm",
        "finance_style": "auto",
        "platform": "auto",
        "visual_energy": "auto",
        "hint": (
            "Router de retención: IA segmenta el gancho en micro-beats (1–2 s) con emoción, cámara y densidad visual. "
            "Plataforma «auto» hereda Metadata si existe."
        ),
    }
    return {
        "narrative_preset": np,
        "mode": mode,
        "finance_style": fs,
        "platform": plat,
        "visual_energy": energy,
        "resolved_platform": resolved_platform,
        "resolved_visual_energy": resolved_energy,
        "metadata_target_platform": meta_tp or str(meta_st.get("target_platform") or ""),
        "system_prompt": sp,
        "system_prompt_source": sp_src,
        "talking_head_after_sec": st.get("talking_head_after_sec", "auto"),
        "resolved_talking_head_after_sec": th_after,
        "default_system_prompt": default_hook_router_system_prompt(
            output_lang=eff_lang,
            platform=resolved_platform,
            visual_energy=resolved_energy,
            talking_head_after_sec=th_after,
        ),
        "recommended_defaults": recommended_defaults,
    }


@router.put("/pipeline/hook-router-settings")
def api_hook_router_settings_put(body: HookRouterSettingsPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    saved = write_hook_router_settings(
        work_dir,
        mode=body.mode,
        finance_style=body.finance_style,
        system_prompt=body.system_prompt,
        platform=body.platform,
        visual_energy=body.visual_energy,
        system_prompt_source=body.system_prompt_source,
        talking_head_after_sec=body.talking_head_after_sec,
    )
    return {"ok": True, "settings": saved}


@router.get("/pipeline/hook-router-artifact")
def api_hook_router_artifact(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "hook_scene_router.json"
    if not p.is_file():
        return {"exists": False, "artifact": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"exists": False, "artifact": None}
        return {"exists": True, "artifact": raw}
    except Exception:
        return {"exists": False, "artifact": None}


class HookRouterArtifactPutBody(BaseModel):
    work: str = "output/ui_session"
    artifact: dict


@router.put("/pipeline/hook-router-artifact")
def api_hook_router_artifact_put(body: HookRouterArtifactPutBody):
    """Persistir `pipeline/hook_scene_router.json` desde la UI y marcar el paso como listo."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import save_manual_hook_router_bundle
    try:
        save_manual_hook_router_bundle(work_dir, body.artifact)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.get("/pipeline/body-router-artifact")
def api_body_router_artifact_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "body_scene_router.json"
    if not p.is_file():
        return {"exists": False, "artifact": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"exists": False, "artifact": None}
        return {"exists": True, "artifact": raw}
    except Exception:
        return {"exists": False, "artifact": None}


class BodyRouterArtifactPutBody(BaseModel):
    work: str = "output/ui_session"
    artifact: dict


@router.get("/pipeline/body-router-diagnostics")
def api_body_router_diagnostics(work: str = "output/ui_session"):
    """Resumen insert/avatar, fragmentos, duplicados y densidad vs audio."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "body_scene_router.json"
    script_p = work_dir / "pipeline" / "script.txt"
    body_text = ""
    if script_p.is_file():
        try:
            body_text = script_p.read_text(encoding="utf-8")
        except OSError:
            body_text = ""
    from videomaker.llm.body_scene_router import _extract_body_text
    from videomaker.llm.body_router_diagnostics import analyze_body_router_bundle

    if not p.is_file():
        return {
            "exists": False,
            "diagnostics": analyze_body_router_bundle(
                {}, work_dir=work_dir, body_text=_extract_body_text(body_text)
            ),
        }
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        bundle = raw if isinstance(raw, dict) else {}
    except Exception:
        bundle = {}
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else None
    if not diag:
        diag = analyze_body_router_bundle(
            bundle,
            work_dir=work_dir,
            body_text=_extract_body_text(body_text),
        )
    return {
        "exists": True,
        "diagnostics": diag,
        "artifact_density_target": bundle.get("density_target"),
        "visual_density_plan": bundle.get("visual_density_plan"),
    }


@router.put("/pipeline/body-router-artifact")
def api_body_router_artifact_put(body: BodyRouterArtifactPutBody):
    """Persistir `pipeline/body_scene_router.json` desde la UI y marcar el paso como listo."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import save_manual_body_router_bundle
    try:
        save_manual_body_router_bundle(work_dir, body.artifact)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.get("/pipeline/subtitles-plan")
def api_pipeline_subtitles_plan(work: str = "output/ui_session"):
    """Read-only: `pipeline/subtitles_plan.json` if present."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "subtitles_plan.json"
    if not p.is_file():
        return {"exists": False, "artifact": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return {"exists": True, "artifact": raw if isinstance(raw, dict) else None}
    except Exception:
        return {"exists": False, "artifact": None}


@router.get("/pipeline/music-plan")
def api_pipeline_music_plan(work: str = "output/ui_session"):
    """Read-only: `pipeline/music_plan.json` if present."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "music_plan.json"
    if not p.is_file():
        return {"exists": False, "artifact": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return {"exists": True, "artifact": raw if isinstance(raw, dict) else None}
    except Exception:
        return {"exists": False, "artifact": None}


@router.get("/pipeline/voiceover-plan")
def api_pipeline_voiceover_plan(work: str = "output/ui_session"):
    """Read-only: `pipeline/voiceover_plan.json` if present."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "voiceover_plan.json"
    if not p.is_file():
        return {"exists": False, "artifact": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return {"exists": True, "artifact": raw if isinstance(raw, dict) else None}
    except Exception:
        return {"exists": False, "artifact": None}


@router.post("/pipeline/hook-router/push-to-image-prompts")
def api_hook_router_push_to_image_prompts(body: WorkModel):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.core.image_prompt_writer_settings_store import read_image_prompt_writer_settings

    st = read_image_prompt_writer_settings(work_dir)
    ip_path = work_dir / "pipeline" / "image_prompts.json"
    if st.get("use_avatar") and ip_path.is_file():
        from videomaker.llm.image_prompt_hybrid import merge_avatar_hybrid_with_hook

        try:
            info = merge_avatar_hybrid_with_hook(work_dir)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True, **info}

    from videomaker.llm.hook_scene_router import merge_hook_router_into_image_prompts

    try:
        info = merge_hook_router_into_image_prompts(work_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, **info}


@router.get("/pipeline/metadata-settings")
def api_pipeline_metadata_settings_get(
    work: str = "output/ui_session",
    lang: str = "es",
    preview_platform: str | None = None,
):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.core.metadata_settings_store import (
        effective_system_prompt_override,
        effective_target_keywords,
    )
    from videomaker.llm.metadata_gen import default_system_prompt

    st = read_metadata_settings(work_dir)
    tp = str(st.get("target_platform") or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    pv = (preview_platform or "").strip().lower()
    default_for = pv if pv in ("youtube", "tiktok", "reels") else tp
    tk_eff = effective_target_keywords(st)
    kw_src = str(st.get("target_keywords_source") or "").strip().lower() or None
    sp_eff = effective_system_prompt_override(st)
    sp_src = str(st.get("system_prompt_source") or "").strip().lower() or None
    return {
        "target_platform": tp,
        "target_keywords": str(st.get("target_keywords") or ""),
        "target_keywords_effective": tk_eff,
        "target_keywords_source": kw_src,
        "system_prompt": str(st.get("system_prompt") or ""),
        "system_prompt_effective": sp_eff,
        "system_prompt_source": sp_src,
        "default_system_prompt": default_system_prompt(
            lang, default_for, target_keywords=tk_eff
        ),
    }


@router.put("/pipeline/metadata-settings")
def api_pipeline_metadata_settings_put(body: MetadataSettingsPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    tp = (body.target_platform or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        raise HTTPException(status_code=400, detail="target_platform debe ser youtube, tiktok o reels")
    src_raw = (body.target_keywords_source or "").strip().lower()
    kw_src: str | None = None
    if src_raw == "manual":
        kw_src = "manual"
    elif src_raw == "inferred":
        kw_src = "inferred"
    elif (body.target_keywords or "").strip():
        kw_src = "manual"
    sp_raw = (body.system_prompt_source or "").strip().lower()
    sp_src: str | None = None
    if sp_raw == "manual":
        sp_src = "manual"
    elif (body.system_prompt or "").strip():
        sp_src = "manual"
    saved = write_metadata_settings(
        work_dir,
        target_platform=tp,
        target_keywords=body.target_keywords,
        system_prompt=body.system_prompt,
        target_keywords_source=kw_src,
        system_prompt_source=sp_src,
    )
    return {"ok": True, "settings": saved}


class PushThumbnailsBody(WorkModel):
    include_avatar: bool = False
    merge: bool = True


@router.get("/pipeline/metadata/thumbnails-status")
def api_pipeline_metadata_thumbnails_status(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.thumbnail_from_metadata import get_metadata_thumbnails_status

    return {"ok": True, **get_metadata_thumbnails_status(work_dir)}


@router.post("/pipeline/metadata/push-thumbnails-to-images")
def api_pipeline_metadata_push_thumbnails(body: PushThumbnailsBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import push_thumbnail_ideas_to_image_prompts

    try:
        info = push_thumbnail_ideas_to_image_prompts(
            work_dir,
            include_avatar=body.include_avatar,
            merge=body.merge,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, **info}


class PrepareMetadataThumbnailsBody(WorkModel):
    include_avatar: bool = False
    merge: bool = True


@router.post("/pipeline/metadata/prepare-thumbnails")
def api_pipeline_metadata_prepare_thumbnails(body: PrepareMetadataThumbnailsBody):
    """Fusiona prompts de miniatura en image_prompts.json y filas en images_generation.json."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.thumbnail_from_metadata import prepare_metadata_thumbnails

    try:
        info = prepare_metadata_thumbnails(
            work_dir,
            include_avatar=body.include_avatar,
            merge=body.merge,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return info


class GenerateMetadataThumbnailsBody(WorkModel):
    work: str = "output/ui_session"
    regenerate: bool = False


@router.get("/pipeline/metadata/thumbnail-generation-job")
def api_pipeline_metadata_thumbnail_generation_job(work: str = "output/ui_session"):
    """Progreso del job de miniaturas (OpenAI en segundo plano)."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.thumbnail_from_metadata import get_thumbnail_generation_status

    return get_thumbnail_generation_status(work_dir)


@router.post("/pipeline/metadata/generate-thumbnails")
async def api_pipeline_metadata_generate_thumbnails(
    body: GenerateMetadataThumbnailsBody,
    background_tasks: BackgroundTasks,
):
    """Encola generación PNG de miniatura (OpenAI Images API); consulta el job con GET."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.thumbnail_from_metadata import (
        read_thumbnail_generation_job,
        run_thumbnail_generation_job,
    )

    job = read_thumbnail_generation_job(work_dir)
    if str(job.get("state") or "") == "running":
        return {
            "ok": True,
            "queued": False,
            "already_running": True,
            "job": job,
            "detail": job.get("detail") or "Generación de miniaturas en curso…",
        }

    background_tasks.add_task(
        run_thumbnail_generation_job,
        work_dir,
        work_slug=body.work,
        regenerate=body.regenerate,
    )
    return {
        "ok": True,
        "queued": True,
        "detail": "Generación en segundo plano. OpenAI suele tardar 1–3 min por miniatura.",
    }


@router.get("/pipeline/metadata-input-preview")
def api_pipeline_metadata_input_preview(
    work: str = "output/ui_session",
    lang: str = "es",
    keywords: str = "",
    context: str = "",
    minutes: float = 10.0,
    provider: str = "",
    model: str = "",
):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.models import PipelineInputs
    from videomaker.pipeline.runner import build_metadata_input_preview

    from videomaker.llm.output_language import resolve_pipeline_lang
    from videomaker.pipeline.runner import _pipeline_inputs_with_resolved_lang

    inputs = _pipeline_inputs_with_resolved_lang(
        work_dir,
        PipelineInputs(
            keywords=keywords or "",
            context=context or "",
            lang=resolve_pipeline_lang(work_dir, request_lang=lang or None),
            minutes=float(minutes) if minutes and minutes > 0 else 10.0,
            provider=provider or "",
            model=model or "",
        ),
    )
    return build_metadata_input_preview(work_dir, inputs)


@router.get("/pipeline/packaging")
def api_pipeline_packaging_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "packaging.json"
    if not p.is_file():
        return {"exists": False, "packaging": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"exists": False, "packaging": None}
        return {"exists": True, "packaging": raw}
    except Exception:
        return {"exists": False, "packaging": None}


@router.put("/pipeline/packaging")
def api_pipeline_packaging_put(body: PipelinePackagingPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import save_manual_packaging_bundle

    try:
        save_manual_packaging_bundle(work_dir, body.packaging)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.get("/pipeline/metadata")
def api_pipeline_metadata_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "metadata.json"
    if not p.is_file():
        return {"exists": False, "metadata": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"exists": False, "metadata": None}
        return {"exists": True, "metadata": raw}
    except Exception:
        return {"exists": False, "metadata": None}


@router.put("/pipeline/metadata")
def api_pipeline_metadata_put(body: PipelineMetadataPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import save_manual_metadata_bundle

    try:
        save_manual_metadata_bundle(work_dir, body.metadata)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.get("/pipeline/image-prompts")
def api_pipeline_image_prompts_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "image_prompts.json"
    if not p.is_file():
        return {"exists": False, "bundle": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"exists": False, "bundle": None}
        return {"exists": True, "bundle": raw}
    except Exception:
        return {"exists": False, "bundle": None}


@router.put("/pipeline/image-prompts")
def api_pipeline_image_prompts_put(body: PipelineImagePromptsPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import save_manual_image_prompts_bundle

    try:
        save_manual_image_prompts_bundle(work_dir, body.bundle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.post("/pipeline/image-prompts/reconcile-timing")
def api_reconcile_image_prompt_timing(body: WorkModel):
    """Alinea duraciones de image_prompts con audio real (Scene Editor / audio_timeline)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.llm.image_prompt_timing_reconcile import (
        reconcile_image_prompts_with_audio,
        reconcile_manifest_from_prompts,
    )

    try:
        info = reconcile_image_prompts_with_audio(work_dir)
        manifest = reconcile_manifest_from_prompts(work_dir)
        return {"ok": True, **info, "images_generation": manifest}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/pipeline/image-prompts/push-to-images-generation")
def api_push_image_prompts_to_images_generation(body: WorkModel):
    """Reemplaza images_generation.json con placeholders desde image_prompts.json."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.image_prompts_to_images import push_image_prompts_to_images_generation

    try:
        info = push_image_prompts_to_images_generation(work_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, **info}


@router.get("/pipeline/image-prompt-writer-settings")
def api_image_prompt_writer_settings_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.core.visual_style_presets_store import (
        ALEX_PRESET_ID,
        ensure_alex_preset,
    )

    st = read_image_prompt_writer_settings(work_dir)
    ensure_alex_preset(work_dir)
    preset_id = str(st.get("visual_style_preset_id") or "").strip() or ALEX_PRESET_ID

    return {
        "target_generator": str(st.get("target_generator") or "midjourney"),
        "append_midjourney_suffix": bool(st.get("append_midjourney_suffix", True)),
        "export_negative_separate": bool(st.get("export_negative_separate", True)),
        "notes": str(st.get("notes") or ""),
        "visual_mode": str(st.get("visual_mode") or "animation"),
        "use_avatar": bool(st.get("use_avatar", False)),
        "hook_essay_counterpoint": bool(st.get("hook_essay_counterpoint", True)),
        "visual_style_preset_id": preset_id,
    }


@router.put("/pipeline/image-prompt-writer-settings")
def api_image_prompt_writer_settings_put(body: ImagePromptWriterSettingsPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.core.visual_style_presets_store import (
        ALEX_PRESET_ID,
        apply_preset_to_work,
        ensure_alex_preset,
        get_preset,
    )

    ensure_alex_preset(work_dir)
    preset_id = (body.visual_style_preset_id or "").strip() or ALEX_PRESET_ID
    if not get_preset(preset_id):
        preset_id = ALEX_PRESET_ID
    if body.use_avatar:
        apply_preset_to_work(work_dir, preset_id)
    saved = write_image_prompt_writer_settings(
        work_dir,
        target_generator=body.target_generator,
        append_midjourney_suffix=body.append_midjourney_suffix,
        export_negative_separate=body.export_negative_separate,
        notes=body.notes,
        visual_mode=body.visual_mode,
        use_avatar=body.use_avatar,
        hook_essay_counterpoint=body.hook_essay_counterpoint,
        visual_style_preset_id=preset_id,
    )
    return {"ok": True, "settings": saved}


class AvatarPromptsGenerateBody(WorkModel):
    provider: str = Field(default="", description="Vacío = leer VIDEOMAKER_LLM_PROVIDER")
    model: str = Field(default="", description="Vacío = leer OPENAI_MODEL / OLLAMA_MODEL")


@router.post("/pipeline/avatar-prompts/generate")
def api_avatar_prompts_generate(body: AvatarPromptsGenerateBody, background_tasks: BackgroundTasks):
    """Genera image_prompts.json con prompts del avatar basados en el guion y en los ajustes guardados."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from videomaker.core.visual_style_presets_store import prepare_avatar_mode_for_work
    from videomaker.llm.avatar_prompt_writer import generate_avatar_image_prompts

    st = read_image_prompt_writer_settings(work_dir)
    ctx = prepare_avatar_mode_for_work(work_dir)
    avatar_desc = str(ctx["avatar_description"])
    intro_enabled = bool(ctx.get("intro_enabled"))
    intro_character_name = str(ctx.get("intro_character_name") or "")
    outro_enabled = bool(ctx.get("outro_enabled"))
    outro_character_name = str(ctx.get("outro_character_name") or "")
    secs = float(ctx["secs_per_image"])
    max_imgs = int(ctx["max_images"])
    target_gen = str(st.get("target_generator") or "midjourney")
    provider = body.provider.strip() or None
    model = body.model.strip() or None

    from videomaker.pipeline.runner import _set_step  # type: ignore[attr-defined]

    def _run() -> None:
        try:
            _set_step(work_dir, "image_prompt_writer", state="running", detail="Generando prompts de avatar…")
            result = generate_avatar_image_prompts(
                work_dir,
                avatar_description=avatar_desc,
                scene_visual_settings=ctx.get("scene_visual_settings"),
                intro_enabled=intro_enabled,
                intro_character_name=intro_character_name,
                outro_enabled=outro_enabled,
                outro_character_name=outro_character_name,
                secs_per_image=secs,
                max_images=max_imgs,
                target_generator=target_gen,
                provider=provider,
                model=model,
            )
            from videomaker.llm.image_prompt_hybrid import merge_avatar_hybrid_with_hook

            hybrid = merge_avatar_hybrid_with_hook(work_dir)
            if hybrid.get("hybrid"):
                detail = (
                    f"Avatar híbrido: {hybrid['avatar_count']} avatar + "
                    f"{hybrid['insert_count']} inserts (hook)."
                )
            else:
                detail = f"Avatar prompts generados: {result['prompt_count']} imágenes."
            _set_step(
                work_dir,
                "image_prompt_writer",
                state="done",
                detail=detail,
            )
        except Exception as exc:
            _set_step(
                work_dir,
                "image_prompt_writer",
                state="error",
                detail=f"Error generando prompts de avatar: {exc}",
            )

    background_tasks.add_task(_run)
    return {"ok": True, "queued": True, "avatar_description": avatar_desc, "secs_per_image": secs, "max_images": max_imgs}


class AvatarPromptPreviewBody(WorkModel):
    segment_text: str = Field(
        ...,
        description="Fragmento narrado (p. ej. text_anchor de un macro_beat avatar)",
    )
    provider: str = Field(default="", description="Vacío = VIDEOMAKER_LLM_PROVIDER")
    model: str = Field(default="", description="Vacío = OPENAI_MODEL / OLLAMA_MODEL")


@router.get("/pipeline/image-prompts/validation-candidates")
def api_pipeline_image_prompts_validation_candidates(work: str = "output/ui_session", limit: int = 24):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.ipw_validation_sample import list_validation_candidates

    candidates = list_validation_candidates(work_dir, limit=max(1, min(limit, 48)))
    return {"ok": True, "candidates": candidates, "count": len(candidates)}


class BuildValidationSampleBody(WorkModel):
    candidate_ids: list[str] = Field(
        default_factory=list,
        description="IDs de filas avatar (hook_avatar_N, body_avatar_N)",
    )
    provider: str = Field(default="", description="Vacío = VIDEOMAKER_LLM_PROVIDER")
    model: str = Field(default="", description="Vacío = modelo por defecto")


@router.post("/pipeline/image-prompts/build-validation-sample")
def api_pipeline_image_prompts_build_validation_sample(body: BuildValidationSampleBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.ipw_validation_sample import build_validation_sample

    if not body.candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids vacío.")
    try:
        return build_validation_sample(
            work_dir,
            body.candidate_ids,
            provider=body.provider.strip() or None,
            model=body.model.strip() or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/pipeline/image-prompts/preview-avatar")
def api_pipeline_image_prompts_preview_avatar(body: AvatarPromptPreviewBody):
    """Una llamada LLM de prueba (avatar); misma lógica que IPW Start, sin guardar bundle."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.llm.avatar_prompt_writer import preview_avatar_prompt_segment

    try:
        return preview_avatar_prompt_segment(
            work_dir,
            segment_text=body.segment_text,
            provider=body.provider.strip() or None,
            model=body.model.strip() or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Presets de estilo visual  (/api/visual-style-presets)
# ---------------------------------------------------------------------------


class VisualStylePresetCreateBody(BaseModel):
    name: str
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


class VisualStylePresetUpdateBody(BaseModel):
    name: str | None = None
    base_style_en: str | None = None
    protagonist_en: str | None = None
    protagonist_wardrobe_en: str | None = None
    protagonist_action_rules_en: str | None = None
    protagonist_expressions_en: str | None = None
    avoid_en: str | None = None
    planner_extra_rules_en: str | None = None
    gemini_continuity_prefix_en: str | None = None
    auto_avoid_supplement_en: str | None = None
    aspect_ratio: str | None = None
    output_spec: str | None = None


@router.get("/visual-style-presets")
def api_visual_style_presets_list(work: str = "output/ui_session"):
    from videomaker.core.visual_style_presets_store import list_presets

    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"presets": list_presets(work_dir=work_dir)}


class VisualStylePresetApplyBody(WorkModel):
    preset_id: str = Field(default="", description="Vacío = preset guardado en image_prompt_writer_settings")


@router.post("/visual-style-presets/apply")
def api_visual_style_preset_apply(body: VisualStylePresetApplyBody):
    from videomaker.core.visual_style_presets_store import (
        ALEX_PRESET_ID,
        apply_preset_to_work,
        get_preset,
        resolve_visual_style_preset_id,
    )
    from videomaker.core.image_prompt_writer_settings_store import (
        read_image_prompt_writer_settings,
        write_image_prompt_writer_settings,
    )

    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    pid = (body.preset_id or "").strip()
    if not pid:
        pid = resolve_visual_style_preset_id(work_dir)
    if not get_preset(pid):
        pid = ALEX_PRESET_ID
    settings = apply_preset_to_work(work_dir, pid)
    st = read_image_prompt_writer_settings(work_dir)
    write_image_prompt_writer_settings(
        work_dir,
        target_generator=str(st.get("target_generator") or "midjourney"),
        append_midjourney_suffix=bool(st.get("append_midjourney_suffix", True)),
        export_negative_separate=bool(st.get("export_negative_separate", True)),
        notes=str(st.get("notes") or ""),
        use_avatar=bool(st.get("use_avatar", False)),
        visual_style_preset_id=pid,
        visual_mode=str(st.get("visual_mode") or "animation"),
    )
    return {"ok": True, "preset_id": pid, "settings": settings}


@router.get("/visual-style-presets/{preset_id}")
def api_visual_style_preset_get(preset_id: str):
    from videomaker.core.visual_style_presets_store import get_preset

    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Estilo no encontrado.")
    return preset


@router.post("/visual-style-presets")
def api_visual_style_preset_create(body: VisualStylePresetCreateBody):
    from videomaker.core.visual_style_presets_store import create_preset

    fields = body.model_dump(exclude={"name"})
    return create_preset(body.name, fields)


@router.put("/visual-style-presets/{preset_id}")
def api_visual_style_preset_update(preset_id: str, body: VisualStylePresetUpdateBody):
    from videomaker.core.visual_style_presets_store import update_preset

    payload = body.model_dump(exclude_none=True)
    name = payload.pop("name", None)
    try:
        return update_preset(preset_id, name=name, fields=payload or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/visual-style-presets/{preset_id}")
def api_visual_style_preset_delete(preset_id: str):
    from videomaker.core.visual_style_presets_store import delete_preset

    try:
        delete_preset(preset_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


# ---------------------------------------------------------------------------
# Avatares globales  (/api/avatars)
# ---------------------------------------------------------------------------

class AvatarCreateBody(BaseModel):
    name: str
    description: str
    expressions: list[str] = Field(default_factory=list)
    style_notes: str = ""
    intro_enabled: bool = True
    intro_character_name: str = ""
    outro_enabled: bool = True
    outro_character_name: str = ""


class AvatarUpdateBody(BaseModel):
    name: str | None = None
    description: str | None = None
    expressions: list[str] | None = None
    style_notes: str | None = None
    intro_enabled: bool | None = None
    intro_character_name: str | None = None
    outro_enabled: bool | None = None
    outro_character_name: str | None = None


@router.get("/avatars")
def api_avatars_list():
    """Lista todos los avatares guardados (resumen)."""
    from videomaker.core.avatars_store import list_avatars
    return {"avatars": list_avatars()}


@router.get("/avatars/{avatar_id}")
def api_avatar_get(avatar_id: str):
    """Devuelve un avatar completo por ID."""
    from videomaker.core.avatars_store import get_avatar
    av = get_avatar(avatar_id)
    if av is None:
        raise HTTPException(status_code=404, detail="Avatar no encontrado.")
    return av


@router.post("/avatars")
def api_avatar_create(body: AvatarCreateBody):
    """Crea un nuevo avatar."""
    from videomaker.core.avatars_store import create_avatar
    av = create_avatar(
        body.name,
        body.description,
        expressions=body.expressions or None,
        style_notes=body.style_notes,
        intro_enabled=body.intro_enabled,
        intro_character_name=body.intro_character_name,
        outro_enabled=body.outro_enabled,
        outro_character_name=body.outro_character_name,
    )
    return av


@router.put("/avatars/{avatar_id}")
def api_avatar_update(avatar_id: str, body: AvatarUpdateBody):
    """Actualiza nombre, descripción, expresiones o notas de estilo de un avatar."""
    from videomaker.core.avatars_store import update_avatar
    av = update_avatar(
        avatar_id,
        name=body.name,
        description=body.description,
        expressions=body.expressions,
        style_notes=body.style_notes,
        intro_enabled=body.intro_enabled,
        intro_character_name=body.intro_character_name,
        outro_enabled=body.outro_enabled,
        outro_character_name=body.outro_character_name,
    )
    if av is None:
        raise HTTPException(status_code=404, detail="Avatar no encontrado.")
    return av


@router.delete("/avatars/{avatar_id}")
def api_avatar_delete(avatar_id: str):
    """Elimina un avatar (no se puede borrar el bundled)."""
    from videomaker.core.avatars_store import delete_avatar
    ok = delete_avatar(avatar_id)
    if not ok:
        raise HTTPException(status_code=400, detail="No se puede eliminar este avatar (bundled o no encontrado).")
    return {"ok": True}


@router.get("/pipeline/images-generation")
def api_pipeline_images_generation_get(work: str = "output/ui_session"):
    """Devuelve el manifest images_generation.json."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "images_generation.json"
    if not p.is_file():
        return {"exists": False, "manifest": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"exists": False, "manifest": None}
    from videomaker.pipeline.image_prompts_to_images import sync_manifest_image_status
    from videomaker.pipeline.images_generation_runner import clear_all_image_errors
    from videomaker.pipeline.runner import save_manual_images_generation_bundle
    from videomaker.web.server_boot import images_errors_cleared_for, mark_images_errors_cleared

    from videomaker.pipeline.images_generation_runner import normalize_manifest_filenames

    data = sync_manifest_image_status(work_dir, data)
    normalize_manifest_filenames(data)
    errors_cleared_on_boot = 0
    if not images_errors_cleared_for(work):
        errors_cleared_on_boot = clear_all_image_errors(data)
        if errors_cleared_on_boot:
            save_manual_images_generation_bundle(work_dir, data)
        mark_images_errors_cleared(work)
        # Cola Gemini interrumpida por reinicio del servidor
        job_p = work_dir / "pipeline" / "gemini_web_job.json"
        if job_p.is_file():
            try:
                job = json.loads(job_p.read_text(encoding="utf-8"))
                if isinstance(job, dict) and job.get("state") == "running":
                    from videomaker.engines.gemini_web_batch import _utc_now

                    job["state"] = "cancelled"
                    job["last_log"] = "Cola interrumpida: servidor reiniciado."
                    job["finished_at"] = _utc_now()
                    job_p.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
            except (OSError, json.JSONDecodeError):
                pass
    return {
        "exists": True,
        "manifest": data,
        "errors_cleared_on_boot": errors_cleared_on_boot,
    }


class ImagesGenerationPutBody(BaseModel):
    work: str = "output/ui_session"
    manifest: dict[str, Any]


@router.put("/pipeline/images-generation")
def api_pipeline_images_generation_put(body: ImagesGenerationPutBody):
    """Persiste el manifest y marca el paso images_generation como done."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import save_manual_images_generation_bundle

    try:
        save_manual_images_generation_bundle(work_dir, body.manifest)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


class ImagesGenerationGenerateBody(BaseModel):
    work: str = "output/ui_session"
    image_ids: list[str] | None = Field(
        default=None,
        description="Si se omite, genera todas las seleccionadas pendientes",
    )
    skip_generated: bool = Field(default=True)
    regenerate: bool = Field(default=False)


@router.post("/pipeline/images-generation/generate-selected")
async def api_pipeline_images_generation_generate_selected(body: ImagesGenerationGenerateBody):
    """Genera imágenes Google Imagen para las entradas seleccionadas del manifest."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.images_generation_runner import generate_selected_images

    try:
        result = await generate_selected_images(
            work_dir,
            work_slug=body.work,
            image_ids=body.image_ids,
            skip_generated=body.skip_generated,
            regenerate=body.regenerate,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"ok": True, **result}


class ImagesGenerationDeleteBody(BaseModel):
    work: str = "output/ui_session"
    image_ids: list[str] = Field(default_factory=list)


class RemoveGeminiWatermarkBody(BaseModel):
    work: str = "output/ui_session"
    image_ids: list[str] = Field(default_factory=list)
    backup: bool = Field(default=True)


@router.post("/pipeline/images-generation/remove-gemini-watermark")
def api_pipeline_remove_gemini_watermark(body: RemoveGeminiWatermarkBody):
    """Inpainting en esquina inferior para quitar la estrella de Gemini."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.gemini_watermark import remove_gemini_watermarks_in_work

    try:
        result = remove_gemini_watermarks_in_work(
            work_dir,
            image_ids=body.image_ids or None,
            backup=body.backup,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True, **result}


@router.post("/pipeline/images-generation/delete-selected")
def api_pipeline_images_generation_delete_selected(body: ImagesGenerationDeleteBody):
    """Elimina PNGs seleccionados de pipeline/images/ y marca las tarjetas como pending."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.images_generation_runner import delete_selected_images

    try:
        result = delete_selected_images(work_dir, image_ids=body.image_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"No se pudo borrar archivo: {e}") from e
    return {"ok": True, **result}


@router.get("/pipeline/images-generation/config")
def api_pipeline_images_generation_config():
    import os

    from videomaker.engines.google_imagen import get_model, use_mock

    return {
        "mock": use_mock(),
        "model": get_model(),
        "has_api_key": bool(os.getenv("GOOGLE_API_KEY", "").strip()),
    }


class GeminiWebStartBody(BaseModel):
    work: str = "output/ui_session"
    image_ids: list[str] = Field(default_factory=list)
    skip_generated: bool = Field(default=True)
    batch_mode: bool = Field(default=True)
    batch_size: int = Field(default=1, ge=1, le=50)
    order_from: int | None = Field(default=None, ge=1)
    order_to: int | None = Field(default=None, ge=1)


@router.get("/pipeline/images-generation/gemini-web/status")
def api_pipeline_gemini_web_status(work: str = "output/ui_session"):
    """Estado de la cola Gemini web (misma conversación en el navegador)."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.engines.gemini_web_batch import check_cdp_available, chrome_launch_hint, read_job

    cdp = check_cdp_available()
    job = read_job(work_dir)
    return {
        "cdp": cdp,
        "job": job,
        "chrome_hint": chrome_launch_hint(),
    }


@router.post("/pipeline/images-generation/gemini-web/start")
def api_pipeline_gemini_web_start(body: GeminiWebStartBody):
    """Encola generación vía Gemini web (Google AI Pro) en background."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.engines.gemini_web_batch import (
        check_cdp_available,
        read_job,
        resolve_gemini_queue_ids,
        run_batch_in_background,
    )

    image_ids = body.image_ids
    if body.batch_mode or body.order_from is not None or body.order_to is not None:
        image_ids = resolve_gemini_queue_ids(
            work_dir,
            body.image_ids,
            order_from=body.order_from,
            order_to=body.order_to,
            skip_generated=body.skip_generated,
        )
    if not image_ids:
        raise HTTPException(status_code=400, detail="No hay imágenes pendientes en el rango indicado.")

    existing = read_job(work_dir)
    if existing and existing.get("state") == "running" and not existing.get("cancel_requested"):
        raise HTTPException(status_code=409, detail="Ya hay una cola Gemini en ejecución.")
    cdp = check_cdp_available()
    if not cdp.get("cdp_connected"):
        raise HTTPException(
            status_code=503,
            detail=cdp.get("detail") or "Chrome con depuración remota no disponible.",
        )
    try:
        run_batch_in_background(
            work_dir,
            body.work,
            image_ids,
            body.skip_generated,
            batch_mode=body.batch_mode,
            batch_size=body.batch_size,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"ok": True, "started": True, "queued": len(body.image_ids)}


class GeminiWebCancelBody(BaseModel):
    work: str = "output/ui_session"


@router.post("/pipeline/images-generation/gemini-web/cancel")
def api_pipeline_gemini_web_cancel(body: GeminiWebCancelBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.engines.gemini_web_batch import request_cancel

    job = request_cancel(work_dir)
    return {"ok": True, "cancel_requested": True, "job": job}


@router.get("/pipeline/images-generation/image")
def api_pipeline_image_file(work: str = "output/ui_session", filename: str = ""):
    """Sirve un fichero PNG/JPG de pipeline/images/ como FileResponse."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="filename requerido")
    img_path = (work_dir / "pipeline" / "images" / safe_name).resolve()
    if not img_path.is_file():
        raise HTTPException(status_code=404, detail=f"Imagen no encontrada: {safe_name}")
    return FileResponse(str(img_path))


@router.get("/pipeline/render-draft")
def api_pipeline_render_draft_get(work: str = "output/ui_session"):
    """Resumen del último montaje (`pipeline/render_draft.json`)."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    p = work_dir / "pipeline" / "render_draft.json"
    if not p.is_file():
        return {"exists": False, "artifact": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"exists": False, "artifact": None}
    return {"exists": True, "artifact": data if isinstance(data, dict) else None}


@router.get("/pipeline/prompt-artifact")
def api_pipeline_prompt_artifact(work: str = "output/ui_session"):
    """Contenido de `pipeline/prompt.json` para rehidratar la UI tras recargar."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_prompt_artifact

    raw = read_prompt_artifact(work_dir)
    if not raw:
        return {"exists": False, "confirmed": False}
    return {
        "exists": True,
        "artifact": raw,
        "confirmed": bool(raw.get("confirmed")),
    }


class PipelinePromptConfirmBody(WorkModel):
    prompt: dict[str, Any] | None = Field(
        default=None,
        description="JSON opcional; si se omite, confirma pipeline/prompt.json en disco.",
    )


@router.post("/pipeline/prompt/confirm")
def api_pipeline_prompt_confirm(body: PipelinePromptConfirmBody):
    """Bloquea el prompt actual y marca el paso como done (sin Start step / LLM)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import confirm_prompt_bundle

    raw = body.prompt if isinstance(body.prompt, dict) else None
    try:
        saved = confirm_prompt_bundle(work_dir, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "confirmed": True, "prompt": saved}


@router.get("/pipeline/script-writer")
def api_pipeline_script_writer_get(work: str = Query("output/ui_session")):
    """Estado del guion en disco para confirmación manual del paso Script Writer."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import _step_artifact_satisfied, read_pipeline_state

    guion = work_dir / "guion.txt"
    pipe = work_dir / "pipeline" / "script.txt"
    source: str | None = None
    chars = 0
    for label, p in (("guion.txt", guion), ("pipeline/script.txt", pipe)):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            source = label
            chars = len(text)
            break
    st = read_pipeline_state(work_dir)
    step = next((s for s in st.get("steps", []) if s.get("id") == "script_writer"), None)
    step_done = (step or {}).get("state") == "done"
    return {
        "exists": bool(source),
        "source": source,
        "chars": chars,
        "step_done": step_done,
        "artifact_satisfied": _step_artifact_satisfied(work_dir, "script_writer"),
    }


@router.post("/pipeline/script-writer/confirm")
def api_pipeline_script_writer_confirm(body: WorkModel):
    """Marca Script Writer como done si hay guion en disco (sin Start step / LLM)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import confirm_script_writer_from_disk

    try:
        meta = confirm_script_writer_from_disk(work_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "confirmed": True, **meta}


@router.get("/pipeline/step-status")
def api_pipeline_step_status(
    work: str = Query("output/ui_session"),
    step_id: str = Query(..., min_length=1),
):
    """Estado del artefacto en disco para confirmación manual de un paso."""
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import get_pipeline_step_confirm_status

    try:
        return get_pipeline_step_confirm_status(work_dir, step_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class PipelineStepConfirmBody(WorkModel):
    step_id: str = Field(..., min_length=1)


@router.post("/pipeline/step/confirm")
def api_pipeline_step_confirm(body: PipelineStepConfirmBody):
    """Marca un paso como done si el artefacto ya está en disco (sin LLM)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import confirm_pipeline_step_from_disk

    try:
        return {"ok": True, **confirm_pipeline_step_from_disk(work_dir, body.step_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/script-fragmentation")
def api_script_fragmentation_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.llm.script_fragmentation import load_state

    st = load_state(work_dir)
    if not st:
        return {"exists": False, "state": None}
    return {"exists": True, "state": st}


@router.patch("/script-fragmentation")
def api_script_fragmentation_patch(body: ScriptFragmentationPatchBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.llm.script_fragmentation import apply_fragment_review

    try:
        st = apply_fragment_review(work_dir, body.index, complete=body.complete)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (IndexError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "state": st}


@router.post("/script-fragmentation/reset")
def api_script_fragmentation_reset(body: WorkModel):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.llm.script_fragmentation import reset_fragmentation_artifacts

    reset_fragmentation_artifacts(work_dir)
    return {"ok": True}


class ProductionResetBody(WorkModel):
    scope: str = Field(
        ...,
        description="scene_editor_visual | image_prompts | voiceovers | images_generation",
    )


@router.post("/pipeline/production-reset")
def api_pipeline_production_reset(body: ProductionResetBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.production_reset import ProductionResetScope, run_production_reset

    scope = (body.scope or "").strip()
    allowed: tuple[ProductionResetScope, ...] = (
        "scene_editor_visual",
        "image_prompts",
        "voiceovers",
        "images_generation",
    )
    if scope not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"scope inválido. Usa uno de: {', '.join(allowed)}",
        )
    try:
        return run_production_reset(work_dir, scope)  # type: ignore[arg-type]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/pipeline/start", status_code=202)
def api_pipeline_start(background: BackgroundTasks, body: PipelineStartBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    background.add_task(
        jobs.run_create_pipeline,
        body.work,
        keywords=body.keywords,
        context=body.context,
        lang=body.lang,
        minutes=body.minutes,
        provider=body.provider,
        model=body.model,
        step_id=None,
        prompt_template_id=body.prompt_template_id,
        prompt_topic=body.prompt_topic,
        prompt_video_restrictions=body.prompt_video_restrictions,
        script_writer_template_id=body.script_writer_template_id,
        script_fragment_index=body.script_fragment_index,
        render_no_music=body.render_no_music,
    )
    return {"started": True}


class PipelineStopBody(WorkModel):
    pass


@router.post("/pipeline/stop", status_code=202)
def api_pipeline_stop(body: PipelineStopBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import request_pipeline_stop

    request_pipeline_stop(work_dir)
    return {"ok": True}


@router.post("/pipeline/reset", status_code=202)
def api_pipeline_reset(body: PipelineStopBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import reset_pipeline

    reset_pipeline(work_dir)
    return {"ok": True}


@router.get("/pipeline/narrative-angle")
def api_narrative_angle_get(work: str = Query("output/ui_session")):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_narrative_angle_artifact

    raw = read_narrative_angle_artifact(work_dir)
    return {
        "exists": bool(raw),
        "narrative_angle": raw or None,
        "confirmed": bool(raw.get("confirmed")) if raw else False,
    }


class PipelineNarrativeAngleConfirmBody(WorkModel):
    narrative_angle: dict[str, Any] | None = Field(
        default=None,
        description="JSON editado en UI; si se omite, confirma el archivo en disco.",
    )


@router.post("/pipeline/narrative-angle/confirm")
def api_narrative_angle_confirm(body: PipelineNarrativeAngleConfirmBody):
    """Bloquea el ángulo narrativo actual y marca el paso como done (sin Start step / LLM)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import confirm_narrative_angle_bundle, read_narrative_angle_artifact

    raw = body.narrative_angle if isinstance(body.narrative_angle, dict) else None
    if not raw:
        raw = read_narrative_angle_artifact(work_dir)
    if not raw:
        raise HTTPException(
            status_code=400,
            detail="No hay pipeline/narrative_angle.json. Ejecuta Start step o pega un JSON válido.",
        )
    try:
        saved = confirm_narrative_angle_bundle(work_dir, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "confirmed": True, "narrative_angle": saved}


@router.get("/pipeline/editorial-analysis")
def api_editorial_analysis_get(work: str = Query("output/ui_session")):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_editorial_analysis_artifact

    return read_editorial_analysis_artifact(work_dir) or {}


class PacingPassSettingsPutBody(WorkModel):
    target_minutes: float | None = None
    trim_to_duration: bool = True
    user_directives: str = ""


class PacingPassDirectivePresetBody(BaseModel):
    text: str = Field(default="", description="Texto de la directriz")
    name: str | None = Field(default=None, max_length=48, description="Opcional; si falta → directriz01, …")


class PacingPassDirectivePresetRenameBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=48)


@router.get("/pipeline/pacing-pass-directive-presets")
def api_pacing_pass_directive_presets_list():
    from videomaker.core.pacing_pass_directive_presets_store import list_directive_presets

    return {"items": list_directive_presets()}


@router.post("/pipeline/pacing-pass-directive-presets")
def api_pacing_pass_directive_presets_create(body: PacingPassDirectivePresetBody):
    from videomaker.core.pacing_pass_directive_presets_store import save_directive_preset

    try:
        row = save_directive_preset(text=body.text, name=body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, **row}


@router.patch("/pipeline/pacing-pass-directive-presets/{preset_id}")
def api_pacing_pass_directive_presets_rename(
    preset_id: str,
    body: PacingPassDirectivePresetRenameBody,
):
    from videomaker.core.pacing_pass_directive_presets_store import rename_directive_preset

    try:
        row = rename_directive_preset(preset_id=preset_id, name=body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, **row}


@router.delete("/pipeline/pacing-pass-directive-presets/{preset_id}")
def api_pacing_pass_directive_presets_delete(preset_id: str):
    from videomaker.core.pacing_pass_directive_presets_store import delete_directive_preset

    try:
        delete_directive_preset(preset_id=preset_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.get("/pipeline/pacing-pass-settings")
def api_pacing_pass_settings_get(work: str = Query("output/ui_session")):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.core.pacing_pass_settings_store import (
        read_pacing_pass_settings,
        resolve_target_minutes,
    )

    st = read_pacing_pass_settings(work_dir)
    session_m = 10.0
    pj = work_dir / "pipeline" / "prompt.json"
    if pj.is_file():
        try:
            pr = json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(pr, dict) and pr.get("minutes"):
                session_m = float(pr["minutes"])
        except Exception:
            pass
    result_path = work_dir / "pipeline" / "pacing_pass_result.json"
    last_result: dict | None = None
    if result_path.is_file():
        try:
            raw = json.loads(result_path.read_text(encoding="utf-8"))
            last_result = raw if isinstance(raw, dict) else None
        except Exception:
            last_result = None
    return {
        "settings": st,
        "resolved_target_minutes": resolve_target_minutes(work_dir, session_minutes=session_m),
        "last_result": last_result,
    }


class PacingPassManualApplyBody(WorkModel):
    text: str = Field(default="", description="Guion completo pegado o editado a mano")


@router.post("/pipeline/pacing-pass/apply-manual")
def api_pacing_pass_apply_manual(body: PacingPassManualApplyBody):
    """Guarda el guion manual y marca Narrative Pacing Pass como done (sin LLM)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import confirm_narrative_pacing_pass_manual

    try:
        meta = confirm_narrative_pacing_pass_manual(work_dir, body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "confirmed": True, **meta}


@router.put("/pipeline/pacing-pass-settings")
def api_pacing_pass_settings_put(body: PacingPassSettingsPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.core.pacing_pass_settings_store import write_pacing_pass_settings

    saved = write_pacing_pass_settings(
        work_dir,
        {
            "target_minutes": body.target_minutes,
            "trim_to_duration": body.trim_to_duration,
            "user_directives": body.user_directives,
        },
    )
    return {"ok": True, "settings": saved}


@router.get("/pipeline/topic-generator")
def api_topic_generator_get(work: str = Query("output/ui_session")):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_topic_generator_artifact
    from videomaker.pipeline.topic_generator_selection import resolve_topic_generator_artifact

    data = read_topic_generator_artifact(work_dir)
    if not data:
        return {"topics": [], "selected_index": None}
    return resolve_topic_generator_artifact(work_dir, data)


@router.post("/pipeline/topic-generator/generate")
def api_topic_generator_generate(body: TopicGeneratorGenerateBody):
    """Genera ideas de tema (LLM) y persiste en pipeline/topic_generator.json."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.llm.topic_generator import generate_topic_ideas
    from videomaker.pipeline.runner import read_topic_generator_artifact, write_topic_generator_artifact
    from videomaker.pipeline.topic_generator_selection import (
        apply_topic_selection,
        session_topic_hints,
    )
    from videomaker.web.transcripts_session import get_combined_text

    transcript = (body.transcript_text or "").strip()
    if body.use_session or len(transcript) < 50:
        session_text = get_combined_text(work_dir)
        if len(session_text) >= 50:
            transcript = session_text
    if len(transcript) < 50:
        raise HTTPException(
            status_code=400,
            detail="Carga transcripts en sesión (Analyse) o pega texto con al menos ~50 caracteres.",
        )

    out_lang = body.output_language
    if not out_lang:
        try:
            from videomaker.web.transcripts_session import read_transcripts_session

            sess = read_transcripts_session(work_dir)
            out_lang = str(sess.get("analyze_output_language") or "").strip().lower() or None
            if not out_lang:
                ch = sess.get("channel") if isinstance(sess.get("channel"), dict) else {}
                out_lang = str(ch.get("language") or "").strip().lower() or None
        except Exception:
            out_lang = None

    try:
        payload = generate_topic_ideas(
            transcript_text=transcript,
            niche_trends=body.niche_trends,
            topic_count=body.topic_count,
            output_language=out_lang,
            provider=body.provider,
            model=body.model,
            detail_level=body.detail_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    previous = read_topic_generator_artifact(work_dir)
    kw, ctx = session_topic_hints(work_dir)
    payload = apply_topic_selection(
        payload,
        previous=previous,
        session_keywords=kw,
        session_context=ctx,
    )
    from videomaker.pipeline.duration_policy import apply_duration_policy_to_topic_payload

    write_topic_generator_artifact(work_dir, apply_duration_policy_to_topic_payload(payload))
    from videomaker.pipeline.runner import _set_step

    _set_step(
        work_dir,
        "topic_generator",
        state="idle",
        detail="Nueva lista — elige un tema.",
    )
    return apply_duration_policy_to_topic_payload(payload)


@router.post("/pipeline/topic-generator/enrich")
def api_topic_generator_enrich(body: TopicGeneratorEnrichBody):
    """Enriquece SOLO el topic seleccionado (scene_pack, hooks, broll_keywords)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_topic_generator_artifact, write_topic_generator_artifact
    from videomaker.web.transcripts_session import get_combined_text
    from videomaker.llm.topic_generator import enrich_topic_idea

    data = read_topic_generator_artifact(work_dir) or {}
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    idx = int(body.selected_index)
    if idx < 0 or idx >= len(topics):
        raise HTTPException(status_code=400, detail="Índice de tema fuera de rango")
    base = topics[idx] if isinstance(topics[idx], dict) else {}
    if not base:
        raise HTTPException(status_code=400, detail="Tema inválido")

    transcript = get_combined_text(work_dir)
    if len(transcript) < 50:
        raise HTTPException(status_code=400, detail="Faltan transcripts en sesión (Analyse).")
    out_lang = data.get("output_language") if isinstance(data, dict) else None
    out_lang = out_lang if out_lang in ("en", "es") else "en"

    enriched = enrich_topic_idea(
        base_topic=base,
        transcript_text=transcript,
        niche_trends=str(data.get("niche_trends") or ""),
        output_language=str(out_lang),
        provider=body.provider,
        model=body.model,
    )
    topics[idx] = enriched
    data["topics"] = topics
    write_topic_generator_artifact(work_dir, data)
    return {"ok": True, "selected_index": idx, "topic": enriched}


@router.post("/pipeline/topic-generator/approve")
def api_topic_generator_approve(body: WorkModel):
    """Marca Topic Generator como completado sin regenerar temas (tema ya elegido)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_topic_generator_artifact, _set_step

    data = read_topic_generator_artifact(work_dir)
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    idx = data.get("selected_index")
    if not isinstance(idx, int) or idx < 0 or idx >= len(topics):
        raise HTTPException(
            status_code=400,
            detail="Selecciona un tema con «Usar este tema» antes de continuar.",
        )
    topic = topics[idx] if isinstance(topics[idx], dict) else {}
    title = str(topic.get("title") or "").strip() or f"Tema #{idx + 1}"
    _set_step(work_dir, "topic_generator", state="done", detail=f"Tema confirmado: {title[:120]}")
    return {"ok": True, "selected_index": idx, "topic": topic}


@router.post("/pipeline/topic-generator/reset-selection")
def api_topic_generator_reset_selection(body: WorkModel):
    """Quita la selección y deja el paso Topic Generator en pendiente."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_topic_generator_artifact, write_topic_generator_artifact, _set_step

    data = read_topic_generator_artifact(work_dir)
    if not data:
        data = {"topics": [], "selected_index": None}
    data["selected_index"] = None
    write_topic_generator_artifact(work_dir, data)
    _set_step(
        work_dir,
        "topic_generator",
        state="idle",
        detail="Pendiente — elige un tema.",
    )
    return {"ok": True, "selected_index": None}


class PipelineSessionSpawnBody(BaseModel):
    parent_work: str = Field(
        ...,
        description="Sesión con topic_generator.json (banco de temas)",
    )
    child_work: str | None = Field(
        default=None,
        description="Carpeta hija; si vacío se deriva del título (output/v01_slug)",
    )
    topic_index: int = Field(..., ge=0, description="Índice en topics[] del padre")
    copy_transcripts: bool = Field(default=True)
    reset_from_step: str = Field(default="narrative_angle")
    overwrite_child: bool = Field(default=False)


@router.post("/pipeline/sessions/spawn")
def api_pipeline_sessions_spawn(body: PipelineSessionSpawnBody):
    """
    Nueva sesión de producción para un tema del banco (sin regenerar temas por LLM).
    """
    try:
        parent_dir = safe_work_dir(body.parent_work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from videomaker.pipeline.runner import read_topic_generator_artifact
    from videomaker.pipeline.session_spawn import (
        default_child_work_slug,
        spawn_production_session,
    )
    parent_tg = read_topic_generator_artifact(parent_dir)
    topics = parent_tg.get("topics") if isinstance(parent_tg.get("topics"), list) else []
    if body.topic_index >= len(topics):
        raise HTTPException(status_code=400, detail="topic_index fuera de rango")

    topic = topics[body.topic_index]
    title = str(topic.get("title") or "").strip() if isinstance(topic, dict) else ""
    child_rel = (body.child_work or "").strip() or default_child_work_slug(
        body.parent_work, body.topic_index, title
    )
    try:
        child_dir = safe_work_dir(child_rel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        result = spawn_production_session(
            parent_work_dir=parent_dir,
            child_work_dir=child_dir,
            topic_index=body.topic_index,
            copy_transcripts=body.copy_transcripts,
            reset_from_step=body.reset_from_step,
            overwrite_child=body.overwrite_child,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return result


class TopicGeneratorOutputLanguageBody(WorkModel):
    output_language: Literal["en", "es"]


@router.put("/pipeline/topic-generator/output-language")
def api_topic_generator_output_language(body: TopicGeneratorOutputLanguageBody):
    """Persiste «Idioma de salida» (canónico para toda la pipeline Create)."""
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import set_topic_generator_output_language

    try:
        data = set_topic_generator_output_language(work_dir, body.output_language)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"ok": True, "output_language": data.get("output_language")}


@router.put("/pipeline/topic-generator/select")
def api_topic_generator_select(body: TopicGeneratorSelectBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import read_topic_generator_artifact, write_topic_generator_artifact

    data = read_topic_generator_artifact(work_dir)
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    if body.selected_index >= len(topics):
        raise HTTPException(status_code=400, detail="Índice de tema fuera de rango")
    data["selected_index"] = body.selected_index
    write_topic_generator_artifact(work_dir, data)
    return {"ok": True, "selected_index": body.selected_index, "topic": topics[body.selected_index]}


@router.post("/pipeline/step/rerun", status_code=202)
def api_pipeline_step_rerun(background: BackgroundTasks, body: PipelineRerunBody):
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    background.add_task(
        jobs.run_create_pipeline,
        body.work,
        keywords="" if body.keywords is None else body.keywords,
        context="" if body.context is None else body.context,
        lang="es" if body.lang is None else body.lang,
        minutes=10.0 if body.minutes is None else float(body.minutes),
        provider="" if body.provider is None else body.provider,
        model="" if body.model is None else body.model,
        step_id=body.step_id,
        prompt_template_id=body.prompt_template_id,
        prompt_topic=body.prompt_topic,
        prompt_video_restrictions=body.prompt_video_restrictions,
        script_writer_template_id=body.script_writer_template_id,
        script_fragment_index=body.script_fragment_index,
        render_no_music=body.render_no_music,
        topic_generator_transcript=body.topic_generator_transcript,
        topic_generator_niche_trends=body.topic_generator_niche_trends,
        topic_generator_topic_count=body.topic_generator_topic_count,
    )
    return {"started": True}


@router.post("/pipeline/step/{step_id}/rerun", status_code=202)
def api_pipeline_step_rerun_compat(background: BackgroundTasks, step_id: str, work: str = "output/ui_session"):
    """Ruta compatible con el plan original: rerun por URL param."""
    try:
        safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    background.add_task(
        jobs.run_create_pipeline,
        work,
        keywords="",
        context="",
        lang="es",
        minutes=10.0,
        provider="",
        model="",
        step_id=step_id,
        prompt_template_id=None,
        prompt_topic=None,
        script_writer_template_id=None,
        script_fragment_index=None,
        render_no_music=None,
    )
    return {"started": True}


@router.get("/prompt-presets")
def api_prompt_presets_list():
    return {"presets": list_presets(), "selected_id": get_selected_id()}


@router.get("/prompt-preset")
def api_prompt_preset_get(preset_id: str):
    p = get_preset(preset_id)
    if not p:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada.")
    return p


@router.post("/prompt-preset")
def api_prompt_preset_create(body: PromptPresetCreateBody):
    entry = create_preset(body.name.strip(), body.system_extra, body.user_extra)
    return {"ok": True, "preset": entry}


@router.put("/prompt-preset")
def api_prompt_preset_update(body: PromptPresetUpdateBody):
    updated = update_preset(
        body.id,
        name=body.name,
        system_extra=body.system_extra,
        user_extra=body.user_extra,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada.")
    return {"ok": True, "preset": updated}


@router.delete("/prompt-preset")
def api_prompt_preset_delete(preset_id: str):
    if not delete_preset(preset_id):
        raise HTTPException(status_code=404, detail="Plantilla no encontrada.")
    return {"ok": True}


@router.post("/prompt-preset/select")
def api_prompt_preset_select(body: PromptPresetSelectBody):
    set_selected_id(body.id)
    return {"ok": True, "selected_id": get_selected_id()}


@router.get("/prompt-templates")
def api_prompt_templates_list(limit: int = 200):
    return {"templates": list_prompt_templates(limit=int(limit))}


@router.get("/prompt-templates/{template_id}")
def api_prompt_template_get(template_id: str):
    t = get_prompt_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template no encontrado.")
    return t


@router.post("/prompt-templates", status_code=201)
def api_prompt_template_create(body: PromptTemplateBody):
    try:
        t = create_prompt_template(
            name=body.name,
            hook_style=body.hook_style,
            visual_style=body.visual_style,
            tone=body.tone,
            system_instructions=body.system_instructions,
            user_instructions=body.user_instructions,
            params_json=body.params_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "template": t}


@router.put("/prompt-templates/{template_id}")
def api_prompt_template_update(template_id: str, body: PromptTemplateBody):
    try:
        t = update_prompt_template(
            template_id,
            name=body.name,
            hook_style=body.hook_style,
            visual_style=body.visual_style,
            tone=body.tone,
            system_instructions=body.system_instructions,
            user_instructions=body.user_instructions,
            params_json=body.params_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not t:
        raise HTTPException(status_code=404, detail="Template no encontrado.")
    return {"ok": True, "template": t}


@router.delete("/prompt-templates/{template_id}")
def api_prompt_template_delete(template_id: str):
    delete_prompt_template(template_id)
    return {"ok": True}


# ── Generador de template a partir de transcripciones ─────────────────────

_ALLOWED_TRANSCRIPT_SUFFIXES = (".txt", ".pdf", ".json", ".srt", ".vtt")


@router.post("/prompt-templates/parse-transcript-files")
async def api_parse_transcript_files(files: list[UploadFile] = File(...)):
    """Extrae texto de transcripts (.txt, .pdf, .json, .srt, .vtt) para preparar el análisis (sin LLM)."""
    from videomaker.web.transcript_files import combine_transcript_documents, extract_transcript_text

    if not files:
        raise HTTPException(status_code=400, detail="Sube al menos un archivo.")
    documents: list[tuple[str, str]] = []
    parsed: list[dict[str, Any]] = []
    for uf in files:
        name = (uf.filename or "upload").strip()
        low = name.lower()
        if not any(low.endswith(s) for s in _ALLOWED_TRANSCRIPT_SUFFIXES):
            raise HTTPException(
                status_code=400,
                detail=f"Formato no soportado: {name}. Usa .txt, .pdf, .json, .srt o .vtt",
            )
        raw = await uf.read()
        if not raw:
            raise HTTPException(status_code=400, detail=f"Archivo vacío: {name}")
        try:
            text = extract_transcript_text(raw, name)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        documents.append((name, text))
        parsed.append({"name": name, "chars": len(text)})
    combined = combine_transcript_documents(documents)
    if len(combined) < 50:
        raise HTTPException(
            status_code=422,
            detail="Texto extraído demasiado corto. Comprueba que los PDF contengan texto seleccionable.",
        )
    return {
        "files": parsed,
        "file_count": len(parsed),
        "combined_text": combined,
        "total_chars": len(combined),
    }


class PromptTemplateFromTranscriptBody(WorkModel):
    transcript_text: str = ""
    provider: str = "anthropic"
    model: str = ""
    use_session: bool = False


@router.post("/prompt-templates/generate-from-transcript")
def api_prompt_template_generate_from_transcript(body: PromptTemplateFromTranscriptBody):
    """Analyzes transcript text with an LLM and returns a filled prompt template JSON."""
    from videomaker.llm.prompt_from_transcript import generate_prompt_template_from_transcript
    from videomaker.web.transcripts_session import get_combined_text, read_transcripts_session

    transcript = (body.transcript_text or "").strip()
    if body.use_session or len(transcript) < 50:
        try:
            work_dir = safe_work_dir(body.work)
            session_data = read_transcripts_session(work_dir)
            if session_data.get("prompt_analysis") and body.use_session:
                from videomaker.llm.prompt_analysis_storage import slim_prompt_analysis_payload

                pa = slim_prompt_analysis_payload(
                    session_data["prompt_analysis"]
                    if isinstance(session_data.get("prompt_analysis"), dict)
                    else None
                )
                if pa:
                    return pa
            session_text = get_combined_text(work_dir)
            if len(session_text) >= 50:
                transcript = session_text
        except ValueError:
            pass
    if len(transcript) < 50:
        raise HTTPException(
            status_code=400,
            detail="Carga transcripts en sesión (Analyse) o envía transcript_text (mín. 50 caracteres).",
        )

    try:
        return generate_prompt_template_from_transcript(
            transcript_text=transcript,
            provider="anthropic",
            model=body.model,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"LLM did not return valid JSON: {exc}") from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Generador de template Script Writer a partir de transcripciones ────────

class ScriptWriterTemplateFromTranscriptBody(BaseModel):
    transcript_text: str = ""
    work: str | None = Field(
        default=None,
        description="Carpeta de trabajo usada para buscar una sesión de transcripts existentes",
    )
    provider: str = "anthropic"
    model: str = ""
    lang: str = "es"


_SW_TRANSCRIPT_SYSTEM = """
You are a YouTube channel strategy analyst and script-writing expert.

Your task: analyze a set of video transcripts from a single YouTube channel and produce a
structured JSON that captures the channel's scripting style for a Videomaker Script Writer template.

Return ONLY a valid JSON object (no markdown, no extra text) with this exact schema:
{
  "name": "<short template name, e.g. 'Nick Invests – Long-form finanzas'>",
  "system_instructions": "<3-6 sentences describing the LLM's role when writing scripts for this channel: narrative persona, voice, structural rules, what to always do>",
  "user_instructions": "<3-6 sentences with content-specific rules: recurring topics, forbidden subjects, how to open/close, pacing notes, CTA style>",
  "params_json": {
    "pacing": "mixed",
    "data_density": "medium",
    "structure_preset": "default_five_blocks",
    "narrative_preset": "entretenimiento",
    "chunking": "full_pass"
  }
}

Guidelines for `params_json` values:
- The values in the example `params_json` are illustrative. You must choose the correct ones based on your analysis.
- `pacing`: One of "short", "mixed", "long". ("short" for fast-cut, "long" for documentary/essay).
- `data_density`: One of "low", "medium", "high". ("high" for data-heavy content).
- `structure_preset`: One of "four_act" (finance/business) or "default_five_blocks" (tutorials/entertainment).
- `narrative_preset`: One of "finanzas", "entretenimiento", "tutorial", "ventas". IMPORTANT: Omit the key entirely if none fit.
- `chunking`: One of "full_pass" or "sequential_fragments". ("sequential_fragments" for videos >15 min).
""".strip()


@router.post("/script-writer-templates/generate-from-transcript")
def api_sw_template_generate_from_transcript(body: ScriptWriterTemplateFromTranscriptBody):
    """Analyzes transcript text with an LLM and returns a filled Script Writer template JSON."""
    from videomaker.llm.avatar_prompt_writer import _call_llm
    from videomaker.web.transcripts_session import get_combined_text

    transcript_text = (body.transcript_text or "").strip()
    selected_provider = (body.provider or "").strip().lower()
    if selected_provider == "":
        selected_provider = "anthropic"

    if not transcript_text and body.work:
        try:
            work_dir = safe_work_dir(body.work)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        transcript_text = get_combined_text(work_dir).strip()

    if not transcript_text:
        raise HTTPException(
            status_code=400,
            detail=(
                "No transcripts were provided and no combined transcripts were found "
                "for the requested work session. Upload or paste a transcript file, "
                "or verify the Analyse session."
            ),
        )

    selected_lang = (body.lang or "es").strip().lower()
    language_label = "English" if selected_lang.startswith("en") else "Spanish"
    user_msg = (
        "Here are the video transcripts to analyze:\n\n"
        + transcript_text[:40_000]
        + "\n\nNow produce the Script Writer JSON template as instructed. "
        + f"Write the JSON object fields in {language_label}, and make sure system_instructions and user_instructions are also written in {language_label}. "
        + "If the transcripts are in a different language, still output the template in the requested language."
    )

    use_mock = (
        selected_provider == "mock"
        or (
            selected_provider == "anthropic"
            and not os.environ.get("ANTHROPIC_API_KEY", "").strip()
        )
    )
    if use_mock:
        import time

        time.sleep(1)
        if selected_lang.startswith("en"):
            return {
                "name": "Mock Script Writer Template",
                "system_instructions": (
                    "Act as an expert scriptwriter for educational content and generate a script template with a clear, approachable, and structured tone. "
                    "Keep the instructions focused on how to write the script, pacing, and channel-specific style rules."
                ),
                "user_instructions": (
                    "Write specific formatting and content rules for the script, including CTA style, closing tone, and what to avoid. "
                    "This content is used to guide narrative block generation and keep editorial consistency."
                ),
                "params_json": {
                    "pacing": "mixed",
                    "data_density": "medium",
                    "structure_preset": "default_five_blocks",
                    "narrative_preset": "entretenimiento",
                    "chunking": "full_pass",
                },
            }
        return {
            "name": "Mock Script Writer Template",
            "system_instructions": (
                "Actúa como un guionista experto en contenido educativo y genera un template de guion con un tono claro, cercano y estructurado. "
                "Mantén las instrucciones enfocadas en la forma de escribir el guion, el ritmo y las reglas de estilo del canal."
            ),
            "user_instructions": (
                "Escribe reglas y matices de formato específicos para el guion, incluyendo CTA, tono del cierre y qué evitar. "
                "Este contenido se usa para guiar la generación de bloques narrativos y mantener coherencia editorial."
            ),
            "params_json": {
                "pacing": "mixed",
                "data_density": "medium",
                "structure_preset": "default_five_blocks",
                "narrative_preset": "entretenimiento",
                "chunking": "full_pass",
            },
        }

    raw = _call_llm(
        system=_SW_TRANSCRIPT_SYSTEM,
        user=user_msg,
        provider=selected_provider,
        model=body.model,
        temperature=0.4,
    )

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"LLM did not return valid JSON: {exc}") from exc

    return result


@router.get("/narrative-presets")
def api_narrative_presets():
    """Presets de pesos por categoría narrativa (4 actos)."""
    from videomaker.llm.narrative_presets import NARRATIVE_PRESETS

    presets: list[dict] = []
    for p in NARRATIVE_PRESETS.values():
        presets.append(
            {
                "id": p["id"],
                "name": p["name"],
                "weights": list(p["weights"]),
                "descriptions": list(p["descriptions"]),
            }
        )
    return {"presets": presets}


@router.get("/script-writer-templates")
def api_script_writer_templates_list(limit: int = 200):
    return {"templates": list_script_writer_templates(limit=int(limit))}


@router.get("/script-writer-templates/{template_id}")
def api_script_writer_template_get(template_id: str):
    t = get_script_writer_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template no encontrado.")
    return t


@router.post("/script-writer-templates", status_code=201)
def api_script_writer_template_create(body: ScriptWriterTemplateBody):
    try:
        t = create_script_writer_template(
            name=body.name,
            system_instructions=body.system_instructions,
            user_instructions=body.user_instructions,
            params_json=body.params_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "template": t}


@router.put("/script-writer-templates/{template_id}")
def api_script_writer_template_update(template_id: str, body: ScriptWriterTemplateBody):
    try:
        t = update_script_writer_template(
            template_id,
            name=body.name,
            system_instructions=body.system_instructions,
            user_instructions=body.user_instructions,
            params_json=body.params_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not t:
        raise HTTPException(status_code=404, detail="Template no encontrado.")
    return {"ok": True, "template": t}


@router.delete("/script-writer-templates/{template_id}")
def api_script_writer_template_delete(template_id: str):
    delete_script_writer_template(template_id)
    return {"ok": True}


@router.post("/upload-script", status_code=201)
async def api_upload_script(work: str = Form("output/ui_session"), file: UploadFile | None = None):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    work_dir.mkdir(parents=True, exist_ok=True)
    if file is None:
        raise HTTPException(status_code=400, detail="Falta el archivo.")
    data = await file.read()
    (work_dir / "guion.txt").write_bytes(data)
    try:
        write_script_bundle(work_dir, data.decode("utf-8"))
    except UnicodeDecodeError:
        pass
    return {"ok": True}


@router.post("/upload-voice-clone")
async def api_upload_voice_clone(work: str = Form("output/ui_session"), file: UploadFile | None = None):
    if file is None or not (file.filename or "").strip():
        raise HTTPException(status_code=400, detail="Falta el archivo de audio.")
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    work_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix.lower()
    if suffix not in REFERENCE_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado: {suffix}. Usa: {', '.join(sorted(REFERENCE_SUFFIXES))}",
        )
    data = await file.read()
    if len(data) > _CLONE_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx. 25 MB).")
    raw = work_dir / f"_clone_upload{suffix}"
    out = work_dir / "clone_reference.wav"
    try:
        raw.write_bytes(data)
        if out.is_file():
            out.unlink()
        normalize_reference_for_xtts(raw, out)
    except Exception as e:
        raw.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        raw.unlink(missing_ok=True)
    return {"ok": True}


@router.post("/clear-voice-clone")
def api_clear_voice_clone(body: WorkModel):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    (work_dir / "clone_reference.wav").unlink(missing_ok=True)
    ref = read_tts_reference(work_dir)
    if ref.get("mode") == "clone":
        write_tts_reference(work_dir, "auto", None)
    return {"ok": True}


@router.post("/tts-reference")
def api_set_tts_reference(body: TtsReferenceBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if body.mode == "preview":
        if not body.preview_filename:
            raise HTTPException(status_code=400, detail="Indica preview_filename para mode=preview.")
        safe = safe_preview_voice_name(body.preview_filename)
        if not safe or not (work_dir / safe).is_file():
            raise HTTPException(status_code=400, detail="Muestra no encontrada o nombre inválido.")
        write_tts_reference(work_dir, "preview", safe)
    else:
        write_tts_reference(work_dir, body.mode, None)
    return {"ok": True}


@router.delete("/voice-preview")
def api_delete_voice_preview(work: str, name: str):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    safe = safe_preview_voice_name(name)
    if not safe or not (work_dir / safe).is_file():
        raise HTTPException(status_code=404, detail="Archivo no válido o inexistente.")
    (work_dir / safe).unlink()
    ref = read_tts_reference(work_dir)
    if ref.get("mode") == "preview" and ref.get("preview_filename") == safe:
        write_tts_reference(work_dir, "auto", None)
    return {"ok": True}


@router.post("/narration/select")
def api_narration_select(body: NarrationSelectBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        select_narration_archive(work_dir, body.name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Narración no encontrada en esta sesión.") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.delete("/narration")
def api_delete_narration(work: str, name: str):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        delete_narration_archive(work_dir, name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.delete("/voice-previews")
def api_delete_all_voice_previews(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    for p in work_dir.glob("preview_voice*.wav"):
        p.unlink(missing_ok=True)
    write_tts_reference(work_dir, "auto", None)
    return {"ok": True}
