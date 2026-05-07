"""Plan de palabras clave para stock: N términos cada ventana de audio."""

from __future__ import annotations

import re
import random
from collections import Counter

from videomaker.core import config
from videomaker.core.models import StockQuery

# Muy simple; más adelante: embeddings o NER local
_STOP_ES = {
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "y",
    "o",
    "pero",
    "por",
    "para",
    "de",
    "del",
    "en",
    "con",
    "sin",
    "que",
    "como",
    "muy",
    "más",
    "este",
    "esta",
    "eso",
    "ser",
    "es",
    "son",
    "al",
    "lo",
    "su",
    "sus",
    "se",
    "nos",
    "les",
    "ya",
    "hay",
    "fue",
    "han",
    "cada",
    "sobre",
    "entre",
    "también",
    "así",
    "todo",
    "todos",
    "puede",
    "pueden",
    "cuando",
    "donde",
    "qué",
    "porque",
    "si",
    "no",
    "un",
    "uno",
    "dos",
    "tres",
}
_STOP_EN = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "without",
    "that",
    "this",
    "these",
    "those",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "as",
    "at",
    "by",
    "from",
    "it",
    "its",
    "we",
    "you",
    "they",
    "them",
    "their",
    "our",
    "your",
    "can",
    "could",
    "should",
    "would",
    "may",
    "might",
    "not",
    "no",
    "so",
    "if",
    "when",
    "where",
    "what",
    "who",
    "how",
    "about",
    "into",
    "over",
    "after",
    "before",
    "than",
    "then",
    "also",
    "just",
    "very",
    "more",
    "most",
    "some",
    "any",
    "each",
    "every",
    "all",
    "both",
    "few",
    "such",
}


def _b_roll_visual_hints(text: str) -> list[str]:
    """Textos dentro de [B-ROLL: …] en el guion (prioridad para búsquedas visuales)."""
    hints: list[str] = []
    for m in re.finditer(r"\[B-ROLL\s*:?\s*([^\]]+)\]", text, re.IGNORECASE):
        h = m.group(1).strip()
        if len(h) > 2:
            hints.append(h[:120])
    return hints


def _tokens(text: str, lang: str) -> list[str]:
    stop = _STOP_ES if lang.startswith("es") else _STOP_EN
    raw = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}", text.lower())
    return [t for t in raw if t not in stop]


def estimate_duration_seconds(text: str, wpm: float = 150.0) -> float:
    words = len(re.findall(r"\b\w+\b", text))
    return max(30.0, (words / max(wpm, 60.0)) * 60.0)


def plan_stock_keywords(
    full_script: str,
    *,
    audio_duration_s: float | None = None,
    lang_hint: str = "es",
) -> list[StockQuery]:
    """
    Genera al menos `KEYWORDS_PER_WINDOW` queries por cada `KEYWORD_WINDOW_AUDIO_S`
    de audio estimado o medido.
    """
    duration = audio_duration_s or estimate_duration_seconds(full_script)
    n_windows = max(1, int(duration // config.KEYWORD_WINDOW_AUDIO_S) + 1)
    chunk_chars = max(200, len(full_script) // n_windows)
    queries: list[StockQuery] = []
    b_roll_hints = _b_roll_visual_hints(full_script)
    hint_i = 0

    for w in range(n_windows):
        start = w * config.KEYWORD_WINDOW_AUDIO_S
        end = min(duration, (w + 1) * config.KEYWORD_WINDOW_AUDIO_S)
        slice_start = min(len(full_script) - 1, w * chunk_chars)
        slice_end = min(len(full_script), slice_start + chunk_chars)
        window_text = full_script[slice_start:slice_end]
        toks = _tokens(window_text, lang_hint)
        counts = Counter(toks)
        top = [word for word, _ in counts.most_common(config.KEYWORDS_PER_WINDOW * 3)]
        random.shuffle(top)
        picked: list[str] = []
        if hint_i < len(b_roll_hints):
            picked.append(b_roll_hints[hint_i])
            hint_i += 1
        for term in top:
            if term not in picked:
                picked.append(term)
            if len(picked) >= config.KEYWORDS_PER_WINDOW:
                break
        while len(picked) < config.KEYWORDS_PER_WINDOW:
            picked.append(f"abstract background {len(picked) + 1}")
        for q in picked[: config.KEYWORDS_PER_WINDOW]:
            queries.append(StockQuery(query=q, start_audio_s=start, end_audio_s=end))
    return queries
