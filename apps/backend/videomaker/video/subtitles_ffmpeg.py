"""Quemar subtítulos SRT con ffmpeg (más estable que capas TextClip en vídeos largos)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def burn_subtitles_srt(
    video_in: Path,
    srt_path: Path,
    video_out: Path,
    *,
    ffmpeg_bin: str | None = None,
) -> Path:
    """Re-codifica vídeo con pista de vídeo filtrada por subtitles=. Requiere ffmpeg en PATH."""
    ffmpeg = ffmpeg_bin or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "No se encontró ffmpeg. En Mac: brew install ffmpeg"
        )
    video_out.parent.mkdir(parents=True, exist_ok=True)
    srt_abs = srt_path.resolve()
    # Rutas con ':' (poco habitual en Unix) pueden molestar al filtro subtitles
    sub = str(srt_abs).replace("\\", "\\\\").replace(":", "\\:")
    vf = f"subtitles='{sub}'"
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        str(video_in),
        "-vf",
        vf,
        "-c:a",
        "copy",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        str(video_out),
    ]
    subprocess.run(cmd, check=True)
    return video_out
