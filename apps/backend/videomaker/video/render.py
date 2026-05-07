"""Montaje draft: narración + carpeta de stock + música opcional."""

from __future__ import annotations

from pathlib import Path

from videomaker.audio.audio_music import pick_random_track
from .video_editor import assemble_from_stock_files


def list_stock_videos(stock_dir: Path) -> list[Path]:
    exts = {".mp4", ".mov", ".m4v", ".webm"}
    if not stock_dir.is_dir():
        return []
    return sorted(p for p in stock_dir.iterdir() if p.suffix.lower() in exts)


def render_draft_video(
    narration_wav: Path,
    stock_dir: Path,
    output_mp4: Path,
    *,
    music_path: Path | None = None,
    pick_music_from_project: bool = True,
    frame_size: tuple[int, int] | None = (1920, 1080),
) -> Path:
    """
    Une clips de `stock_dir` al ritmo 4–6 s, añade `narracion.wav` y mezcla música si existe.
    """
    paths = list_stock_videos(stock_dir)
    if not paths:
        raise FileNotFoundError(
            f"No hay vídeos en {stock_dir}. Ejecuta antes: python main.py stock-fetch …"
        )
    if not narration_wav.is_file():
        raise FileNotFoundError(f"No existe la narración: {narration_wav}")

    music = music_path
    if music is None and pick_music_from_project:
        music = pick_random_track()

    return assemble_from_stock_files(
        paths,
        narration_wav,
        output_mp4,
        music_audio=music,
        frame_size=frame_size,
    )
