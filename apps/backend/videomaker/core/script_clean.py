"""Limpieza del guion antes de TTS: metadatos, outline y marcas que no deben leerse."""

from __future__ import annotations

import re

# Encabezado explícito de la parte narrable (tras OUTLINE u otros prefacios).
_GUION_HEADER = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?(GUIÓN|GUION|GUÍON)(?:\*\*)?(?:\s*[:\-—][^\n]*)?\s*$",
)

# Líneas que son solo guiones temporales / duración.
_TIME_ONLY = re.compile(
    r"^\s*\(?\d{1,2}:\d{2}(?:\s*[-–—]\s*\d{1,2}:\d{2})?\)?\s*$",
)


def _cut_before_guion_header(text: str) -> str:
    m = _GUION_HEADER.search(text)
    if not m:
        return text
    return text[m.end() :].lstrip("\n")


def _cut_from_etiquetas_broll(text: str) -> str:
    """Quita desde la cabecera de etiquetas B-roll (y similares) hasta el final del archivo."""
    # Una línea que declara la sección de etiquetas (no narración).
    patterns = (
        r"(?im)^[^\n]*\bETIQUETAS\s+(DE\s+)?B[\s\-]?ROLL\b[^\n]*(?:\n|$)",
        r"(?im)^[^\n]*\bB[\s\-]?ROLL\s+ETIQUETAS\b[^\n]*(?:\n|$)",
        r"(?im)^[^\n]*\bTAGS?\s+(PARA\s+)?B[\s\-]?ROLL\b[^\n]*(?:\n|$)",
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return text[: m.start()].rstrip()
    return text


def _strip_square_bracket_tags(text: str) -> str:
    """Quita cualquier fragmento […] (marcas PUENTE, TÉCNICA N, etc.)."""
    lines_out: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"\[[^\]]*\]", "", line)
        cleaned = re.sub(r" {2,}", " ", cleaned).strip()
        if cleaned:
            lines_out.append(cleaned)
    return "\n\n".join(lines_out).strip()


def _cut_outline_before_first_category(text: str) -> str:
    """Si el texto empieza con OUTLINE pero no hubo marcador GUIÓN, empieza en el primer [CATEGORIA:."""
    if not re.search(r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?outline\b", text[:2500]):
        return text
    m = re.search(r"(?im)^\[CATEGORIA:", text)
    if m:
        return text[m.start() :]
    return text


def _strip_inline_category_markers(line: str) -> str:
    return re.sub(r"\s*\[CATEGORIA:[^\]]*\]", "", line, flags=re.IGNORECASE)


def _should_skip_meta_line(stripped: str) -> bool:
    if not stripped:
        return False
    s = stripped.strip()
    if not s:
        return False
    if re.match(r"^\[CATEGORIA:", s, re.IGNORECASE):
        return True
    if re.match(r"^\[(NOTA|REF|META|TIMING|DURACIÓN|DURACION)[:\s]", s, re.IGNORECASE):
        return True
    if re.match(r"^#{1,6}\s+", s):
        return True
    if re.match(r"^(---+|\*{3,}|_{3,})$", s):
        return True
    up = s.upper()
    if up in ("OUTLINE", "GUIÓN", "GUION", "GUÍON"):
        return True
    if re.match(r"^outline\s*:", s, re.IGNORECASE):
        return True
    if re.match(r"^(tags?\s+para\s+stock|keywords?\s*(pexels)?|b[- ]?roll\s+tags?)\b", s, re.IGNORECASE):
        return True
    if _TIME_ONLY.match(s):
        return True
    if re.match(r"^\(?\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}\)?\s*$", s):
        return True
    # Viñetas de outline con tiempos (no narración).
    if re.match(r"^[-*]\s+.+\d{1,2}:\d{2}", s):
        return True
    if re.match(r"^\d+\.\s+.+\d{1,2}:\d{2}", s):
        return True
    # Línea que solo es una etiqueta entre corchetes (p. ej. [PUENTE], [TÉCNICA 1: …]).
    if re.match(r"^\[[^\]]+\]\s*$", s):
        return True
    return False


def _strip_trailing_stock_tags(text: str) -> str:
    """
    Quita el último párrafo si parece la línea de keywords para Pexels
    (muchas comas, tokens cortos, sin narrativa larga).
    """
    stripped = text.strip()
    if not stripped:
        return text
    parts = re.split(r"\n\s*\n", stripped)
    if len(parts) < 2:
        return text
    last = parts[-1].strip()
    if "\n" in last:
        return text
    if last.count(",") < 4:
        return text
    segments = [x.strip() for x in last.split(",") if x.strip()]
    if len(segments) < 6:
        return text
    if any(len(x) > 45 for x in segments):
        return text
    # Evitar quitar un párrafo que sea discurso con muchas comas.
    if last.count(".") >= 2 and last.count(",") <= last.count("."):
        return text
    return "\n\n".join(parts[:-1]).strip()


def text_for_tts(full_script: str) -> str:
    """
    Deja solo texto apto para VO: sin OUTLINE, sin [CATEGORIA:…],
    sin encabezados de sección ni la línea final de tags de stock.
    """
    text = full_script.replace("\r\n", "\n")
    text = _cut_before_guion_header(text)
    text = _cut_outline_before_first_category(text)
    text = _cut_from_etiquetas_broll(text)

    lines_out: list[str] = []
    for line in text.splitlines():
        s_stripped = line.strip()
        if _should_skip_meta_line(s_stripped):
            continue
        line = _strip_inline_category_markers(line)
        if not line.strip():
            lines_out.append("")
            continue
        lines_out.append(line)

    text = "\n".join(lines_out)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = _strip_square_bracket_tags(text)
    text = _strip_trailing_stock_tags(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not re.search(r"\w", text):
        raise ValueError(
            "El guion quedó vacío tras quitar metadatos (outline, categorías, tags). "
            "Revisa que exista la parte narrable o desactiva strip_markers."
        )
    return text
