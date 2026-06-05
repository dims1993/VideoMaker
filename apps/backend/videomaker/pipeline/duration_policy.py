"""Duración objetivo del pipeline (primer vídeo completo / depuración audio-visual)."""

from __future__ import annotations

PIPELINE_TARGET_MIN_MINUTES = 10.0
PIPELINE_TARGET_MAX_MINUTES = 12.0
PIPELINE_DEFAULT_MINUTES = 10.0


def clamp_pipeline_minutes(raw: float | int | None) -> float:
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return PIPELINE_DEFAULT_MINUTES
    if n <= 0:
        return PIPELINE_DEFAULT_MINUTES
    return max(PIPELINE_TARGET_MIN_MINUTES, min(PIPELINE_TARGET_MAX_MINUTES, n))


def format_pipeline_duration_minutes(raw: float | int | None) -> int | float:
    """Entero si es redondo; si no, un decimal."""
    n = clamp_pipeline_minutes(raw)
    if abs(n - round(n)) < 1e-6:
        return int(round(n))
    return round(n, 1)


def apply_duration_policy_to_topic_payload(payload: dict) -> dict:
    topics = payload.get("topics")
    if isinstance(topics, list):
        for t in topics:
            if isinstance(t, dict):
                t["recommended_duration_minutes"] = format_pipeline_duration_minutes(
                    t.get("recommended_duration_minutes"),
                )
    payload["duration_policy"] = {
        "target_min_minutes": PIPELINE_TARGET_MIN_MINUTES,
        "target_max_minutes": PIPELINE_TARGET_MAX_MINUTES,
        "default_minutes": PIPELINE_DEFAULT_MINUTES,
    }
    return payload
