"""Plan de imágenes por sección: hook denso, cuerpo más relajado pero sin planos estáticos."""

from __future__ import annotations

import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from videomaker.llm.body_macro_beats import _word_count
from videomaker.llm.image_prompt_timing_reconcile import _chunk_events, _load_timeline, _pool_ms_from_chunks
from videomaker.scene_editor.audio_service import _chunk_gap_ms

# Objetivo de segundos por imagen (no el máximo absoluto de retención)
_DEFAULT_HOOK_TARGET_HOLD_S = 3.5
_DEFAULT_BODY_TARGET_HOLD_S = 6.5
# Tope duro al reconciliar / partir (evita 10s+ estáticos)
_DEFAULT_HOOK_MAX_HOLD_S = 4.5
_DEFAULT_BODY_MAX_HOLD_S = 8.0


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _section_is_hook(section: str | None) -> bool:
    s = (section or "").strip().lower()
    if not s:
        return False
    if s == "hook":
        return True
    return any(k in s for k in ("introducción", "introduccion", "gancho", "intro "))


def _estimate_pool_from_words(text: str) -> float:
    w = _word_count(text)
    return max(30.0, w / 2.5) if w else 60.0


def estimate_hook_audio_pool_s(work_dir: Path, hook_text: str) -> float:
    timeline = _load_timeline(work_dir)
    if timeline:
        gap_ms = int(timeline.get("chunk_gap_ms") or _chunk_gap_ms(None))
        chunks = [c for c in _chunk_events(timeline) if _section_is_hook(c.get("section"))]
        pool_ms = _pool_ms_from_chunks(chunks, gap_ms=gap_ms)
        if pool_ms > 0:
            return pool_ms / 1000.0
    return _estimate_pool_from_words(hook_text)


def estimate_body_audio_pool_s(work_dir: Path, body_text: str) -> float:
    timeline = _load_timeline(work_dir)
    if timeline:
        gap_ms = int(timeline.get("chunk_gap_ms") or _chunk_gap_ms(None))
        chunks = [c for c in _chunk_events(timeline) if not _section_is_hook(c.get("section"))]
        pool_ms = _pool_ms_from_chunks(chunks, gap_ms=gap_ms)
        if pool_ms > 0:
            return pool_ms / 1000.0
    return _estimate_pool_from_words(body_text)


def _sanity_total_cap() -> int | None:
    """0 en env = sin tope global; si no, límite de seguridad anti miles de planos."""
    raw = (os.environ.get("VIDEOMAKER_SANITY_MAX_TOTAL_IMAGES") or "0").strip()
    if not raw or raw == "0":
        return None
    try:
        return max(80, int(raw))
    except ValueError:
        return None


@dataclass
class SectionDensityPlan:
    hook_pool_s: float
    body_pool_s: float
    total_narration_s: float
    hook_target_hold_s: float
    body_target_hold_s: float
    hook_max_hold_s: float
    body_max_hold_s: float
    hook_target_images: int
    body_target_images: int
    total_target_images: int
    audio_source: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["hook_pool_min"] = round(self.hook_pool_s / 60, 2)
        d["body_pool_min"] = round(self.body_pool_s / 60, 2)
        d["total_narration_min"] = round(self.total_narration_s / 60, 2)
        return d


def build_section_density_plan(
    work_dir: Path,
    *,
    script_text: str = "",
    hook_text: str = "",
    body_text: str = "",
) -> SectionDensityPlan:
    """
    Calcula cuántas imágenes conviene por gancho y cuerpo a partir del audio (medido o estimado).

    Hook: muchos cortes (~3.5 s/imagen). Cuerpo: más lento (~6.5 s) pero nunca >8 s por plano.
    """
    hook_pool = estimate_hook_audio_pool_s(work_dir, hook_text)
    body_pool = estimate_body_audio_pool_s(work_dir, body_text)
    total = hook_pool + body_pool

    timeline = _load_timeline(work_dir)
    audio_source = "audio_timeline" if timeline and _chunk_events(timeline) else "script_words"

    hook_hold = _env_float("VIDEOMAKER_HOOK_TARGET_HOLD_S", _DEFAULT_HOOK_TARGET_HOLD_S)
    body_hold = _env_float("VIDEOMAKER_BODY_TARGET_HOLD_S", _DEFAULT_BODY_TARGET_HOLD_S)
    hook_max = _env_float("VIDEOMAKER_HOOK_MAX_HOLD_S", _DEFAULT_HOOK_MAX_HOLD_S)
    body_max = _env_float("VIDEOMAKER_BODY_MAX_HOLD_S", _DEFAULT_BODY_MAX_HOLD_S)

    hook_n = max(8, int(math.ceil(hook_pool / hook_hold))) if hook_hold > 0 else 8
    body_n = max(12, int(math.ceil(body_pool / body_hold))) if body_hold > 0 else 12

    cap = _sanity_total_cap()
    notes = (
        f"Gancho ~{hook_hold}s/plano → {hook_n} imágenes; "
        f"cuerpo ~{body_hold}s/plano → {body_n} imágenes "
        f"(máx. {body_max}s/plano al montar)."
    )
    if cap and hook_n + body_n > cap:
        scale = cap / (hook_n + body_n)
        hook_n = max(8, int(hook_n * scale))
        body_n = max(12, cap - hook_n)
        notes += f" Tope global {cap} imágenes aplicado."

    return SectionDensityPlan(
        hook_pool_s=round(hook_pool, 1),
        body_pool_s=round(body_pool, 1),
        total_narration_s=round(total, 1),
        hook_target_hold_s=hook_hold,
        body_target_hold_s=body_hold,
        hook_max_hold_s=hook_max,
        body_max_hold_s=body_max,
        hook_target_images=hook_n,
        body_target_images=body_n,
        total_target_images=hook_n + body_n,
        audio_source=audio_source,
        notes=notes,
    )


def hook_max_beats_for_platform(platform: str, plan: SectionDensityPlan) -> int:
    """Límite de micro_beats del Hook Router según duración real del gancho."""
    plat = (platform or "youtube").strip().lower()
    if plat in ("youtube", "youtube_long", "youtube_longform"):
        return min(55, max(12, plan.hook_target_images))
    if plat in ("youtube_shorts", "tiktok", "reels"):
        return min(24, max(10, plan.hook_target_images))
    return min(20, max(8, plan.hook_target_images))


def max_hold_for_section(plan: SectionDensityPlan, section: str | None) -> float:
    if _section_is_hook(section):
        return plan.hook_max_hold_s
    return plan.body_max_hold_s
