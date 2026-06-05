"""Ajustes del paso Metadata por sesión (`pipeline/metadata_settings.json`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

VALID_PLATFORMS = frozenset({"youtube", "tiktok", "reels"})
KeywordSource = Literal["manual", "inferred"]


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


def effective_system_prompt_override(st: dict[str, Any] | None) -> str | None:
    """Override de system prompt solo si el usuario lo guardó en modo manual."""
    if not isinstance(st, dict):
        return None
    if str(st.get("system_prompt_source") or "").strip().lower() != "manual":
        return None
    raw = str(st.get("system_prompt") or "").strip()
    return raw or None


def effective_target_keywords(st: dict[str, Any] | None) -> str:
    """
    Keywords SEO que se envían al LLM.
    Solo si el usuario las guardó explícitamente en Metadata (source=manual).
    Valores antiguos en disco sin source=manual se ignoran (no heredan de otros pasos).
    """
    if not isinstance(st, dict):
        return ""
    if str(st.get("target_keywords_source") or "").strip().lower() != "manual":
        return ""
    return str(st.get("target_keywords") or "").strip()


def write_metadata_settings(
    work_dir: Path,
    *,
    target_platform: str,
    target_keywords: str,
    system_prompt: str,
    target_keywords_source: KeywordSource | None = None,
    system_prompt_source: KeywordSource | None = None,
) -> dict[str, Any]:
    tp = (target_platform or "youtube").strip().lower()
    if tp not in VALID_PLATFORMS:
        tp = "youtube"
    payload: dict[str, Any] = {
        "version": 1,
        "target_platform": tp,
        "target_keywords": (target_keywords or "").strip(),
        "system_prompt": (system_prompt or "").strip(),
    }
    kw_src = (target_keywords_source or "").strip().lower() if target_keywords_source else ""
    if kw_src in ("manual", "inferred"):
        payload["target_keywords_source"] = kw_src
    sp_src = (system_prompt_source or "").strip().lower() if system_prompt_source else ""
    if sp_src == "manual":
        payload["system_prompt_source"] = "manual"
    work_dir.mkdir(parents=True, exist_ok=True)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    _path(work_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def persist_inferred_target_keywords(
    work_dir: Path,
    tags: list[Any],
    existing: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Tras generar metadata, guarda tags inferidos (solo referencia; no se reinyectan al LLM)."""
    if not isinstance(tags, list):
        return None
    parts = [str(t).strip() for t in tags if str(t).strip()]
    if not parts:
        return None
    ex = existing if isinstance(existing, dict) else {}
    kw = ", ".join(parts[:15])
    return write_metadata_settings(
        work_dir,
        target_platform=str(ex.get("target_platform") or "youtube"),
        target_keywords=kw,
        system_prompt=str(ex.get("system_prompt") or ""),
        target_keywords_source="inferred",
    )
