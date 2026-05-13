"""Ajustes del paso Metadata por sesión (`pipeline/metadata_settings.json`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALID_PLATFORMS = frozenset({"youtube", "tiktok", "reels"})


def _path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "metadata_settings.json"


def read_metadata_settings(work_dir: Path) -> dict[str, Any]:
    p = _path(work_dir)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def write_metadata_settings(
    work_dir: Path,
    *,
    target_platform: str,
    target_keywords: str,
    system_prompt: str,
) -> dict[str, Any]:
    tp = (target_platform or "youtube").strip().lower()
    if tp not in VALID_PLATFORMS:
        tp = "youtube"
    payload = {
        "version": 1,
        "target_platform": tp,
        "target_keywords": (target_keywords or "").strip(),
        "system_prompt": (system_prompt or "").strip(),
    }
    work_dir.mkdir(parents=True, exist_ok=True)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    _path(work_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
