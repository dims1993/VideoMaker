"""Síntesis de voz local: Coqui (VITS / Tacotron) y ⓍTTS v2 (multilingüe + clonación)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from videomaker.core import config
from .xtts_tuning import apply_xtts_config_from_env
from .coqui_torch_compat import (
    ensure_torchaudio_load_without_torchcodec,
    relaxing_torch_load_weights_only_for_trusted_ckpt,
)
from videomaker.core.models import Locale, VoiceProfile

# Modelo multilingüe recomendado (calidad tipo “premium” en local)
XTTS_V2_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

# Caché por (modelo, gpu) para no recargar pesos en cada fragmento de guion
_tts_cache: dict[tuple[str, bool], object] = {}


def _want_gpu() -> bool:
    if os.environ.get("TTS_USE_GPU", "").lower() in ("0", "false", "no"):
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def _is_xtts_model(model_ref: str) -> bool:
    return "xtts" in model_ref.lower()


def _get_tts(model_name: str):
    ensure_torchaudio_load_without_torchcodec()
    gpu = _want_gpu()
    key = (model_name, gpu)
    if key not in _tts_cache:
        try:
            from TTS.api import TTS  # type: ignore
        except ImportError as e:
            msg = str(e)
            if "BeamSearchScorer" in msg or "transformers" in msg.lower():
                raise RuntimeError(
                    "Tu instalación de Coqui TTS no es compatible con la versión actual de "
                    "`transformers` (error típico: BeamSearchScorer). "
                    "En el venv ejecuta:\n"
                    '  python -m pip install "transformers==4.37.2" "tokenizers==0.15.2"\n'
                    "y vuelve a probar."
                ) from e
            raise
        try:
            with relaxing_torch_load_weights_only_for_trusted_ckpt():
                inst = TTS(model_name=model_name, progress_bar=False, gpu=gpu)
                apply_xtts_config_from_env(inst)
                _tts_cache[key] = inst
        except ImportError as e:
            msg = str(e)
            if "BeamSearchScorer" in msg or "transformers" in msg.lower():
                raise RuntimeError(
                    "Coqui TTS falló al cargar el modelo por incompatibilidad con `transformers`. "
                    "Prueba:\n"
                    '  python -m pip install "transformers==4.37.2" "tokenizers==0.15.2"\n'
                    "y reinicia el servidor."
                ) from e
            raise
    return _tts_cache[key]


def _resolve_clone_paths(profile: VoiceProfile) -> list[Path] | None:
    """Rutas WAV para clonación XTTS; None si no hay ninguna válida."""
    candidates: list[Path] = []
    if profile.speaker_wav and profile.speaker_wav.is_file():
        candidates.append(profile.speaker_wav)
    if profile.auto_clone_from_samples:
        root = config.VOICE_SAMPLES_DIR
        for name in ("reference.wav", f"reference_{profile.locale.value}.wav"):
            p = root / name
            if p.is_file():
                candidates.append(p)
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in candidates:
        k = str(p.resolve())
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq or None


def synthesize_with_coqui(
    text: str,
    profile: VoiceProfile,
    out_wav: Path,
    *,
    split_sentences: bool | None = None,
) -> None:
    try:
        import TTS  # noqa: F401
    except ImportError as e:
        msg = str(e)
        if "BeamSearchScorer" in msg or "transformers" in msg.lower():
            raise RuntimeError(
                "Coqui TTS no pudo importarse por incompatibilidad con `transformers`. "
                "Ejecuta en el venv:\n"
                '  python -m pip install "transformers==4.37.2" "tokenizers==0.15.2"\n'
                "y vuelve a intentar."
            ) from e
        raise RuntimeError(
            "Coqui TTS no está instalado. En tu venv: pip install TTS "
            "y torch (CPU o CUDA según https://pytorch.org/get-started/locally/)."
        ) from e

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with relaxing_torch_load_weights_only_for_trusted_ckpt():
        tts = _get_tts(profile.model_ref)

        if _is_xtts_model(profile.model_ref):
            lang = profile.locale.value
            clone_paths = _resolve_clone_paths(profile)
            kwargs: dict = {
                "text": text,
                "file_path": str(out_wav),
                "language": lang,
            }
            if split_sentences is not None:
                kwargs["split_sentences"] = split_sentences
            else:
                kwargs["split_sentences"] = True

            if clone_paths:
                kwargs["speaker_wav"] = [str(p) for p in clone_paths]
            elif profile.xtts_builtin_speaker:
                kwargs["speaker"] = profile.xtts_builtin_speaker
            else:
                kwargs["speaker"] = "Ana Florence"

            tts.tts_to_file(**kwargs)
        else:
            tts.tts_to_file(text=text, file_path=str(out_wav))


def synthesize_chunks(
    segments: list[str],
    profile: VoiceProfile,
    out_dir: Path,
    *,
    start_index: int = 0,
    on_segment: Callable[[int, Path], None] | None = None,
    split_sentences: bool | None = None,
) -> list[Path]:
    """
    Genera un WAV por segmento. Concatenación final la hace ffmpeg o el editor.

    ``start_index`` desplaza la numeración ``voice_XXXX.wav`` (p. ej. pausas entre párrafos).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, seg in enumerate(segments):
        target = out_dir / f"voice_{start_index + i:04d}.wav"
        if profile.engine == "coqui":
            synthesize_with_coqui(
                seg, profile, target, split_sentences=split_sentences
            )
        elif profile.engine == "bark":
            raise NotImplementedError(
                "Bark: integra suno-bark y escribe aquí la llamada; API distinta a Coqui."
            )
        else:
            raise ValueError(f"Motor no soportado: {profile.engine}")
        paths.append(target)
        if on_segment:
            on_segment(start_index + i, target)
    return paths


VOICE_PRESETS: dict[str, VoiceProfile] = {
    "xtts_v2_es": VoiceProfile(
        id="xtts_v2_es",
        label="ⓍTTS v2 — español (clon o voz Coqui)",
        engine="coqui",
        model_ref=XTTS_V2_MODEL,
        locale=Locale.ES,
        notes="Opcional: coloca voice_samples/reference_es.wav (o reference.wav) para clonar. "
        "Sin archivo, usa voz integrada (xtts_builtin_speaker).",
        xtts_builtin_speaker="Ana Florence",
    ),
    "xtts_v2_en": VoiceProfile(
        id="xtts_v2_en",
        label="ⓍTTS v2 — English (clone or built-in)",
        engine="coqui",
        model_ref=XTTS_V2_MODEL,
        locale=Locale.EN,
        notes="Optional: voice_samples/reference_en.wav. Default built-in speaker.",
        xtts_builtin_speaker="Ana Florence",
    ),
    "es_coqui_default": VoiceProfile(
        id="es_coqui_default",
        label="Español — VITS ligero (Coqui)",
        engine="coqui",
        model_ref="tts_models/es/css10/vits",
        locale=Locale.ES,
        notes="Más rápido que XTTS; menos ‘cinematográfico’.",
        auto_clone_from_samples=False,
    ),
    "en_coqui_default": VoiceProfile(
        id="en_coqui_default",
        label="English — LJSpeech Tacotron2 (Coqui)",
        engine="coqui",
        model_ref="tts_models/en/ljspeech/tacotron2-DDC",
        locale=Locale.EN,
        notes="Ligero; para máxima calidad usa xtts_v2_en.",
        auto_clone_from_samples=False,
    ),
}


def list_voice_presets() -> list[VoiceProfile]:
    return list(VOICE_PRESETS.values())


def get_voice_preset(preset_id: str) -> VoiceProfile:
    if preset_id not in VOICE_PRESETS:
        known = ", ".join(sorted(VOICE_PRESETS))
        raise KeyError(f"Preset de voz desconocido: {preset_id}. Disponibles: {known}")
    return VOICE_PRESETS[preset_id]


def list_xtts_builtin_speakers() -> list[str]:
    """Lista voces integradas del modelo XTTS (requiere descargar el modelo la primera vez)."""
    try:
        tts = _get_tts(XTTS_V2_MODEL)
    except ImportError as e:
        raise RuntimeError("Instala Coqui TTS: pip install TTS") from e
    speakers = getattr(tts, "speakers", None)
    if not speakers:
        return []
    if isinstance(speakers, (list, tuple)):
        return list(speakers)
    return list(speakers)
