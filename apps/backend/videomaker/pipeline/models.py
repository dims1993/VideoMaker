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


PIPELINE_STEPS: list[tuple[str, str]] = [
    ("prompt", "Prompt"),
    ("script_writer", "Script Writer"),
    ("metadata", "Metadata"),
    ("hook_scene_router", "Hook Scene Router"),
    ("body_scene_router", "Body Scene Router"),
    ("image_prompt_writer", "Image Prompt Writer"),
    ("images_generation", "Images Generation"),
    ("voiceovers_generation", "Voiceovers Generation"),
]

