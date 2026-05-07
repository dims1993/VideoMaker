"""Valores por defecto del generador (ritmo, capítulos, stock)."""

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
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MUSIC_DIR = PROJECT_ROOT / "musica_libre"
VOICE_SAMPLES_DIR = PROJECT_ROOT / "voice_samples"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / ".tmp_videomaker"

# Whisper (local)
WHISPER_MODEL = "base"

# Idiomas soportados para prompts y metadatos
SUPPORTED_LANGS = ("es", "en")
