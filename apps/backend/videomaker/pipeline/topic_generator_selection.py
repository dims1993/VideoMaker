"""Preservar o inferir selected_index en topic_generator.json."""

from __future__ import annotations

from typing import Any


def _norm(s: str) -> str:
    return (s or "").strip().casefold()


def _index_by_title(topics: list[Any], title: str) -> int | None:
    want = _norm(title)
    if not want:
        return None
    for i, t in enumerate(topics):
        if not isinstance(t, dict):
            continue
        if _norm(str(t.get("title") or "")) == want:
            return i
    return None


def _index_by_angle(topics: list[Any], angle: str) -> int | None:
    want = _norm(angle)
    if not want:
        return None
    for i, t in enumerate(topics):
        if not isinstance(t, dict):
            continue
        if _norm(str(t.get("angle") or "")) == want:
            return i
    return None


def get_selected_topic(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Tema elegido en topic_generator.json (selected_index)."""
    if not isinstance(data, dict):
        return None
    topics = data.get("topics")
    if not isinstance(topics, list) or not topics:
        return None
    idx = data.get("selected_index")
    if not isinstance(idx, int) or idx < 0 or idx >= len(topics):
        return None
    row = topics[idx]
    return row if isinstance(row, dict) else None


def session_topic_hints(work_dir) -> tuple[str, str]:
    """Keywords/ángulo de sesión desde prompt.json (si existe)."""
    from pathlib import Path

    import json

    p = Path(work_dir) / "pipeline" / "prompt.json"
    if not p.is_file():
        return "", ""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    kw = str(data.get("topic") or data.get("keywords") or "").strip()
    ctx = str(data.get("context") or "").strip()
    return kw, ctx


def apply_topic_selection(
    payload: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
    session_keywords: str = "",
    session_context: str = "",
) -> dict[str, Any]:
    """
    Ajusta selected_index tras generar temas:
    - conserva selección previa si el título sigue en la lista;
    - si no, infiere por keywords/ángulo de sesión.
    """
    topics = payload.get("topics")
    if not isinstance(topics, list) or not topics:
        payload["selected_index"] = None
        return payload

    prev = previous if isinstance(previous, dict) else {}
    prev_topics = prev.get("topics") if isinstance(prev.get("topics"), list) else []
    prev_idx = prev.get("selected_index")
    if isinstance(prev_idx, int) and prev_idx >= 0:
        if prev_idx < len(prev_topics):
            old_t = prev_topics[prev_idx]
            if isinstance(old_t, dict):
                title = str(old_t.get("title") or "").strip()
                idx = _index_by_title(topics, title)
                if idx is not None:
                    payload["selected_index"] = idx
                    return payload

    kw = (session_keywords or "").strip()
    ctx = (session_context or "").strip()
    if kw:
        idx = _index_by_title(topics, kw)
        if idx is not None:
            payload["selected_index"] = idx
            return payload
    if ctx:
        idx = _index_by_angle(topics, ctx)
        if idx is not None:
            payload["selected_index"] = idx
            return payload

    payload["selected_index"] = None
    return payload


def resolve_topic_generator_artifact(
    work_dir,
    data: dict[str, Any],
    *,
    persist_if_inferred: bool = True,
) -> dict[str, Any]:
    """Si falta selected_index, intenta inferirlo y opcionalmente persiste."""
    if not data:
        return data
    from videomaker.pipeline.duration_policy import apply_duration_policy_to_topic_payload

    data = apply_duration_policy_to_topic_payload(dict(data))
    if data.get("selected_index") is not None:
        return data
    kw, ctx = session_topic_hints(work_dir)
    if not kw and not ctx:
        return data
    updated = apply_topic_selection(
        dict(data),
        previous=data,
        session_keywords=kw,
        session_context=ctx,
    )
    if updated.get("selected_index") is None:
        return data
    if persist_if_inferred:
        from videomaker.pipeline.runner import write_topic_generator_artifact

        write_topic_generator_artifact(work_dir, updated)
    return updated
