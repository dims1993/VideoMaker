"""Ajustes del paso Image Prompt Writer (`pipeline/image_prompt_writer_settings.json`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from videomaker.llm.avatar_prompt_writer import AVATAR_DEFAULT_DESCRIPTION

VALID_GENERATORS = frozenset({"midjourney", "flux", "dall_e", "sd", "custom"})

_AVATAR_SECS_DEFAULT = 6.0
_AVATAR_MAX_IMAGES_DEFAULT = 80


def _coerce_target_generator(raw: str | None) -> str:
    """Normaliza `target_generator` guardado (valores desconocidos u obsoletos → midjourney)."""
    tg = (raw or "").strip().lower()
    if tg not in VALID_GENERATORS:
        return "midjourney"
    return tg


def _path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "image_prompt_writer_settings.json"


def read_image_prompt_writer_settings(work_dir: Path) -> dict[str, Any]:
    p = _path(work_dir)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        out = dict(raw)
        out["target_generator"] = _coerce_target_generator(str(out.get("target_generator") or ""))
        # Defaults para campos de avatar
        out.setdefault("use_avatar", False)
        out.setdefault("avatar_id", "")
        out.setdefault("avatar_description", AVATAR_DEFAULT_DESCRIPTION)
        out.setdefault("avatar_secs_per_image", _AVATAR_SECS_DEFAULT)
        out.setdefault("avatar_max_images", _AVATAR_MAX_IMAGES_DEFAULT)
        return out
    except Exception:
        return {}


def write_image_prompt_writer_settings(
    work_dir: Path,
    *,
    target_generator: str,
    append_midjourney_suffix: bool,
    export_negative_separate: bool,
    notes: str,
    use_avatar: bool = False,
    avatar_id: str = "",
    avatar_description: str = "",
    avatar_secs_per_image: float = _AVATAR_SECS_DEFAULT,
    avatar_max_images: int = _AVATAR_MAX_IMAGES_DEFAULT,
) -> dict[str, Any]:
    tg = _coerce_target_generator(target_generator)
    payload = {
        "version": 2,
        "target_generator": tg,
        "append_midjourney_suffix": bool(append_midjourney_suffix),
        "export_negative_separate": bool(export_negative_separate),
        "notes": (notes or "").strip(),
        "use_avatar": bool(use_avatar),
        "avatar_id": (avatar_id or "").strip(),
        "avatar_description": (avatar_description or AVATAR_DEFAULT_DESCRIPTION).strip(),
        "avatar_secs_per_image": max(2.0, float(avatar_secs_per_image)),
        "avatar_max_images": max(1, int(avatar_max_images)),
    }
    work_dir.mkdir(parents=True, exist_ok=True)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    _path(work_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
