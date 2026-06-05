"""Tareas largas en background (compartidas por formularios HTML y API JSON)."""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

from videomaker.audio.narration import build_narration_wav
from videomaker.video.render import render_draft_video
from videomaker.llm.script_gen import generate_script
from videomaker.tts.voice_gen import synthesize_with_coqui
from videomaker.youtube.youtube_analyze import (
    YoutubeAnalyzeInputs,
    YoutubeChannelAnalyzeInputs,
    analyze_channel,
    analyze_youtube,
    resolve_channel_id,
)
from videomaker.core.script_bundle import write_script_bundle
from videomaker.pipeline.runner import run_pipeline
from videomaker.pipeline.models import PipelineInputs
from videomaker.youtube.channel_store import upsert_channel
from videomaker.youtube.channel_store import (
    insert_video_insights,
    touch_channel_synced,
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
    from videomaker.core.image_prompt_writer_settings_store import read_image_prompt_writer_settings

    st = read_image_prompt_writer_settings(work_dir)
    visual_mode = str(st.get("visual_mode") or "animation").strip().lower()
    include_broll = visual_mode != "static"

    try:
        set_status(work_dir, state="running", step="script", detail="Generando guion…")

        def _progress(detail: str) -> None:
            set_status(work_dir, state="running", step="script", detail=detail[:240])

        text = generate_script(
            bp,
            provider=provider,
            model=model,
            system_extra=system_extra or "",
            user_extra=user_extra or "",
            include_broll=include_broll,
            on_progress=_progress,
        )
        (work_dir / "guion.txt").write_text(text, encoding="utf-8")
        write_script_bundle(work_dir, text)
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


def run_render_draft(work: str, *, no_music: bool) -> None:
    work_dir = safe_work_dir(work)
    narr = work_dir / "narracion.wav"
    stock_dir = work_dir / "stock"
    if not narr.is_file():
        set_status(work_dir, state="error", step="render", detail="Falta narracion.wav")
        return
    try:
        from videomaker.video.render_progress import clear_render_progress, update_render_progress

        clear_render_progress(work_dir)

        def _on_progress(phase: str, current: int, total: int, message: str) -> None:
            update_render_progress(
                work_dir,
                kind="draft_mp4",
                phase=phase,
                current=current,
                total=total,
                message=message,
            )
            if phase == "segment" and total > 0:
                set_status(
                    work_dir,
                    state="running",
                    step="render",
                    detail=f"Render draft: plano {current}/{total} — {message}",
                )
            elif phase != "done":
                set_status(
                    work_dir,
                    state="running",
                    step="render",
                    detail=f"Render draft — {message}",
                )

        set_status(work_dir, state="running", step="render", detail="Render draft: iniciando…")
        render_draft_video(
            narr,
            stock_dir,
            work_dir / "draft.mp4",
            work_dir=work_dir,
            pick_music_from_project=not bool(no_music),
            render_no_music=bool(no_music),
            on_progress=_on_progress,
        )
        update_render_progress(
            work_dir,
            kind="draft_mp4",
            phase="done",
            current=1,
            total=1,
            message="Completado",
        )
        set_status(work_dir, state="done", step="render", detail="Vídeo listo.")
    except Exception as e:
        set_status(work_dir, state="error", step="render", detail=str(e))


def run_render_preview(
    work: str,
    *,
    no_music: bool,
    max_segments: int = 12,
    max_duration_s: float = 120.0,
) -> None:
    work_dir = safe_work_dir(work)
    if not (work_dir / "narracion.wav").is_file():
        set_status(work_dir, state="error", step="render", detail="Falta narracion.wav")
        return
    try:
        from videomaker.video.render import render_preview_video
        from videomaker.video.render_progress import clear_render_progress, update_render_progress

        clear_render_progress(work_dir)

        def _on_progress(phase: str, current: int, total: int, message: str) -> None:
            update_render_progress(
                work_dir,
                kind="preview_mp4",
                phase=phase,
                current=current,
                total=total,
                message=message,
            )
            if phase == "segment" and total > 0:
                set_status(
                    work_dir,
                    state="running",
                    step="render",
                    detail=f"Preview MP4: plano {current}/{total} — {message}",
                )
            elif phase == "encode":
                set_status(
                    work_dir,
                    state="running",
                    step="render",
                    detail=f"Preview MP4: codificando… ({message})",
                )
            elif phase != "done":
                set_status(
                    work_dir,
                    state="running",
                    step="render",
                    detail=f"Preview MP4 — {message}",
                )

        set_status(
            work_dir,
            state="running",
            step="render",
            detail=f"Preview MP4: iniciando (hasta {max_segments} planos)…",
        )
        render_preview_video(
            work_dir,
            max_segments=max_segments,
            max_duration_s=max_duration_s,
            no_music=bool(no_music),
            on_progress=_on_progress,
        )
        update_render_progress(
            work_dir,
            kind="preview_mp4",
            phase="done",
            current=1,
            total=1,
            message="Completado",
        )
        set_status(work_dir, state="done", step="render", detail="Preview MP4 listo (preview_draft.mp4).")
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


def run_channel_scan_lite(work: str, *, channel_id: str, max_videos: int = 50) -> None:
    """
    Discovery scan (lite): fetch last N videos + stats only (no transcript, no LLM).
    Persists channel snapshot + videos so opportunity metrics can be computed.
    """
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_log = work_dir / f"channel_{channel_id}_scan.log"
    try:
        set_status(work_dir, state="running", step="channel_scan", detail=f"Scan (lite) {channel_id}…")
        from videomaker.youtube.youtube_analyze import enrich_channels_stats, enrich_videos_metadata, enrich_videos_snippet, list_channel_videos

        # Channel basics + snapshot
        stats = enrich_channels_stats([channel_id]).get(channel_id) or {}
        upsert_channel(
            channel_id=channel_id,
            handle=(stats.get("handle") or None),
            title=(stats.get("title") or ""),
            avatar_url=(stats.get("avatar_url") or None),
            description=(stats.get("description") or None),
        )
        upsert_channel_snapshot(
            channel_id,
            subscribers=int(stats.get("subscribers") or 0) or None,
            total_views=int(stats.get("total_views") or 0) or None,
            video_count=int(stats.get("video_count") or 0) or None,
        )

        vids = list_channel_videos(channel_id, max_videos=int(max_videos))
        ids = [v.get("video_id") for v in vids if isinstance(v, dict) and v.get("video_id")]
        meta = enrich_videos_metadata(ids)
        snips = enrich_videos_snippet(ids)

        to_upsert = []
        for vid in ids:
            md = meta.get(vid) or {}
            sn = snips.get(vid) or {}
            to_upsert.append(
                {
                    "video_id": vid,
                    "title": md.get("title") or sn.get("title") or "",
                    "published_at": md.get("published_at"),
                    "duration_s": md.get("duration_s"),
                    "views": md.get("views"),
                    "likes": md.get("likes"),
                    "comments": md.get("comments"),
                    "thumbnail_url": sn.get("thumbnail_url"),
                    "description": md.get("description") or "",
                    "tags": md.get("tags") or [],
                    "category_id": md.get("category_id") or "",
                    "default_language": md.get("default_language") or "",
                    "default_audio_language": md.get("default_audio_language") or "",
                }
            )
        upsert_videos(channel_id, to_upsert)

        out_log.write_text(f"ok channel_id={channel_id} videos={len(to_upsert)}\n", encoding="utf-8")
        set_status(work_dir, state="done", step="channel_scan", detail="Scan (lite) listo.")
    except Exception as e:
        out_log.write_text(str(e), encoding="utf-8")
        set_status(work_dir, state="error", step="channel_scan", detail=str(e))


def run_channel_sync(work: str, *, channel_id: str, max_videos: int = 50, lang: str = "es") -> None:
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
        # IMPORTANT: Sync should NOT depend on LLM (Ollama/OpenAI). We persist channel stats + videos first.
        from videomaker.youtube.youtube_analyze import (
            enrich_channels_stats,
            enrich_videos_metadata,
            enrich_videos_snippet,
            list_channel_videos,
        )

        resolved = resolve_channel_id(channel_id) if isinstance(channel_id, str) and not channel_id.startswith("UC") else {"channel_id": channel_id}
        cid = (resolved.get("channel_id") or channel_id) if isinstance(resolved, dict) else channel_id

        # Channel basics + snapshot
        stats = enrich_channels_stats([cid]).get(cid) or {}
        upsert_channel(
            channel_id=cid,
            handle=(stats.get("handle") or resolved.get("handle") or None) if isinstance(resolved, dict) else (stats.get("handle") or None),
            title=(stats.get("title") or resolved.get("title") or "") if isinstance(resolved, dict) else (stats.get("title") or ""),
            avatar_url=(stats.get("avatar_url") or None),
            description=(stats.get("description") or None),
        )
        upsert_channel_snapshot(
            cid,
            subscribers=int(stats.get("subscribers") or 0) or None,
            total_views=int(stats.get("total_views") or 0) or None,
            video_count=int(stats.get("video_count") or 0) or None,
        )

        vids = list_channel_videos(cid, max_videos=int(max_videos))
        ids = [v.get("video_id") for v in vids if isinstance(v, dict) and v.get("video_id")]
        meta = enrich_videos_metadata(ids)
        snips = enrich_videos_snippet(ids)
        to_upsert = []
        for vid in ids:
            md = meta.get(vid) or {}
            sn = snips.get(vid) or {}
            to_upsert.append(
                {
                    "video_id": vid,
                    "title": md.get("title") or sn.get("title") or "",
                    "published_at": md.get("published_at"),
                    "duration_s": md.get("duration_s"),
                    "views": md.get("views"),
                    "likes": md.get("likes"),
                    "comments": md.get("comments"),
                    "thumbnail_url": sn.get("thumbnail_url"),
                    "description": md.get("description") or "",
                    "tags": md.get("tags") or [],
                    "category_id": md.get("category_id") or "",
                    "default_language": md.get("default_language") or "",
                    "default_audio_language": md.get("default_audio_language") or "",
                }
            )

        upsert_videos(cid, to_upsert)

        report = {
            "channel_id": cid,
            "resolved": resolved,
            "stats": stats,
            "videos": to_upsert,
            "note": "sync_lite (no LLM insights)",
        }
        out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        out_log.write_text(f"ok channel_id={cid} videos={len(to_upsert)}\n", encoding="utf-8")
        try:
            touch_channel_synced(cid)
        except Exception:
            pass
        set_status(work_dir, state="done", step="channel_sync", detail=f"Sync listo: {cid}")
    except Exception as e:
        out_log.write_text(f"{e}\n\n{traceback.format_exc()}\n", encoding="utf-8")
        set_status(work_dir, state="error", step="channel_sync", detail=f"{channel_id}: {e}")
        raise


def run_channel_videos_backfill(work: str, *, channel_id: str, limit: int = 200) -> None:
    """
    Backfill description/tags/category/lang for already-stored videos of a channel.
    Useful for channels saved before we started persisting snippet fields.
    """
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_log = work_dir / f"channel_{channel_id}_backfill.log"
    try:
        set_status(work_dir, state="running", step="channel_backfill", detail=f"Backfill vídeos {channel_id}…")
        from videomaker import db
        from videomaker.youtube.channel_store import upsert_videos
        from videomaker.youtube.youtube_analyze import enrich_videos_metadata

        limit = max(1, min(int(limit), 500))
        ids_rows = db.fetch_all(
            """
            select video_id
            from videos
            where channel_id = %(cid)s
            order by published_at desc nulls last
            limit %(limit)s
            """,
            {"cid": channel_id, "limit": limit},
        )
        ids = [r.get("video_id") for r in ids_rows if isinstance(r, dict) and r.get("video_id")]
        if not ids:
            out_log.write_text("no videos found\n", encoding="utf-8")
            set_status(work_dir, state="done", step="channel_backfill", detail=f"Backfill: no había vídeos ({channel_id}).")
            return

        existing_rows = db.fetch_all(
            """
            select video_id, title, published_at, duration_s, views, likes, comments, thumbnail_url
            from videos
            where video_id = any(%(ids)s)
            """,
            {"ids": ids},
        )
        existing = {r["video_id"]: r for r in existing_rows if isinstance(r, dict) and r.get("video_id")}

        meta = enrich_videos_metadata(ids)
        to_upsert = []
        filled = 0
        for vid in ids:
            base = existing.get(vid) or {"video_id": vid}
            md = meta.get(vid) or {}
            desc = md.get("description") or ""
            tags = md.get("tags") or []
            if desc or tags:
                filled += 1
            to_upsert.append(
                {
                    "video_id": vid,
                    "title": md.get("title") or base.get("title") or "",
                    "published_at": md.get("published_at") or base.get("published_at"),
                    "duration_s": md.get("duration_s") or base.get("duration_s"),
                    "views": md.get("views") or base.get("views"),
                    "likes": md.get("likes") or base.get("likes"),
                    "comments": md.get("comments") or base.get("comments"),
                    "thumbnail_url": base.get("thumbnail_url"),
                    "description": desc,
                    "tags": tags,
                    "category_id": md.get("category_id") or "",
                    "default_language": md.get("default_language") or "",
                    "default_audio_language": md.get("default_audio_language") or "",
                }
            )
        upsert_videos(channel_id, to_upsert)

        out_log.write_text(f"ok channel_id={channel_id} videos={len(ids)} filled={filled}\n", encoding="utf-8")
        set_status(work_dir, state="done", step="channel_backfill", detail=f"Backfill listo ({channel_id}): {filled}/{len(ids)}.")
    except Exception as e:
        out_log.write_text(f"{e}\n\n{traceback.format_exc()}\n", encoding="utf-8")
        set_status(work_dir, state="error", step="channel_backfill", detail=f"{channel_id}: {e}")
        raise


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
    prompt_template_id: str | None = None,
    prompt_topic: str | None = None,
    prompt_video_restrictions: str | None = None,
    script_writer_template_id: str | None = None,
    script_fragment_index: int | None = None,
    render_no_music: bool | None = None,
    topic_generator_transcript: str | None = None,
    topic_generator_niche_trends: str | None = None,
    topic_generator_topic_count: int | None = None,
) -> None:
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    from videomaker.llm.output_language import resolve_pipeline_lang

    resolved_lang = resolve_pipeline_lang(work_dir, request_lang=lang or None)
    tid = (prompt_template_id or "").strip() or None
    sw_tid = (script_writer_template_id or "").strip() or None
    pt = "" if prompt_topic is None else str(prompt_topic).strip()
    pvr = "" if prompt_video_restrictions is None else str(prompt_video_restrictions).strip()
    rnm = False if render_no_music is None else bool(render_no_music)
    from videomaker.pipeline.duration_policy import clamp_pipeline_minutes

    inputs = PipelineInputs(
        keywords=keywords,
        context=context,
        lang=resolved_lang,
        minutes=clamp_pipeline_minutes(minutes),
        provider=provider or "",
        model=model or "",
        prompt_template_id=tid,
        prompt_topic=pt,
        prompt_video_restrictions=pvr,
        script_writer_template_id=sw_tid,
        script_fragment_index=script_fragment_index,
        render_no_music=rnm,
        topic_generator_transcript="" if topic_generator_transcript is None else str(topic_generator_transcript),
        topic_generator_niche_trends="" if topic_generator_niche_trends is None else str(topic_generator_niche_trends),
        topic_generator_topic_count=8 if topic_generator_topic_count is None else int(topic_generator_topic_count),
    )
    run_pipeline(work_dir, inputs, rerun_step_id=step_id)
