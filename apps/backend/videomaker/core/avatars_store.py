"""Store global de avatares para el canal (avatars.json en la raíz del proyecto).

Cada avatar describe al personaje que aparecerá en los prompts de imagen.
Sigue el mismo patrón que prompt_presets_store: CRUD atómico con lock,
un avatar bundled por defecto (Nerd Boy) que se inyecta si no existe.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from videomaker.core import config
from videomaker.llm.avatar_prompt_writer import AVATAR_DEFAULT_DESCRIPTION, AVATAR_EXPRESSIONS

_LOCK = threading.Lock()
_FILENAME = "avatars.json"

BUNDLED_AVATAR_ID = "nerd_boy_v1"
BUNDLED_AVATAR_NAME = "Nerd Boy (canal por defecto)"

_BUNDLED_STYLE_NOTES = (
    "Whiteboard animation style, flat 2D illustration, thick black outlines, "
    "clean simple colors, educational YouTube channel aesthetic."
)

# Nombre del personaje que usa el canal en sus guiones
BUNDLED_AVATAR_CHARACTER_NAME = "Nerd"


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


def _ensure_bundled(raw: dict[str, Any]) -> bool:
    """Inyecta el avatar Nerd Boy si no está en disco. Devuelve True si hubo cambios."""
    ids = {it.get("id") for it in raw.get("items", []) if isinstance(it, dict)}
    if BUNDLED_AVATAR_ID in ids:
        return False
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    raw.setdefault("items", []).insert(
        0,
        {
            "id": BUNDLED_AVATAR_ID,
            "name": BUNDLED_AVATAR_NAME,
            "description": AVATAR_DEFAULT_DESCRIPTION,
            "expressions": list(AVATAR_EXPRESSIONS.keys()),
            "style_notes": _BUNDLED_STYLE_NOTES,
            "intro_enabled": True,
            "intro_character_name": BUNDLED_AVATAR_CHARACTER_NAME,
            "outro_enabled": True,
            "outro_character_name": BUNDLED_AVATAR_CHARACTER_NAME,
            "created_at": now,
            "bundled": True,
        },
    )
    return True


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def list_avatars() -> list[dict[str, Any]]:
    """Devuelve lista resumida {id, name, created_at, bundled}."""
    with _LOCK:
        raw = _load_raw()
        if _ensure_bundled(raw):
            _save_raw(raw)
        out = []
        for it in raw.get("items", []):
            if isinstance(it, dict) and it.get("id") and it.get("name"):
                out.append(
                    {
                        "id": it["id"],
                        "name": it["name"],
                        "created_at": it.get("created_at", ""),
                        "bundled": bool(it.get("bundled")),
                    }
                )
        return out


def get_avatar(avatar_id: str) -> dict[str, Any] | None:
    with _LOCK:
        raw = _load_raw()
        if _ensure_bundled(raw):
            _save_raw(raw)
        for it in raw.get("items", []):
            if isinstance(it, dict) and it.get("id") == avatar_id:
                return _serialize(it)
        return None


def create_avatar(
    name: str,
    description: str,
    *,
    expressions: list[str] | None = None,
    style_notes: str = "",
    intro_enabled: bool = True,
    intro_character_name: str = "",
    outro_enabled: bool = True,
    outro_character_name: str = "",
) -> dict[str, Any]:
    name = (name or "").strip() or "Sin nombre"
    description = (description or "").strip() or AVATAR_DEFAULT_DESCRIPTION
    aid = secrets.token_hex(8)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = {
        "id": aid,
        "name": name[:120],
        "description": description,
        "expressions": expressions or list(AVATAR_EXPRESSIONS.keys()),
        "style_notes": (style_notes or "").strip(),
        "intro_enabled": bool(intro_enabled),
        "intro_character_name": (intro_character_name or name).strip()[:80],
        "outro_enabled": bool(outro_enabled),
        "outro_character_name": (outro_character_name or name).strip()[:80],
        "created_at": now,
        "bundled": False,
    }
    with _LOCK:
        raw = _load_raw()
        _ensure_bundled(raw)
        raw.setdefault("items", []).append(entry)
        _save_raw(raw)
    return _serialize(entry)


def update_avatar(
    avatar_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    expressions: list[str] | None = None,
    style_notes: str | None = None,
    intro_enabled: bool | None = None,
    intro_character_name: str | None = None,
    outro_enabled: bool | None = None,
    outro_character_name: str | None = None,
) -> dict[str, Any] | None:
    with _LOCK:
        raw = _load_raw()
        for it in raw.get("items", []):
            if isinstance(it, dict) and it.get("id") == avatar_id:
                if name is not None:
                    it["name"] = (name.strip() or it.get("name", ""))[:120]
                if description is not None:
                    it["description"] = description.strip() or it.get("description", "")
                if expressions is not None:
                    it["expressions"] = expressions
                if style_notes is not None:
                    it["style_notes"] = style_notes.strip()
                if intro_enabled is not None:
                    it["intro_enabled"] = bool(intro_enabled)
                if intro_character_name is not None:
                    it["intro_character_name"] = intro_character_name.strip()[:80]
                if outro_enabled is not None:
                    it["outro_enabled"] = bool(outro_enabled)
                if outro_character_name is not None:
                    it["outro_character_name"] = outro_character_name.strip()[:80]
                _save_raw(raw)
                return _serialize(it)
        return None


def delete_avatar(avatar_id: str) -> bool:
    """No se puede borrar el avatar bundled."""
    with _LOCK:
        raw = _load_raw()
        original = raw.get("items", [])
        filtered = [
            it for it in original
            if not (isinstance(it, dict) and it.get("id") == avatar_id and not it.get("bundled"))
        ]
        if len(filtered) == len(original):
            return False
        raw["items"] = filtered
        _save_raw(raw)
        return True


def _serialize(it: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": it["id"],
        "name": it.get("name", ""),
        "description": it.get("description", ""),
        "expressions": it.get("expressions") or list(AVATAR_EXPRESSIONS.keys()),
        "style_notes": it.get("style_notes") or "",
        "intro_enabled": bool(it.get("intro_enabled", True)),
        "intro_character_name": it.get("intro_character_name") or it.get("name", ""),
        "outro_enabled": bool(it.get("outro_enabled", True)),
        "outro_character_name": it.get("outro_character_name") or it.get("name", ""),
        "created_at": it.get("created_at", ""),
        "bundled": bool(it.get("bundled")),
    }
