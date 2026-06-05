"""Montaje draft: narración + imágenes del pipeline, vídeo legacy en stock/, o solo audio sobre fondo."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from videomaker.audio.audio_concat import wav_duration_seconds
from videomaker.audio.audio_music import pick_random_track
from videomaker.video.render_progress import ProgressCallback
from .video_editor import assemble_from_image_files, assemble_from_narration_only, assemble_from_stock_files


def list_stock_videos(stock_dir: Path) -> list[Path]:
    exts = {".mp4", ".mov", ".m4v", ".webm"}
    if not stock_dir.is_dir():
        return []
    return sorted(p for p in stock_dir.iterdir() if p.suffix.lower() in exts)


_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def _intensity_to_cut_s(intensity: int) -> float:
    i = max(0, min(int(intensity), 100))
    if i >= 85:
        return 3.0
    if i >= 70:
        return 4.0
    if i >= 55:
        return 5.0
    return 6.0


def _cut_schedule_from_beats(beats: list[dict[str, Any]], *, target_dur: float) -> dict[str, Any]:
    timed: list[dict[str, Any]] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        try:
            start_s = float(b["start_s"])
            end_s = float(b["end_s"])
        except (KeyError, TypeError, ValueError):
            continue
        if end_s <= start_s:
            continue
        beat = str(b.get("beat") or "").strip() or None
        try:
            inten = int(float(b.get("intensity")))
        except Exception:
            inten = 55
        timed.append(
            {
                "beat": beat,
                "intensity": max(0, min(inten, 100)),
                "start_s": start_s,
                "end_s": end_s,
                "cut_s": round(end_s - start_s, 3),
            }
        )
    if timed and target_dur > 0:
        cuts: list[dict[str, Any]] = []
        idx = 0
        t = 0.0
        guard = 0
        while t < target_dur and guard < 100_000:
            row = timed[idx % len(timed)]
            dur = float(row["cut_s"])
            t2 = min(target_dur, t + dur)
            cuts.append(
                {
                    "t_start": round(t, 3),
                    "t_end": round(t2, 3),
                    "duration_s": round(t2 - t, 3),
                    "intensity": int(row["intensity"]),
                    "beat": row.get("beat"),
                    "anchor_start_s": row.get("start_s"),
                    "anchor_end_s": row.get("end_s"),
                }
            )
            t = t2
            idx += 1
            guard += 1
        return {"source": "music_plan.beats.timed", "cuts": cuts, "base": timed}

    base: list[dict[str, Any]] = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        beat = str(b.get("beat") or "").strip() or None
        try:
            inten = int(float(b.get("intensity")))
        except Exception:
            inten = 55
        cut_s = _intensity_to_cut_s(inten)
        base.append({"beat": beat, "intensity": max(0, min(inten, 100)), "cut_s": cut_s})
        if len(base) >= 24:
            break
    if not base or target_dur <= 0:
        return {"source": "music_plan.beats", "cuts": []}
    cuts = []
    t = 0.0
    idx = 0
    guard = 0
    while t < target_dur and guard < 100_000:
        row = base[idx % len(base)]
        dur = float(row["cut_s"])
        t2 = min(target_dur, t + dur)
        cuts.append(
            {
                "t_start": round(t, 3),
                "t_end": round(t2, 3),
                "duration_s": round(t2 - t, 3),
                "intensity": int(row["intensity"]),
                "beat": row.get("beat"),
            }
        )
        t = t2
        idx += 1
        guard += 1
    return {"source": "music_plan.beats", "cuts": cuts, "base": base}


def _resolve_paths_from_manifest_rows(
    images_dir: Path, rows: list[dict[str, Any]]
) -> tuple[list[Path], list[dict[str, Any]]]:
    out_paths: list[Path] = []
    out_rows: list[dict[str, Any]] = []
    for x in rows:
        fn = x.get("filename")
        if not fn or not isinstance(fn, str):
            continue
        safe = Path(fn).name
        if Path(safe).suffix.lower() not in _IMAGE_EXTS:
            continue
        p = (images_dir / safe).resolve()
        try:
            p.relative_to(images_dir.resolve())
        except ValueError:
            continue
        if p.is_file():
            out_paths.append(p)
            out_rows.append(x)
    return out_paths, out_rows


def _load_selected_manifest_rows(work_dir: Path) -> list[dict[str, Any]] | None:
    manifest = work_dir / "pipeline" / "images_generation.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        rows = [x for x in (data.get("images") or []) if isinstance(x, dict)]
        rows = [
            x
            for x in rows
            if x.get("selected", True) is not False
            and str(x.get("role") or "") != "thumbnail"
        ]
        rows.sort(key=lambda x: int(x.get("order", 0) or 0))
        return rows
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def resolve_pipeline_image_paths(work_dir: Path) -> list[Path]:
    """
    Lista rutas absolutas de imágenes para el montaje.

    Si existe ``pipeline/images_generation.json``, usa las entradas con
    ``selected: true`` ordenadas por ``order`` y resuelve ``filename`` bajo
    ``pipeline/images/``. Si no, ordena por nombre todos los PNG/JPG en esa carpeta.
    """
    images_dir = work_dir / "pipeline" / "images"
    rows = _load_selected_manifest_rows(work_dir)
    if rows:
        paths, _ = _resolve_paths_from_manifest_rows(images_dir, rows)
        if paths:
            return paths

    if not images_dir.is_dir():
        return []
    return sorted(
        (p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTS),
        key=lambda p: p.name.lower(),
    )


def resolve_segment_camera_motions(manifest_rows: list[dict[str, Any]]) -> list[str] | None:
    """Movimiento Ken Burns por plano (push_in / pull_out / static), alineado al manifest."""
    if not manifest_rows:
        return None
    from videomaker.video.video_editor import normalize_camera_motion

    motions: list[str] = []
    for row in manifest_rows:
        raw = row.get("camera_motion")
        if not raw:
            meta = row.get("text_metadata")
            if isinstance(meta, dict):
                raw = meta.get("camera_motion") or meta.get("motion")
        motions.append(normalize_camera_motion(str(raw or "push_in")))
    return motions if len(motions) == len(manifest_rows) else None


def resolve_segment_durations_s(
    work_dir: Path, manifest_rows: list[dict[str, Any]]
) -> list[float] | None:
    """
    Duración en segundos por imagen seleccionada, alineada con ``narracion.wav`` unificado.

    Usa ``duration_ms`` del Scene Editor (+ silencio entre bloques si ``SCENE_AUDIO_CHUNK_GAP_MS``).
    Si falta en un bloque, lee el MP3 en ``scene_audio/`` o ``duration_hint_s`` del manifest.
    """
    if not manifest_rows:
        return None

    from videomaker.scene_editor.audio_service import (
        _chunk_gap_ms,
        _duration_ms_from_audio,
        resolve_chunk_audio_file,
    )
    from videomaker.scene_editor.store import read_chunks

    chunks = read_chunks(work_dir)
    by_id: dict[str, Any] = {}
    by_stem: dict[str, Any] = {}
    if chunks:
        for c in chunks:
            by_id[c.id] = c
            by_stem[Path(c.id).name] = c

    gap_s = _chunk_gap_ms(None) / 1000.0
    durs: list[float] = []

    for i, row in enumerate(manifest_rows):
        cid = str(row.get("prompt_id") or row.get("id") or "").strip()
        chunk = by_id.get(cid) or by_stem.get(Path(cid).name) if cid else None

        row_ms = row.get("duration_ms")
        if isinstance(row_ms, (int, float)) and float(row_ms) > 0:
            ms = int(row_ms)
        else:
            ms = None

        if (ms is None or ms <= 0) and chunk is not None:
            raw_ms = chunk.duration_ms
            if isinstance(raw_ms, int) and raw_ms > 0:
                ms = raw_ms
            else:
                audio_p = resolve_chunk_audio_file(work_dir, chunk.id)
                if audio_p is not None:
                    ms = _duration_ms_from_audio(audio_p) or None

        if ms is None or ms <= 0:
            hint = row.get("duration_hint_s")
            if isinstance(hint, (int, float)) and float(hint) > 0:
                dur = float(hint)
            else:
                return None
        else:
            dur = ms / 1000.0

        if i < len(manifest_rows) - 1:
            dur += gap_s
        durs.append(max(0.05, dur))

    return durs if len(durs) == len(manifest_rows) else None


def _trim_assembly_for_preview(
    image_paths: list[Path],
    segment_durations_s: list[float] | None,
    *,
    max_segments: int | None,
    max_duration_s: float | None,
    segment_motions: list[str] | None = None,
) -> tuple[list[Path], list[float] | None, float | None, list[str] | None]:
    """Recorta planos y devuelve tope de duración de narración para preview MP4."""
    paths = list(image_paths)
    segs = list(segment_durations_s) if segment_durations_s else None
    motions = list(segment_motions) if segment_motions else None

    if max_segments is not None and max_segments > 0 and len(paths) > max_segments:
        paths = paths[:max_segments]
        if segs:
            segs = segs[:max_segments]
        if motions:
            motions = motions[:max_segments]

    cap: float | None = None
    if segs and max_duration_s is not None and max_duration_s > 0:
        acc = 0.0
        trimmed_paths: list[Path] = []
        trimmed_segs: list[float] = []
        trimmed_motions: list[str] = []
        for i, (p, s) in enumerate(zip(paths, segs)):
            if trimmed_paths and acc + s > max_duration_s:
                break
            trimmed_paths.append(p)
            trimmed_segs.append(s)
            if motions and i < len(motions):
                trimmed_motions.append(motions[i])
            acc += s
        paths, segs = trimmed_paths, trimmed_segs
        if trimmed_motions:
            motions = trimmed_motions
        cap = acc
    elif max_duration_s is not None and max_duration_s > 0:
        cap = float(max_duration_s)

    return paths, segs, cap, motions


def build_render_preview_timeline(work_dir: Path, work_slug: str) -> dict[str, Any]:
    """
    Timeline para preview en navegador: imagen + audio por bloque (sin codificar MP4).
    """
    from urllib.parse import quote

    from videomaker.scene_editor.audio_service import (
        _chunk_gap_ms,
        _duration_ms_from_audio,
        resolve_chunk_audio_file,
    )
    from videomaker.scene_editor.store import read_chunks

    rows = _load_selected_manifest_rows(work_dir)
    if not rows:
        return {
            "ok": False,
            "error": "No hay imágenes seleccionadas en images_generation.json.",
            "segments": [],
        }

    images_dir = work_dir / "pipeline" / "images"
    paths, resolved_rows = _resolve_paths_from_manifest_rows(images_dir, rows)
    if not paths:
        return {
            "ok": False,
            "error": "No hay archivos de imagen en pipeline/images/.",
            "segments": [],
        }

    chunks = read_chunks(work_dir) or []
    by_id = {c.id: c for c in chunks}
    by_stem = {Path(c.id).name: c for c in chunks}
    gap_ms = _chunk_gap_ms(None)
    work_q = quote(work_slug, safe="")

    segments: list[dict[str, Any]] = []
    for row in resolved_rows:
        cid = str(row.get("prompt_id") or row.get("id") or "").strip()
        chunk = by_id.get(cid) or by_stem.get(Path(cid).name) if cid else None
        fn = Path(str(row.get("filename") or "")).name
        if not fn:
            continue

        ms: int | None = None
        has_audio = False
        narration_text = ""
        if chunk is not None:
            narration_text = (chunk.narration_text or "").strip()
            if isinstance(chunk.duration_ms, int) and chunk.duration_ms > 0:
                ms = chunk.duration_ms
            audio_p = resolve_chunk_audio_file(work_dir, chunk.id)
            if audio_p is not None:
                has_audio = True
                if not ms or ms <= 0:
                    ms = _duration_ms_from_audio(audio_p) or None
        if not has_audio and cid:
            has_audio = resolve_chunk_audio_file(work_dir, cid) is not None

        if ms is None or ms <= 0:
            hint = row.get("duration_hint_s")
            if isinstance(hint, (int, float)) and float(hint) > 0:
                ms = int(float(hint) * 1000)
            else:
                ms = 10_000

        audio_url = None
        if has_audio and cid:
            audio_url = f"/api/audio/chunk-file?work={work_q}&chunk_id={quote(cid, safe='')}"

        segments.append(
            {
                "order": int(row.get("order") or len(segments) + 1),
                "chunk_id": cid,
                "filename": fn,
                "image_url": (
                    f"/api/pipeline/images-generation/image"
                    f"?work={work_q}&filename={quote(fn, safe='')}"
                ),
                "audio_url": audio_url,
                "duration_ms": ms,
                "narration_text": narration_text[:500],
                "scene_description_es": str(row.get("scene_description_es") or "")[:240],
                "has_audio": bool(audio_url),
            }
        )

    segments.sort(key=lambda s: int(s.get("order") or 0))
    total_ms = sum(int(s["duration_ms"]) for s in segments)
    if len(segments) > 1:
        total_ms += gap_ms * (len(segments) - 1)

    return {
        "ok": True,
        "segment_count": len(segments),
        "chunk_gap_ms": gap_ms,
        "total_duration_ms": total_ms,
        "segments": segments,
    }


def render_preview_video(
    work_dir: Path,
    *,
    max_segments: int = 12,
    max_duration_s: float = 120.0,
    no_music: bool = True,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """MP4 corto (720p, ultrafast) con Ken Burns y sync por bloque — como el draft, menos planos."""
    narr = work_dir / "narracion.wav"
    if not narr.is_file():
        raise FileNotFoundError("Falta narracion.wav.")
    return render_draft_video(
        narr,
        work_dir / "stock",
        work_dir / "preview_draft.mp4",
        work_dir=work_dir,
        pick_music_from_project=not bool(no_music),
        render_no_music=bool(no_music),
        frame_size=(1280, 720),
        max_segments=max_segments,
        max_duration_s=max_duration_s,
        fast_preview=True,
        persist_artifact=True,
        preview_mode=True,
        on_progress=on_progress,
    )


def _resolve_image_assembly_timing(
    work_dir: Path,
    img_paths: list[Path],
    *,
    beat_schedule: list[dict[str, Any]] | None,
) -> tuple[list[float] | None, list[dict[str, Any]] | None, str, list[str] | None]:
    """Duraciones por plano, filas manifest, modo de montaje y movimientos de cámara."""
    try:
        from videomaker.llm.image_prompt_timing_reconcile import try_reconcile_image_prompts

        rec = try_reconcile_image_prompts(work_dir)
        if rec:
            from videomaker.pipeline.image_prompts_to_images import (
                build_images_generation_manifest,
            )
            from videomaker.pipeline.runner import save_manual_images_generation_bundle

            ip = work_dir / "pipeline" / "image_prompts.json"
            if ip.is_file():
                bundle = json.loads(ip.read_text(encoding="utf-8"))
                if isinstance(bundle, dict):
                    manifest = build_images_generation_manifest(work_dir, bundle)
                    save_manual_images_generation_bundle(work_dir, manifest)
    except Exception:
        pass

    rows = _load_selected_manifest_rows(work_dir)
    if rows:
        _, resolved_rows = _resolve_paths_from_manifest_rows(work_dir / "pipeline" / "images", rows)
        if resolved_rows and len(resolved_rows) == len(img_paths):
            seg = resolve_segment_durations_s(work_dir, resolved_rows)
            if seg and len(seg) == len(img_paths):
                motions = resolve_segment_camera_motions(resolved_rows)
                return seg, None, "chunk_sync", motions
    if beat_schedule:
        return None, beat_schedule, "music_beats", None
    return None, None, "equal_split", None


def _persist_render_draft_artifact(
    work_dir: Path,
    meta: dict[str, Any],
    *,
    render_no_music: bool | None = None,
) -> None:
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {**meta, "version": 1}
    payload["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if render_no_music is not None:
        payload["render_no_music"] = bool(render_no_music)
    # Attach planning artifacts/spines if present (for editor tooling).
    try:
        pj = work_dir / "pipeline" / "prompt.json"
        if pj.is_file():
            raw = json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload["spine"] = {
                    "energy_curve": raw.get("energy_curve"),
                    "visual_density": raw.get("visual_density"),
                    "emotional_arc": raw.get("emotional_arc"),
                    "visual_symbols": raw.get("visual_symbols"),
                    "thumbnail_narrative": raw.get("thumbnail_narrative"),
                }
    except Exception:
        pass
    try:
        mp = work_dir / "pipeline" / "music_plan.json"
        if mp.is_file():
            raw = json.loads(mp.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload["music_plan"] = raw.get("plan")
    except Exception:
        pass
    try:
        sp = work_dir / "pipeline" / "subtitles_plan.json"
        if sp.is_file():
            raw = json.loads(sp.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload["subtitles_plan"] = raw.get("plan")
    except Exception:
        pass
    (d / "render_draft.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def render_draft_video(
    narration_wav: Path,
    stock_dir: Path,
    output_mp4: Path,
    *,
    work_dir: Path | None = None,
    music_path: Path | None = None,
    pick_music_from_project: bool = True,
    frame_size: tuple[int, int] | None = (1920, 1080),
    render_no_music: bool | None = None,
    max_segments: int | None = None,
    max_duration_s: float | None = None,
    fast_preview: bool = False,
    persist_artifact: bool = True,
    preview_mode: bool = False,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """
    Monta ``draft.mp4`` con ``narracion.wav``.

    * Si hay vídeos en ``stock_dir`` (``.mp4``…), usa el flujo legacy con cortes 4–6 s.
    * Si no hay stock pero sí imágenes en ``pipeline/images``, reparte la duración con Ken Burns.
    * Si no hay ni stock ni imágenes, genera un MP4 de color sólido con solo la narración (preview).

    Si ``work_dir`` está definido, escribe ``pipeline/render_draft.json`` con resumen del montaje.
    """
    if not narration_wav.is_file():
        raise FileNotFoundError(f"No existe la narración: {narration_wav}")

    root = work_dir if work_dir is not None else stock_dir.parent
    paths_stock = list_stock_videos(stock_dir)
    img_paths = resolve_pipeline_image_paths(root)
    narration_cap_s: float | None = None
    manifest_path = root / "pipeline" / "images_generation.json"
    manifest_exists = manifest_path.is_file()

    music = music_path
    if music is None and pick_music_from_project:
        # If a music plan exists, try to pick a track matching its palette.
        hint = ""
        try:
            mp = root / "pipeline" / "music_plan.json"
            if mp.is_file():
                raw = json.loads(mp.read_text(encoding="utf-8"))
                plan = raw.get("plan") if isinstance(raw, dict) else None
                pal = plan.get("palette") if isinstance(plan, dict) else None
                if isinstance(pal, dict):
                    hint = str(pal.get("hook") or "") + " " + str(pal.get("ending") or "")
        except Exception:
            hint = ""
        try:
            from videomaker.audio.audio_music import pick_track_by_hint

            music = pick_track_by_hint(hint) if hint.strip() else pick_random_track()
        except Exception:
            music = pick_random_track()

    use_images = bool(img_paths) and (manifest_exists or not paths_stock)
    fs = frame_size or (1920, 1080)

    beat_schedule_used: list[dict[str, Any]] | None = None
    timing_mode: str | None = None
    segment_durations_s: list[float] | None = None

    if use_images:
        branch = "images"
        preferred_manifest = bool(manifest_exists)
        beat_schedule = None
        try:
            mp = root / "pipeline" / "music_plan.json"
            if mp.is_file():
                raw = json.loads(mp.read_text(encoding="utf-8"))
                plan = raw.get("plan") if isinstance(raw, dict) else None
                beats = plan.get("beats") if isinstance(plan, dict) else None
                if isinstance(beats, list) and beats:
                    beat_schedule = [b for b in beats if isinstance(b, dict)][:24]
        except Exception:
            beat_schedule = None
        segment_durations_s, beat_schedule, timing_mode, segment_motions = _resolve_image_assembly_timing(
            root, img_paths, beat_schedule=beat_schedule
        )
        if max_segments is not None or max_duration_s is not None:
            img_paths, segment_durations_s, cap, segment_motions = _trim_assembly_for_preview(
                img_paths,
                segment_durations_s,
                max_segments=max_segments,
                max_duration_s=max_duration_s,
                segment_motions=segment_motions,
            )
            if cap is not None:
                narration_cap_s = cap
        beat_schedule_used = beat_schedule if isinstance(beat_schedule, list) else None
        assemble_from_image_files(
            img_paths,
            narration_wav,
            output_mp4,
            music_audio=music,
            frame_size=frame_size,
            beat_schedule=beat_schedule,
            segment_durations_s=segment_durations_s,
            narration_cap_s=narration_cap_s,
            fast_preview=fast_preview,
            on_progress=on_progress,
            work_dir=root,
            segment_motions=segment_motions,
        )
    elif paths_stock:
        branch = "stock"
        preferred_manifest = False
        beat_schedule = None
        try:
            mp = root / "pipeline" / "music_plan.json"
            if mp.is_file():
                raw = json.loads(mp.read_text(encoding="utf-8"))
                plan = raw.get("plan") if isinstance(raw, dict) else None
                beats = plan.get("beats") if isinstance(plan, dict) else None
                if isinstance(beats, list) and beats:
                    beat_schedule = [b for b in beats if isinstance(b, dict)][:24]
        except Exception:
            beat_schedule = None
        beat_schedule_used = beat_schedule if isinstance(beat_schedule, list) else None
        assemble_from_stock_files(
            paths_stock,
            narration_wav,
            output_mp4,
            music_audio=music,
            frame_size=frame_size,
            beat_schedule=beat_schedule,
        )
    elif img_paths:
        branch = "images"
        preferred_manifest = False
        beat_schedule = None
        try:
            mp = root / "pipeline" / "music_plan.json"
            if mp.is_file():
                raw = json.loads(mp.read_text(encoding="utf-8"))
                plan = raw.get("plan") if isinstance(raw, dict) else None
                beats = plan.get("beats") if isinstance(plan, dict) else None
                if isinstance(beats, list) and beats:
                    beat_schedule = [b for b in beats if isinstance(b, dict)][:24]
        except Exception:
            beat_schedule = None
        segment_durations_s, beat_schedule, timing_mode, segment_motions = _resolve_image_assembly_timing(
            root, img_paths, beat_schedule=beat_schedule
        )
        if max_segments is not None or max_duration_s is not None:
            img_paths, segment_durations_s, cap, segment_motions = _trim_assembly_for_preview(
                img_paths,
                segment_durations_s,
                max_segments=max_segments,
                max_duration_s=max_duration_s,
                segment_motions=segment_motions,
            )
            if cap is not None:
                narration_cap_s = cap
        beat_schedule_used = beat_schedule if isinstance(beat_schedule, list) else None
        assemble_from_image_files(
            img_paths,
            narration_wav,
            output_mp4,
            music_audio=music,
            frame_size=frame_size,
            beat_schedule=beat_schedule,
            segment_durations_s=segment_durations_s,
            narration_cap_s=narration_cap_s,
            fast_preview=fast_preview,
            on_progress=on_progress,
            work_dir=root,
            segment_motions=segment_motions,
        )
    else:
        branch = "narration_only"
        preferred_manifest = False
        beat_schedule_used = None
        assemble_from_narration_only(
            narration_wav,
            output_mp4,
            music_audio=music,
            frame_size=frame_size,
        )

    try:
        narr_dur = wav_duration_seconds(narration_wav)
    except Exception:
        narr_dur = 0.0
    out_bytes = int(output_mp4.stat().st_size) if output_mp4.is_file() else 0
    music_track = None
    if music is not None and Path(music).is_file():
        music_track = Path(music).name

    meta: dict[str, Any] = {
        "visual_branch": branch,
        "images_manifest_preferred": preferred_manifest,
        "images_resolved_count": len(img_paths),
        "stock_video_count": len(paths_stock),
        "narration_duration_s": round(float(narr_dur), 3),
        "output_bytes": out_bytes,
        "frame_width": int(fs[0]),
        "frame_height": int(fs[1]),
        "music_track": music_track,
        "pick_music_from_project": bool(pick_music_from_project),
        "output_file": output_mp4.name,
        "preview_mode": bool(preview_mode),
        "fast_preview_encode": bool(fast_preview),
    }
    if max_segments is not None:
        meta["preview_max_segments"] = max_segments
    if max_duration_s is not None:
        meta["preview_max_duration_s"] = max_duration_s
    if timing_mode:
        meta["timing_mode"] = timing_mode
    try:
        from videomaker.video.video_editor import render_ken_burns_settings

        kb_on, kb_zoom, kb_fps, kb_engine = render_ken_burns_settings()
        meta["ken_burns"] = {
            "enabled": kb_on,
            "zoom_end": kb_zoom,
            "fps": kb_fps,
            "engine": kb_engine,
            "method": (
                "eased_affine_pipe"
                if kb_on and kb_engine == "eased"
                else (f"{kb_engine}_affine" if kb_on else "static")
            ),
        }
    except Exception:
        pass
    if segment_durations_s:
        meta["segment_count"] = len(segment_durations_s)
        meta["segment_duration_sum_s"] = round(sum(segment_durations_s), 3)
    if beat_schedule_used and float(narr_dur) > 0:
        meta["cut_schedule"] = _cut_schedule_from_beats(
            beat_schedule_used, target_dur=float(narr_dur)
        )

    if work_dir is not None and persist_artifact:
        if preview_mode:
            d = work_dir / "pipeline"
            d.mkdir(parents=True, exist_ok=True)
            payload: dict[str, Any] = {**meta, "version": 1}
            payload["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if render_no_music is not None:
                payload["render_no_music"] = bool(render_no_music)
            (d / "render_preview.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            _persist_render_draft_artifact(work_dir, meta, render_no_music=render_no_music)

    return output_mp4
