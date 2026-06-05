"""Escritura del guion en la carpeta de sesión (`work`)."""

from __future__ import annotations

from pathlib import Path

from videomaker.core.script_bundle import write_script_bundle


def write_guion_to_session_work_dir(work_dir: Path, text: str) -> None:
    """Escribe guion.txt, pipeline/script.txt y pipeline/script.json."""
    raw = (text or "").replace("\r\n", "\n")
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "guion.txt").write_text(raw, encoding="utf-8")
    pipe = work_dir / "pipeline" / "script.txt"
    pipe.parent.mkdir(parents=True, exist_ok=True)
    pipe.write_text(raw, encoding="utf-8")
    write_script_bundle(work_dir, raw)
