"""Presets de estilo visual (catálogo global, como avatares legacy)."""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from videomaker.core import config
from videomaker.scene_editor.scene_visual_settings_store import (
    default_settings,
    read_scene_visual_settings,
    write_scene_visual_settings,
)

_LOCK = threading.RLock()
_FILENAME = "visual_style_presets.json"

ALEX_PRESET_ID = "alex_v1"
ALEX_PRESET_NAME = "Alex"

STYLE_FIELD_KEYS = (
    "base_style_en",
    "protagonist_en",
    "protagonist_wardrobe_en",
    "protagonist_action_rules_en",
    "protagonist_expressions_en",
    "avoid_en",
    "planner_extra_rules_en",
    "gemini_continuity_prefix_en",
    "auto_avoid_supplement_en",
    "aspect_ratio",
    "output_spec",
)


def _path() -> Path:
    return config.PROJECT_ROOT / _FILENAME


def _default_store() -> dict[str, Any]:
    return {"version": 1, "items": []}


def _load_raw() -> dict[str, Any]:
    p = _path()
    if not p.is_file():
        return _default_store()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_store()
        data.setdefault("version", 1)
        data.setdefault("items", [])
        return data
    except Exception:
        return _default_store()


def _save_raw(data: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _fields_from_dict(src: dict[str, Any]) -> dict[str, str]:
    base = default_settings()
    out: dict[str, str] = {}
    for key in STYLE_FIELD_KEYS:
        if key in src:
            out[key] = str(src.get(key) or "").strip()
        else:
            out[key] = str(base.get(key) or "").strip()
    return out


def _preset_item(
    *,
    preset_id: str,
    name: str,
    fields: dict[str, str],
    bundled: bool = False,
) -> dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "id": preset_id,
        "name": name.strip(),
        "bundled": bundled,
        "created_at": now,
        "updated_at": now,
        **_fields_from_dict(fields),
    }


def ensure_alex_preset(work_dir: Path | None = None) -> dict[str, Any]:
    """Crea el preset Alex si no existe (desde scene_visual_settings del work o defaults)."""
    with _LOCK:
        raw = _load_raw()
        ids = {it.get("id") for it in raw.get("items", []) if isinstance(it, dict)}
        if ALEX_PRESET_ID in ids:
            for it in raw.get("items", []):
                if isinstance(it, dict) and it.get("id") == ALEX_PRESET_ID:
                    return dict(it)
            return {}
        src = default_settings()
        if work_dir is not None:
            try:
                src = read_scene_visual_settings(work_dir)
            except Exception:
                pass
        item = _preset_item(
            preset_id=ALEX_PRESET_ID,
            name=ALEX_PRESET_NAME,
            fields=_fields_from_dict(src),
            bundled=True,
        )
        raw.setdefault("items", []).insert(0, item)
        _save_raw(raw)
        return dict(item)


def list_presets(*, work_dir: Path | None = None) -> list[dict[str, Any]]:
    ensure_alex_preset(work_dir)
    with _LOCK:
        raw = _load_raw()
        items = [it for it in raw.get("items", []) if isinstance(it, dict)]
        return [
            {
                "id": str(it.get("id") or ""),
                "name": str(it.get("name") or ""),
                "bundled": bool(it.get("bundled")),
                "updated_at": str(it.get("updated_at") or ""),
            }
            for it in items
            if it.get("id")
        ]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    pid = (preset_id or "").strip()
    if not pid:
        return None
    with _LOCK:
        for it in _load_raw().get("items", []):
            if isinstance(it, dict) and str(it.get("id") or "") == pid:
                return dict(it)
    return None


def create_preset(name: str, fields: dict[str, Any]) -> dict[str, Any]:
    nm = (name or "").strip()
    if not nm:
        raise ValueError("El estilo necesita un nombre.")
    item = _preset_item(
        preset_id=secrets.token_hex(8),
        name=nm,
        fields=_fields_from_dict(fields),
        bundled=False,
    )
    with _LOCK:
        raw = _load_raw()
        raw.setdefault("items", []).append(item)
        _save_raw(raw)
    return item


def update_preset(preset_id: str, *, name: str | None = None, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    pid = (preset_id or "").strip()
    if not pid:
        raise ValueError("preset_id requerido.")
    with _LOCK:
        raw = _load_raw()
        for it in raw.get("items", []):
            if not isinstance(it, dict) or str(it.get("id") or "") != pid:
                continue
            if name is not None and str(name).strip():
                it["name"] = str(name).strip()
            if fields is not None:
                merged = _fields_from_dict({**it, **fields})
                for key, val in merged.items():
                    it[key] = val
            it["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _save_raw(raw)
            return dict(it)
    raise ValueError(f"Preset no encontrado: {pid}")


def delete_preset(preset_id: str) -> None:
    pid = (preset_id or "").strip()
    if pid == ALEX_PRESET_ID:
        raise ValueError('No se puede eliminar el estilo "Alex".')
    with _LOCK:
        raw = _load_raw()
        before = len(raw.get("items", []))
        raw["items"] = [
            it
            for it in raw.get("items", [])
            if not (isinstance(it, dict) and str(it.get("id") or "") == pid)
        ]
        if len(raw.get("items", [])) == before:
            raise ValueError(f"Preset no encontrado: {pid}")
        _save_raw(raw)


def apply_preset_to_work(work_dir: Path, preset_id: str) -> dict[str, Any]:
    preset = get_preset(preset_id)
    if not preset:
        raise ValueError(f"Preset no encontrado: {preset_id}")
    return write_scene_visual_settings(work_dir, _fields_from_dict(preset))


def preset_to_scene_settings(preset: dict[str, Any]) -> dict[str, Any]:
    fields = _fields_from_dict(preset)
    return {**default_settings(), **fields, "version": 1, "target_generator": "nano_banana"}


_AVATAR_SECS_PER_IMAGE = 6.0
_AVATAR_MAX_IMAGES = 80


def protagonist_description_from_settings(settings: dict[str, Any]) -> str:
    """Descripción del protagonista para el Avatar Prompt Writer."""
    from videomaker.llm.avatar_prompt_writer import AVATAR_DEFAULT_DESCRIPTION

    face = str(settings.get("protagonist_en") or "").strip()
    wardrobe = str(settings.get("protagonist_wardrobe_en") or "").strip()
    if face and wardrobe:
        return f"{face.rstrip('.')}. {wardrobe.rstrip('.')}"
    if face:
        return face
    if wardrobe:
        return wardrobe
    return AVATAR_DEFAULT_DESCRIPTION


def resolve_visual_style_preset_id(work_dir: Path) -> str:
    from videomaker.core.image_prompt_writer_settings_store import read_image_prompt_writer_settings

    st = read_image_prompt_writer_settings(work_dir)
    pid = str(st.get("visual_style_preset_id") or "").strip()
    if pid and get_preset(pid):
        return pid
    ensure_alex_preset(work_dir)
    return ALEX_PRESET_ID


def prepare_avatar_mode_for_work(work_dir: Path) -> dict[str, Any]:
    """Aplica el preset seleccionado al work y devuelve kwargs para generate_avatar_image_prompts."""
    preset_id = resolve_visual_style_preset_id(work_dir)
    apply_preset_to_work(work_dir, preset_id)
    settings = read_scene_visual_settings(work_dir)
    return {
        "avatar_description": protagonist_description_from_settings(settings),
        "scene_visual_settings": settings,
        "visual_style_preset_id": preset_id,
        "intro_enabled": False,
        "intro_character_name": "",
        "outro_enabled": False,
        "outro_character_name": "",
        "secs_per_image": _AVATAR_SECS_PER_IMAGE,
        "max_images": _AVATAR_MAX_IMAGES,
    }
