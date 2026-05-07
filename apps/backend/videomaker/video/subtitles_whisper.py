"""Subtítulos con tiempos vía Whisper local (modelo base por defecto)."""

from __future__ import annotations

from pathlib import Path

from videomaker.core import config


def transcribe_for_subtitles(
    audio_path: Path,
    *,
    model_size: str | None = None,
    language: str | None = None,
) -> list[dict]:
    """
    Devuelve segmentos tipo:
    [{"start": 0.0, "end": 2.4, "text": "Hola mundo"}, ...]
    """
    try:
        import whisper  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Whisper no está instalado. pip install openai-whisper"
        ) from e
    model = whisper.load_model(model_size or config.WHISPER_MODEL)
    kwargs = {"verbose": False}
    if language:
        kwargs["language"] = language
    result = model.transcribe(str(audio_path), **kwargs)
    out: list[dict] = []
    for s in result.get("segments", []):
        out.append(
            {
                "start": float(s["start"]),
                "end": float(s["end"]),
                "text": (s.get("text") or "").strip(),
            }
        )
    return out


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
