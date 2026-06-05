"""Sesiones hijas de producción reutilizando topic_generator.json del padre (sin re-LLM)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from videomaker.core import config
from videomaker.pipeline.models import PIPELINE_RUN_ORDER, PIPELINE_STEPS
from videomaker.web.transcripts_session import SESSION_FILENAME


def _rel_work_path(p: Path) -> str:
    root = config.PROJECT_ROOT.resolve()
    try:
        return str(p.resolve().relative_to(root))
    except ValueError:
        return str(p)


def _now_iso() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _slugify_title(title: str, *, max_len: int = 36) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (title or "").strip().lower())
    s = s.strip("_")
    return (s[:max_len] if s else "video")


def default_child_work_slug(parent_work: str, topic_index: int, title: str) -> str:
    slug = _slugify_title(title)
    base = Path(parent_work.strip().lstrip("/"))
    if base.parts and base.parts[0] == "output":
        return str(Path("output") / f"v{topic_index + 1:02d}_{slug}")
    return str(Path("output") / f"v{topic_index + 1:02d}_{slug}")


def _steps_from_reset_step(reset_from_step: str) -> set[str]:
    if reset_from_step not in PIPELINE_RUN_ORDER:
        raise ValueError(f"reset_from_step desconocido: {reset_from_step}")
    idx = PIPELINE_RUN_ORDER.index(reset_from_step)
    return set(PIPELINE_RUN_ORDER[idx:])


def clear_downstream_production_artifacts(work_dir: Path, *, reset_from_step: str = "narrative_angle") -> None:
    """Borra artefactos de producción desde ``reset_from_step`` (conserva topic_generator)."""
    steps_to_clear = _steps_from_reset_step(reset_from_step)
    paths = work_dir / "pipeline"
    expected = {
        "narrative_angle": paths / "narrative_angle.json",
        "packaging": paths / "packaging.json",
        "prompt": paths / "prompt.json",
        "script_writer": paths / "script.txt",
        "editorial_analyzer": paths / "editorial_analysis.json",
        "subtitle_engine": paths / "subtitles_plan.json",
        "music_engine": paths / "music_plan.json",
        "voiceover_engine": paths / "voiceover_plan.json",
        "metadata": paths / "metadata.json",
        "hook_scene_router": paths / "hook_scene_router.json",
        "body_scene_router": paths / "body_scene_router.json",
        "image_prompt_writer": paths / "image_prompts.json",
        "images_generation": paths / "images_generation.json",
        "voiceovers_generation": paths / "voiceovers.json",
        "render_draft": work_dir / "draft.mp4",
    }
    for sid, p in expected.items():
        if sid in steps_to_clear and p.is_file():
            p.unlink(missing_ok=True)

    extras = [
        work_dir / "guion.txt",
        work_dir / "narracion.wav",
        paths / "scene_editor.json",
        paths / "subtitles.srt",
        paths / "audio_timeline.json",
        paths / "render_draft.json",
        paths / "render_progress.json",
        paths / "session_spawn.json",
    ]
    for p in extras:
        if p.is_file():
            p.unlink(missing_ok=True)

    for dname in ("scene_audio", "images", "render", "render_segments", "stock"):
        d = paths / dname if dname != "stock" else work_dir / dname
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)

    try:
        from videomaker.llm.script_fragmentation import chunks_dir, outline_path, reset_fragmentation_artifacts

        reset_fragmentation_artifacts(work_dir)
        o = outline_path(work_dir)
        if o.is_file():
            o.unlink(missing_ok=True)
        cd = chunks_dir(work_dir)
        if cd.is_dir():
            shutil.rmtree(cd, ignore_errors=True)
    except Exception:
        pass


def _init_child_pipeline_state(
    work_dir: Path,
    *,
    topic_title: str,
    reset_from_step: str,
) -> None:
    from videomaker.pipeline.runner import _set_step, read_pipeline_state, reset_pipeline, write_pipeline_state

    reset_pipeline(work_dir)
    reset_steps = _steps_from_reset_step(reset_from_step)

    state = read_pipeline_state(work_dir)
    for s in state.get("steps", []):
        sid = str(s.get("id") or "")
        if sid == "topic_generator":
            s["state"] = "done"
            s["detail"] = f"Tema del banco: {topic_title[:100]}"
        elif sid in reset_steps:
            s["state"] = "idle"
            s["detail"] = "Pendiente — sesión de producción nueva."
        elif sid not in reset_steps and sid != "topic_generator":
            s["state"] = "idle"
            s["detail"] = ""
    state["state"] = "idle"
    state["current_step"] = None
    state["last_error"] = None
    write_pipeline_state(work_dir, state)
    _set_step(work_dir, "narrative_angle", state="idle", detail="Listo — ejecuta Narrative Angle.")


def spawn_production_session(
    *,
    parent_work_dir: Path,
    child_work_dir: Path,
    topic_index: int,
    copy_transcripts: bool = True,
    reset_from_step: str = "narrative_angle",
    overwrite_child: bool = False,
) -> dict[str, Any]:
    """
    Crea una sesión hija con el tema ``topic_index`` del padre, sin llamar al Topic Generator LLM.
    """
    from videomaker.pipeline.runner import read_topic_generator_artifact, write_topic_generator_artifact

    parent_tg = read_topic_generator_artifact(parent_work_dir)
    topics = parent_tg.get("topics") if isinstance(parent_tg.get("topics"), list) else []
    if not topics:
        raise ValueError("El padre no tiene topic_generator.json con temas. Genera la lista primero.")
    if topic_index < 0 or topic_index >= len(topics):
        raise ValueError(f"topic_index fuera de rango (0..{len(topics) - 1}).")

    topic = topics[topic_index]
    if not isinstance(topic, dict):
        raise ValueError("Tema inválido en el banco.")

    title = str(topic.get("title") or "").strip() or f"Tema {topic_index + 1}"

    if child_work_dir.resolve() == parent_work_dir.resolve():
        raise ValueError("child_work debe ser distinto de parent_work.")

    if child_work_dir.exists() and any(child_work_dir.iterdir()) and not overwrite_child:
        manifest = child_work_dir / "pipeline_manifest.json"
        if manifest.is_file():
            raise ValueError(
                f"La carpeta {child_work_dir.name} ya tiene una pipeline. "
                "Usa otro child_work o overwrite_child=true."
            )

    child_work_dir.mkdir(parents=True, exist_ok=True)
    (child_work_dir / "pipeline").mkdir(parents=True, exist_ok=True)

    child_tg = dict(parent_tg)
    child_tg["selected_index"] = topic_index
    child_tg["topic_bank"] = {
        "parent_work": _rel_work_path(parent_work_dir),
        "topic_index": topic_index,
        "spawned_at": _now_iso(),
        "reuse_topic_artifact": True,
    }
    write_topic_generator_artifact(child_work_dir, child_tg)

    if copy_transcripts:
        src_sess = parent_work_dir / "pipeline" / SESSION_FILENAME
        if src_sess.is_file():
            shutil.copy2(src_sess, child_work_dir / "pipeline" / SESSION_FILENAME)

    clear_downstream_production_artifacts(child_work_dir, reset_from_step=reset_from_step)
    _init_child_pipeline_state(child_work_dir, topic_title=title, reset_from_step=reset_from_step)

    spawn_meta = {
        "version": 1,
        "parent_work": _rel_work_path(parent_work_dir),
        "child_work": _rel_work_path(child_work_dir),
        "topic_index": topic_index,
        "topic_title": title,
        "reset_from_step": reset_from_step,
        "spawned_at": _now_iso(),
    }
    (child_work_dir / "pipeline" / "session_spawn.json").write_text(
        json.dumps(spawn_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "parent_work": spawn_meta["parent_work"],
        "child_work": spawn_meta["child_work"],
        "topic_index": topic_index,
        "topic": topic,
        "topic_title": title,
    }


def should_skip_topic_generator_llm(work_dir: Path, *, rerun_step_id: str | None) -> bool:
    """True si la pipeline completa puede reutilizar temas ya generados."""
    if rerun_step_id == "topic_generator":
        return False
    from videomaker.pipeline.runner import read_topic_generator_artifact

    data = read_topic_generator_artifact(work_dir)
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    if not topics:
        return False
    bank = data.get("topic_bank")
    if isinstance(bank, dict) and bank.get("reuse_topic_artifact"):
        return True
    return False
