"""Ajustes del Narrative Pacing Pass (`pipeline/pacing_pass_settings.json`)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "pacing_pass_settings.json"


def read_pacing_pass_settings(work_dir: Path) -> dict[str, Any]:
    p = _path(work_dir)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def write_pacing_pass_settings(work_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    target = data.get("target_minutes")
    tm: float | None = None
    if target is not None and str(target).strip() != "":
        try:
            tm = float(target)
        except (TypeError, ValueError):
            tm = None
        if tm is not None and tm <= 0:
            tm = None

    trim_raw = data.get("trim_to_duration")
    trim = True if trim_raw is None else bool(trim_raw)

    directives = str(data.get("user_directives") or "").strip()[:8000]

    out: dict[str, Any] = {
        "target_minutes": tm,
        "trim_to_duration": trim,
        "user_directives": directives,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    p = _path(work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def resolve_target_minutes(
    work_dir: Path,
    *,
    session_minutes: float,
) -> float:
    """Minutos objetivo: override del panel → prompt.json → sesión."""
    st = read_pacing_pass_settings(work_dir)
    if st.get("target_minutes") is not None:
        try:
            v = float(st["target_minutes"])
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    pj = work_dir / "pipeline" / "prompt.json"
    if pj.is_file():
        try:
            pr = json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(pr, dict) and pr.get("minutes") is not None:
                v = float(pr["minutes"])
                if v > 0:
                    return v
        except Exception:
            pass
    return max(1.0, float(session_minutes or 10))
