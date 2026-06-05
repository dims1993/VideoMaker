"""Parsea guion.txt → lista de Chunks (solo narración; etiquetas [B-ROLL] se ignoran)."""

from __future__ import annotations

import re
import uuid

from videomaker.core.script_clean import extract_guion_body
from videomaker.scene_editor.models import Chunk
from videomaker.scene_editor.section_mapping import _extract_category_line, normalize_section_name

_CATEGORY_LINE = re.compile(r"(?im)^\s*\[CATEGORIA\s*:\s*([^\]]+)\]\s*$")
_BROLL_ONLY = re.compile(r"(?im)^\s*\[B-ROLL\s*:\s*([^\]]*)\]\s*$")
_BROLL_INLINE = re.compile(r"(?im)\[B-ROLL\s*:\s*([^\]]*)\]")
_KEYWORDS_HEADER = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?"
    r"(?:KEYWORDS(?:\s+PARA\s+STOCK)?|REFERENCIA\s+VISUAL|"
    r"TAGS?\s+PARA\s+STOCK|B[- ]?ROLL\s+TAGS?)"
    r"(?:\*\*)?\s*$"
)


def _is_non_narrable_block(block: str) -> bool:
    """KEYWORDS, separadores ---, líneas comma-stock sin prosa."""
    s = block.strip()
    if not s:
        return True
    if s in ("---", "***", "___"):
        return True
    if _KEYWORDS_HEADER.match(s):
        return True
    if re.match(r"(?i)^keywords\b", s):
        return True
    if "\n" not in s and s.count(",") >= 4:
        segments = [x.strip() for x in s.split(",") if x.strip()]
        if len(segments) >= 6 and all(len(x) <= 50 for x in segments):
            if s.count(".") < 2:
                return True
    return False


def parse_script_to_chunks(raw_script: str) -> list[Chunk]:
    """
    Ignora OUTLINE. Conserva [CATEGORIA: …] como section en cada bloque.
    Divide por párrafos (\\n\\n).
    [B-ROLL: …] se elimina (no alimenta prompts visuales).
    """
    body = extract_guion_body(raw_script or "")
    if not body.strip():
        return []

    chunks: list[Chunk] = []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    current_section: str | None = None

    for block in blocks:
        if _is_non_narrable_block(block):
            continue

        cat_only = _CATEGORY_LINE.match(block.strip())
        if cat_only and "\n" not in block.strip():
            current_section = normalize_section_name(cat_only.group(1))
            continue

        section_from_block, block = _extract_category_line(block)
        if section_from_block:
            current_section = section_from_block
        if not block.strip():
            continue

        if _BROLL_ONLY.match(block):
            continue

        narration = _BROLL_INLINE.sub("", block)
        narration = re.sub(r"\*\*([^*]+)\*\*", r"\1", narration)
        narration = re.sub(r"[ \t]+", " ", narration)
        narration = re.sub(r"\n{2,}", "\n", narration).strip()

        if not narration:
            continue

        chunks.append(
            Chunk(
                id=str(uuid.uuid4()),
                narration_text=narration,
                section=current_section,
                director_note=None,
                status="idle",
            )
        )

    return chunks
