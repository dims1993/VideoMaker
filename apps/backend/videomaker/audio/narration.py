"""Guion → fragmentos TTS → un solo WAV de narración."""

from __future__ import annotations

import os
from pathlib import Path

from .audio_concat import (
    concat_paragraph_groups_pydub,
    concat_wav_files,
    wav_duration_seconds,
    write_silence_wav_like,
)
from videomaker.core.models import VoiceProfile
from videomaker.core.script_clean import text_for_tts
from videomaker.llm.script_gen import split_script_into_segments
from videomaker.tts.voice_gen import synthesize_chunks


def _paragraph_pause_seconds(explicit: float | None) -> float:
    if explicit is not None:
        return max(0.0, min(float(explicit), 5.0))
    raw = os.environ.get("VIDEOMAKER_PARAGRAPH_PAUSE_SEC", "2").strip()
    try:
        s = float(raw.replace(",", "."))
    except ValueError:
        s = 2.0
    return max(0.0, min(s, 5.0))


def _paragraphs_from_clean_script(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def build_narration_wav(
    script_text: str,
    profile: VoiceProfile,
    work_dir: Path,
    *,
    max_chars_per_segment: int = 900,
    strip_markers: bool = True,
    max_segments: int | None = None,
    paragraph_pause_s: float | None = None,
) -> tuple[Path, float]:
    """
    Escribe ``work_dir/narracion.wav`` y devuelve (ruta, duración en segundos).
    Los fragmentos quedan en ``work_dir/tts_chunks/``.

    Entre **párrafos** (línea en blanco en el guion limpio) la cadena final usa **pydub**:
    *fade-out* al final de cada párrafo (por defecto 100 ms, ``VIDEOMAKER_PARAGRAPH_FADE_OUT_MS``)
    y silencio antes del siguiente bloque (por defecto 2 s, ``VIDEOMAKER_PARAGRAPH_PAUSE_SEC``).
    Desactiva pausas con ``paragraph_pause_s=0`` o variable ``0``.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    raw = text_for_tts(script_text) if strip_markers else script_text
    pause_s = _paragraph_pause_seconds(paragraph_pause_s)
    paragraphs = _paragraphs_from_clean_script(raw)

    if not paragraphs:
        raise ValueError("El guion quedó vacío tras la limpieza; nada que narrar.")

    chunk_dir = work_dir / "tts_chunks"
    out = work_dir / "narracion.wav"

    # Un solo bloque o sin pausa: comportamiento clásico (troceo solo por tamaño).
    if len(paragraphs) == 1 or pause_s <= 0:
        segments = split_script_into_segments(raw, max_chars=max_chars_per_segment)
        if max_segments is not None:
            segments = segments[: max(0, max_segments)]
        if not segments:
            raise ValueError("El guion quedó vacío tras la limpieza; nada que narrar.")
        wavs = synthesize_chunks(segments, profile, chunk_dir)
        concat_wav_files(wavs, out)
        return out, wav_duration_seconds(out)

    groups: list[list[Path]] = []
    idx = 0
    for pi, para in enumerate(paragraphs):
        segs = split_script_into_segments(para.strip(), max_chars=max_chars_per_segment)
        if max_segments is not None:
            allowed = max_segments - idx
            if allowed <= 0:
                break
            segs = segs[:allowed]
        if not segs:
            continue
        batch = synthesize_chunks(
            segs,
            profile,
            chunk_dir,
            start_index=idx,
        )
        groups.append(batch)
        idx += len(batch)

    if not groups:
        raise ValueError("El guion quedó vacío tras la limpieza; nada que narrar.")

    silence_ms = max(0, int(round(pause_s * 1000)))
    try:
        concat_paragraph_groups_pydub(
            groups,
            out,
            silence_between_ms=silence_ms,
        )
    except ImportError:
        wavs: list[Path] = []
        for gi, batch in enumerate(groups):
            wavs.extend(batch)
            if gi < len(groups) - 1 and pause_s > 0 and batch:
                pause_path = chunk_dir / f"pause_after_para_{gi:02d}.wav"
                write_silence_wav_like(pause_path, pause_s, batch[-1])
                wavs.append(pause_path)
        concat_wav_files(wavs, out)
    return out, wav_duration_seconds(out)
