"""Ajustes del Hook Scene Router (`pipeline/hook_router_settings.json`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALID_MODES = frozenset({"llm", "template"})
VALID_FINANCE_STYLES = frozenset(
    {"auto", "deep_documentary", "data_minimalist", "financial_noir", "intimate_pov"}
)
VALID_PLATFORMS = frozenset({"auto", "tiktok", "youtube_shorts", "reels", "youtube"})
VALID_VISUAL_ENERGY = frozenset({"auto", "high", "medium", "low"})
VALID_SYSTEM_PROMPT_SOURCES = frozenset({"internal", "manual"})


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


def effective_hook_system_prompt_override(st: dict[str, Any] | None) -> str:
    """Override solo si el usuario eligió system prompt manual."""
    if not isinstance(st, dict):
        return ""
    if str(st.get("system_prompt_source") or "").strip().lower() != "manual":
        return ""
    return str(st.get("system_prompt") or "").strip()


def write_hook_router_settings(
    work_dir: Path,
    *,
    mode: str,
    finance_style: str,
    system_prompt: str = "",
    platform: str = "auto",
    visual_energy: str = "auto",
    system_prompt_source: str | None = None,
    talking_head_after_sec: str | int | None = "auto",
) -> dict[str, Any]:
    m = (mode or "llm").strip().lower()
    if m not in VALID_MODES:
        m = "llm"
    fs = (finance_style or "auto").strip().lower()
    if fs not in VALID_FINANCE_STYLES:
        fs = "auto"
    plat = (platform or "auto").strip().lower()
    if plat not in VALID_PLATFORMS:
        plat = "auto"
    energy = (visual_energy or "auto").strip().lower()
    if energy not in VALID_VISUAL_ENERGY:
        energy = "auto"
    sp_src = (system_prompt_source or "").strip().lower()
    if sp_src not in VALID_SYSTEM_PROMPT_SOURCES:
        sp_src = "manual" if (system_prompt or "").strip() else "internal"
    th = talking_head_after_sec
    if th is not None and str(th).strip().lower() not in ("", "auto"):
        try:
            th_val: Any = int(float(th))
        except (TypeError, ValueError):
            th_val = "auto"
    else:
        th_val = "auto"
    payload: dict[str, Any] = {
        "version": 2,
        "mode": m,
        "finance_style": fs,
        "platform": plat,
        "visual_energy": energy,
        "system_prompt_source": sp_src,
        "system_prompt": (system_prompt or "").strip(),
        "talking_head_after_sec": th_val,
    }
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "pipeline").mkdir(parents=True, exist_ok=True)
    _path(work_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
