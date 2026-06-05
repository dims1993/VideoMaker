"""Subtítulos con tiempos vía Whisper local (modelo base por defecto)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from videomaker.core import config


def transcribe_for_subtitles(
    audio_path: Path,
    *,
    model_size: str | None = None,
    language: str | None = None,
    word_timestamps: bool = False,
) -> dict[str, Any]:
    """
    Transcribe audio with Whisper.

    Returns ``{"segments": [...], "words": [...]}``.
    Segments: ``{start, end, text}``. Words (optional): ``{start, end, word}``.
    """
    try:
        import whisper  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Whisper no está instalado. pip install openai-whisper"
        ) from e
    model = whisper.load_model(model_size or config.WHISPER_MODEL)
    kwargs: dict = {"verbose": False}
    if language:
        kwargs["language"] = language
    if word_timestamps:
        kwargs["word_timestamps"] = True
    result = model.transcribe(str(audio_path), **kwargs)
    segments: list[dict] = []
    words: list[dict] = []
    for s in result.get("segments", []):
        seg = {
            "start": round(float(s["start"]), 3),
            "end": round(float(s["end"]), 3),
            "text": (s.get("text") or "").strip(),
        }
        segments.append(seg)
        if word_timestamps:
            for w in s.get("words") or []:
                if not isinstance(w, dict):
                    continue
                token = str(w.get("word") or "").strip()
                if not token:
                    continue
                words.append(
                    {
                        "start": round(float(w.get("start", 0)), 3),
                        "end": round(float(w.get("end", 0)), 3),
                        "word": token,
                    }
                )
    return {"segments": segments, "words": words, "language": result.get("language")}


def segments_to_srt(segments: list[dict]) -> str:
    def ts(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{ts(seg['start'])} --> {ts(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"
