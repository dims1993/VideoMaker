"""API JSON para la SPA (React). Las rutas HTML clásicas siguen en `app.py`."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile
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
from videomaker.core.saved_guiones_store import (
    delete_saved,
    list_saved,
    read_saved_text,
    save_from_work_dir,
    save_text_to_library,
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
    script_writer_template_id: str | None = None
    script_fragment_index: int | None = None
    render_no_music: bool = False


class PipelineRerunBody(WorkModel):
    step_id: str = Field(..., min_length=2)
    prompt_template_id: str | None = None
    prompt_topic: str | None = None
    script_writer_template_id: str | None = None
    keywords: str | None = None
    context: str | None = None
    lang: str | None = None
    minutes: float | None = None
    provider: str | None = None
    model: str | None = None
    script_fragment_index: int | None = None
    render_no_music: bool | None = None


class ScriptFragmentationPatchBody(WorkModel):
    index: int = Field(..., ge=0)
    complete: bool = True


class ScriptUpdateBody(WorkModel):
    text: str = Field(default="", description="Contenido completo de guion.txt")


class SavedGuionTitleFields(BaseModel):
    title: str | None = Field(default=None, max_length=240)


class SavedGuionSnapshotBody(WorkModel, SavedGuionTitleFields):
    """Guarda en la biblioteca una copia del guion ya presente en la sesión (`work`)."""


class SavedGuionRawLibraryBody(SavedGuionTitleFields):
    text: str = Field(default="", description="Texto completo a archivar en la biblioteca")


class SavedGuionApplyTextBody(WorkModel):
    text: str = Field(default="", description="Texto a escribir en la sesión y marcar Script Writer listo")


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
        return build_session_state(work)
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
    return {
        "llm_provider": os.environ.get("VIDEOMAKER_LLM_PROVIDER", ""),
        "ollama_model": os.environ.get("OLLAMA_MODEL", ""),
        "openai_model": os.environ.get("OPENAI_MODEL", ""),
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
    return {"text": text, "has_script": has_script, "structured": structured}


@router.put("/script")
def api_put_script(body: ScriptUpdateBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import apply_imported_guion_to_work

    apply_imported_guion_to_work(work_dir, body.text, detail="Guion guardado desde el editor.")
    return {"ok": True}


@router.get("/saved-guiones")
def api_saved_guiones_list(limit: int = 100):
    return {"items": list_saved(limit=limit)}


@router.post("/saved-guiones")
def api_saved_guiones_snapshot(body: SavedGuionSnapshotBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        entry = save_from_work_dir(work_dir, title=body.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "entry": entry}


@router.post("/saved-guiones/raw")
def api_saved_guiones_save_raw(body: SavedGuionRawLibraryBody):
    try:
        entry = save_text_to_library(body.text, title=body.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "entry": entry}


@router.post("/saved-guiones/upload")
async def api_saved_guiones_upload(
    title: str = Form(""),
    file: UploadFile | None = None,
):
    if file is None:
        raise HTTPException(status_code=400, detail="Falta archivo (campo file).")
    raw_bytes = await file.read()
    if len(raw_bytes) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx. 4 MiB).")
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1", errors="replace")
    try:
        entry = save_text_to_library(text, title=title.strip() or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "entry": entry}


@router.post("/saved-guiones/apply-text")
def api_saved_guiones_apply_text(body: SavedGuionApplyTextBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not (body.text or "").strip():
        raise HTTPException(status_code=400, detail="El texto del guion está vacío.")
    from videomaker.pipeline.runner import apply_imported_guion_to_work

    apply_imported_guion_to_work(work_dir, body.text, detail="Guion aplicado (texto pegado o archivo).")
    return {"ok": True}


@router.post("/saved-guiones/{saved_id}/apply")
def api_saved_guiones_apply(saved_id: str, body: WorkModel):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        text = read_saved_text(saved_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="id inválido") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Guion no encontrado en la biblioteca.") from None
    from videomaker.pipeline.runner import apply_imported_guion_to_work

    apply_imported_guion_to_work(work_dir, text, detail="Guion cargado desde biblioteca.")
    return {"ok": True}


@router.delete("/saved-guiones/{saved_id}")
def api_saved_guiones_delete(saved_id: str):
    try:
        delete_saved(saved_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="id inválido") from None
    return {"ok": True}


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
    No requiere YouTube Data API key (usa youtube-transcript-api).
    """
    from fastapi.responses import Response

    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Canal no encontrado en el directorio.")
    try:
        safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=400, detail="Falta youtube-transcript-api en el venv.") from e
    ytt = YouTubeTranscriptApi()

    want = [v.strip() for v in (body.video_ids or []) if v and v.strip()]
    if want:
        from videomaker.youtube.channel_store import list_channel_videos_detail_by_ids

        vids_raw = list_channel_videos_detail_by_ids(channel_id, video_ids=want)
        # preserva el orden pedido
        by_id = {v.get("video_id"): v for v in vids_raw}
        vids = [by_id[i] for i in want if i in by_id]
    else:
        vids = list_channel_videos_detail(channel_id, limit=max(1, min(int(body.limit), 200)))

    lang = (body.lang or "es").strip().lower()
    out_videos: list[dict] = []
    for v in vids:
        vid = v.get("video_id") or ""
        if not vid:
            continue
        err: str | None = None
        try:
            rows = ytt.fetch(vid, languages=[lang, "es", "en"])
        except Exception as e:
            # Fallback: try to list available transcripts and pick the first one.
            rows = []
            err = f"{type(e).__name__}: {e}"
            try:
                lst = ytt.list(vid)
                picked = None
                try:
                    picked = lst.find_transcript([lang])
                except Exception:
                    picked = None
                if picked is None:
                    try:
                        picked = lst.find_transcript(["es", "en"])
                    except Exception:
                        picked = None
                if picked is None:
                    try:
                        picked = next(iter(lst), None)
                    except Exception:
                        picked = None
                if picked is not None:
                    try:
                        rows = picked.fetch()
                        err = None
                    except Exception as e2:
                        err = f"{err} | fetch failed: {type(e2).__name__}: {e2}"
            except Exception as e2:
                err = f"{err} | list failed: {type(e2).__name__}: {e2}"

        # youtube-transcript-api v1.x returns snippet objects (text/start/duration), not dicts.
        def _seg_text(seg: object) -> str:
            if isinstance(seg, dict):
                return str(seg.get("text") or "").strip()
            return str(getattr(seg, "text", "") or "").strip()

        lines = [_seg_text(s) for s in (rows or [])]
        text = "\n".join(t for t in lines if t).strip()
        dur = v.get("duration_s")
        try:
            duration_s = int(dur) if dur is not None else None
        except (TypeError, ValueError):
            duration_s = None
        out_videos.append(
            {
                "video_id": vid,
                "title": v.get("title") or "",
                "published_at": v.get("published_at"),
                "duration_s": duration_s,
                "transcript": text,
                "status": "ok" if text else "missing",
                "error": err,
            }
        )

    import json

    payload = {"channel": ch, "count": len(out_videos), "videos": out_videos}
    return Response(content=json.dumps(payload, ensure_ascii=False, indent=2, default=str), media_type="application/json")


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


class PipelineImagePromptsPutBody(WorkModel):
    bundle: dict[str, Any] = Field(default_factory=dict)


class ImagePromptWriterSettingsPutBody(WorkModel):
    target_generator: str = Field(
        default="midjourney",
        description="midjourney | flux | dall_e | sd | custom",
    )
    append_midjourney_suffix: bool = Field(default=True)
    export_negative_separate: bool = Field(default=True)
    notes: str = Field(default="", description="Notas internas para el equipo o futuro LLM")
    use_avatar: bool = Field(default=False)
    avatar_id: str = Field(default="", description="ID de avatar del store global (vacío = descripción manual)")
    avatar_description: str = Field(default="", description="Descripción del avatar para los prompts IA")
    avatar_secs_per_image: float = Field(default=6.0, description="Segundos de narración por imagen")
    avatar_max_images: int = Field(default=80, description="Máximo de imágenes a generar")


class MetadataSettingsPutBody(WorkModel):
    target_platform: str = Field(default="youtube", description="youtube | tiktok | reels")
    target_keywords: str = ""
    system_prompt: str = Field(default="", description="Vacío = usar prompt por defecto del servidor al generar")


class HookRouterSettingsPutBody(WorkModel):
    mode: str = Field(default="template", description="template | llm")
    finance_style: str = Field(default="auto", description="auto | deep_documentary | …")
    system_prompt: str = Field(default="", description="Solo modo llm; vacío = predeterminado interno")


@router.get("/pipeline/hook-router-settings")
def api_hook_router_settings_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.llm.hook_scene_router import narrative_preset_from_work

    st = read_hook_router_settings(work_dir)
    np = narrative_preset_from_work(work_dir)
    mode = str(st.get("mode") or "template").strip().lower()
    fs = str(st.get("finance_style") or "auto").strip().lower()
    sp = str(st.get("system_prompt") or "")
    recommended_defaults = (
        {
            "mode": "template",
            "finance_style": "auto",
            "hint": "Con categoría Finanzas en Script Writer suele ir bien plantilla + auto (clasificador por palabras).",
        }
        if (np or "").lower() == "finanzas"
        else {
            "mode": "llm",
            "finance_style": "auto",
            "hint": "Sin preset finanzas: puedes usar IA para clasificar o plantilla + keywords.",
        }
    )
    return {
        "narrative_preset": np,
        "mode": mode,
        "finance_style": fs,
        "system_prompt": sp,
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


@router.post("/pipeline/hook-router/push-to-image-prompts")
def api_hook_router_push_to_image_prompts(body: WorkModel):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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
    from videomaker.llm.metadata_gen import default_system_prompt

    st = read_metadata_settings(work_dir)
    tp = str(st.get("target_platform") or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    pv = (preview_platform or "").strip().lower()
    default_for = pv if pv in ("youtube", "tiktok", "reels") else tp
    return {
        "target_platform": tp,
        "target_keywords": str(st.get("target_keywords") or ""),
        "system_prompt": str(st.get("system_prompt") or ""),
        "default_system_prompt": default_system_prompt(lang, default_for),
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
    saved = write_metadata_settings(
        work_dir,
        target_platform=tp,
        target_keywords=body.target_keywords,
        system_prompt=body.system_prompt,
    )
    return {"ok": True, "settings": saved}


@router.post("/pipeline/metadata/push-thumbnails-to-images")
def api_pipeline_metadata_push_thumbnails(body: WorkModel):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from videomaker.pipeline.runner import push_thumbnail_ideas_to_image_prompts

    try:
        info = push_thumbnail_ideas_to_image_prompts(work_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, **info}


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


@router.get("/pipeline/image-prompt-writer-settings")
def api_image_prompt_writer_settings_get(work: str = "output/ui_session"):
    try:
        work_dir = safe_work_dir(work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    st = read_image_prompt_writer_settings(work_dir)
    from videomaker.llm.avatar_prompt_writer import AVATAR_DEFAULT_DESCRIPTION

    return {
        "target_generator": str(st.get("target_generator") or "midjourney"),
        "append_midjourney_suffix": bool(st.get("append_midjourney_suffix", True)),
        "export_negative_separate": bool(st.get("export_negative_separate", True)),
        "notes": str(st.get("notes") or ""),
        "use_avatar": bool(st.get("use_avatar", False)),
        "avatar_id": str(st.get("avatar_id") or ""),
        "avatar_description": str(st.get("avatar_description") or AVATAR_DEFAULT_DESCRIPTION),
        "avatar_secs_per_image": float(st.get("avatar_secs_per_image", 6.0)),
        "avatar_max_images": int(st.get("avatar_max_images", 80)),
    }


@router.put("/pipeline/image-prompt-writer-settings")
def api_image_prompt_writer_settings_put(body: ImagePromptWriterSettingsPutBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    # Si hay avatar_id, resolver la descripción desde el store
    resolved_desc = body.avatar_description
    if body.avatar_id:
        from videomaker.core.avatars_store import get_avatar
        av = get_avatar(body.avatar_id)
        if av:
            resolved_desc = av["description"]
    saved = write_image_prompt_writer_settings(
        work_dir,
        target_generator=body.target_generator,
        append_midjourney_suffix=body.append_midjourney_suffix,
        export_negative_separate=body.export_negative_separate,
        notes=body.notes,
        use_avatar=body.use_avatar,
        avatar_id=body.avatar_id,
        avatar_description=resolved_desc,
        avatar_secs_per_image=body.avatar_secs_per_image,
        avatar_max_images=body.avatar_max_images,
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

    st = read_image_prompt_writer_settings(work_dir)
    from videomaker.llm.avatar_prompt_writer import (
        AVATAR_DEFAULT_DESCRIPTION,
        generate_avatar_image_prompts,
    )

    # Prioridad: avatar_id del store > descripción manual guardada > default
    avatar_desc = str(st.get("avatar_description") or AVATAR_DEFAULT_DESCRIPTION).strip()
    saved_avatar_id = str(st.get("avatar_id") or "").strip()
    intro_enabled = False
    intro_character_name = "Nerd"
    outro_enabled = False
    outro_character_name = "Nerd"
    if saved_avatar_id:
        from videomaker.core.avatars_store import get_avatar
        av = get_avatar(saved_avatar_id)
        if av:
            avatar_desc = av["description"]
            intro_enabled = bool(av.get("intro_enabled", False))
            intro_character_name = str(av.get("intro_character_name") or av.get("name") or "Nerd")
            outro_enabled = bool(av.get("outro_enabled", False))
            outro_character_name = str(av.get("outro_character_name") or av.get("name") or "Nerd")
    secs = float(st.get("avatar_secs_per_image") or 6.0)
    max_imgs = int(st.get("avatar_max_images") or 80)
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
            _set_step(
                work_dir,
                "image_prompt_writer",
                state="done",
                detail=f"Avatar prompts generados: {result['prompt_count']} imágenes.",
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
    return {"exists": True, "manifest": data}


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
    p = work_dir / "pipeline" / "prompt.json"
    if not p.is_file():
        return {"exists": False}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"exists": False}
        return {"exists": True, "artifact": raw}
    except Exception:
        return {"exists": False}


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
        script_writer_template_id=body.script_writer_template_id,
        script_fragment_index=body.script_fragment_index,
        render_no_music=body.render_no_music,
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

class PromptTemplateFromTranscriptBody(BaseModel):
    transcript_text: str = Field(..., min_length=50)
    provider: str = "anthropic"
    model: str = ""


_TRANSCRIPT_SYSTEM = """
You are a YouTube channel strategy analyst and AI prompt engineer.

Your task: analyze a set of video transcripts from a single YouTube channel and produce a
structured JSON that captures the channel's identity and can be used as a Videomaker prompt template.

Return ONLY a valid JSON object (no markdown, no extra text) with this exact schema:
{
  "name": "<short template name, e.g. 'Nick Invests – Finanzas personales'>",
  "hook_style": "<how hooks open: question / data / story / shock / etc.>",
  "visual_style": "<visual tone: talking head + b-roll / whiteboard / motion graphics / etc.>",
  "tone": "<overall tone: educational / entertaining / conversational / energetic / etc.>",
  "system_instructions": "<3-6 sentences describing the channel's persona, narrative rules, and what the LLM must always do>",
  "user_instructions": "<3-6 sentences with specific content rules: topics, forbidden subjects, CTA style, pacing, opening/closing phrases>",
  "params_json": {
    "target_audience": "<describe the viewer: age, interests, pain points>",
    "language_context": {
      "code": "<BCP-47 code, e.g. es-ES>",
      "slang_level": "<low | medium | high>"
    },
    "narrative_structure": {
      "tone": "<pacing and narrative tone>",
      "hook_type": "<data-driven | question | story | shock | etc.>",
      "cta_type": "<subscribe | comment | like | share | none>"
    },
    "visual_identity": {
      "style": "<visual identity descriptor>",
      "aspect_ratio": "<16:9 | 9:16 | 1:1>"
    },
    "key_points": ["<recurring theme 1>", "<recurring theme 2>", "..."]
  }
}
""".strip()


@router.post("/prompt-templates/generate-from-transcript")
def api_prompt_template_generate_from_transcript(body: PromptTemplateFromTranscriptBody):
    """Analyzes transcript text with an LLM and returns a filled prompt template JSON."""
    from videomaker.llm.avatar_prompt_writer import _call_llm

    user_msg = (
        "Here are the video transcripts to analyze:\n\n"
        + body.transcript_text[:40_000]
        + "\n\nNow produce the JSON template as instructed."
    )

    raw = _call_llm(
        system=_TRANSCRIPT_SYSTEM,
        user=user_msg,
        provider=body.provider,
        model=body.model,
        temperature=0.4,
    )

    # Strip markdown fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"LLM did not return valid JSON: {exc}") from exc

    return result


# ── Generador de template Script Writer a partir de transcripciones ────────

class ScriptWriterTemplateFromTranscriptBody(BaseModel):
    transcript_text: str = Field(..., min_length=50)
    provider: str = "anthropic"
    model: str = ""


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
    "pacing": "<short | mixed | long>",
    "data_density": "<low | medium | high>",
    "structure_preset": "<four_act | default_five_blocks>",
    "narrative_preset": "<finanzas | entretenimiento | tutorial | ventas | (omit if unsure)>",
    "chunking": "<full_pass | sequential_fragments>"
  }
}

Guidelines:
- pacing: "short" for fast-cut punchy videos, "long" for documentary/essay style, "mixed" otherwise.
- data_density: "high" if the channel uses lots of numbers/statistics, "low" for storytelling/metaphor, "medium" otherwise.
- structure_preset: "four_act" (hook→promise→body→close) for finance/business; "default_five_blocks" for tutorial/entertainment.
- narrative_preset: choose the closest match from the list; omit the key if none fits.
- chunking: "sequential_fragments" for long-form content (>15 min), "full_pass" otherwise.
""".strip()


@router.post("/script-writer-templates/generate-from-transcript")
def api_sw_template_generate_from_transcript(body: ScriptWriterTemplateFromTranscriptBody):
    """Analyzes transcript text with an LLM and returns a filled Script Writer template JSON."""
    from videomaker.llm.avatar_prompt_writer import _call_llm

    user_msg = (
        "Here are the video transcripts to analyze:\n\n"
        + body.transcript_text[:40_000]
        + "\n\nNow produce the Script Writer JSON template as instructed."
    )

    raw = _call_llm(
        system=_SW_TRANSCRIPT_SYSTEM,
        user=user_msg,
        provider=body.provider,
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
