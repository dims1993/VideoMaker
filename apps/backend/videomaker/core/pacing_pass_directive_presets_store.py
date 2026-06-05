"""Biblioteca de directrices guardadas para Narrative Pacing Pass (persiste en repo)."""

from __future__ import annotations

import json
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from videomaker.core import config

_LOCK = threading.Lock()
_FILENAME = "pacing_pass_directive_presets.json"
_NAME_RE = re.compile(r"^directriz(\d+)$", re.I)
_MAX_ITEMS = 32
_MAX_TEXT = 8000
_MAX_NAME = 48


def _path() -> Path:
    return config.PROJECT_ROOT / _FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _sanitize_name(name: str) -> str:
    n = (name or "").strip()[:_MAX_NAME]
    if not n:
        raise ValueError("El nombre de la directriz no puede estar vacío.")
    return n


def _next_default_name(items: list[dict[str, Any]]) -> str:
    used = set()
    max_n = 0
    for it in items:
        raw_name = str(it.get("name") or "").strip()
        used.add(raw_name.lower())
        m = _NAME_RE.match(raw_name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    n = max_n + 1
    while True:
        candidate = f"directriz{n:02d}"
        if candidate.lower() not in used:
            return candidate
        n += 1
        if n > 999:
            raise ValueError("Demasiadas directrices guardadas.")


def list_directive_presets() -> list[dict[str, Any]]:
    with _LOCK:
        data = _load_raw()
        items = data.get("items") if isinstance(data.get("items"), list) else []
        out: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            pid = str(it.get("id") or "").strip()
            name = str(it.get("name") or "").strip()
            text = str(it.get("text") or "")
            if pid and name:
                out.append(
                    {
                        "id": pid,
                        "name": name,
                        "text": text,
                        "updated_at": it.get("updated_at"),
                    }
                )
        out.sort(key=lambda x: str(x.get("name") or "").lower())
        return out


def save_directive_preset(*, text: str, name: str | None = None) -> dict[str, Any]:
    body = (text or "").strip()
    if not body:
        raise ValueError("Escribe la directriz antes de guardarla.")
    if len(body) > _MAX_TEXT:
        raise ValueError(f"La directriz supera {_MAX_TEXT} caracteres.")

    with _LOCK:
        data = _load_raw()
        items: list[dict[str, Any]] = [
            x for x in (data.get("items") or []) if isinstance(x, dict)
        ]
        if len(items) >= _MAX_ITEMS:
            raise ValueError(f"Máximo {_MAX_ITEMS} directrices guardadas.")

        label = _sanitize_name(name) if name and str(name).strip() else _next_default_name(items)
        lower_names = {str(x.get("name") or "").strip().lower() for x in items}
        if label.lower() in lower_names:
            raise ValueError(f"Ya existe una directriz llamada «{label}». Renómbrala o elige otro nombre.")

        row = {
            "id": secrets.token_hex(8),
            "name": label,
            "text": body,
            "updated_at": _now_iso(),
        }
        items.append(row)
        data["items"] = items
        _save_raw(data)
        return row


def rename_directive_preset(*, preset_id: str, name: str) -> dict[str, Any]:
    pid = (preset_id or "").strip()
    if not pid:
        raise ValueError("Falta id de la directriz.")
    label = _sanitize_name(name)

    with _LOCK:
        data = _load_raw()
        items: list[dict[str, Any]] = [
            x for x in (data.get("items") or []) if isinstance(x, dict)
        ]
        found: dict[str, Any] | None = None
        for it in items:
            if str(it.get("id") or "").strip() == pid:
                found = it
                break
        if found is None:
            raise ValueError("Directriz no encontrada.")

        for it in items:
            if str(it.get("id") or "").strip() == pid:
                continue
            if str(it.get("name") or "").strip().lower() == label.lower():
                raise ValueError(f"Ya existe una directriz llamada «{label}».")

        found["name"] = label
        found["updated_at"] = _now_iso()
        data["items"] = items
        _save_raw(data)
        return {
            "id": pid,
            "name": label,
            "text": str(found.get("text") or ""),
            "updated_at": found.get("updated_at"),
        }


def delete_directive_preset(*, preset_id: str) -> None:
    pid = (preset_id or "").strip()
    if not pid:
        raise ValueError("Falta id de la directriz.")
    with _LOCK:
        data = _load_raw()
        items = [x for x in (data.get("items") or []) if isinstance(x, dict)]
        next_items = [x for x in items if str(x.get("id") or "").strip() != pid]
        if len(next_items) == len(items):
            raise ValueError("Directriz no encontrada.")
        data["items"] = next_items
        _save_raw(data)
