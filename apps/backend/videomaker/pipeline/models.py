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
    # Índice 0..n-1 del fragmento a generar (modo fragmentación secuencial); None = auto (primer pendiente).
    script_fragment_index: int | None = None
    # Render draft (después de voiceovers).
    render_no_music: bool = False


PIPELINE_STEPS: list[tuple[str, str]] = [
    ("prompt", "Prompt"),
    ("script_writer", "Script Writer"),
    ("metadata", "Metadata"),
    ("hook_scene_router", "Hook Scene Router"),
    ("body_scene_router", "Body Scene Router"),
    ("image_prompt_writer", "Image Prompt Writer"),
    ("images_generation", "Images Generation"),
    ("voiceovers_generation", "Voiceovers Generation"),
    ("render_draft", "Render draft"),
]

