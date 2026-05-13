"""Estructuras compartidas del pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


class Locale(str, Enum):
    ES = "es"
    EN = "en"


@dataclass
class VoiceProfile:
    """Perfil reutilizable para TTS (Coqui/Bark/etc.)."""

    id: str
    label: str
    engine: Literal["coqui", "bark", "piper"]
    # Para Coqui: nombre de modelo o path; para Bark: preset de voz
    model_ref: str
    locale: Locale
    # Notas para el operador (tono pausado, grave, etc.)
    notes: str = ""
    # XTTS v2: clonación por muestra (WAV limpio, unos segundos bastan)
    speaker_wav: Path | None = None
    # XTTS v2: voz integrada Coqui si no hay `speaker_wav` (ver `tts --list_speaker_idx`)
    xtts_builtin_speaker: str | None = None
    # Si True, busca voice_samples/reference*.wav además de `speaker_wav`
    auto_clone_from_samples: bool = True


@dataclass
class ScriptCategory:
    """Bloque narrativo para mantener coherencia en guiones largos."""

    title: str
    beats: list[str]  # puntos que debe cubrir la sección
    target_seconds: int | None = None


@dataclass
class ScriptBlueprint:
    """Entrada del usuario antes de llamar al LLM."""

    keywords: list[str]
    extra_context: str
    locale: Locale
    target_minutes: float = 10.0
    #: Si se define, el prompt maestro usa esta duración para el contexto del “vídeo completo” (p. ej. fragmentación).
    prompt_duration_minutes: float | None = None
    categories: list[ScriptCategory] = field(default_factory=list)


@dataclass
class ScriptSegment:
    """Fragmento de guion alineado con audio/TTS por trozos."""

    index: int
    text: str
    category_title: str | None = None


@dataclass
class VisualReferenceQuery:
    """Término de referencia visual alineado a un tramo de la narración (montaje / IA)."""

    query: str
    start_audio_s: float
    end_audio_s: float


@dataclass
class RenderPlan:
    """Plan mínimo que consume el editor de vídeo."""

    audio_path: Path
    reference_queries: list[VisualReferenceQuery]
    locale: Locale
    chapter_titles: list[tuple[float, str]]  # (t_s, título corto)
    music_path: Path | None
    subtitles_path: Path | None  # opcional si ya están quemados en otro paso
