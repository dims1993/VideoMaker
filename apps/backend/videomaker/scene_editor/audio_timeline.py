"""Línea de tiempo real desde Scene Editor (duraciones de audio + huecos)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from videomaker.scene_editor.audio_service import (
    _chunk_gap_ms,
    _duration_ms_from_audio,
    export_chunks_to_narration_wav,
    resolve_chunk_audio_file,
)
from videomaker.scene_editor.store import read_chunks


@dataclass(frozen=True)
class TimelineEvent:
    kind: str  # "chunk" | "gap"
    index: int
    chunk_id: str | None
    start_s: float
    end_s: float
    duration_s: float
    section: str | None
    narration_chars: int


def _chunk_duration_ms(work_dir: Path, chunk_id: str, stored_ms: int | None) -> int:
    if isinstance(stored_ms, int) and stored_ms > 0:
        return stored_ms
    p = resolve_chunk_audio_file(work_dir, chunk_id)
    if p is not None:
        ms = _duration_ms_from_audio(p)
        if ms > 0:
            return ms
    return 0


def build_audio_timeline(
    work_dir: Path,
    *,
    chunk_gap_ms: int | None = None,
) -> dict[str, Any]:
    """
    Construye timeline desde ``scene_editor.json`` + ficheros en ``scene_audio/``.

    Raises si no hay bloques con audio en disco.
    """
    raw = read_chunks(work_dir)
    if not raw:
        raise ValueError(
            "No hay scene_editor.json. Genera audio por bloques en Voiceovers / Scene Editor."
        )
    gap_ms = _chunk_gap_ms(chunk_gap_ms)
    gap_s = gap_ms / 1000.0
    events: list[TimelineEvent] = []
    t = 0.0
    narrable = 0

    for i, c in enumerate(raw):
        text = (c.narration_text or "").strip()
        if not text:
            continue
        narrable += 1
        ms = _chunk_duration_ms(work_dir, c.id, c.duration_ms)
        if ms <= 0:
            continue
        dur = ms / 1000.0
        events.append(
            TimelineEvent(
                kind="chunk",
                index=len(events),
                chunk_id=c.id,
                start_s=round(t, 3),
                end_s=round(t + dur, 3),
                duration_s=round(dur, 3),
                section=(c.section or "").strip() or None,
                narration_chars=len(text),
            )
        )
        t += dur
        if gap_s > 0:
            events.append(
                TimelineEvent(
                    kind="gap",
                    index=len(events),
                    chunk_id=None,
                    start_s=round(t, 3),
                    end_s=round(t + gap_s, 3),
                    duration_s=round(gap_s, 3),
                    section=None,
                    narration_chars=0,
                )
            )
            t += gap_s

    if not events or narrable == 0:
        raise ValueError(
            "Ningún bloque tiene audio medido. Genera TTS en Scene Editor y unifica narracion.wav si hace falta."
        )

    total_s = round(t, 3)
    gap_events = [e for e in events if e.kind == "gap"]
    chunk_events = [e for e in events if e.kind == "chunk"]
    return {
        "version": 1,
        "source": "scene_editor_audio",
        "total_duration_s": total_s,
        "chunk_gap_ms": gap_ms,
        "chunk_count": len(chunk_events),
        "gap_count": len(gap_events),
        "events": [
            {
                "kind": e.kind,
                "index": e.index,
                "chunk_id": e.chunk_id,
                "start_s": e.start_s,
                "end_s": e.end_s,
                "duration_s": e.duration_s,
                "section": e.section,
                "narration_chars": e.narration_chars,
                "chars_per_sec": round(e.narration_chars / e.duration_s, 2)
                if e.duration_s > 0 and e.narration_chars
                else None,
            }
            for e in events
        ],
    }


def ensure_narration_wav(work_dir: Path, *, chunk_gap_ms: int | None = None) -> Path:
    """``narracion.wav`` existente o exportado desde bloques con audio."""
    out = work_dir / "narracion.wav"
    if out.is_file() and out.stat().st_size > 0:
        return out
    raw = read_chunks(work_dir)
    if not raw:
        raise ValueError("Falta narracion.wav y no hay chunks en Scene Editor.")
    export_chunks_to_narration_wav(work_dir, raw, chunk_gap_ms=chunk_gap_ms)
    if not out.is_file():
        raise ValueError("No se pudo crear narracion.wav desde los bloques.")
    return out


def write_audio_timeline_artifact(work_dir: Path, timeline: dict[str, Any]) -> Path:
    p = work_dir / "pipeline" / "audio_timeline.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
