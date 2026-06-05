"""Persistencia de chunks del Scene Editor en pipeline/scene_editor.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from videomaker.scene_editor.models import Chunk

ARTIFACT_NAME = "scene_editor.json"


def artifact_path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / ARTIFACT_NAME


def read_chunks(work_dir: Path) -> list[Chunk] | None:
    p = artifact_path(work_dir)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = data.get("chunks") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return None
    out: list[Chunk] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                out.append(Chunk.model_validate(item))
            except Exception:
                continue
    if out and any(c.director_note for c in out):
        out = [c.model_copy(update={"director_note": None}) for c in out]
        write_chunks(work_dir, out)
    return out


def write_chunks(work_dir: Path, chunks: list[Chunk]) -> Path:
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chunks": [c.model_dump() for c in chunks],
    }
    p = artifact_path(work_dir)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def scene_audio_dir(work_dir: Path) -> Path:
    p = work_dir / "scene_audio"
    p.mkdir(parents=True, exist_ok=True)
    return p
