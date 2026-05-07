"""Concatenar WAVs (misma frecuencia/canales).

Entre fragmentos TTS (frases / trozos de una misma locución) se aplican desvanecimientos
con pydub (``VIDEOMAKER_PHRASE_FADE_MS``, por defecto 100 ms), además del fade de cierre
de párrafo y silencio entre párrafos en ``concat_paragraph_groups_pydub``.
"""

from __future__ import annotations

import os
import wave
from pathlib import Path
from typing import Any


def _effective_fade_ms(segment_ms: int, requested: int) -> int:
    """Evita que el fade coma casi todo un clip muy corto."""
    if requested <= 0 or segment_ms < 4:
        return 0
    return min(requested, max(4, segment_ms // 3))


def _concat_wav_files_wave(inputs: list[Path], output: Path) -> None:
    with wave.open(str(inputs[0]), "rb") as w0:
        nch = w0.getnchannels()
        sw = w0.getsampwidth()
        fr = w0.getframerate()
        comptype = w0.getcomptype()
        compname = w0.getcompname()

    with wave.open(str(output), "wb") as out:
        out.setnchannels(nch)
        out.setsampwidth(sw)
        out.setframerate(fr)
        out.setcomptype(comptype, compname)

        for p in inputs:
            with wave.open(str(p), "rb") as w:
                if (
                    w.getnchannels() != nch
                    or w.getsampwidth() != sw
                    or w.getframerate() != fr
                ):
                    raise ValueError(
                        f"Formato distinto en {p}: esperaba {nch}ch, {sw}b, {fr}Hz "
                        "en todos los fragmentos. Re-exporta o usa ffmpeg."
                    )
                out.writeframes(w.readframes(w.getnframes()))


def _concat_wav_files_pydub_fades(
    inputs: list[Path],
    output: Path,
    *,
    join_fade_ms: int,
) -> None:
    from pydub import AudioSegment

    combined = AudioSegment.empty()
    n = len(inputs)
    for i, p in enumerate(inputs):
        seg = AudioSegment.from_wav(str(p))
        ms = len(seg)
        fd = _effective_fade_ms(ms, join_fade_ms)
        if i > 0 and fd > 0:
            seg = seg.fade_in(fd)
        if i < n - 1 and fd > 0:
            seg = seg.fade_out(fd)
        combined += seg
    combined.export(str(output), format="wav")


def phrase_join_fade_ms_default() -> int:
    """
    Desvanecimiento entre trozos TTS consecutivos (frases dentro del mismo párrafo).

    Prioriza ``VIDEOMAKER_PHRASE_FADE_MS``; si no existe, usa ``VIDEOMAKER_CONCAT_FADE_MS``
    (compatibilidad); si tampoco, 100 ms.
    """
    raw = os.environ.get("VIDEOMAKER_PHRASE_FADE_MS", "").strip()
    if not raw:
        raw = os.environ.get("VIDEOMAKER_CONCAT_FADE_MS", "100").strip()
    try:
        v = int(raw)
    except ValueError:
        v = 100
    return max(0, min(v, 300))


def merge_wav_paths_pydub(paths: list[Path], join_fade_ms: int | None = None) -> Any:
    """
    Une varios WAV en un solo ``AudioSegment`` (pydub), con *fade in / fade out* en cada
    unión entre trozos (misma lógica que ``concat_wav_files``). Requiere pydub.

    ``join_fade_ms``: duración pedida; si es ``None``, usa ``phrase_join_fade_ms_default()``.
    """
    from pydub import AudioSegment

    if not paths:
        return AudioSegment.empty()
    combined = AudioSegment.empty()
    n = len(paths)
    if join_fade_ms is None:
        jf = phrase_join_fade_ms_default()
    else:
        jf = max(0, min(int(join_fade_ms), 300))
    for i, p in enumerate(paths):
        seg = AudioSegment.from_wav(str(p))
        ms = len(seg)
        fd = _effective_fade_ms(ms, jf)
        if i > 0 and fd > 0:
            seg = seg.fade_in(fd)
        if i < n - 1 and fd > 0:
            seg = seg.fade_out(fd)
        combined += seg
    return combined


def paragraph_fade_out_ms_default() -> int:
    raw = os.environ.get("VIDEOMAKER_PARAGRAPH_FADE_OUT_MS", "100").strip()
    try:
        v = int(raw)
    except ValueError:
        v = 100
    return max(0, min(v, 500))


def concat_paragraph_groups_pydub(
    groups: list[list[Path]],
    output: Path,
    *,
    silence_between_ms: int,
    paragraph_fade_out_ms: int | None = None,
    intra_join_fade_ms: int | None = None,
) -> None:
    """
    Por cada párrafo: une sus clips TTS (micro-fades entre ellos), aplica *fade-out* al
    final del bloque y, si no es el último párrafo, añade silencio antes del siguiente.

    ``paragraph_fade_out_ms``: por defecto ``VIDEOMAKER_PARAGRAPH_FADE_OUT_MS`` (100).
    ``silence_between_ms``: duración del silencio entre párrafos en ms (p. ej. 2000).
    ``intra_join_fade_ms``: trozos dentro del párrafo; por defecto ``phrase_join_fade_ms_default()``
    (``VIDEOMAKER_PHRASE_FADE_MS``).
    """
    from pydub import AudioSegment

    if not groups:
        raise ValueError("No hay grupos de WAV para concatenar.")
    output.parent.mkdir(parents=True, exist_ok=True)

    if paragraph_fade_out_ms is None:
        paragraph_fade_out_ms = paragraph_fade_out_ms_default()

    if intra_join_fade_ms is None:
        intra_join_fade_ms = phrase_join_fade_ms_default()
    else:
        intra_join_fade_ms = max(0, min(int(intra_join_fade_ms), 300))

    non_empty = [g for g in groups if g]
    if not non_empty:
        raise ValueError("Todos los grupos de párrafo están vacíos.")

    final = AudioSegment.empty()
    last_idx = len(non_empty) - 1
    for gi, group in enumerate(non_empty):
        block = merge_wav_paths_pydub(group, join_fade_ms=intra_join_fade_ms)
        fo = paragraph_fade_out_ms
        if fo > 0:
            fo = min(fo, len(block))
            if fo > 0:
                block = block.fade_out(fo)
        final += block
        if gi < last_idx:
            final += AudioSegment.silent(duration=max(0, silence_between_ms))

    final.export(str(output), format="wav")


def concat_wav_files(
    inputs: list[Path],
    output: Path,
    *,
    join_fade_ms: int | None = None,
) -> None:
    """
    Une WAVs en orden.

    Con 2+ fragmentos y ``join_fade_ms`` > 0 (por defecto ``phrase_join_fade_ms_default()``,
    típicamente 100 ms), aplica *fade_in* al inicio de cada trozo salvo el primero y
    *fade_out* al final de cada trozo salvo el último.

    Si pydub no está instalado, se concatena en crudo (comportamiento anterior).
    """
    if not inputs:
        raise ValueError("No hay WAVs para concatenar.")
    output.parent.mkdir(parents=True, exist_ok=True)

    if join_fade_ms is None:
        join_fade_ms = phrase_join_fade_ms_default()
    else:
        join_fade_ms = max(0, min(int(join_fade_ms), 300))

    use_fades = join_fade_ms > 0 and len(inputs) > 1
    if use_fades:
        try:
            _concat_wav_files_pydub_fades(inputs, output, join_fade_ms=join_fade_ms)
            return
        except ImportError:
            pass

    _concat_wav_files_wave(inputs, output)


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return frames / float(rate) if rate else 0.0


def read_wav_format(path: Path) -> tuple[int, int, int]:
    """Devuelve ``(sample_rate, n_channels, sample_width)`` de un WAV PCM."""
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth()


def write_silence_wav(
    path: Path,
    duration_s: float,
    *,
    sample_rate: int,
    n_channels: int,
    sample_width: int,
) -> None:
    """WAV silencioso (PCM), mismo formato que los trozos TTS para concatenar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    nframes = max(0, int(duration_s * sample_rate))
    frame_bytes = n_channels * sample_width
    with wave.open(str(path), "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(sample_width)
        w.setframerate(sample_rate)
        w.setcomptype("NONE", "not compressed")
        w.writeframes(b"\x00" * (nframes * frame_bytes))


def write_silence_wav_like(path: Path, duration_s: float, reference_wav: Path) -> None:
    """Silencio con la misma tasa/canales/ancho que ``reference_wav``."""
    sr, nch, sw = read_wav_format(reference_wav)
    write_silence_wav(path, duration_s, sample_rate=sr, n_channels=nch, sample_width=sw)
