"""Tareas largas en background (compartidas por formularios HTML y API JSON)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from videomaker.audio.audio_concat import wav_duration_seconds
from videomaker.stock.keyword_planner import plan_stock_keywords
from videomaker.audio.narration import build_narration_wav
from videomaker.video.render import render_draft_video
from videomaker.llm.script_gen import generate_script
from videomaker.stock.stock_download import download_stock_for_queries
from videomaker.stock.stock_pexels import PexelsClient
from videomaker.tts.voice_gen import synthesize_with_coqui
from videomaker.youtube.youtube_analyze import (
    YoutubeAnalyzeInputs,
    YoutubeChannelAnalyzeInputs,
    analyze_channel,
    analyze_youtube,
    resolve_channel_id,
)
from videomaker.pipeline.runner import run_pipeline
from videomaker.pipeline.models import PipelineInputs
from videomaker.youtube.channel_store import upsert_channel
from videomaker.youtube.channel_store import (
    insert_video_insights,
    upsert_channel_snapshot,
    upsert_videos,
 )

from .io_util import finalize_new_narration, safe_work_dir, set_status, voice_profile_for_work


def run_voice_preview(work: str, preset: str, text: str) -> None:
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    profile = voice_profile_for_work(work_dir, preset)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = work_dir / f"preview_voice_{preset}_{ts}.wav"
    try:
        set_status(work_dir, state="running", step="voice_preview", detail="Generando muestra de voz…")
        synthesize_with_coqui(text, profile, out)
        set_status(work_dir, state="done", step="voice_preview", detail="Muestra lista.")
    except Exception as e:
        set_status(work_dir, state="error", step="voice_preview", detail=str(e))


def run_generate_script(
    work: str,
    *,
    keywords: str,
    context: str,
    lang: str,
    minutes: float,
    provider: str | None,
    model: str | None,
    system_extra: str = "",
    user_extra: str = "",
) -> None:
    from videomaker.core.models import ScriptBlueprint

    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    from .io_util import parse_locale

    bp = ScriptBlueprint(
        keywords=[k.strip() for k in keywords.split(",") if k.strip()],
        extra_context=context or "",
        locale=parse_locale(lang),
        target_minutes=float(minutes),
    )

    try:
        set_status(work_dir, state="running", step="script", detail="Generando guion…")
        text = generate_script(
            bp,
            provider=provider,
            model=model,
            system_extra=system_extra or "",
            user_extra=user_extra or "",
        )
        (work_dir / "guion.txt").write_text(text, encoding="utf-8")
        set_status(work_dir, state="done", step="script", detail="Guion listo.")
    except Exception as e:
        set_status(work_dir, state="error", step="script", detail=str(e))


def run_speak_script(
    work: str,
    *,
    preset: str,
    max_chars: int,
    max_segments: int,
) -> None:
    work_dir = safe_work_dir(work)
    script_path = work_dir / "guion.txt"
    if not script_path.is_file():
        set_status(work_dir, state="error", step="tts", detail="No hay guion.txt")
        return
    profile = voice_profile_for_work(work_dir, preset)
    script = script_path.read_text(encoding="utf-8")
    lim = int(max_segments) if int(max_segments) > 0 else None
    try:
        set_status(work_dir, state="running", step="tts", detail="Generando narración (TTS)…")
        build_narration_wav(
            script,
            profile,
            work_dir,
            max_chars_per_segment=int(max_chars),
            max_segments=lim,
        )
        finalize_new_narration(work_dir)
        set_status(work_dir, state="done", step="tts", detail="Narración lista.")
    except Exception as e:
        set_status(work_dir, state="error", step="tts", detail=str(e))


def run_stock_fetch(work: str, *, lang: str, max_clips: int) -> None:
    work_dir = safe_work_dir(work)
    script_path = work_dir / "guion.txt"
    if not script_path.is_file():
        set_status(work_dir, state="error", step="stock", detail="No hay guion.txt")
        return
    script = script_path.read_text(encoding="utf-8")
    narration = work_dir / "narracion.wav"
    audio_s = None
    if narration.is_file():
        audio_s = wav_duration_seconds(narration)
    try:
        set_status(work_dir, state="running", step="stock", detail="Descargando stock (Pexels)…")
        plan = plan_stock_keywords(script, audio_duration_s=audio_s, lang_hint=lang)
        client = PexelsClient()
        stock_dir = work_dir / "stock"
        download_stock_for_queries(client, plan, stock_dir, max_downloads=int(max_clips))
        set_status(work_dir, state="done", step="stock", detail="Stock listo.")
    except Exception as e:
        set_status(work_dir, state="error", step="stock", detail=str(e))


def run_render_draft(work: str, *, no_music: bool) -> None:
    work_dir = safe_work_dir(work)
    narr = work_dir / "narracion.wav"
    stock_dir = work_dir / "stock"
    if not narr.is_file() or not stock_dir.is_dir():
        set_status(work_dir, state="error", step="render", detail="Falta narracion.wav o carpeta stock/")
        return
    try:
        set_status(work_dir, state="running", step="render", detail="Renderizando vídeo (MoviePy)…")
        render_draft_video(
            narr,
            stock_dir,
            work_dir / "draft.mp4",
            pick_music_from_project=not bool(no_music),
        )
        set_status(work_dir, state="done", step="render", detail="Vídeo listo.")
    except Exception as e:
        set_status(work_dir, state="error", step="render", detail=str(e))


def run_analyze_youtube(work: str, *, url: str, lang: str) -> None:
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_json = work_dir / "analyze_youtube.json"
    out_log = work_dir / "analyze_youtube.log"
    try:
        set_status(work_dir, state="running", step="analyze", detail="Analizando YouTube…")
        report, log_text = analyze_youtube(YoutubeAnalyzeInputs(url=url, lang=lang))
        out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        out_log.write_text(log_text, encoding="utf-8")
        set_status(work_dir, state="done", step="analyze", detail="Análisis listo.")
    except Exception as e:
        out_log.write_text(str(e), encoding="utf-8")
        set_status(work_dir, state="error", step="analyze", detail=str(e))


def run_analyze_channel(work: str, *, channel: str, lang: str, max_videos: int) -> None:
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_json = work_dir / "analyze_channel.json"
    out_log = work_dir / "analyze_channel.log"
    try:
        set_status(work_dir, state="running", step="analyze_channel", detail="Analizando canal de YouTube…")
        report, log_text = analyze_channel(
            YoutubeChannelAnalyzeInputs(channel=channel, lang=lang, max_videos=int(max_videos))
        )
        out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        out_log.write_text(log_text, encoding="utf-8")
        set_status(work_dir, state="done", step="analyze_channel", detail="Análisis de canal listo.")
    except Exception as e:
        out_log.write_text(str(e), encoding="utf-8")
        set_status(work_dir, state="error", step="analyze_channel", detail=str(e))


def run_channel_sync(work: str, *, channel_id: str, max_videos: int = 25, lang: str = "es") -> None:
    """
    Sincroniza un canal guardado: refresca métricas + lista de vídeos + insights para N vídeos recientes.
    (MVP) Reutiliza analyze_channel y luego el UI consume el JSON o se migra a tablas.
    """
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_json = work_dir / f"channel_{channel_id}_sync.json"
    out_log = work_dir / f"channel_{channel_id}_sync.log"
    try:
        set_status(work_dir, state="running", step="channel_sync", detail=f"Sync canal {channel_id}…")
        # analyze_channel acepta input genérico; aquí pasamos channel_id directamente.
        report, log_text = analyze_channel(
            YoutubeChannelAnalyzeInputs(channel=channel_id, lang=lang, max_videos=int(max_videos))
        )
        # Persistimos el canal base si no existía.
        resolved = report.get("resolved") or {}
        upsert_channel(
            channel_id=report.get("channel_id") or channel_id,
            handle=(resolved.get("handle") or None),
            title=(resolved.get("title") or ""),
            avatar_url=None,
        )
        # snapshot canal
        try:
            meta = resolve_channel_id(channel_id) if isinstance(channel_id, str) and not channel_id.startswith("UC") else {"channel_id": channel_id}
            # enriquecemos stats de canal con channels.list
            from videomaker.youtube.youtube_analyze import enrich_channels_stats

            stats = enrich_channels_stats([report.get("channel_id") or channel_id]).get(report.get("channel_id") or channel_id) or {}
            upsert_channel_snapshot(
                report.get("channel_id") or channel_id,
                subscribers=int(stats.get("subscribers") or 0) or None,
                total_views=int(stats.get("total_views") or 0) or None,
                video_count=int(stats.get("video_count") or 0) or None,
            )
        except Exception:
            pass

        # videos + insights
        videos = report.get("videos") or []
        # enriquecer thumbnails
        from videomaker.youtube.youtube_analyze import enrich_videos_snippet

        snips = enrich_videos_snippet([v.get("video_id") for v in videos if isinstance(v, dict) and v.get("video_id")])
        to_upsert = []
        for v in videos:
            if not isinstance(v, dict):
                continue
            vid = v.get("video_id") or ""
            if not vid:
                continue
            sn = snips.get(vid) or {}
            to_upsert.append(
                {
                    "video_id": vid,
                    "title": v.get("title") or sn.get("title") or "",
                    "published_at": v.get("published_at"),
                    "duration_s": v.get("duration_s"),
                    "views": v.get("views"),
                    "likes": v.get("likes"),
                    "comments": v.get("comments"),
                    "thumbnail_url": sn.get("thumbnail_url"),
                }
            )
            ins = v.get("insights")
            if isinstance(ins, dict):
                try:
                    insert_video_insights(vid, ins)
                except Exception:
                    pass
        try:
            upsert_videos(report.get("channel_id") or channel_id, to_upsert)
        except Exception:
            pass
        out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        out_log.write_text(log_text, encoding="utf-8")
        set_status(work_dir, state="done", step="channel_sync", detail="Sync listo.")
    except Exception as e:
        out_log.write_text(str(e), encoding="utf-8")
        set_status(work_dir, state="error", step="channel_sync", detail=str(e))


def run_create_pipeline(
    work: str,
    *,
    keywords: str,
    context: str,
    lang: str,
    minutes: float,
    provider: str,
    model: str,
    step_id: str | None = None,
) -> None:
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    inputs = PipelineInputs(
        keywords=keywords,
        context=context,
        lang=lang,
        minutes=float(minutes),
        provider=provider or "",
        model=model or "",
    )
    run_pipeline(work_dir, inputs, rerun_step_id=step_id)
