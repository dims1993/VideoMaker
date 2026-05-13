"""Biblioteca de guiones: copias con nombre fuera de la carpeta `work` (persisten al cambiar de sesión)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from videomaker.core import config
from videomaker.core.script_bundle import write_script_bundle

_DIR_NAME = "saved_guiones"
_INDEX = "index.json"
_MAX_TEXT_BYTES = 4 * 1024 * 1024
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)


def _base_dir() -> Path:
    d = config.OUTPUT_DIR / _DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return _base_dir() / _INDEX


def _read_index() -> dict[str, Any]:
    p = _index_path()
    if not p.is_file():
        return {"version": 1, "items": []}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("items"), list):
            return raw
    except Exception:
        pass
    return {"version": 1, "items": []}


def _write_index(data: dict[str, Any]) -> None:
    _index_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_id(sid: str) -> str:
    sid = sid.strip().lower()
    if not _UUID_RE.match(sid):
        raise ValueError("id inválido")
    return sid


def list_saved(*, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    data = _read_index()
    items = data.get("items") or []
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        iid = str(row.get("id") or "").strip()
        if not iid:
            continue
        out.append(
            {
                "id": iid,
                "title": str(row.get("title") or "Sin título"),
                "created_at": str(row.get("created_at") or ""),
                "byte_len": int(row.get("byte_len") or 0),
                "preview": str(row.get("preview") or "")[:400],
            }
        )
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return out[:limit]


def _preview(text: str, n: int = 220) -> str:
    t = " ".join((text or "").replace("\r\n", "\n").split())
    return t[:n] + ("…" if len(t) > n else "")


def save_text_to_library(text: str, title: str | None = None) -> dict[str, Any]:
    raw = (text or "").replace("\r\n", "\n")
    b = raw.encode("utf-8")
    if len(b) > _MAX_TEXT_BYTES:
        raise ValueError(f"El guion supera el máximo permitido ({_MAX_TEXT_BYTES // (1024 * 1024)} MiB).")
    if not raw.strip():
        raise ValueError("El texto del guion está vacío.")

    sid = str(uuid.uuid4())
    path = _base_dir() / f"{sid}.txt"
    path.write_text(raw, encoding="utf-8")

    title_clean = (title or "").strip() or f"Guion {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
    entry = {
        "id": sid,
        "title": title_clean,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_len": len(b),
        "preview": _preview(raw),
    }

    data = _read_index()
    items = list(data.get("items") or [])
    if not isinstance(items, list):
        items = []
    items.insert(0, entry)
    data["items"] = items
    _write_index(data)
    return entry


def save_from_work_dir(work_dir: Path, title: str | None = None) -> dict[str, Any]:
    guion = work_dir / "guion.txt"
    pipe = work_dir / "pipeline" / "script.txt"
    text = ""
    if guion.is_file() and guion.stat().st_size > 0:
        text = guion.read_text(encoding="utf-8")
    elif pipe.is_file():
        text = pipe.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("No hay guion en esta sesión (guion.txt / pipeline/script.txt vacíos o inexistentes).")
    return save_text_to_library(text, title=title)


def read_saved_text(sid: str) -> str:
    sid = _safe_id(sid)
    p = _base_dir() / f"{sid}.txt"
    if not p.is_file():
        raise FileNotFoundError("Guion no encontrado en la biblioteca.")
    return p.read_text(encoding="utf-8")


def delete_saved(sid: str) -> bool:
    sid = _safe_id(sid)
    p = _base_dir() / f"{sid}.txt"
    try:
        p.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass
    data = _read_index()
    items = [x for x in (data.get("items") or []) if isinstance(x, dict) and str(x.get("id")) != sid]
    data["items"] = items
    _write_index(data)
    return True


def write_guion_to_session_work_dir(work_dir: Path, text: str) -> None:
    """Escribe guion.txt, pipeline/script.txt y pipeline/script.json (misma semántica que PUT /api/script)."""
    raw = (text or "").replace("\r\n", "\n")
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "guion.txt").write_text(raw, encoding="utf-8")
    pipe = work_dir / "pipeline" / "script.txt"
    pipe.parent.mkdir(parents=True, exist_ok=True)
    pipe.write_text(raw, encoding="utf-8")
    write_script_bundle(work_dir, raw)
