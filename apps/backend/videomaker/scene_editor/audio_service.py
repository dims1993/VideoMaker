"""TTS por chunk — ElevenLabs (producción) o mock (desarrollo sin API key)."""

from __future__ import annotations

import asyncio
import os
import random
import struct
import time
import wave
from collections.abc import Callable
from pathlib import Path

from videomaker.scene_editor.models import Chunk
from videomaker.tts.elevenlabs_client import (
    ElevenLabsError,
    scene_tts_provider,
    synthesize_speech,
)


def _write_silent_wav(path: Path, duration_ms: int, sample_rate: int = 22050) -> None:
    """WAV mínimo para mock / fallback."""
    n_frames = max(1, int(sample_rate * duration_ms / 1000))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<h", 0) * n_frames)


def _duration_ms_from_audio(path: Path) -> int:
    try:
        from pydub import AudioSegment

        seg = AudioSegment.from_file(str(path))
        return max(1, len(seg))
    except Exception:
        return 0


def _chunk_audio_path(work_dir: Path, chunk_id: str, *, ext: str) -> Path:
    return work_dir / "scene_audio" / f"{Path(chunk_id).name}{ext}"


def resolve_chunk_audio_file(work_dir: Path, chunk_id: str) -> Path | None:
    """Busca MP3 (ElevenLabs) o WAV (mock) del chunk."""
    safe = Path(chunk_id).name
    base = work_dir / "scene_audio"
    for ext in (".mp3", ".wav"):
        p = base / f"{safe}{ext}"
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _sync_elevenlabs(path: Path, text: str, *, voice_id: str | None) -> int:
    mp3_bytes = synthesize_speech(text, voice_id=voice_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(mp3_bytes)
    ms = _duration_ms_from_audio(path)
    return ms or max(1000, len(text.split()) * 280)


async def _generate_mock(path: Path, text: str) -> int:
    await asyncio.sleep(2.0)
    duration_ms = random.randint(2500, min(9000, max(3000, len(text.split()) * 320)))
    _write_silent_wav(path, duration_ms)
    return duration_ms


async def generate_chunk_audio(
    *,
    work_dir: Path,
    chunk: Chunk,
    narration_text: str | None = None,
    api_base: str = "/api",
    work_slug: str = "output/ui_session",
    voice_id: str | None = None,
) -> Chunk:
    text = (narration_text if narration_text is not None else chunk.narration_text).strip()
    if not text:
        raise ValueError("El bloque no tiene texto narrable para TTS.")

    provider = scene_tts_provider()
    safe_id = Path(chunk.id).name

    # Limpia audios previos de otro proveedor
    for ext in (".mp3", ".wav"):
        old = _chunk_audio_path(work_dir, safe_id, ext=ext)
        if old.is_file():
            old.unlink(missing_ok=True)

    if provider == "elevenlabs":
        out_path = _chunk_audio_path(work_dir, safe_id, ext=".mp3")
        try:
            duration_ms = await asyncio.to_thread(
                _sync_elevenlabs, out_path, text, voice_id=voice_id
            )
        except ElevenLabsError:
            raise
        except Exception as e:
            raise ElevenLabsError(f"Error al sintetizar con ElevenLabs: {e}") from e
    else:
        out_path = _chunk_audio_path(work_dir, safe_id, ext=".wav")
        duration_ms = await _generate_mock(out_path, text)

    audio_url = (
        f"{api_base}/audio/chunk-file"
        f"?work={work_slug}&chunk_id={safe_id}&t={int(time.time() * 1000)}"
    )
    from videomaker.scene_editor.chunk_visual_rhythm import ensure_visual_shots_for_rhythm

    updated = chunk.model_copy(
        update={
            "narration_text": text,
            "status": "done",
            "audio_url": audio_url,
            "duration_ms": duration_ms,
        }
    )
    return ensure_visual_shots_for_rhythm(work_dir, updated)


def _batch_delay_sec() -> float:
    raw = (os.environ.get("ELEVENLABS_BATCH_DELAY_MS") or "350").strip()
    try:
        ms = max(0, int(raw))
    except ValueError:
        ms = 350
    return ms / 1000.0


def _should_skip_chunk(
    chunk: Chunk,
    work_dir: Path,
    *,
    skip_with_audio: bool,
    regenerate_all: bool,
) -> bool:
    if regenerate_all:
        return False
    if not skip_with_audio:
        return False
    if chunk.status != "done":
        return False
    if not (chunk.narration_text or "").strip():
        return True
    if not (chunk.audio_url or "").strip():
        return False
    return resolve_chunk_audio_file(work_dir, chunk.id) is not None


async def generate_all_chunks_audio(
    *,
    work_dir: Path,
    chunks: list[Chunk],
    work_slug: str = "output/ui_session",
    voice_id: str | None = None,
    skip_with_audio: bool = True,
    regenerate_all: bool = False,
    on_progress: Callable[[list[Chunk]], None] | None = None,
) -> tuple[list[Chunk], int, int, int, list[dict[str, str]]]:
    """
    Genera TTS para todos los bloques pendientes, uno tras otro.
    Persiste progreso vía callback ``on_progress(updated_chunks)`` tras cada bloque.
    """
    out = [c.model_copy() for c in chunks]
    generated = 0
    skipped = 0
    failed = 0
    errors: list[dict[str, str]] = []
    delay = _batch_delay_sec() if scene_tts_provider() == "elevenlabs" else 0.0

    for i, chunk in enumerate(out):
        if not (chunk.narration_text or "").strip():
            skipped += 1
            continue
        if _should_skip_chunk(
            chunk, work_dir, skip_with_audio=skip_with_audio, regenerate_all=regenerate_all
        ):
            skipped += 1
            continue

        out[i] = chunk.model_copy(update={"status": "generating"})
        if on_progress:
            on_progress(out)

        did_call_tts = False
        try:
            updated = await generate_chunk_audio(
                work_dir=work_dir,
                chunk=chunk,
                work_slug=work_slug,
                voice_id=voice_id,
            )
            out[i] = updated
            generated += 1
            did_call_tts = True
        except (ValueError, ElevenLabsError) as e:
            out[i] = chunk.model_copy(update={"status": "error"})
            failed += 1
            errors.append({"chunk_id": chunk.id, "detail": str(e)})
        except Exception as e:
            out[i] = chunk.model_copy(update={"status": "error"})
            failed += 1
            errors.append({"chunk_id": chunk.id, "detail": str(e)})

        if on_progress:
            on_progress(out)

        if delay > 0 and did_call_tts:
            await asyncio.sleep(delay)

    return out, generated, skipped, failed, errors


def _chunk_gap_ms(explicit: int | None) -> int:
    if explicit is not None:
        return max(0, min(int(explicit), 3000))
    raw = (os.environ.get("SCENE_AUDIO_CHUNK_GAP_MS") or "0").strip()
    try:
        return max(0, min(int(raw), 3000))
    except ValueError:
        return 0


def export_chunks_to_narration_wav(
    work_dir: Path,
    chunks: list[Chunk],
    *,
    chunk_gap_ms: int | None = None,
) -> dict[str, object]:
    """
    Une los MP3/WAV de ``scene_audio/`` en orden de bloques → ``narracion.wav``.
    """
    from videomaker.audio.audio_concat import phrase_join_fade_ms_default, wav_duration_seconds

    gap_ms = _chunk_gap_ms(chunk_gap_ms)
    paths: list[Path] = []
    missing: list[str] = []

    for chunk in chunks:
        if not (chunk.narration_text or "").strip():
            continue
        p = resolve_chunk_audio_file(work_dir, chunk.id)
        if p is None:
            missing.append(chunk.id)
            continue
        paths.append(p)

    if not paths:
        raise ValueError(
            "No hay audios de bloques en disco. Genera audio en el Scene Editor primero."
        )

    try:
        from pydub import AudioSegment
    except ImportError as e:
        raise RuntimeError(
            "Falta pydub para unir MP3. En el venv: pip install pydub (y ffmpeg en PATH)."
        ) from e

    fade_ms = phrase_join_fade_ms_default()
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=gap_ms) if gap_ms > 0 else None
    n = len(paths)

    for i, p in enumerate(paths):
        seg = AudioSegment.from_file(str(p))
        ms = len(seg)
        if fade_ms > 0 and ms >= 4:
            fd = min(fade_ms, max(4, ms // 3))
            if i > 0:
                seg = seg.fade_in(fd)
            if i < n - 1:
                seg = seg.fade_out(fd)
        combined += seg
        if silence is not None and i < n - 1:
            combined += silence

    out = work_dir / "narracion.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(out), format="wav")

    duration_s = wav_duration_seconds(out)
    return {
        "path": out.name,
        "duration_s": duration_s,
        "chunks_used": len(paths),
        "chunks_missing": missing,
    }
