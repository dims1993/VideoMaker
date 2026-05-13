"""Montaje: ritmo 4–6s, Ken Burns, tarjetas de capítulo cada ~2 min."""

from __future__ import annotations

from . import pil_compat  # noqa: F401  # Pillow 10+ / MoviePy 1.x (Image.ANTIALIAS)

import math
import random
from pathlib import Path

from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from videomaker.core import config
from videomaker.audio.audio_music import build_looped_music


def random_clip_duration_s() -> float:
    return random.uniform(config.CLIP_DURATION_MIN_S, config.CLIP_DURATION_MAX_S)


def ken_burns_on_clip(clip, zoom_end: float = 1.07):
    """Zoom lineal suave a lo largo del clip (ligero movimiento de cámara)."""
    d = max(float(clip.duration), 1e-6)
    return clip.resize(lambda t: 1.0 + (zoom_end - 1.0) * (t / d))


def slice_visual_to_beat(
    clip,
    beat_s: float | None = None,
    *,
    frame_size: tuple[int, int] | None = None,
):
    """Recorta al ritmo 4–6s, Ken Burns y opcionalmente escala a resolución fija (concat estable)."""
    dur = beat_s if beat_s is not None else random_clip_duration_s()
    dur = min(dur, clip.duration)
    sub = clip.subclip(0, dur)
    out = ken_burns_on_clip(sub)
    if frame_size:
        out = out.resize(newsize=frame_size)
    return out


def chapter_title_card(
    title: str,
    duration_s: float = 2.5,
    size: tuple[int, int] = (1920, 1080),
):
    """
    Pantalla simple de capítulo. TextClip suele requerir ImageMagick instalado en el sistema.
    """
    bg = ColorClip(size=size, color=(12, 14, 18), duration=duration_s)
    try:
        txt = TextClip(
            title,
            fontsize=56,
            color="white",
            font="Arial-Bold",
            method="caption",
            size=(int(size[0] * 0.86), None),
            align="center",
        ).set_duration(duration_s)
        return CompositeVideoClip([bg, txt.set_position("center")])
    except Exception:
        return bg


def build_chapter_schedule(total_duration_s: float, titles: list[str] | None = None):
    """Devuelve lista de (t_start, título) cada CHAPTER_INTERVAL_S."""
    marks: list[tuple[float, str]] = []
    t = config.CHAPTER_INTERVAL_S
    idx = 1
    while t < total_duration_s:
        title = (
            titles[idx - 1]
            if titles and idx - 1 < len(titles)
            else f"Parte {idx}"
        )
        marks.append((t, title))
        t += config.CHAPTER_INTERVAL_S
        idx += 1
    return marks


def _extend_video_to_duration(clip, target_s: float):
    """Repite `clip` hasta cubrir al menos `target_s` y recorta al segundo exacto."""
    if clip.duration >= target_s:
        return clip.subclip(0, target_s)
    n = int(math.ceil(target_s / float(clip.duration)))
    parts = [clip.copy() for _ in range(max(n, 2))]
    long_clip = concatenate_videoclips(parts, method="compose")
    return long_clip.subclip(0, target_s)


def assemble_from_stock_files(
    video_paths: list[Path],
    narration_audio: Path,
    output_path: Path,
    *,
    music_audio: Path | None = None,
    chapter_titles: list[tuple[float, str]] | None = None,
    frame_size: tuple[int, int] | None = (1920, 1080),
) -> Path:
    """
    Concatena stock en cortes de 4–6s, alinea duración a la narración,
    mezcla música en bucle con fade-out y deja hooks para capítulos en timeline.
    """
    if not video_paths:
        raise ValueError("No hay vídeos de stock para montar.")

    narration = AudioFileClip(str(narration_audio))
    target_dur = float(narration.duration)

    beat_layers = []
    total = 0.0
    guard = 0
    while total < target_dur and guard < 20_000:
        path = video_paths[guard % len(video_paths)]
        src = VideoFileClip(str(path))
        piece = slice_visual_to_beat(src, frame_size=frame_size)
        beat_layers.append(piece)
        total += float(piece.duration)
        guard += 1

    base_video = concatenate_videoclips(beat_layers, method="compose")
    if base_video.duration > target_dur:
        base_video = base_video.subclip(0, target_dur)
    elif base_video.duration < target_dur:
        base_video = _extend_video_to_duration(base_video, target_dur)

    narration = narration.set_duration(target_dur)
    music_clip = None
    if music_audio and music_audio.exists():
        music_clip = build_looped_music(music_audio, target_dur)
        final_audio = CompositeAudioClip([narration, music_clip])
    else:
        final_audio = narration

    final = base_video.set_audio(final_audio)
    _ = chapter_titles  # siguiente paso: insertar `chapter_title_card` en timeline

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=4,
            preset="medium",
        )
    finally:
        try:
            final.close()
        except Exception:
            pass
        try:
            base_video.close()
        except Exception:
            pass
        try:
            narration.close()
        except Exception:
            pass
        if music_clip is not None:
            try:
                music_clip.close()
            except Exception:
                pass
        for c in beat_layers:
            try:
                c.close()
            except Exception:
                pass
    return output_path


def assemble_from_narration_only(
    narration_audio: Path,
    output_path: Path,
    *,
    music_audio: Path | None = None,
    frame_size: tuple[int, int] | None = (1920, 1080),
    bg_color: tuple[int, int, int] = (12, 14, 18),
) -> Path:
    """
    Vídeo 16:9 de un color sólido con la duración exacta de la narración (sin stock ni imágenes).
    Útil cuando el montaje final se hará en otro editor y solo necesitas preview con audio.
    """
    fs = frame_size or (1920, 1080)
    narration = AudioFileClip(str(narration_audio))
    target_dur = float(narration.duration)
    bg = ColorClip(size=fs, color=bg_color, duration=target_dur)
    narration = narration.set_duration(target_dur)
    music_clip = None
    if music_audio and music_audio.exists():
        music_clip = build_looped_music(music_audio, target_dur)
        final_audio = CompositeAudioClip([narration, music_clip])
    else:
        final_audio = narration
    final = bg.set_audio(final_audio)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=4,
            preset="medium",
        )
    finally:
        try:
            final.close()
        except Exception:
            pass
        try:
            bg.close()
        except Exception:
            pass
        try:
            narration.close()
        except Exception:
            pass
        if music_clip is not None:
            try:
                music_clip.close()
            except Exception:
                pass
    return output_path


def _image_clip_cover_kenburns(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
    *,
    zoom_end: float = 1.06,
):
    """Imagen estática a vídeo: cover 16:9, duración fija, Ken Burns ligero."""
    tw, th = frame_size
    clip = ImageClip(str(image_path), duration=max(float(duration_s), 0.05))
    cw, ch = clip.size
    scale = max(tw / cw, th / ch)
    clip = clip.resize(scale)
    nw, nh = clip.size
    x1 = max(0, int((nw - tw) / 2))
    y1 = max(0, int((nh - th) / 2))
    clip = clip.crop(x1=x1, y1=y1, width=tw, height=th)
    return ken_burns_on_clip(clip, zoom_end=zoom_end)


def assemble_from_image_files(
    image_paths: list[Path],
    narration_audio: Path,
    output_path: Path,
    *,
    music_audio: Path | None = None,
    chapter_titles: list[tuple[float, str]] | None = None,
    frame_size: tuple[int, int] | None = (1920, 1080),
    min_segment_s: float = 2.5,
) -> Path:
    """
    Monta un vídeo a partir de imágenes fijas (PNG/JPG), repartiendo la duración
    de la narración entre ellas (con repetición si hace falta para respetar ``min_segment_s``).
    """
    if not image_paths:
        raise ValueError("No hay imágenes para montar.")

    fs = frame_size or (1920, 1080)
    narration = AudioFileClip(str(narration_audio))
    target_dur = float(narration.duration)

    paths = list(image_paths)
    seg = target_dur / len(paths)
    if seg < min_segment_s:
        n_needed = max(1, int(math.ceil(target_dur / min_segment_s)))
        paths = [paths[i % len(paths)] for i in range(n_needed)]

    seg = target_dur / len(paths)
    beat_layers: list = []
    for p in paths:
        beat_layers.append(_image_clip_cover_kenburns(p, seg, fs))

    base_video = concatenate_videoclips(beat_layers, method="compose")
    if base_video.duration > target_dur:
        base_video = base_video.subclip(0, target_dur)
    elif base_video.duration < target_dur:
        base_video = _extend_video_to_duration(base_video, target_dur)

    narration = narration.set_duration(target_dur)
    music_clip = None
    if music_audio and music_audio.exists():
        music_clip = build_looped_music(music_audio, target_dur)
        final_audio = CompositeAudioClip([narration, music_clip])
    else:
        final_audio = narration

    final = base_video.set_audio(final_audio)
    _ = chapter_titles

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=4,
            preset="medium",
        )
    finally:
        try:
            final.close()
        except Exception:
            pass
        try:
            base_video.close()
        except Exception:
            pass
        try:
            narration.close()
        except Exception:
            pass
        if music_clip is not None:
            try:
                music_clip.close()
            except Exception:
                pass
        for c in beat_layers:
            try:
                c.close()
            except Exception:
                pass
    return output_path
