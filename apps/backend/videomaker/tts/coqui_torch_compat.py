"""Compatibilidad Coqui TTS con PyTorch 2.6+ y TorchAudio 2.9+.

En PyTorch 2.6, `torch.load` usa por defecto `weights_only=True`. Los checkpoints XTTS
de Coqui incluyen objetos arbitrarios (p.ej. `XttsConfig`) y fallan con WeightsUnpickler.

Solo relajamos la carga dentro del bloque (modelos Coqui/HF fijados por la app).

TorchAudio 2.9+ hace que `torchaudio.load` dependa del paquete opcional `torchcodec`.
Coqui XTTS llama a `torchaudio.load` para las muestras de voz; si no hay torchcodec,
parcheamos `torchaudio.load` con una implementación basada en librosa (rutas locales)."""

from __future__ import annotations

import importlib.util
import inspect
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_torchaudio_load_patched = False


def ensure_torchaudio_load_without_torchcodec() -> None:
    """Evita el error «TorchCodec is required for load_with_torchcodec» sin instalar torchcodec."""
    global _torchaudio_load_patched
    if _torchaudio_load_patched:
        return
    if importlib.util.find_spec("torchcodec") is not None:
        _torchaudio_load_patched = True
        return
    try:
        import numpy as np
        import torch
        import torchaudio
    except ImportError:
        _torchaudio_load_patched = True
        return

    def _load_via_librosa(
        uri: Any,
        frame_offset: int = 0,
        num_frames: int = -1,
        normalize: bool = True,
        channels_first: bool = True,
        format: Any = None,
        buffer_size: int = 4096,
        backend: Any = None,
    ) -> tuple[Any, int]:
        import librosa

        path: str | None
        if isinstance(uri, (str, Path)):
            path = os.fspath(uri)
        elif hasattr(uri, "__fspath__"):
            path = os.fspath(uri)
        else:
            raise TypeError(
                "Sin paquete torchcodec, solo se admiten rutas de archivo en torchaudio.load "
                f"(recibido {type(uri).__name__}). Instala torchcodec o usa WAV por ruta."
            )

        y, sr = librosa.load(path, sr=None, mono=False)
        y = np.asarray(y, dtype=np.float32)
        if y.ndim == 1:
            audio = torch.from_numpy(np.ascontiguousarray(y)).unsqueeze(0)
        else:
            audio = torch.from_numpy(np.ascontiguousarray(y.T))
        if not channels_first:
            audio = audio.transpose(0, 1)
        fo = int(frame_offset)
        if fo > 0 or (num_frames is not None and int(num_frames) > 0):
            end: int | None = None
            if num_frames is not None and int(num_frames) > 0:
                end = fo + int(num_frames)
            if audio.dim() == 2:
                audio = audio[:, fo:end]
            else:
                audio = audio[fo:end]
        return audio, int(sr)

    torchaudio.load = _load_via_librosa  # type: ignore[method-assign]
    _torchaudio_load_patched = True


@contextmanager
def relaxing_torch_load_weights_only_for_trusted_ckpt() -> Iterator[None]:
    try:
        import torch
    except ImportError:
        yield
        return

    try:
        if "weights_only" not in inspect.signature(torch.load).parameters:
            yield
            return
    except (TypeError, ValueError):
        yield
        return

    _orig = torch.load

    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("weights_only", False)
        return _orig(*args, **kwargs)

    torch.load = _wrapped  # type: ignore[method-assign]
    try:
        yield
    finally:
        torch.load = _orig  # type: ignore[method-assign]
