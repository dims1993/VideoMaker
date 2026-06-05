"""Contrato Chunk (front ↔ back) para el Scene Editor."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChunkStatus = Literal["idle", "generating", "done", "error"]
VisualStatus = Literal["idle", "planning", "done", "error"]


class VisualShot(BaseModel):
    """Sub-plano visual dentro de un bloque de audio (un WAV, varios cortes)."""

    id: str
    order: int = 0
    shot_type: str | None = Field(
        default=None,
        description="broll_cutaway, close_up, over_shoulder, wide_context, data_ui, …",
    )
    director_note: str | None = Field(
        default=None,
        description="Pista del Body Scene Router para este corte",
    )
    narration_excerpt: str | None = Field(
        default=None,
        description="Fragmento del guion que ilustra este plano",
    )
    situation_es: str | None = None
    scene_prompt_en: str | None = None
    protagonist_expression_key: str | None = None
    protagonist_expression_en: str | None = None
    ai_prompt: str | None = None
    negative_prompt: str | None = None


class Chunk(BaseModel):
    id: str
    narration_text: str = ""
    section: str | None = Field(
        default=None,
        description="Sección del guion ([CATEGORIA: …]), p. ej. Introducción, Pilar 1, Cierre",
    )
    director_note: str | None = None
    audio_url: str | None = None
    duration_ms: int | None = None
    status: ChunkStatus = "idle"
    visual_status: VisualStatus = "idle"
    situation_es: str | None = None
    scene_prompt_en: str | None = Field(
        default=None,
        description="Párrafo de escena sin estilo base (delta para cola Gemini)",
    )
    protagonist_expression_key: str | None = Field(
        default=None,
        description="Clave de expresión facial inferida de la narración (p. ej. concerned, shocked)",
    )
    protagonist_expression_en: str | None = Field(
        default=None,
        description="Descripción visual en inglés de la expresión facial del protagonista",
    )
    ai_prompt: str | None = None
    negative_prompt: str | None = None
    visual_shots: list[VisualShot] = Field(default_factory=list)
    visual_rhythm_ok: bool | None = Field(
        default=None,
        description="True si duración de audio respeta max_hold o hay suficientes sub-planos",
    )
    visual_rhythm_warning: str | None = None


class ParseScriptRequest(BaseModel):
    text: str = Field(default="", description="Guion en texto plano; si work está definido y text vacío, lee script.txt/guion.txt")
    work: str | None = Field(default=None, description="Sesión de trabajo (p. ej. output/ui_session)")


class ParseScriptResponse(BaseModel):
    chunks: list[Chunk]


class GenerateChunkRequest(BaseModel):
    chunk_id: str
    narration_text: str = ""
    work: str = Field(default="output/ui_session")
    voice_id: str | None = Field(
        default=None,
        description="Opcional: voice_id ElevenLabs; si vacío usa ELEVENLABS_VOICE_ID del .env",
    )


class GenerateChunkResponse(BaseModel):
    chunk: Chunk


class GenerateAllChunksRequest(BaseModel):
    work: str = Field(default="output/ui_session")
    voice_id: str | None = None
    skip_with_audio: bool = Field(
        default=True,
        description="Si true, no regenera bloques que ya tienen status=done y audio en disco",
    )
    regenerate_all: bool = Field(
        default=False,
        description="Si true, regenera todos los bloques con texto narrable",
    )


class BatchChunkError(BaseModel):
    chunk_id: str
    detail: str


class GenerateAllChunksResponse(BaseModel):
    chunks: list[Chunk]
    generated: int
    skipped: int
    failed: int
    errors: list[BatchChunkError]


class ExportNarrationRequest(BaseModel):
    work: str = Field(default="output/ui_session")
    chunk_gap_ms: int = Field(
        default=0,
        ge=0,
        le=3000,
        description="Silencio entre bloques del Scene Editor (ms)",
    )


class ExportNarrationResponse(BaseModel):
    ok: bool = True
    path: str = "narracion.wav"
    duration_s: float
    chunks_used: int
    chunks_missing: list[str] = Field(default_factory=list)


class SaveChunksRequest(BaseModel):
    work: str = Field(default="output/ui_session")
    chunks: list[Chunk]


class SaveChunksResponse(BaseModel):
    ok: bool = True
    chunks: list[Chunk]


class PlanVisualChunkRequest(BaseModel):
    work: str = Field(default="output/ui_session")
    chunk_id: str
    narration_text: str = ""
    director_note: str | None = None


class PlanVisualChunkResponse(BaseModel):
    chunk: Chunk


class PlanAllVisualRequest(BaseModel):
    work: str = Field(default="output/ui_session")
    skip_with_prompt: bool = Field(default=True)
    regenerate_all: bool = Field(default=False)
    chunk_ids: list[str] | None = Field(
        default=None,
        description="Si se indica, solo replanifica estos bloques (siempre regenera, ignora skip).",
    )


class PlanAllVisualResponse(BaseModel):
    chunks: list[Chunk]
    planned: int
    skipped: int
    failed: int
    errors: list[BatchChunkError]


class ExportImagePromptsRequest(BaseModel):
    work: str = Field(default="output/ui_session")


class ExportImagePromptsResponse(BaseModel):
    path: str
    prompt_count: int


class ExpandVisualRhythmRequest(BaseModel):
    work: str = Field(default="output/ui_session")
    chunk_id: str
    auto_plan: bool = Field(
        default=True,
        description="Si true, invoca Visual Planner en cada sub-plano",
    )


class ExpandVisualRhythmResponse(BaseModel):
    chunk: Chunk
    assessment: dict[str, object]
