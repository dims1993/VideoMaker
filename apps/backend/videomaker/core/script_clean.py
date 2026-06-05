"""Limpieza del guion antes de TTS: metadatos, outline y marcas que no deben leerse."""

from __future__ import annotations

import re

# Encabezado explícito de la parte narrable (tras OUTLINE u otros prefacios).
_GUION_HEADER = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?(GUIÓN|GUION|GUÍON|SCRIPT)(?:\*\*)?(?:\s*[:\-—][^\n]*)?\s*$",
)

_EDITORIAL_ANALYSIS_HEADER = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?(?:ANÁLISIS\s+EDITORIAL|EDITORIAL\s+ANALYSIS)(?:\*\*)?\s*$",
)

# Líneas que son solo guiones temporales / duración.
_TIME_ONLY = re.compile(
    r"^\s*\(?\d{1,2}:\d{2}(?:\s*[-–—]\s*\d{1,2}:\d{2})?\)?\s*$",
)


def _cut_editorial_analysis(text: str) -> str:
    """Elimina sección ANÁLISIS EDITORIAL / EDITORIAL ANALYSIS si el modelo la generó por error."""
    m = _EDITORIAL_ANALYSIS_HEADER.search(text)
    if not m:
        return text
    rest = text[m.end() :]
    m2 = re.search(
        r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?(?:OUTLINE|GUIÓN|GUION|GUÍON|SCRIPT)(?:\*\*)?\s*$|^\[CATEGORIA:",
        rest,
    )
    if m2:
        head = text[: m.start()].rstrip()
        tail = rest[m2.start() :].lstrip("\n")
        return f"{head}\n\n{tail}".strip() if head else tail
    return text[: m.start()].rstrip()


def _cut_before_guion_header(text: str) -> str:
    m = _GUION_HEADER.search(text)
    if not m:
        return text
    return text[m.end() :].lstrip("\n")


def _is_planning_segment(text: str) -> bool:
    """Bloque de planificación (outline / beats) que no debe contarse como narración."""
    t = (text or "").strip()
    if not t:
        return True
    if re.search(r"(?im)^\[CATEGORIA:", t) or re.search(r"(?im)\[CATEGORIA:", t):
        return False
    if _GUION_HEADER.search(t):
        return False
    if re.search(r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?outline\b", t[:1200]):
        return True
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if not lines:
        return True
    bullet_like = sum(
        1 for ln in lines if re.match(r"^[-*•]\s+", ln) or re.match(r"^\d+[\.)]\s+", ln)
    )
    time_like = sum(1 for ln in lines if re.search(r"\d{1,2}:\d{2}", ln))
    words = len(re.findall(r"\b\w+\b", t, flags=re.UNICODE))
    if bullet_like >= max(2, len(lines) * 0.35) or time_like >= 2:
        return True
    if words < 150 and (bullet_like >= 1 or time_like >= 1):
        return True
    return False


def _segment_word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or "", flags=re.UNICODE))


def _first_narrative_segment_index(parts: list[str]) -> int:
    """Índice del primer bloque `---` que parece narración (no planificación)."""
    for i, part in enumerate(parts):
        if _is_planning_segment(part):
            continue
        if _segment_word_count(part) >= 80:
            return i
    for i, part in enumerate(parts):
        if re.search(r"(?im)^\[CATEGORIA:", part) or re.search(r"(?im)\[CATEGORIA:", part):
            return i
    if len(parts) >= 2:
        w0, w1 = _segment_word_count(parts[0]), _segment_word_count(parts[1])
        if w0 < 600 and w1 > w0 * 1.5 and not re.search(
            r"(?im)\[CATEGORIA:", parts[0]
        ):
            return 1
    return 0


def _drop_planning_segments(text: str) -> str:
    if not re.search(r"\n---\n", text):
        return text
    parts = [p.strip() for p in re.split(r"\n---\n", text) if p.strip()]
    if len(parts) < 2:
        return text
    start = _first_narrative_segment_index(parts)
    if start > 0:
        parts = parts[start:]
    narrative = [p for p in parts if not _is_planning_segment(p)]
    if narrative:
        return "\n\n---\n\n".join(narrative)
    for i, part in enumerate(parts):
        if re.search(r"(?im)^\[CATEGORIA:", part) or re.search(r"(?im)\[CATEGORIA:", part):
            return "\n\n---\n\n".join(parts[i:])
    return text


def extract_guion_body(full_script: str) -> str:
    """
    Parte narrable del guion: desde GUIÓN/SCRIPT o, si solo hay OUTLINE previo,
    desde el primer [CATEGORIA:]. Omite planificación (OUTLINE) y bloques
    ensamblados antes del primer fragmento con categoría.
    """
    text = full_script.replace("\r\n", "\n").strip()
    if not text:
        return ""
    text = _cut_editorial_analysis(text)
    m = _GUION_HEADER.search(text)
    if m:
        text = text[m.end() :].lstrip("\n")
    elif re.search(r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?outline\b", text[:2500]):
        m2 = re.search(r"(?im)^\[CATEGORIA:", text)
        if m2:
            text = text[m2.start() :].lstrip("\n")
    if re.search(r"\n---\n", text):
        parts = [p.strip() for p in re.split(r"\n---\n", text) if p.strip()]
        if len(parts) >= 2:
            start = _first_narrative_segment_index(parts)
            text = "\n\n---\n\n".join(parts[start:])
        elif re.search(r"(?im)^\[CATEGORIA:", text):
            for i, part in enumerate(parts):
                if re.search(r"(?im)^\[CATEGORIA:", part) or re.search(
                    r"(?im)\[CATEGORIA:", part
                ):
                    text = "\n\n---\n\n".join(parts[i:])
                    break
    text = _drop_planning_segments(text)
    return _cut_from_keywords_section(text)


def guion_is_newer_than_fragment_chunks(work_dir: Path) -> bool:
    """
    True si `guion.txt` se escribió después de los chunks (p. ej. Narrative Pacing Pass
    o edición manual del guion completo). En ese caso los fragmentos ya no reflejan el texto actual.
    """
    guion = work_dir / "guion.txt"
    if not guion.is_file() or guion.stat().st_size == 0:
        return False
    chunks_dir = work_dir / "pipeline" / "script_chunks"
    if not chunks_dir.is_dir():
        return False
    chunk_paths = [p for p in chunks_dir.glob("*.txt") if p.is_file() and p.stat().st_size > 0]
    if not chunk_paths:
        return False
    guion_mtime = guion.stat().st_mtime
    return guion_mtime > max(p.stat().st_mtime for p in chunk_paths)


def script_text_for_metrics(work_dir: Path | None, raw: str) -> tuple[str, str]:
    """
    Texto a analizar para longitud/minutos narrables.

    - Tras Pacing Pass / reescritura global: `guion.txt` (más reciente que `script_chunks/`).
    - Si no, fragmentación secuencial: solo chunks (evita OUTLINE duplicado en guion ensamblado).
    """
    raw_norm = (raw or "").replace("\r\n", "\n").strip()
    if work_dir is not None:
        guion_path = work_dir / "guion.txt"
        if guion_is_newer_than_fragment_chunks(work_dir) and guion_path.is_file():
            try:
                return guion_path.read_text(encoding="utf-8").strip(), "guion_revised"
            except OSError:
                pass
        try:
            from videomaker.llm.script_fragmentation import chunk_file, load_state

            st = load_state(work_dir)
            steps = st.get("steps") if isinstance(st, dict) else None
            if isinstance(steps, list) and steps:
                parts: list[str] = []
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        continue
                    if step.get("status") not in {"generated", "done"}:
                        continue
                    p = chunk_file(work_dir, i)
                    if p.is_file() and p.stat().st_size > 0:
                        parts.append(p.read_text(encoding="utf-8").strip())
                if parts:
                    joined = "\n\n---\n\n".join(parts)
                    if not re.search(r"(?im)^\s*(GUI[ÓO]N|GUION|SCRIPT)\s*$", joined):
                        joined = f"GUIÓN\n{joined}"
                    return joined, "fragments"
        except Exception:
            pass
    return raw_norm, "guion_file"


def _cut_from_keywords_section(text: str) -> str:
    """Quita KEYWORDS / referencia visual al final (no narrable)."""
    patterns = (
        r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?"
        r"(KEYWORDS(?:\s+PARA\s+STOCK)?|REFERENCIA\s+VISUAL|"
        r"TAGS?\s+PARA\s+STOCK|B[- ]?ROLL\s+TAGS?)"
        r"(?:\*\*)?\s*(?:[:\-—].*)?\s*$",
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            head = text[: m.start()].rstrip()
            head = re.sub(r"\n---\s*$", "", head).rstrip()
            return head
    return text


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


# Prefijos de dirección de voz al inicio de línea: **Voz**: / Voz: / **Narrador**: etc.
_VOZ_PREFIX = re.compile(
    r"(?:^\s*\*\*)?(?:Voz|Narrador|Presentador|Host|VO|Locutor|Voz en off|Narración)(?:\*\*)?"
    r"\s*[:\-]\s*",
    re.IGNORECASE,
)


def _strip_voice_prefixes(text: str) -> str:
    """Elimina prefijos de dirección de voz al inicio de cada línea (e.g. '**Voz**: texto')."""
    lines_out: list[str] = []
    for line in text.splitlines():
        # Solo actúa si el prefijo está al inicio de la línea (con espacios opcionales)
        stripped = line.lstrip()
        m = _VOZ_PREFIX.match(stripped)
        if m:
            remainder = stripped[m.end():].strip()
            if remainder:
                lines_out.append(remainder)
            # Si tras quitar el prefijo no queda nada, omitimos la línea
        else:
            lines_out.append(line)
    return "\n".join(lines_out)


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
    if up in ("OUTLINE", "GUIÓN", "GUION", "GUÍON", "SCRIPT", "KEYWORDS"):
        return True
    if re.match(r"^(ANÁLISIS\s+EDITORIAL|EDITORIAL\s+ANALYSIS)\s*$", up):
        return True
    if re.match(r"^outline\s*:", s, re.IGNORECASE):
        return True
    if re.match(r"^(tags?\s+para\s+stock|keywords?\s+para\s+stock|referencia\s+visual|b[- ]?roll\s+tags?)\b", s, re.IGNORECASE):
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
    Quita el último párrafo si parece la línea de keywords de referencia visual
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
    Deja solo texto apto para VO: cuerpo GUIÓN (sin OUTLINE), sin [CATEGORIA:…],
    sin encabezados de sección ni la línea final de keywords de referencia visual.
    """
    text = extract_guion_body(full_script)
    if not text.strip():
        text = full_script.replace("\r\n", "\n")
    text = _cut_from_keywords_section(text)
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
    text = _strip_voice_prefixes(text)          # quita **Voz**: / Voz: antes y después del bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = _strip_voice_prefixes(text)          # segunda pasada por si quedó "Voz:" sin bold
    text = _strip_square_bracket_tags(text)
    text = _strip_trailing_stock_tags(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not re.search(r"\w", text):
        raise ValueError(
            "El guion quedó vacío tras quitar metadatos (outline, categorías, tags). "
            "Revisa que exista la parte narrable o desactiva strip_markers."
        )
    return text


def narrable_wpm() -> float:
    return _narrable_wpm()


def _narrable_wpm() -> float:
    import os

    raw = (os.environ.get("VIDEOMAKER_SCRIPT_WORDS_PER_MINUTE", "") or "").strip() or "150"
    try:
        v = float(raw)
    except ValueError:
        v = 150.0
    return max(80.0, min(v, 240.0))


def narrable_plain_text(full_script: str) -> str:
    """
    Texto narrable para métricas (lint, debug, UI): mismo criterio que TTS cuando es posible.
    Omite OUTLINE, [CATEGORIA], [B-ROLL], keywords finales y separadores `---`.
    """
    text = (full_script or "").replace("\r\n", "\n").strip()
    if not text:
        return ""
    try:
        return text_for_tts(text)
    except ValueError:
        body = extract_guion_body(text) or text
        body = _cut_from_keywords_section(body)
        body = _cut_from_etiquetas_broll(body)
        lines_out: list[str] = []
        for line in body.splitlines():
            s_stripped = line.strip()
            if _should_skip_meta_line(s_stripped):
                continue
            if re.match(r"^\s*---\s*$", s_stripped):
                continue
            line = _strip_inline_category_markers(line)
            if line.strip():
                lines_out.append(line)
        body = "\n".join(lines_out)
        body = _strip_voice_prefixes(body)
        body = re.sub(r"\*\*([^*]+)\*\*", r"\1", body)
        body = _strip_square_bracket_tags(body)
        return re.sub(r"\n{3,}", "\n\n", body).strip()


def count_narrable_words(full_script: str) -> int:
    plain = narrable_plain_text(full_script)
    if not plain:
        return 0
    return len(re.findall(r"\b\w+\b", plain, flags=re.UNICODE))


def estimated_narrable_minutes(word_count: int, *, wpm: float | None = None) -> float:
    if word_count <= 0:
        return 0.0
    rate = _narrable_wpm() if wpm is None else max(80.0, min(float(wpm), 240.0))
    return word_count / rate
