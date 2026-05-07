"""Plantillas de prompt extra (system/user) guardadas en disco — lista, CRUD, selección."""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from videomaker.core import config
from videomaker.llm.bundled_prompt_text import (
    REFLECTIVE_10MIN_USER_EXTRA,
    YOUTUBE_PSYCH_FINANCE_USER_EXTRA,
)

_LOCK = threading.Lock()
_FILENAME = "prompt_presets.json"

# Plantillas incluidas: se inyectan una vez si no están en disco.
BUNDLED_PRESET_ID = "videomaker_youtube_psych_fin_v1"
BUNDLED_PRESET_NAME = "YouTube · Psicología y finanzas (reflexivo)"

BUNDLED_REFLECTIVE_ID = "videomaker_reflective_10min_v1"
BUNDLED_REFLECTIVE_NAME = "★ Vídeo reflexivo 10 min — pausas + stock integrado"


def _path() -> Path:
    return config.PROJECT_ROOT / _FILENAME


def _default_store() -> dict[str, Any]:
    return {"version": 1, "selected_id": None, "items": []}


def _load_raw() -> dict[str, Any]:
    p = _path()
    if not p.is_file():
        return _default_store()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_store()
        data.setdefault("version", 1)
        data.setdefault("selected_id", None)
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


def _ensure_bundled_presets(raw: dict[str, Any]) -> bool:
    """Inyecta las plantillas incluidas si no están en disco. Devuelve True si hubo cambios."""
    ids = {it.get("id") for it in raw.get("items", []) if isinstance(it, dict)}
    changed = False
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if BUNDLED_PRESET_ID not in ids:
        raw.setdefault("items", []).append(
            {
                "id": BUNDLED_PRESET_ID,
                "name": BUNDLED_PRESET_NAME,
                "system_extra": "",
                "user_extra": YOUTUBE_PSYCH_FINANCE_USER_EXTRA,
                "created_at": now,
                "bundled": True,
            }
        )
        changed = True

    if BUNDLED_REFLECTIVE_ID not in ids:
        raw.setdefault("items", []).append(
            {
                "id": BUNDLED_REFLECTIVE_ID,
                "name": BUNDLED_REFLECTIVE_NAME,
                "system_extra": "",
                "user_extra": REFLECTIVE_10MIN_USER_EXTRA,
                "created_at": now,
                "bundled": True,
            }
        )
        changed = True

    return changed


def list_presets() -> list[dict[str, Any]]:
    """Lista ``{id, name, created_at}`` por ítem."""
    with _LOCK:
        raw = _load_raw()
        if _ensure_bundled_presets(raw):
            _save_raw(raw)
        out = []
        for it in raw.get("items", []):
            if isinstance(it, dict) and it.get("id") and it.get("name"):
                out.append(
                    {
                        "id": it["id"],
                        "name": it["name"],
                        "created_at": it.get("created_at", ""),
                    }
                )
        return sorted(out, key=lambda x: (x.get("name") or "").lower())


def get_preset(preset_id: str) -> dict[str, Any] | None:
    with _LOCK:
        raw = _load_raw()
        if _ensure_bundled_presets(raw):
            _save_raw(raw)
        for it in raw.get("items", []):
            if isinstance(it, dict) and it.get("id") == preset_id:
                return {
                    "id": it["id"],
                    "name": it.get("name", ""),
                    "system_extra": it.get("system_extra") or "",
                    "user_extra": it.get("user_extra") or "",
                    "created_at": it.get("created_at", ""),
                }
        return None


def get_selected_id() -> str | None:
    with _LOCK:
        sid = _load_raw().get("selected_id")
        return sid if isinstance(sid, str) and sid else None


def set_selected_id(preset_id: str | None) -> None:
    with _LOCK:
        raw = _load_raw()
        if preset_id is None:
            raw["selected_id"] = None
        else:
            ids = {it.get("id") for it in raw.get("items", []) if isinstance(it, dict)}
            raw["selected_id"] = preset_id if preset_id in ids else None
        _save_raw(raw)


def create_preset(name: str, system_extra: str, user_extra: str) -> dict[str, Any]:
    name = (name or "").strip() or "Sin nombre"
    pid = secrets.token_hex(8)
    entry = {
        "id": pid,
        "name": name[:120],
        "system_extra": system_extra or "",
        "user_extra": user_extra or "",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with _LOCK:
        raw = _load_raw()
        raw.setdefault("items", []).append(entry)
        raw["selected_id"] = pid
        _save_raw(raw)
    return entry


def update_preset(
    preset_id: str,
    *,
    name: str | None = None,
    system_extra: str | None = None,
    user_extra: str | None = None,
) -> dict[str, Any] | None:
    with _LOCK:
        raw = _load_raw()
        for it in raw.get("items", []):
            if isinstance(it, dict) and it.get("id") == preset_id:
                if name is not None:
                    it["name"] = (name.strip() or it.get("name"))[:120]
                if system_extra is not None:
                    it["system_extra"] = system_extra
                if user_extra is not None:
                    it["user_extra"] = user_extra
                _save_raw(raw)
                return {
                    "id": it["id"],
                    "name": it.get("name", ""),
                    "system_extra": it.get("system_extra") or "",
                    "user_extra": it.get("user_extra") or "",
                    "created_at": it.get("created_at", ""),
                }
        return None


def delete_preset(preset_id: str) -> bool:
    with _LOCK:
        raw = _load_raw()
        items = [it for it in raw.get("items", []) if isinstance(it, dict) and it.get("id") != preset_id]
        if len(items) == len(raw.get("items", [])):
            return False
        raw["items"] = items
        if raw.get("selected_id") == preset_id:
            raw["selected_id"] = None
        _save_raw(raw)
        return True
