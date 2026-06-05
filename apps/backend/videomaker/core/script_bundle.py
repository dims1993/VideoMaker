"""Guion híbrido: JSON con texto TTS + outline + secciones con notas B-roll.

El LLM sigue devolviendo el formato markdown con OUTLINE, GUIÓN, [CATEGORIA] y [B-ROLL].
Este módulo deriva `pipeline/script.json` sin sustituir `guion.txt` / `pipeline/script.txt`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from videomaker.core.script_clean import extract_guion_body, text_for_tts

_CAT_LINE = re.compile(r"(?im)^\[CATEGORIA:\s*([^\]]+)\]\s*$")

_BROLL = re.compile(r"\[B-ROLL\s*:\s*([^\]]*)\]", re.IGNORECASE)


def extract_outline_and_body(full: str) -> tuple[str, str]:
    """Separa outline (planificación) del cuerpo narrativo (GUIÓN / [CATEGORIA:])."""
    full = full.replace("\r\n", "\n")
    body = extract_guion_body(full).strip()
    full_st = full.strip()
    if not body or body == full_st:
        return "", full_st
    anchor = body.split("\n", 1)[0].strip()
    pos = full.find(anchor)
    if pos <= 0:
        return "", body
    return full[:pos].strip(), body


def _parse_broll_parts(fragment: str) -> list[dict[str, str]]:
    """Alterna narración y etiquetas [B-ROLL: …] en orden."""
    parts: list[dict[str, str]] = []
    pos = 0
    for m in _BROLL.finditer(fragment):
        if m.start() > pos:
            n = fragment[pos : m.start()].strip()
            if n:
                parts.append({"type": "narration", "text": n})
        parts.append({"type": "b_roll", "text": m.group(1).strip()})
        pos = m.end()
    if pos < len(fragment):
        tail = fragment[pos:].strip()
        if tail:
            parts.append({"type": "narration", "text": tail})
    return parts


def _sections_from_body(body: str) -> list[dict[str, Any]]:
    matches = list(_CAT_LINE.finditer(body))
    if not matches:
        b = body.strip()
        if not b:
            return []
        return [{"category": None, "parts": _parse_broll_parts(b)}]

    sections: list[dict[str, Any]] = []
    if matches[0].start() > 0:
        pre = body[: matches[0].start()].strip()
        if pre:
            sections.append({"category": None, "parts": _parse_broll_parts(pre)})

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        cat = m.group(1).strip()
        chunk_body = body[start:end].strip()
        sections.append({"category": cat, "parts": _parse_broll_parts(chunk_body)})
    return sections


def build_script_bundle(raw_script: str) -> dict[str, Any]:
    """
    Construye el objeto guardado en `pipeline/script.json`.

    - plain_text: apto para TTS (mismo criterio que text_for_tts).
    - sections: bloques por [CATEGORIA] con partes narración / b_roll.
    """
    raw_script = raw_script.replace("\r\n", "\n")
    outline, body = extract_outline_and_body(raw_script)

    plain = ""
    tts_ready = False
    tts_note = ""
    try:
        plain = text_for_tts(raw_script)
        tts_ready = bool(plain.strip())
    except ValueError as e:
        tts_note = str(e)

    bundle: dict[str, Any] = {
        "version": 1,
        "plain_text": plain,
        "tts_ready": tts_ready,
        "raw_markdown": raw_script.strip(),
        "outline": outline,
        "sections": _sections_from_body(body),
    }
    if tts_note:
        bundle["tts_warning"] = tts_note
    return bundle


def write_script_bundle(work_dir: Path, raw_script: str) -> Path:
    """Escribe `work_dir/pipeline/script.json`."""
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "script.json"
    bundle = build_script_bundle(raw_script)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from videomaker.llm.script_lint import persist_script_quality

        persist_script_quality(work_dir, raw_script)
    except Exception:
        pass
    return path


def read_script_bundle(work_dir: Path) -> dict[str, Any] | None:
    p = work_dir / "pipeline" / "script.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
