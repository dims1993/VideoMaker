"""Progreso de render en disco para polling desde la UI."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable


ProgressCallback = Callable[[str, int, int, str], None]

_ARTIFACT = "render_progress.json"


def progress_path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / _ARTIFACT


def clear_render_progress(work_dir: Path) -> None:
    p = progress_path(work_dir)
    if p.is_file():
        p.unlink(missing_ok=True)


def update_render_progress(
    work_dir: Path,
    *,
    kind: str = "preview_mp4",
    phase: str,
    current: int = 0,
    total: int = 0,
    message: str = "",
) -> None:
    percent = 0
    if total > 0:
        percent = min(100, max(0, int(round(100 * current / total))))
    elif phase == "encode":
        percent = 92
    elif phase == "concat":
        percent = 78
    elif phase == "done":
        percent = 100

    payload: dict[str, Any] = {
        "kind": kind,
        "phase": phase,
        "current": int(current),
        "total": int(total),
        "percent": percent,
        "message": message.strip(),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    progress_path(work_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_render_progress(work_dir: Path) -> dict[str, Any] | None:
    p = progress_path(work_dir)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def make_progress_reporter(
    work_dir: Path | None,
    *,
    kind: str = "preview_mp4",
    on_status_detail: Callable[[str], None] | None = None,
) -> ProgressCallback | None:
    if work_dir is None:
        return None

    def report(phase: str, current: int, total: int, message: str) -> None:
        update_render_progress(
            work_dir, kind=kind, phase=phase, current=current, total=total, message=message
        )
        if on_status_detail and message:
            if total > 0 and phase == "segment":
                on_status_detail(f"Preview MP4: plano {current}/{total} — {message}")
            else:
                on_status_detail(f"Preview MP4 — {message}")

    return report
