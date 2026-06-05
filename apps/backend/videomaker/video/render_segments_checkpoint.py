"""Checkpoints de planos del render (segmentos MP4 en disco para reanudar)."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CHECKPOINT_VERSION = 1
_MIN_SEGMENT_BYTES = 800


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_key(path: Path) -> str:
    try:
        st = path.stat()
        return f"{path.resolve()}:{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        return str(path.resolve())


def build_assembly_fingerprint(
    paths: list[Path],
    segment_durations_s: list[float],
    *,
    frame_size: tuple[int, int],
    ken_burns_enabled: bool,
    zoom_end: float,
    fps: int,
    engine: str,
    fast_preview: bool,
) -> str:
    parts: list[str] = [
        f"v{_CHECKPOINT_VERSION}",
        f"fs={frame_size[0]}x{frame_size[1]}",
        f"kb={int(ken_burns_enabled)}",
        f"zoom={zoom_end:.4f}",
        f"fps={fps}",
        f"engine={engine}",
        f"fast={int(fast_preview)}",
        f"n={len(paths)}",
    ]
    for p, d in zip(paths, segment_durations_s):
        parts.append(_source_key(p))
        parts.append(f"d={float(d):.4f}")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:24]


def segments_dir_for_work(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "render_segments"


def checkpoint_path_for_work(work_dir: Path) -> Path:
    return work_dir / "pipeline" / "render_segments_checkpoint.json"


def checkpoint_batch_size() -> int:
    raw = (os.environ.get("RENDER_CHECKPOINT_EVERY") or "5").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 5
    return max(1, min(n, 50))


def segment_is_usable(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return path.stat().st_size >= _MIN_SEGMENT_BYTES
    except OSError:
        return False


def load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def save_checkpoint(
    path: Path,
    *,
    fingerprint: str,
    segments_total: int,
    completed_indices: list[int],
    segments_root: Path,
    last_message: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": _CHECKPOINT_VERSION,
        "fingerprint": fingerprint,
        "segments_total": segments_total,
        "segments_root": str(segments_root),
        "completed_indices": sorted(set(completed_indices)),
        "last_completed_index": max(completed_indices) if completed_indices else -1,
        "updated_at": _now_iso(),
    }
    if last_message:
        payload["message"] = last_message[:240]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def clear_segments_dir(segments_root: Path) -> None:
    if not segments_root.is_dir():
        return
    for p in segments_root.glob("seg_*.mp4"):
        p.unlink(missing_ok=True)
    for p in segments_root.glob("video_only.mp4"):
        p.unlink(missing_ok=True)
    (segments_root / ".fingerprint").unlink(missing_ok=True)


def sync_segments_fingerprint(segments_root: Path, fingerprint: str) -> None:
    """Si cambió imágenes/duración/motor Ken Burns, borra segmentos obsoletos."""
    segments_root.mkdir(parents=True, exist_ok=True)
    marker = segments_root / ".fingerprint"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == fingerprint:
        return
    clear_segments_dir(segments_root)
    marker.write_text(fingerprint, encoding="utf-8")


def resolve_resume_indices(
    segments_root: Path,
    fingerprint: str,
    n_segments: int,
) -> set[int]:
    """Índices de planos ya en disco y válidos para reutilizar."""
    marker = segments_root / ".fingerprint"
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != fingerprint:
        return set()
    done: set[int] = set()
    for i in range(n_segments):
        seg = segments_root / f"seg_{i:04d}.mp4"
        if segment_is_usable(seg):
            done.add(i)
    return done


def cleanup_after_success(work_dir: Path, *, keep: bool = False) -> None:
    if keep:
        return
    root = segments_dir_for_work(work_dir)
    ck = checkpoint_path_for_work(work_dir)
    clear_segments_dir(root)
    ck.unlink(missing_ok=True)
    try:
        root.rmdir()
    except OSError:
        pass
