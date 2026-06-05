"""Mapeo [CATEGORIA: …] → section / act (hook, body, cta) para Scene Editor."""

from __future__ import annotations

import re
from pathlib import Path

from videomaker.core.script_clean import extract_guion_body
from videomaker.scene_editor.models import Chunk

_CATEGORY_LINE = re.compile(r"(?im)^\s*\[CATEGORIA\s*:\s*([^\]]+)\]\s*$")


def normalize_section_name(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip())


def section_to_act(section: str | None) -> str:
    """Introducción → hook, Pilares → body, Cierre → cta."""
    if not section:
        return "body"
    s = section.lower()
    if any(k in s for k in ("introducción", "introduccion", "gancho", "hook", "intro ")):
        return "hook"
    if s.startswith("intro"):
        return "hook"
    if any(k in s for k in ("cierre", "cta", "closing", "outro")):
        return "cta"
    return "body"


def _extract_category_line(block: str) -> tuple[str | None, str]:
    """Si el bloque empieza con [CATEGORIA: …], devuelve (section, resto)."""
    lines = block.splitlines()
    if not lines:
        return None, block
    m = _CATEGORY_LINE.match(lines[0].strip())
    if not m:
        return None, block
    rest = "\n".join(lines[1:]).strip()
    return normalize_section_name(m.group(1)), rest


def build_script_section_ranges(script_text: str) -> list[tuple[int, int, str]]:
    """Índice de posiciones de carácter → nombre de sección en el cuerpo del guion."""
    body = extract_guion_body(script_text or "")
    if not body.strip():
        return []

    ranges: list[tuple[int, int, str]] = []
    current: str | None = None
    start = 0
    pos = 0

    for line in body.splitlines(keepends=True):
        m = _CATEGORY_LINE.match(line.strip())
        if m:
            if current is not None:
                ranges.append((start, pos, current))
            current = normalize_section_name(m.group(1))
            start = pos + len(line)
        pos += len(line)

    if current is not None:
        ranges.append((start, len(body), current))

    return ranges


def infer_section_from_script(script_text: str, narration: str) -> str | None:
    """Infiere sección buscando el texto narrado en el guion."""
    body = extract_guion_body(script_text or "")
    text = (narration or "").strip()
    if not body or not text:
        return None

    ranges = build_script_section_ranges(script_text)
    if not ranges:
        return None

    candidates: list[str] = []
    for part in (
        text,
        text.split("\n\n", 1)[0].strip(),
        text.split("\n", 1)[0].strip(),
    ):
        if part and part not in candidates:
            candidates.append(part)

    for candidate in candidates:
        for needle_len in (80, 60, 40, 24):
            needle = candidate[:needle_len].strip()
            if len(needle) < 8:
                continue
            pos = body.find(needle)
            if pos < 0:
                pos = body.find(re.sub(r"\s+", " ", needle))
            if pos < 0:
                continue
            for start, end, section in ranges:
                if start <= pos < end:
                    return section

    return None


def backfill_chunk_sections(script_text: str, chunks: list[Chunk]) -> list[Chunk]:
    """Rellena section en chunks que no la tienen, sin tocar audio ni prompts."""
    if not script_text.strip() or not chunks:
        return chunks

    out: list[Chunk] = []
    for chunk in chunks:
        if chunk.section:
            out.append(chunk)
            continue
        inferred = infer_section_from_script(script_text, chunk.narration_text)
        if inferred:
            out.append(chunk.model_copy(update={"section": inferred}))
        else:
            out.append(chunk)
    return out


def load_script_text(work_dir: Path) -> str:
    guion = work_dir / "guion.txt"
    pipe = work_dir / "pipeline" / "script.txt"
    if guion.is_file() and guion.stat().st_size > 0:
        return guion.read_text(encoding="utf-8")
    if pipe.is_file():
        return pipe.read_text(encoding="utf-8")
    return ""


def ensure_chunk_sections(work_dir: Path, chunks: list[Chunk], *, persist: bool = True) -> list[Chunk]:
    """Backfill desde guion.txt; persiste si hubo cambios."""
    if not chunks or all((c.section or "").strip() for c in chunks):
        return chunks

    script = load_script_text(work_dir)
    if not script.strip():
        return chunks

    updated = backfill_chunk_sections(script, chunks)
    if persist and any((a.section or "") != (b.section or "") for a, b in zip(chunks, updated, strict=False)):
        from videomaker.scene_editor.store import write_chunks

        write_chunks(work_dir, updated)
    return updated
