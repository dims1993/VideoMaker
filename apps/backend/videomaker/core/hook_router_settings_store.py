"""Ajustes del Hook Scene Router (`pipeline/hook_router_settings.json`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALID_MODES = frozenset({"llm", "template"})
VALID_FINANCE_STYLES = frozenset(
    {"auto", "deep_documentary", "data_minimalist", "financial_noir", "intimate_pov"}
)


def _path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "hook_router_settings.json"


def read_hook_router_settings(work_dir: Path) -> dict[str, Any]:
    p = _path(work_dir)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def write_hook_router_settings(
    work_dir: Path,
    *,
    mode: str,
    finance_style: str,
    system_prompt: str = "",
) -> dict[str, Any]:
    m = (mode or "template").strip().lower()
    if m not in VALID_MODES:
        m = "template"
    fs = (finance_style or "auto").strip().lower()
    if fs not in VALID_FINANCE_STYLES:
        fs = "auto"
    payload = {
        "version": 1,
        "mode": m,
        "finance_style": fs,
        "system_prompt": (system_prompt or "").strip(),
    }
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "pipeline").mkdir(parents=True, exist_ok=True)
    _path(work_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
