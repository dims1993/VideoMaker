"""Valores por defecto del generador (ritmo, capítulos, montaje)."""

from __future__ import annotations

import os
from pathlib import Path

# Duración objetivo guion (minutos)
SCRIPT_DURATION_MIN = 6
SCRIPT_DURATION_MAX = 10

# Retención: cambio de clip (segundos)
CLIP_DURATION_MIN_S = 4.0
CLIP_DURATION_MAX_S = 6.0

# Capítulos visuales cada N segundos (~2 min)
CHAPTER_INTERVAL_S = 120.0

# Stock: al menos esta cantidad de términos de búsqueda por cada N segundos de audio
KEYWORDS_PER_WINDOW = 3
KEYWORD_WINDOW_AUDIO_S = 10.0

# Rutas
# - BACKEND_ROOT: apps/backend
# - PROJECT_ROOT: raíz del repo (para output/, musica_libre/, voice_samples/, etc.)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
# apps/backend/videomaker/core/config.py -> repo root está 4 niveles arriba
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MUSIC_DIR = PROJECT_ROOT / "musica_libre"
VOICE_SAMPLES_DIR = PROJECT_ROOT / "voice_samples"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / ".tmp_videomaker"

# Whisper (local) — se reevalúan tras load_project_dotenv()
def _whisper_model() -> str:
    return (os.environ.get("VIDEOMAKER_WHISPER_MODEL") or "base").strip() or "base"


def whisper_word_timestamps_enabled() -> bool:
    v = (os.environ.get("VIDEOMAKER_WHISPER_WORD_LEVEL") or "1").strip().lower()
    return v in ("1", "true", "yes", "on", "y", "si", "sí")

# Idiomas soportados para prompts y metadatos
SUPPORTED_LANGS = ("es", "en")


def load_project_dotenv() -> None:
    """
    Carga variables desde PROJECT_ROOT/.env.

    Usa la ruta del repo (no el cwd de uvicorn) y rellena claves que estén
    vacías en el entorno — p. ej. ANTHROPIC_API_KEY="" exportada en el shell.
    """
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    for key, val in dotenv_values(env_file).items():
        if val is None or val == "":
            continue
        if not str(os.environ.get(key, "")).strip():
            os.environ[key] = val


load_project_dotenv()

WHISPER_MODEL = _whisper_model()
