"""Audio de referencia para clonación XTTS (MP3/WAV/… → WAV mono)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

# Extensiones que intentamos leer con librosa (MP3 vía ffmpeg/audioread).
REFERENCE_SUFFIXES = frozenset({".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm", ".opus"})

# XTTS funciona bien con audio claro; 22.05 kHz mono reduce tamaño y es habitual en TTS.
_REFERENCE_SR = 22050
_MAX_SECONDS = 120


def normalize_reference_for_xtts(src: Path, dest_wav: Path) -> None:
    """
    Lee `src`, recorta/resamplea y escribe `dest_wav` (PCM 16, mono).
    Requiere `librosa` y, para MP3/M4A, ffmpeg en el PATH.
    """
    import librosa
    import soundfile as sf

    if not src.is_file():
        raise FileNotFoundError(str(src))

    y, _sr = librosa.load(str(src), sr=_REFERENCE_SR, mono=True)
    if y.size == 0:
        raise ValueError("No se pudo leer audio útil del archivo (¿vacío o corrupto?).")

    # Quitar silencios inicial/final para que el embedding use solo voz útil.
    trimmed, _ = librosa.effects.trim(y, top_db=22)
    if trimmed.size >= _REFERENCE_SR * 3:
        y = trimmed

    # Suavizar picos extremos (referencias grabadas muy fuerte)
    y = np.clip(y.astype(np.float64), -1.0, 1.0).astype(np.float32)

    max_samples = _REFERENCE_SR * _MAX_SECONDS
    if y.shape[0] > max_samples:
        y = y[:max_samples]

    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest_wav), y, _REFERENCE_SR, subtype="PCM_16")
