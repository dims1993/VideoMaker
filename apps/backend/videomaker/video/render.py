"""Montaje draft: narración + imágenes del pipeline, vídeo legacy en stock/, o solo audio sobre fondo."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from videomaker.audio.audio_concat import wav_duration_seconds
from videomaker.audio.audio_music import pick_random_track
from .video_editor import assemble_from_image_files, assemble_from_narration_only, assemble_from_stock_files


def list_stock_videos(stock_dir: Path) -> list[Path]:
    exts = {".mp4", ".mov", ".m4v", ".webm"}
    if not stock_dir.is_dir():
        return []
    return sorted(p for p in stock_dir.iterdir() if p.suffix.lower() in exts)


_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def resolve_pipeline_image_paths(work_dir: Path) -> list[Path]:
    """
    Lista rutas absolutas de imágenes para el montaje.

    Si existe ``pipeline/images_generation.json``, usa las entradas con
    ``selected: true`` ordenadas por ``order`` y resuelve ``filename`` bajo
    ``pipeline/images/``. Si no, ordena por nombre todos los PNG/JPG en esa carpeta.
    """
    images_dir = work_dir / "pipeline" / "images"
    manifest = work_dir / "pipeline" / "images_generation.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            rows = [x for x in (data.get("images") or []) if isinstance(x, dict)]
            rows = [x for x in rows if x.get("selected", True) is not False]
            rows.sort(key=lambda x: int(x.get("order", 0) or 0))
            out: list[Path] = []
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
                    out.append(p)
            if out:
                return out
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    if not images_dir.is_dir():
        return []
    return sorted(
        (p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTS),
        key=lambda p: p.name.lower(),
    )


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
    manifest_path = root / "pipeline" / "images_generation.json"
    manifest_exists = manifest_path.is_file()

    music = music_path
    if music is None and pick_music_from_project:
        music = pick_random_track()

    use_images = bool(img_paths) and (manifest_exists or not paths_stock)
    fs = frame_size or (1920, 1080)

    if use_images:
        branch = "images"
        preferred_manifest = bool(manifest_exists)
        assemble_from_image_files(
            img_paths,
            narration_wav,
            output_mp4,
            music_audio=music,
            frame_size=frame_size,
        )
    elif paths_stock:
        branch = "stock"
        preferred_manifest = False
        assemble_from_stock_files(
            paths_stock,
            narration_wav,
            output_mp4,
            music_audio=music,
            frame_size=frame_size,
        )
    elif img_paths:
        branch = "images"
        preferred_manifest = False
        assemble_from_image_files(
            img_paths,
            narration_wav,
            output_mp4,
            music_audio=music,
            frame_size=frame_size,
        )
    else:
        branch = "narration_only"
        preferred_manifest = False
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
        "output_file": "draft.mp4",
    }

    if work_dir is not None:
        _persist_render_draft_artifact(work_dir, meta, render_no_music=render_no_music)

    return output_mp4
