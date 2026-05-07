"""Ajustes de inferencia XTTS v2 para clonación más estable (Coqui TTS).

Los valores por defecto aquí son más conservadores que los del config empaquetado:
menos temperatura → timbre más consistente; normalización de referencias → menos salto de volumen.

Todo se puede anular con variables de entorno (ver `.env.example`)."""

from __future__ import annotations

import os


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def apply_xtts_config_from_env(tts: object) -> None:
    """
    Tras `TTS(...)`, Coqui lee estos campos desde `tts_config` en cada `synthesize`.
    Solo actúa si el modelo es XTTS.
    """
    syn = getattr(tts, "synthesizer", None)
    cfg = getattr(syn, "tts_config", None) if syn else None
    if cfg is None:
        return
    model = getattr(cfg, "model", None)
    if model != "xtts":
        return

    if _env_bool("VIDEOMAKER_XTTS_DISABLE_TUNING", False):
        return

    # Inferencia: menos azar → clon más parecido al timbre de referencia (a costa de menos variedad prosódica).
    cfg.temperature = _env_float("VIDEOMAKER_XTTS_TEMPERATURE", 0.68)
    cfg.top_p = _env_float("VIDEOMAKER_XTTS_TOP_P", 0.82)
    cfg.top_k = _env_int("VIDEOMAKER_XTTS_TOP_K", 50)
    cfg.repetition_penalty = _env_float("VIDEOMAKER_XTTS_REPETITION_PENALTY", 10.0)
    cfg.length_penalty = _env_float("VIDEOMAKER_XTTS_LENGTH_PENALTY", 1.0)

    # Referencia: más segundos para latentes GPT + normalizar nivel entre cortes mejora clones con MP3 variable.
    cfg.sound_norm_refs = _env_bool("VIDEOMAKER_XTTS_SOUND_NORM_REFS", True)
    gpt_len = _env_int("VIDEOMAKER_XTTS_GPT_COND_LEN", 18)
    chunk = _env_int("VIDEOMAKER_XTTS_GPT_COND_CHUNK_LEN", 6)
    if chunk > gpt_len:
        chunk = gpt_len
    cfg.gpt_cond_len = gpt_len
    cfg.gpt_cond_chunk_len = chunk
    cfg.max_ref_len = _env_int("VIDEOMAKER_XTTS_MAX_REF_LEN", 12)
