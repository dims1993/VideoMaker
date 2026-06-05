"""Rutas de trabajo, estado en disco y helpers de sesión (compartido por HTML y API)."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from videomaker.core import config
from videomaker.core.models import Locale
from videomaker.tts.voice_gen import VOICE_PRESETS, get_voice_preset

_status_lock = threading.Lock()

TTS_REFERENCE_FILE = ".videomaker_tts_reference.json"
NARRATION_MANIFEST_FILE = ".videomaker_narration.json"


def read_tts_reference(work_dir: Path) -> dict:
    """Preferencia para narración: auto | clone | builtin | preview (archivo preview_voice*.wav)."""
    default: dict = {"mode": "auto", "preview_filename": None}
    p = work_dir / TTS_REFERENCE_FILE
    if not p.is_file():
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        mode = data.get("mode", "auto")
        if mode not in ("auto", "clone", "builtin", "preview"):
            mode = "auto"
        fn = data.get("preview_filename") or data.get("filename")
        if mode == "preview" and fn:
            safe = Path(fn).name
            if not (work_dir / safe).is_file():
                return default
            fn = safe
        else:
            fn = None
        return {"mode": mode, "preview_filename": fn}
    except Exception:
        return default


def write_tts_reference(work_dir: Path, mode: str, preview_filename: str | None = None) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    payload = {"mode": mode, "preview_filename": preview_filename}
    (work_dir / TTS_REFERENCE_FILE).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def safe_preview_voice_name(name: str) -> str | None:
    """Solo `preview_voice*.wav` en la carpeta (anti path traversal)."""
    safe = Path(name).name
    if not safe.startswith("preview_voice") or not safe.endswith(".wav"):
        return None
    return safe


def safe_work_dir(rel: str) -> Path:
    root = config.PROJECT_ROOT.resolve()
    p = (root / rel.strip().lstrip("/")).resolve()
    if not p.is_relative_to(root):
        raise ValueError("La carpeta de trabajo debe estar dentro del proyecto.")
    return p


def parse_locale(s: str) -> Locale:
    s = (s or "es").lower().strip()
    if s in ("es", "spa", "spanish"):
        return Locale.ES
    return Locale.EN


def voice_profile_for_work(work_dir: Path, preset: str):
    """Perfil Coqui/XTTS según preferencia guardada y archivos presentes."""
    profile = get_voice_preset(preset)
    ref = read_tts_reference(work_dir)
    mode = ref.get("mode") or "auto"
    clone = work_dir / "clone_reference.wav"
    has_clone = clone.is_file()

    if mode == "builtin":
        return replace(profile, speaker_wav=None, auto_clone_from_samples=False)

    if mode == "clone":
        if has_clone:
            return replace(profile, speaker_wav=clone, auto_clone_from_samples=False)
        return replace(profile, speaker_wav=None, auto_clone_from_samples=False)

    if mode == "preview":
        fn = ref.get("preview_filename")
        if fn:
            p = work_dir / Path(fn).name
            if p.is_file():
                return replace(profile, speaker_wav=p, auto_clone_from_samples=False)
        if has_clone:
            return replace(profile, speaker_wav=clone, auto_clone_from_samples=False)
        return replace(profile, speaker_wav=None, auto_clone_from_samples=False)

    # auto: clon subido tiene prioridad
    if has_clone:
        return replace(profile, speaker_wav=clone, auto_clone_from_samples=False)
    return profile


def status_paths(work_dir: Path) -> tuple[Path, Path]:
    return (work_dir / ".videomaker_status.json", work_dir / ".videomaker_log.txt")


def set_status(work_dir: Path, *, state: str, step: str, detail: str = "") -> None:
    status_path, log_path = status_paths(work_dir)
    payload = {
        "state": state,
        "step": step,
        "detail": detail,
        "updated_at": time.time(),
    }
    with _status_lock:
        status_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        if detail:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {step}: {detail}\n")


def read_status(work_dir: Path) -> dict:
    status_path, log_path = status_paths(work_dir)
    status = {"state": "idle", "step": "", "detail": "", "updated_at": None}
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    log_tail = ""
    if log_path.is_file():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            log_tail = "\n".join(lines[-40:])
        except Exception:
            log_tail = ""
    return {"status": status, "log_tail": log_tail}


def read_narration_manifest(work_dir: Path) -> dict:
    p = work_dir / NARRATION_MANIFEST_FILE
    if not p.is_file():
        return {"active": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        active = data.get("active")
        if isinstance(active, str) and active.strip():
            return {"active": Path(active).name}
        return {"active": None}
    except Exception:
        return {"active": None}


def write_narration_manifest(work_dir: Path, active: str | None) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    payload = {"active": active}
    (work_dir / NARRATION_MANIFEST_FILE).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def safe_narration_archive_name(name: str) -> str | None:
    """Solo archivos `narracion_*.wav` en la carpeta de trabajo (anti path traversal)."""
    safe = Path(name).name
    if not safe.startswith("narracion_") or not safe.endswith(".wav"):
        return None
    return safe


def list_narration_archives(work_dir: Path) -> list[Path]:
    return list(work_dir.glob("narracion_*.wav"))


def migrate_legacy_narration(work_dir: Path) -> None:
    """Primera vez con solo narracion.wav: archivar como narracion_*_legacy.wav."""
    if (work_dir / NARRATION_MANIFEST_FILE).is_file():
        return
    wav = work_dir / "narracion.wav"
    if not wav.is_file():
        return
    if list_narration_archives(work_dir):
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    arch = work_dir / f"narracion_{ts}_legacy.wav"
    shutil.copy2(wav, arch)
    write_narration_manifest(work_dir, arch.name)


def reconcile_narration_active(work_dir: Path) -> None:
    """Si la entrada activa ya no existe, elige otra copia o borra narracion.wav."""
    man = read_narration_manifest(work_dir)
    active = man.get("active")
    archives = sorted(list_narration_archives(work_dir), key=lambda p: p.stat().st_mtime, reverse=True)
    names = {p.name for p in archives}
    if active and active in names:
        return
    if archives:
        chosen = archives[0]
        shutil.copy2(chosen, work_dir / "narracion.wav")
        write_narration_manifest(work_dir, chosen.name)
        return
    (work_dir / "narracion.wav").unlink(missing_ok=True)
    write_narration_manifest(work_dir, None)


def ensure_narration_consistency(work_dir: Path) -> None:
    migrate_legacy_narration(work_dir)
    man = read_narration_manifest(work_dir)
    active = man.get("active")
    names = {p.name for p in list_narration_archives(work_dir)}
    if active and active not in names:
        reconcile_narration_active(work_dir)


def finalize_new_narration(work_dir: Path) -> None:
    """Tras generar narracion.wav: guardar copia en historial y marcarla como activa."""
    wav = work_dir / "narracion.wav"
    if not wav.is_file():
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    arch = work_dir / f"narracion_{ts}.wav"
    n = 0
    while arch.is_file():
        n += 1
        arch = work_dir / f"narracion_{ts}_{n}.wav"
    shutil.copy2(wav, arch)
    write_narration_manifest(work_dir, arch.name)


def select_narration_archive(work_dir: Path, archive_name: str) -> None:
    safe = safe_narration_archive_name(archive_name)
    if not safe:
        raise ValueError("Nombre de narración no válido (usa narracion_*.wav).")
    src = work_dir / safe
    if not src.is_file():
        raise FileNotFoundError(str(safe))
    shutil.copy2(src, work_dir / "narracion.wav")
    write_narration_manifest(work_dir, safe)


def delete_narration_archive(work_dir: Path, archive_name: str) -> None:
    safe = safe_narration_archive_name(archive_name)
    if not safe:
        raise ValueError("Nombre de narración no válido.")
    p = work_dir / safe
    if not p.is_file():
        raise FileNotFoundError(str(safe))
    p.unlink()
    reconcile_narration_active(work_dir)


def build_session_state(work: str) -> dict:
    work_dir = safe_work_dir(work)
    work_dir.mkdir(parents=True, exist_ok=True)
    ensure_narration_consistency(work_dir)
    script_path = work_dir / "guion.txt"
    narration_path = work_dir / "narracion.wav"
    clone_ref = work_dir / "clone_reference.wav"
    draft_path = work_dir / "draft.mp4"
    preview_files = sorted(work_dir.glob("preview_voice*.wav"))
    status_bundle = read_status(work_dir)
    manifest = read_narration_manifest(work_dir)
    active_name = manifest.get("active")
    narr_mtime = int(narration_path.stat().st_mtime) if narration_path.is_file() else 0
    draft_mtime = int(draft_path.stat().st_mtime) if draft_path.is_file() else 0
    imgs_dir = work_dir / "pipeline" / "images"
    _img_exts = {".png", ".jpg", ".jpeg", ".webp"}
    pipeline_images_count = (
        sum(1 for p in imgs_dir.iterdir() if p.is_file() and p.suffix.lower() in _img_exts)
        if imgs_dir.is_dir()
        else 0
    )
    arch_sorted = sorted(
        list_narration_archives(work_dir),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    narration_versions = []
    for p in arch_sorted:
        try:
            m = int(p.stat().st_mtime)
        except OSError:
            m = 0
        narration_versions.append(
            {
                "name": p.name,
                "url": f"/work-file?work={work}&name={p.name}&v={m}",
                "active": bool(active_name and p.name == active_name),
            }
        )
    env = {
        "VIDEOMAKER_LLM_PROVIDER": os.environ.get("VIDEOMAKER_LLM_PROVIDER", ""),
        "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL", ""),
        "OPENAI_MODEL": os.environ.get("OPENAI_MODEL", ""),
        "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL", ""),
        "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", ""),
        "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY")),
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
    }
    transcripts_session: dict = {}
    try:
        from videomaker.web.transcripts_session import read_transcripts_session, session_public_view

        transcripts_session = session_public_view(read_transcripts_session(work_dir))
    except Exception:
        transcripts_session = {}

    return {
        "work": work,
        "work_dir": str(work_dir),
        "transcripts_session": transcripts_session,
        "voice_presets": sorted(VOICE_PRESETS.keys()),
        "has_script": script_path.is_file(),
        "script_path": str(script_path),
        "has_narration": narration_path.is_file(),
        "narration_path": str(narration_path),
        "active_narration": active_name,
        "narration_versions": narration_versions,
        "narration_url": f"/work-file?work={work}&name=narracion.wav&v={narr_mtime}",
        "has_clone_reference": clone_ref.is_file(),
        "clone_reference_url": f"/work-file?work={work}&name=clone_reference.wav",
        "pipeline_images_count": pipeline_images_count,
        "draft_exists": draft_path.is_file(),
        "draft_path": str(draft_path),
        "env": env,
        "status": status_bundle["status"],
        "log_tail": status_bundle["log_tail"],
        "voice_previews": [
            {"name": p.name, "url": f"/work-file?work={work}&name={p.name}"}
            for p in preview_files
        ],
        "tts_reference": read_tts_reference(work_dir),
        "urls": {
            "narration": f"/work-file?work={work}&name=narracion.wav&v={narr_mtime}",
            "clone_reference": f"/work-file?work={work}&name=clone_reference.wav",
            "draft": (
                f"/work-file?work={work}&name=draft.mp4&v={draft_mtime}"
                if draft_path.is_file()
                else ""
            ),
        },
    }
