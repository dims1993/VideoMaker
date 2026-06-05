"""Persistencia y normalización de transcripts_session por carpeta de trabajo."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from videomaker.web.transcript_files import extract_transcripts_from_json

SESSION_FILENAME = "transcripts_session.json"
ANALYZE_STATUSES = ("pending", "analyzing", "completed", "error")


def _session_path(work_dir: Path) -> Path:
    return work_dir / "pipeline" / SESSION_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_video_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Conserva solo video_id, title, transcript, duration_s y status."""
    vid = str(raw.get("video_id") or "").strip()
    title = str(raw.get("title") or "").strip()
    transcript = str(raw.get("transcript") or "").strip()
    dur = raw.get("duration_s")
    duration_s: int | None = None
    try:
        if dur is not None:
            duration_s = int(dur)
    except (TypeError, ValueError):
        duration_s = None
    status = raw.get("status")
    if status is None:
        status = "ok" if transcript else "missing"
    else:
        status = str(status).strip() or ("ok" if transcript else "missing")
    return {
        "video_id": vid,
        "title": title,
        "transcript": transcript,
        "duration_s": duration_s,
        "status": status,
    }


def slim_channel(channel: dict[str, Any] | None, *, fallback_id: str = "") -> dict[str, Any]:
    ch = channel if isinstance(channel, dict) else {}
    cid = str(ch.get("channel_id") or fallback_id or "").strip()
    lang = ch.get("language")
    if lang is not None:
        lang = str(lang).strip() or None
    out: dict[str, Any] = {}
    if cid:
        out["channel_id"] = cid
    if lang:
        out["language"] = lang
    return out


def count_valid_transcripts(videos: list[dict[str, Any]]) -> int:
    n = 0
    for v in videos:
        if v.get("status") != "ok":
            continue
        if not str(v.get("transcript") or "").strip():
            continue
        n += 1
    return n


def count_ip_blocked_transcripts(videos: list[dict[str, Any]]) -> int:
    return sum(1 for v in videos if isinstance(v, dict) and v.get("status") == "blocked")


def count_forbidden_transcripts(videos: list[dict[str, Any]]) -> int:
    return sum(1 for v in videos if isinstance(v, dict) and v.get("status") == "forbidden")


def count_blocked_transcripts(videos: list[dict[str, Any]]) -> int:
    """Scrape IpBlocked + Data API 403."""
    return count_ip_blocked_transcripts(videos) + count_forbidden_transcripts(videos)


def build_combined_text(videos: list[dict[str, Any]]) -> str:
    return extract_transcripts_from_json({"videos": videos})


def build_session_from_api_payload(
    payload: dict[str, Any],
    *,
    source_channel_id: str = "",
) -> dict[str, Any]:
    """Normaliza la respuesta de /channels/.../transcripts.json a transcripts_session."""
    raw_videos = payload.get("videos") if isinstance(payload.get("videos"), list) else []
    videos = [normalize_video_row(v) for v in raw_videos if isinstance(v, dict)]
    channel = slim_channel(
        payload.get("channel") if isinstance(payload.get("channel"), dict) else None,
        fallback_id=source_channel_id,
    )
    valid_count = count_valid_transcripts(videos)
    combined_text = ""
    combined_chars = 0
    if valid_count > 0:
        try:
            combined_text = build_combined_text(videos)
            combined_chars = len(combined_text)
        except ValueError:
            combined_text = ""
            combined_chars = 0

    provider = str(payload.get("transcript_provider") or "auto").strip()
    ip_blocked = bool(payload.get("youtube_ip_blocked")) if provider == "scrape" else False
    out: dict[str, Any] = {
        "version": 1,
        "stored_at": _now_iso(),
        "source_channel_id": (source_channel_id or channel.get("channel_id") or "").strip(),
        "channel": channel,
        "videos": videos,
        "combined_text": combined_text,
        "valid_count": valid_count,
        "combined_chars": combined_chars,
        "analyze_status": "pending",
        "analyze_error": None,
        "analyze_completed_at": None,
        "prompt_analysis": None,
        "topic_analysis": None,
        "transcript_provider": provider,
        "youtube_ip_blocked": ip_blocked or (
            provider != "data_api" and count_ip_blocked_transcripts(videos) > 0
        ),
    }
    hint = payload.get("youtube_ip_blocked_hint")
    if isinstance(hint, str) and hint.strip():
        out["youtube_ip_blocked_hint"] = hint.strip()
    return out


def write_transcripts_session(work_dir: Path, data: dict[str, Any]) -> Path:
    p = _session_path(work_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_transcripts_session(work_dir: Path) -> dict[str, Any]:
    p = _session_path(work_dir)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def get_combined_text(work_dir: Path) -> str:
    data = read_transcripts_session(work_dir)
    return str(data.get("combined_text") or "").strip()


def session_public_view(data: dict[str, Any], *, include_combined_text: bool = False) -> dict[str, Any]:
    """Vista para API sin reenviar texto completo salvo que se pida explícitamente."""
    if not data:
        return {
            "stored": False,
            "has_file": False,
            "valid_count": 0,
            "missing_count": 0,
            "blocked_count": 0,
            "youtube_ip_blocked": False,
            "combined_chars": 0,
            "ready_to_analyze": False,
            "analyze_status": "pending",
            "analyze_error": None,
            "source_channel_id": "",
            "channel": {},
            "video_count": 0,
            "stored_at": None,
            "analyze_completed_at": None,
            "prompt_analysis": None,
            "has_prompt_analysis": False,
        }
    valid = int(data.get("valid_count") or 0)
    chars = int(data.get("combined_chars") or 0)
    status = str(data.get("analyze_status") or "pending")
    videos = data.get("videos") if isinstance(data.get("videos"), list) else []
    video_count = len(videos)
    ip_blocked_count = count_ip_blocked_transcripts(videos)
    forbidden_count = count_forbidden_transcripts(videos)
    blocked_count = ip_blocked_count + forbidden_count
    missing_count = max(0, video_count - valid - blocked_count)
    has_file = bool(data.get("stored_at"))
    stored = has_file and valid > 0 and chars > 0
    provider_stored = str(data.get("transcript_provider") or "").strip()
    if provider_stored == "data_api":
        youtube_ip_blocked = False
    elif provider_stored == "scrape":
        youtube_ip_blocked = bool(data.get("youtube_ip_blocked")) or ip_blocked_count > 0
    else:
        # Sesiones antiguas sin transcript_provider (suelen ser scrape)
        youtube_ip_blocked = bool(data.get("youtube_ip_blocked")) or ip_blocked_count > 0
    out: dict[str, Any] = {
        "stored": stored,
        "has_file": has_file,
        "valid_count": valid,
        "missing_count": missing_count,
        "blocked_count": blocked_count,
        "forbidden_count": forbidden_count,
        "transcript_provider": provider_stored or None,
        "session_needs_reload": has_file
        and valid < 1
        and (
            ip_blocked_count > 0
            or forbidden_count > 0
            or bool(data.get("youtube_ip_blocked"))
        ),
        "youtube_ip_blocked": youtube_ip_blocked,
        "youtube_ip_blocked_hint": data.get("youtube_ip_blocked_hint"),
        "combined_chars": chars,
        "ready_to_analyze": stored and status in ("pending", "error"),
        "analyze_status": status,
        "analyze_error": data.get("analyze_error"),
        "source_channel_id": data.get("source_channel_id") or "",
        "channel": data.get("channel") if isinstance(data.get("channel"), dict) else {},
        "video_count": video_count,
        "stored_at": data.get("stored_at"),
        "analyze_completed_at": data.get("analyze_completed_at"),
        "has_prompt_analysis": bool(data.get("prompt_analysis")),
        "has_topic_analysis": bool(data.get("topic_analysis")),
        "analyze_output_language": data.get("analyze_output_language") or None,
    }
    pa_raw = data.get("prompt_analysis")
    if isinstance(pa_raw, dict) and pa_raw:
        from videomaker.llm.prompt_analysis_storage import slim_prompt_analysis_payload

        slim = slim_prompt_analysis_payload(pa_raw)
        if slim:
            out["prompt_analysis"] = slim
    ta_raw = data.get("topic_analysis")
    if isinstance(ta_raw, dict) and ta_raw:
        out["topic_analysis"] = ta_raw
    if include_combined_text:
        out["combined_text"] = data.get("combined_text") or ""
    return out


def update_analyze_status(
    work_dir: Path,
    *,
    status: str,
    error: str | None = None,
    prompt_analysis: dict[str, Any] | None = None,
    topic_analysis: dict[str, Any] | None = None,
    analyze_output_language: str | None = None,
) -> dict[str, Any]:
    data = read_transcripts_session(work_dir)
    if not data:
        raise ValueError("No hay transcripts_session guardada en esta sesión.")
    data["analyze_status"] = status
    if error is not None:
        data["analyze_error"] = error or None
    if status == "completed":
        data["analyze_completed_at"] = _now_iso()
        data["analyze_error"] = None
    if prompt_analysis is not None:
        from videomaker.llm.prompt_analysis_storage import slim_prompt_analysis_payload

        if isinstance(prompt_analysis, dict):
            data["prompt_analysis"] = slim_prompt_analysis_payload(prompt_analysis)
        else:
            data["prompt_analysis"] = None
    if topic_analysis is not None:
        data["topic_analysis"] = topic_analysis
    if analyze_output_language in ("en", "es"):
        data["analyze_output_language"] = analyze_output_language
    write_transcripts_session(work_dir, data)
    return data
