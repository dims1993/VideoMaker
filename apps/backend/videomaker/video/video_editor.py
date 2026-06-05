"""Montaje: ritmo 4–6s, Ken Burns, tarjetas de capítulo cada ~2 min."""

from __future__ import annotations

from . import pil_compat  # noqa: F401  # Pillow 10+ / MoviePy 1.x (Image.ANTIALIAS)

import math
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    ImageSequenceClip,
    TextClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
)
from PIL import Image

from videomaker.core import config
from videomaker.audio.audio_music import build_looped_music
from videomaker.video.render_progress import ProgressCallback
from videomaker.video.render_segments_checkpoint import (
    build_assembly_fingerprint,
    checkpoint_batch_size,
    checkpoint_path_for_work,
    cleanup_after_success,
    resolve_resume_indices,
    save_checkpoint,
    segment_is_usable,
    segments_dir_for_work,
    sync_segments_fingerprint,
)

_PIL_LANCZOS = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
_PIL_BICUBIC = getattr(Image.Resampling, "BICUBIC", Image.BICUBIC)
_PIL_AFFINE = getattr(getattr(Image, "Transform", Image), "AFFINE", Image.AFFINE)


def random_clip_duration_s() -> float:
    return random.uniform(config.CLIP_DURATION_MIN_S, config.CLIP_DURATION_MAX_S)


def render_ken_burns_settings() -> tuple[bool, float, int, str]:
    """
    Ken Burns en imágenes del draft.

    RENDER_KEN_BURNS=0 desactiva (plano fijo).
    RENDER_KEN_BURNS_ZOOM=1.03 zoom final relativo (1.0 = sin zoom).
    RENDER_KEN_BURNS_ENGINE=pil|ffmpeg (pil = transform afín + secuencia fija).
    RENDER_FPS=30 fps del vídeo exportado (más fps = pan más suave).
    """
    raw = (os.environ.get("RENDER_KEN_BURNS") or "1").strip().lower()
    enabled = raw not in ("0", "false", "no", "off")
    try:
        zoom = float((os.environ.get("RENDER_KEN_BURNS_ZOOM") or "1.03").strip())
    except ValueError:
        zoom = 1.03
    zoom = min(max(zoom, 1.0), 1.12)
    try:
        fps = int((os.environ.get("RENDER_FPS") or "30").strip())
    except ValueError:
        fps = 30
    fps = max(12, min(fps, 30))
    engine = (os.environ.get("RENDER_KEN_BURNS_ENGINE") or "eased").strip().lower()
    if engine in ("pil", "eased", "smooth"):
        engine = "eased"
    elif engine != "ffmpeg":
        engine = "eased"
    return enabled, zoom, fps, engine


def render_ken_burns_settings_legacy() -> tuple[bool, float, int]:
    """Compat: devuelve (enabled, zoom, fps) sin engine."""
    enabled, zoom, fps, _ = render_ken_burns_settings()
    return enabled, zoom, fps


def _x264_preset(*, fast_preview: bool = False) -> str:
    return "ultrafast" if fast_preview else "fast"


def _probe_media_duration_s(path: Path) -> float:
    if not path.is_file():
        return 0.0
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return max(0.0, float(out.stdout.strip()))
    except Exception:
        return 0.0


def _ffmpeg_concat_segment_files(
    segment_paths: list[Path],
    out_path: Path,
    *,
    fast_preview: bool = False,
) -> None:
    """
    Une segmentos ya codificados con el mismo CFR.

    Primero ``-c copy`` (sin tocar frames = zoom suave intacto). Si falla, un solo
    re-encode CFR sin filtro ``fps=`` (ese filtro introducía saltos / movimiento brusco).
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg no está en PATH.")
    _, _, fps, _ = render_ken_burns_settings()
    list_file = out_path.parent / "concat_list.txt"
    lines = [f"file '{sp.resolve()}'" for sp in segment_paths]
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    preset = _x264_preset(fast_preview=fast_preview)
    base_args = ["-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-an"]
    try:
        subprocess.run(
            [
                "ffmpeg",
                *base_args,
                "-c:v",
                "copy",
                "-movflags",
                "+faststart",
                str(out_path),
            ],
            check=True,
            capture_output=True,
            timeout=max(900, len(segment_paths) * 20),
        )
        return
    except subprocess.CalledProcessError:
        out_path.unlink(missing_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            *base_args,
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-vsync",
            "cfr",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        check=True,
        capture_output=True,
        timeout=max(1200, len(segment_paths) * 60),
    )


def _write_mixed_audio_wav(
    narration_audio: Path,
    target_dur: float,
    out_wav: Path,
    *,
    music_audio: Path | None = None,
) -> None:
    """Mezcla narración (+ música opcional) a un WAV para mux final sin re-codificar vídeo."""
    narration = AudioFileClip(str(narration_audio))
    narration = narration.subclip(0, min(float(narration.duration), target_dur)).set_duration(target_dur)
    music_clip = None
    if music_audio and music_audio.exists():
        music_clip = build_looped_music(music_audio, target_dur)
        mixed = CompositeAudioClip([narration, music_clip])
    else:
        mixed = narration
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    try:
        mixed.write_audiofile(str(out_wav), fps=44100, nbytes=2, codec="pcm_s16le", logger=None)
    finally:
        try:
            mixed.close()
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


def _ffmpeg_mux_video_with_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    *,
    target_dur: float,
) -> None:
    """Copia el stream de vídeo tal cual (Ken Burns ya codificado) y añade audio AAC."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
    ]
    vid_dur = _probe_media_duration_s(video_path)
    if vid_dur > target_dur + 0.05:
        cmd.extend(["-t", f"{target_dur:.3f}"])
    cmd.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
    )
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        timeout=max(600, int(target_dur * 2)),
    )


def _export_mp4_kwargs(*, fast_preview: bool = False) -> dict:
    _, _, fps, _ = render_ken_burns_settings()
    if fast_preview:
        # Misma fps que el draft final para que el Ken Burns del preview se vea igual.
        return {
            "codec": "libx264",
            "audio_codec": "aac",
            "fps": fps,
            "threads": 4,
            "preset": "ultrafast",
        }
    return {
        "codec": "libx264",
        "audio_codec": "aac",
        "fps": fps,
        "threads": 4,
        "preset": "medium",
    }


def ken_burns_on_clip(clip, zoom_end: float = 1.07):
    """
    Zoom lineal (legacy MoviePy resize por frame).

    Puede verse entrecortado; el montaje de imágenes usa ``image_clip_cover_ken_burns_smooth``.
    """
    d = max(float(clip.duration), 1e-6)
    return clip.resize(lambda t: 1.0 + (zoom_end - 1.0) * (t / d))


def _ken_burns_eased_progress(linear: float) -> float:
    """Ease in-out: evita arranque/parada bruscos del zoom."""
    t = min(1.0, max(0.0, linear))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def normalize_camera_motion(raw: str | None) -> str:
    """Normaliza etiqueta de beat/manifest → push_in | pull_out | static."""
    m = (raw or "").strip().lower().replace("-", "_")
    if m in ("static", "none", "locked", "hold"):
        return "static"
    if m in ("pull_out", "slow_pull_out", "pull_back", "out", "reveal", "pull"):
        return "pull_out"
    if m in ("push_in", "slow_push_in", "in", "push", "slow_zoom", "fast_zoom", "zoom_in"):
        return "push_in"
    if m in ("whip_pan", "handheld"):
        return "push_in"
    return "push_in"


def _ken_burns_scale_at_progress(
    progress: float,
    *,
    zoom_amount: float,
    motion: str,
) -> float:
    """Escala relativa 1.0 = sin zoom; >1 acercamiento visual."""
    p = _ken_burns_eased_progress(progress)
    z = max(0.01, float(zoom_amount) - 1.0)
    mode = normalize_camera_motion(motion)
    if mode == "static":
        return 1.0
    if mode == "pull_out":
        return (1.0 + z) - z * p
    return 1.0 + z * p


def _ken_burns_base_image(
    image_path: Path,
    frame_size: tuple[int, int],
    zoom_end: float,
    *,
    motion: str = "push_in",
) -> Image.Image:
    tw, th = frame_size
    pil = Image.open(str(image_path)).convert("RGB")
    cw, ch = pil.size
    mode = normalize_camera_motion(motion)
    peak = 1.0 if mode == "static" else max(float(zoom_end), 1.0)
    base_scale = max(tw / cw, th / ch) * peak
    base_w = max(tw, int(math.ceil(cw * base_scale)))
    base_h = max(th, int(math.ceil(ch * base_scale)))
    return pil.resize((base_w, base_h), _PIL_LANCZOS)


def _ken_burns_frame_affine(
    base: Image.Image,
    frame_size: tuple[int, int],
    progress: float,
    zoom_end: float,
    *,
    motion: str = "push_in",
) -> np.ndarray:
    """Zoom con transform afín subpíxel (sin redondear cajas de crop por frame)."""
    tw, th = frame_size
    scale = _ken_burns_scale_at_progress(progress, zoom_amount=zoom_end, motion=motion)
    w, h = base.size
    inv = 1.0 / scale
    cw, ch = w * inv, h * inv
    x0, y0 = (w - cw) * 0.5, (h - ch) * 0.5
    matrix = (cw / tw, 0.0, x0, 0.0, ch / th, y0)
    out = base.transform((tw, th), _PIL_AFFINE, matrix, resample=_PIL_BICUBIC)
    return np.asarray(out, dtype=np.uint8)


def image_clip_cover_ken_burns_pil(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
    *,
    zoom_end: float = 1.03,
    fps: int = 30,
    motion: str = "push_in",
) -> VideoClip:
    """Secuencia de frames precalculados + transform afín (sin ``make_frame`` ni crop entero)."""
    tw, th = frame_size
    d = max(float(duration_s), 0.05)
    n_frames = max(1, int(round(d * fps)))
    base = _ken_burns_base_image(image_path, frame_size, zoom_end, motion=motion)
    frames = [
        _ken_burns_frame_affine(
            base, frame_size, i / max(n_frames - 1, 1), zoom_end, motion=motion
        )
        for i in range(n_frames)
    ]
    clip = ImageSequenceClip(frames, fps=fps)
    return clip.set_duration(d)


def _write_image_segment_static_mp4(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
    out_path: Path,
    *,
    fps: int = 30,
) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    tw, th = frame_size
    d = max(float(duration_s), 0.05)
    vf = f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-vf",
        vf,
        "-t",
        f"{d:.3f}",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-r",
        str(fps),
        "-fps_mode",
        "cfr",
        str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=max(180, int(d * 40)))
        return out_path.is_file() and out_path.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        out_path.unlink(missing_ok=True)
        return False


def _write_image_segment_eased_mp4(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
    out_path: Path,
    *,
    zoom_end: float = 1.03,
    fps: int = 30,
    motion: str = "push_in",
) -> bool:
    """
    Ken Burns con easing (mismo algoritmo que el preview fluido), un frame en RAM.
    Frames por stdin → ffmpeg (sin zoompan lineal ni ImageSequenceClip masivo).
    """
    if not shutil.which("ffmpeg"):
        return False
    tw, th = frame_size
    d = max(float(duration_s), 0.05)
    n_frames = max(1, int(round(d * fps)))
    mode = normalize_camera_motion(motion)
    if mode == "static" or zoom_end <= 1.001:
        return _write_image_segment_static_mp4(
            image_path, duration_s, frame_size, out_path, fps=fps
        )
    base = _ken_burns_base_image(image_path, frame_size, zoom_end, motion=motion)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{tw}x{th}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-fps_mode",
        "cfr",
        "-g",
        str(fps),
        "-keyint_min",
        str(fps),
        str(out_path),
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        assert proc.stdin is not None
        try:
            for i in range(n_frames):
                frame = _ken_burns_frame_affine(
                    base,
                    frame_size,
                    i / max(n_frames - 1, 1),
                    zoom_end,
                    motion=motion,
                )
                if frame.shape[0] != th or frame.shape[1] != tw:
                    frame = np.asarray(
                        Image.fromarray(frame).resize((tw, th), _PIL_LANCZOS),
                        dtype=np.uint8,
                    )
                proc.stdin.write(frame.tobytes())
        finally:
            proc.stdin.close()
        rc = proc.wait(timeout=max(300, int(d * 50)))
        if rc != 0:
            err = (proc.stderr.read() if proc.stderr else b"").decode(errors="replace")
            raise subprocess.CalledProcessError(rc, cmd, stderr=err)
        return out_path.is_file() and out_path.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, BrokenPipeError):
        out_path.unlink(missing_ok=True)
        return False


def _write_image_segment_mp4(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
    out_path: Path,
    *,
    zoom_end: float = 1.03,
    fps: int = 30,
    ken_burns_enabled: bool = True,
    motion: str = "push_in",
) -> bool:
    """Escribe un plano a MP4 en disco (bajo RAM). Prioriza easing PIL como el preview."""
    if not shutil.which("ffmpeg"):
        return False
    mode = normalize_camera_motion(motion)
    if not ken_burns_enabled or mode == "static" or zoom_end <= 1.001:
        return _write_image_segment_static_mp4(
            image_path, duration_s, frame_size, out_path, fps=fps
        )
    if _write_image_segment_eased_mp4(
        image_path,
        duration_s,
        frame_size,
        out_path,
        zoom_end=zoom_end,
        fps=fps,
        motion=motion,
    ):
        return True
    # Fallback: zoompan lineal (menos suave)
    tw, th = frame_size
    d = max(float(duration_s), 0.05)
    n_frames = max(1, int(round(d * fps)))
    zoom_delta = max(0.0, zoom_end - 1.0)
    rate = zoom_delta / max(n_frames - 1, 1)
    vf = (
        f"scale={tw * 2}:{th * 2}:force_original_aspect_ratio=increase,"
        f"crop={tw * 2}:{th * 2},"
        f"zoompan=z='min(zoom+{rate:.8f},{zoom_end})':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={n_frames}:s={tw}x{th}:fps={fps}"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-vf",
        vf,
        "-t",
        f"{d:.3f}",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-r",
        str(fps),
        "-fps_mode",
        "cfr",
        str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=max(180, int(d * 40)))
        return out_path.is_file() and out_path.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        out_path.unlink(missing_ok=True)
        return False


def image_clip_cover_ken_burns_ffmpeg(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
    *,
    zoom_end: float = 1.03,
    fps: int = 30,
) -> VideoClip:
    """Zoom vía filtro ffmpeg ``zoompan`` (muy fluido si hay ffmpeg en PATH)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    out_path = Path(tmp.name)
    if not _write_image_segment_mp4(
        image_path,
        duration_s,
        frame_size,
        out_path,
        zoom_end=zoom_end,
        fps=fps,
        ken_burns_enabled=True,
        motion="push_in",
    ):
        out_path.unlink(missing_ok=True)
        return image_clip_cover_ken_burns_pil(
            image_path, duration_s, frame_size, zoom_end=zoom_end, fps=fps, motion="push_in"
        )
    clip = VideoFileClip(str(out_path))
    clip._vm_temp_path = str(out_path)  # type: ignore[attr-defined]
    return clip.set_duration(max(float(duration_s), 0.05))


def image_clip_cover_ken_burns_smooth(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
    *,
    zoom_end: float = 1.03,
    fps: int = 30,
    motion: str = "push_in",
) -> VideoClip:
    """Ken Burns: easing (preview) o zoompan ffmpeg si ``RENDER_KEN_BURNS_ENGINE=ffmpeg``."""
    _, _, _, engine = render_ken_burns_settings()
    if engine == "ffmpeg":
        return image_clip_cover_ken_burns_ffmpeg(
            image_path, duration_s, frame_size, zoom_end=zoom_end, fps=fps
        )
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    out_path = Path(tmp.name)
    if _write_image_segment_eased_mp4(
        image_path,
        duration_s,
        frame_size,
        out_path,
        zoom_end=zoom_end,
        fps=fps,
        motion=motion,
    ):
        clip = VideoFileClip(str(out_path))
        clip._vm_temp_path = str(out_path)  # type: ignore[attr-defined]
        return clip.set_duration(max(float(duration_s), 0.05))
    return image_clip_cover_ken_burns_pil(
        image_path, duration_s, frame_size, zoom_end=zoom_end, fps=fps, motion=motion
    )


def image_clip_cover_static(
    image_path: Path,
    duration_s: float,
    frame_size: tuple[int, int],
) -> ImageClip:
    """Imagen fija 16:9 sin zoom (RENDER_KEN_BURNS=0)."""
    tw, th = frame_size
    clip = ImageClip(str(image_path), duration=max(float(duration_s), 0.05))
    cw, ch = clip.size
    scale = max(tw / cw, th / ch)
    clip = clip.resize(scale)
    nw, nh = clip.size
    x1 = max(0, int((nw - tw) / 2))
    y1 = max(0, int((nh - th) / 2))
    return clip.crop(x1=x1, y1=y1, width=tw, height=th)


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


def _beat_schedule_to_durations(beat_schedule: list[dict], *, target_dur: float) -> list[float]:
    """
    Convert a music-plan beat schedule into cut durations.

    If beats carry ``start_s``/``end_s`` (audio timeline), use those lengths;
    otherwise map intensity to 3–6s cuts.
    """
    timed: list[float] = []
    for b in beat_schedule:
        if not isinstance(b, dict):
            continue
        try:
            start_s = float(b["start_s"])
            end_s = float(b["end_s"])
        except (KeyError, TypeError, ValueError):
            continue
        d = end_s - start_s
        if d > 0.05:
            timed.append(round(d, 3))
    if timed:
        base = timed
    else:
        base = []
        for b in beat_schedule:
            if not isinstance(b, dict):
                continue
            inten = b.get("intensity")
            try:
                i = int(float(inten))
            except Exception:
                i = 55
            i = max(0, min(100, i))
            if i >= 85:
                base.append(3.0)
            elif i >= 70:
                base.append(4.0)
            elif i >= 55:
                base.append(5.0)
            else:
                base.append(6.0)
    if not base:
        return []
    total = 0.0
    out: list[float] = []
    idx = 0
    guard = 0
    while total < target_dur and guard < 100_000:
        d = float(base[idx % len(base)])
        out.append(d)
        total += d
        idx += 1
        guard += 1
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
    beat_schedule: list[dict] | None = None,
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
    forced_durs = (
        _beat_schedule_to_durations(beat_schedule or [], target_dur=target_dur)
        if beat_schedule
        else []
    )
    while total < target_dur and guard < 20_000:
        path = video_paths[guard % len(video_paths)]
        src = VideoFileClip(str(path))
        beat_s = forced_durs[guard] if guard < len(forced_durs) else None
        piece = slice_visual_to_beat(src, beat_s=beat_s, frame_size=frame_size)
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
        final.write_videofile(str(output_path), **_export_mp4_kwargs())
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
        final.write_videofile(str(output_path), **_export_mp4_kwargs())
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
    zoom_end: float | None = None,
    fps: int | None = None,
    ken_burns_enabled: bool | None = None,
    motion: str = "push_in",
):
    """Imagen estática a vídeo: cover 16:9, duración fija, Ken Burns opcional."""
    kb_on, kb_zoom, kb_fps, _ = render_ken_burns_settings()
    use_kb = kb_on if ken_burns_enabled is None else ken_burns_enabled
    z = zoom_end if zoom_end is not None else kb_zoom
    f = fps if fps is not None else kb_fps
    mode = normalize_camera_motion(motion)
    if not use_kb or mode == "static" or z <= 1.001:
        return image_clip_cover_static(image_path, duration_s, frame_size)
    return image_clip_cover_ken_burns_smooth(
        image_path, duration_s, frame_size, zoom_end=z, fps=f, motion=motion
    )


def _segment_paths_ordered(segments_root: Path, n_paths: int) -> list[Path]:
    return [segments_root / f"seg_{i:04d}.mp4" for i in range(n_paths)]


def _all_segments_usable(segment_paths: list[Path]) -> bool:
    return bool(segment_paths) and all(segment_is_usable(p) for p in segment_paths)


def _concat_segment_files_to_video_only(
    segment_paths: list[Path],
    tmp_root: Path,
    *,
    fast_preview: bool,
    on_progress: ProgressCallback | None,
) -> Path:
    n = len(segment_paths)
    if on_progress:
        on_progress("concat", n, n, "Uniendo planos (ffmpeg CFR)…")
    video_only = tmp_root / "video_only.mp4"
    _ffmpeg_concat_segment_files(
        segment_paths,
        video_only,
        fast_preview=fast_preview,
    )
    return video_only


def _recover_streaming_concat_from_disk(
    work_dir: Path | None,
    n_paths: int,
    *,
    fast_preview: bool,
    on_progress: ProgressCallback | None,
) -> Path | None:
    """Si los planos ya están en disco, reintenta solo el concat (sin MoviePy)."""
    if work_dir is None:
        return None
    root = segments_dir_for_work(work_dir)
    seg_paths = _segment_paths_ordered(root, n_paths)
    if not _all_segments_usable(seg_paths):
        return None
    if on_progress:
        on_progress(
            "segment",
            n_paths,
            n_paths,
            f"Reutilizando {n_paths} planos en disco…",
        )
    return _concat_segment_files_to_video_only(
        seg_paths, root, fast_preview=fast_preview, on_progress=on_progress
    )


def _assemble_images_streaming_ffmpeg(
    paths: list[Path],
    segs: list[float],
    frame_size: tuple[int, int],
    *,
    fast_preview: bool,
    on_progress: ProgressCallback | None,
    work_dir: Path | None = None,
    segment_motions: list[str] | None = None,
) -> Path:
    """
    Monta planos escribiendo cada segmento a disco y concatena con ffmpeg.
    Evita acumular decenas de ImageSequenceClip en RAM (OOM ~plano 15–25).

    Con ``work_dir``, guarda ``pipeline/render_segments/seg_XXXX.mp4`` y un
    checkpoint cada ``RENDER_CHECKPOINT_EVERY`` planos (default 5) para reanudar.
    """
    kb_on, kb_zoom, kb_fps, kb_engine = render_ken_burns_settings()
    tw, th = frame_size
    n_paths = len(paths)
    persistent = work_dir is not None
    if persistent:
        tmp_root = segments_dir_for_work(work_dir)
        tmp_root.mkdir(parents=True, exist_ok=True)
        ck_path = checkpoint_path_for_work(work_dir)
        fingerprint = build_assembly_fingerprint(
            paths,
            [float(s) for s in segs],
            frame_size=frame_size,
            ken_burns_enabled=kb_on,
            zoom_end=kb_zoom,
            fps=kb_fps,
            engine=kb_engine,
            fast_preview=fast_preview,
        )
        sync_segments_fingerprint(tmp_root, fingerprint)
        resume = resolve_resume_indices(tmp_root, fingerprint, n_paths)
        completed: list[int] = sorted(resume)
        if resume and on_progress:
            on_progress(
                "segment",
                len(resume),
                n_paths,
                f"Reanudando: {len(resume)} planos ya en disco…",
            )
    else:
        tmp_root = Path(tempfile.mkdtemp(prefix="vm_render_"))
        ck_path = None
        fingerprint = ""
        resume = set()
        completed = []

    segment_paths: list[Path] = []
    batch_every = checkpoint_batch_size()
    try:
        for i, p in enumerate(paths):
            seg_path = tmp_root / f"seg_{i:04d}.mp4"
            if i in resume and segment_is_usable(seg_path):
                segment_paths.append(seg_path)
                if on_progress:
                    on_progress(
                        "segment",
                        i + 1,
                        n_paths,
                        f"Plano {i + 1}/{n_paths} (reutilizado)",
                    )
                continue

            if on_progress:
                on_progress("segment", i + 1, n_paths, f"Plano {i + 1}/{n_paths}")
            motion = (
                segment_motions[i]
                if segment_motions and i < len(segment_motions)
                else "push_in"
            )
            ok = _write_image_segment_mp4(
                p,
                float(segs[i]),
                (tw, th),
                seg_path,
                zoom_end=kb_zoom,
                fps=kb_fps,
                ken_burns_enabled=kb_on,
                motion=motion,
            )
            if not ok:
                clip = _image_clip_cover_kenburns(
                    p,
                    float(segs[i]),
                    (tw, th),
                    ken_burns_enabled=kb_on,
                    motion=motion,
                )
                clip.write_videofile(
                    str(seg_path),
                    codec="libx264",
                    audio=False,
                    fps=kb_fps,
                    preset="fast",
                    threads=2,
                    logger=None,
                )
                clip.close()
            segment_paths.append(seg_path)
            if persistent and ck_path is not None:
                completed.append(i)
                if (i + 1) % batch_every == 0 or (i + 1) == n_paths:
                    save_checkpoint(
                        ck_path,
                        fingerprint=fingerprint,
                        segments_total=n_paths,
                        completed_indices=completed,
                        segments_root=tmp_root,
                        last_message=f"Plano {i + 1}/{n_paths}",
                    )

        return _concat_segment_files_to_video_only(
            segment_paths,
            tmp_root,
            fast_preview=fast_preview,
            on_progress=on_progress,
        )
    except Exception:
        if not persistent:
            shutil.rmtree(tmp_root, ignore_errors=True)
        raise


def _render_keep_segments_on_disk() -> bool:
    raw = (os.environ.get("RENDER_KEEP_SEGMENTS") or "").strip().lower()
    return raw in ("1", "true", "yes")


def assemble_from_image_files(
    image_paths: list[Path],
    narration_audio: Path,
    output_path: Path,
    *,
    music_audio: Path | None = None,
    chapter_titles: list[tuple[float, str]] | None = None,
    frame_size: tuple[int, int] | None = (1920, 1080),
    min_segment_s: float = 2.5,
    beat_schedule: list[dict] | None = None,
    segment_durations_s: list[float] | None = None,
    narration_cap_s: float | None = None,
    fast_preview: bool = False,
    ken_burns_enabled: bool | None = None,
    on_progress: ProgressCallback | None = None,
    work_dir: Path | None = None,
    segment_motions: list[str] | None = None,
) -> Path:
    """
    Monta un vídeo a partir de imágenes fijas (PNG/JPG).

    Prioridad de duración por plano:
    1. ``segment_durations_s`` (p. ej. ``duration_ms`` por bloque del Scene Editor)
    2. ``beat_schedule`` (music plan)
    3. Reparto uniforme (con repetición de imágenes si hace falta para ``min_segment_s``)
    """
    if not image_paths:
        raise ValueError("No hay imágenes para montar.")

    fs = frame_size or (1920, 1080)
    narration = AudioFileClip(str(narration_audio))
    target_dur = float(narration.duration)
    if narration_cap_s is not None and narration_cap_s > 0:
        target_dur = min(target_dur, float(narration_cap_s))
        narration = narration.subclip(0, target_dur)

    paths = list(image_paths)
    # fast_preview solo acelera la codificación (preset/fps export); no quita Ken Burns.
    kb_enabled = ken_burns_enabled
    chunk_durs = (
        [max(0.05, float(d)) for d in segment_durations_s]
        if segment_durations_s
        else []
    )
    if chunk_durs and len(chunk_durs) == len(paths):
        total_seg = sum(chunk_durs)
        if total_seg > 0 and abs(total_seg - target_dur) > 0.02:
            scale = target_dur / total_seg
            segs = [max(0.05, d * scale) for d in chunk_durs]
        else:
            segs = chunk_durs
    elif chunk_durs:
        segs = []
    else:
        segs = []

    if not segs:
        forced_durs = (
            _beat_schedule_to_durations(beat_schedule or [], target_dur=target_dur)
            if beat_schedule
            else []
        )
        if forced_durs:
            paths = [paths[i % len(paths)] for i in range(len(forced_durs))]
            segs = forced_durs

    if not segs:
        seg = target_dur / len(paths)
        if seg < min_segment_s:
            n_needed = max(1, int(math.ceil(target_dur / min_segment_s)))
            paths = [paths[i % len(paths)] for i in range(n_needed)]
        segs = [target_dur / len(paths)] * len(paths)
    n_paths = len(paths)
    # Mismo pipeline para preview (12 planos) y draft (92): easing por plano + concat.
    use_streaming = n_paths >= 2 and shutil.which("ffmpeg") is not None
    tmp_stream_root: Path | None = None
    beat_layers: list = []

    streamed_video_only: Path | None = None
    base_video = None
    if use_streaming:
        if on_progress:
            on_progress("segment", 0, n_paths, "Preparando planos (ffmpeg, bajo RAM)…")
        try:
            streamed_video_only = _assemble_images_streaming_ffmpeg(
                paths,
                segs,
                fs,
                fast_preview=fast_preview,
                on_progress=on_progress,
                work_dir=work_dir,
                segment_motions=segment_motions,
            )
            tmp_stream_root = streamed_video_only.parent
        except Exception as stream_err:
            recovered = _recover_streaming_concat_from_disk(
                work_dir,
                n_paths,
                fast_preview=fast_preview,
                on_progress=on_progress,
            )
            if recovered is not None:
                streamed_video_only = recovered
                tmp_stream_root = recovered.parent
            elif work_dir is not None and _all_segments_usable(
                _segment_paths_ordered(segments_dir_for_work(work_dir), n_paths)
            ):
                raise RuntimeError(
                    "Todos los planos están en pipeline/render_segments/ pero ffmpeg "
                    "no pudo unirlos en un solo vídeo. Revisa ffmpeg, espacio en disco "
                    "y la consola del backend. No se volverán a generar los planos."
                ) from stream_err
            else:
                use_streaming = False
                streamed_video_only = None
                beat_layers = []

    if not use_streaming:
        if on_progress:
            on_progress("segment", 0, n_paths, "Preparando planos (Ken Burns)…")
        for i, p in enumerate(paths):
            if on_progress:
                on_progress(
                    "segment",
                    i + 1,
                    n_paths,
                    f"Plano {i + 1}/{n_paths}",
                )
            motion = (
                segment_motions[i]
                if segment_motions and i < len(segment_motions)
                else "push_in"
            )
            beat_layers.append(
                _image_clip_cover_kenburns(
                    p,
                    float(segs[i]),
                    fs,
                    ken_burns_enabled=kb_enabled,
                    motion=motion,
                )
            )
        if on_progress:
            on_progress("concat", n_paths, n_paths, "Uniendo planos…")
        base_video = concatenate_videoclips(beat_layers, method="compose")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = chapter_titles

    if streamed_video_only is not None and streamed_video_only.is_file():
        mixed_wav = (tmp_stream_root or output_path.parent) / "_render_audio_mix.wav"
        try:
            if on_progress:
                on_progress("encode", 0, 1, "Mezclando audio y mux (sin re-codificar vídeo)…")
            _write_mixed_audio_wav(
                narration_audio,
                target_dur,
                mixed_wav,
                music_audio=music_audio,
            )
            _ffmpeg_mux_video_with_audio(
                streamed_video_only,
                mixed_wav,
                output_path,
                target_dur=target_dur,
            )
            if on_progress:
                on_progress("done", 1, 1, "MP4 listo")
        finally:
            try:
                narration.close()
            except Exception:
                pass
            mixed_wav.unlink(missing_ok=True)
            if tmp_stream_root is not None:
                if work_dir is not None:
                    cleanup_after_success(
                        work_dir, keep=_render_keep_segments_on_disk()
                    )
                else:
                    shutil.rmtree(tmp_stream_root, ignore_errors=True)
        return output_path

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
    try:
        if on_progress:
            on_progress("encode", 0, 1, "Codificando MP4 (MoviePy/ffmpeg)…")
        final.write_videofile(
            str(output_path), **_export_mp4_kwargs(fast_preview=fast_preview)
        )
        if on_progress:
            on_progress("done", 1, 1, "MP4 listo")
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
                tmp = getattr(c, "_vm_temp_path", None)
                if tmp:
                    Path(str(tmp)).unlink(missing_ok=True)
            except Exception:
                pass
            try:
                c.close()
            except Exception:
                pass
    return output_path
