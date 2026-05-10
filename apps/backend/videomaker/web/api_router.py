"""API JSON para la SPA (React). Las rutas HTML clásicas siguen en `app.py`."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

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


class StockFetchBody(WorkModel):
    lang: str = "es"
    max_clips: int = 25


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


class ScriptFragmentationPatchBody(WorkModel):
    index: int = Field(..., ge=0)
    complete: bool = True


class ScriptUpdateBody(WorkModel):
    text: str = Field(default="", description="Contenido completo de guion.txt")


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
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "guion.txt").write_text(body.text, encoding="utf-8")
    pipe = work_dir / "pipeline" / "script.txt"
    pipe.parent.mkdir(parents=True, exist_ok=True)
    pipe.write_text(body.text, encoding="utf-8")
    write_script_bundle(work_dir, body.text)
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


@router.post("/stock-fetch", status_code=202)
def api_stock_fetch(background: BackgroundTasks, body: StockFetchBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not (work_dir / "guion.txt").is_file():
        raise HTTPException(status_code=400, detail="No existe guion.txt.")
    background.add_task(
        jobs.run_stock_fetch,
        body.work,
        lang=body.lang,
        max_clips=body.max_clips,
    )
    return {"started": True, "step": "stock"}


@router.post("/render-draft", status_code=202)
def api_render_draft(background: BackgroundTasks, body: RenderDraftBody):
    try:
        work_dir = safe_work_dir(body.work)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not (work_dir / "narracion.wav").is_file() or not (work_dir / "stock").is_dir():
        raise HTTPException(status_code=400, detail="Falta narracion.wav o carpeta stock/.")
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
