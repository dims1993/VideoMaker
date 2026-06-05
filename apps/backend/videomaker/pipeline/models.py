"""Modelos y helpers para la pipeline de creación (por sesión/work_dir)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

PipelineStatus = Literal["idle", "running", "done", "error"]


class PipelineStepState(TypedDict, total=False):
    id: str
    title: str
    state: PipelineStatus
    detail: str
    updated_at: str


class PipelineState(TypedDict, total=False):
    state: PipelineStatus
    current_step: str | None
    steps: list[PipelineStepState]
    last_error: str | None
    updated_at: str


@dataclass(frozen=True)
class PipelineInputs:
    keywords: str
    context: str
    lang: str
    minutes: float
    provider: str
    model: str
    voice_preset: str = "xtts_v2_es"
    # UUID en prompt_templates; solo se persiste en prompt.json al ejecutar el paso prompt.
    prompt_template_id: str | None = None
    # UUID en script_writer_templates; se guarda en catalog al ejecutar Script Writer.
    script_writer_template_id: str | None = None
    # Tema / input del usuario (panel Prompt); se guarda en prompt.json.
    prompt_topic: str = ""
    # Restricciones del vídeo (sesión); no van al catálogo de templates.
    prompt_video_restrictions: str = ""
    # Índice 0..n-1 del fragmento a generar (modo fragmentación secuencial); None = auto (primer pendiente).
    script_fragment_index: int | None = None
    # Render draft (después de voiceovers).
    render_no_music: bool = False
    # Topic Generator (paso previo a Prompt).
    topic_generator_transcript: str = ""
    topic_generator_niche_trends: str = ""
    topic_generator_topic_count: int = 8


# Orden en la barra lateral Create (ideación → guion → routers → prompts → audio → imágenes → publicación).
PIPELINE_STEPS: list[tuple[str, str]] = [
    ("topic_generator", "Topic Generator"),
    ("narrative_angle", "Narrative Angle"),
    ("packaging", "Packaging (Título + Miniatura)"),
    ("prompt", "Prompt"),
    ("script_writer", "Script Writer"),
    ("editorial_analyzer", "Editorial Analyzer"),
    ("narrative_pacing_pass", "Narrative Pacing Pass"),
    ("hook_scene_router", "Hook Scene Router"),
    ("body_scene_router", "Body Scene Router"),
    ("image_prompt_writer", "Image Prompt Writer"),
    ("voiceovers_generation", "Voiceovers Generation"),
    ("images_generation", "Images Generation"),
    ("music_engine", "Music Engine"),
    ("metadata", "Metadata"),
    ("subtitle_engine", "Subtitle Engine"),
    ("render_draft", "Render draft"),
    # Auxiliares / diagnóstico (al final del listado)
    ("voiceover_engine", "Voiceover Engine"),
]

# Orden al ejecutar «pipeline» completa (dependencias técnicas; voiceovers antes de images para reconciliación).
PIPELINE_RUN_ORDER: list[str] = [
    "topic_generator",
    "narrative_angle",
    "packaging",
    "prompt",
    "script_writer",
    "editorial_analyzer",
    "narrative_pacing_pass",
    "hook_scene_router",
    "body_scene_router",
    "voiceover_engine",
    "image_prompt_writer",
    "voiceovers_generation",
    "images_generation",
    "music_engine",
    "metadata",
    "subtitle_engine",
    "render_draft",
]

