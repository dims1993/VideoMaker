"""Música libre de derechos desde carpeta local: elegir pista, bucle y fade final."""

from __future__ import annotations

import random
from pathlib import Path

from moviepy.editor import AudioFileClip, concatenate_audioclips

from videomaker.core import config


def pick_random_track(music_dir: Path | None = None) -> Path | None:
    root = music_dir or config.MUSIC_DIR
    if not root.is_dir():
        return None
    exts = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
    files = [p for p in root.iterdir() if p.suffix.lower() in exts]
    if not files:
        return None
    return random.choice(files)


def build_looped_music(
    music_path: Path,
    total_duration_s: float,
    *,
    fade_out_s: float = 3.0,
    volume: float = 0.18,
):
    """
    Devuelve un AudioClip de MoviePy en bucle cubriendo `total_duration_s`,
    con fade-out en los últimos `fade_out_s` segundos.
    """
    base = AudioFileClip(str(music_path)).volumex(volume)
    if base.duration >= total_duration_s:
        clip = base.subclip(0, total_duration_s)
    else:
        n = int(total_duration_s // base.duration) + 2
        clip = concatenate_audioclips([base] * n).subclip(0, total_duration_s)
    fo = min(fade_out_s, total_duration_s * 0.5)
    return clip.audio_fadeout(fo)
