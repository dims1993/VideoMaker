"""Runner de pipeline: estado en disco + ejecución por pasos.

Persistencia por sesión en `work_dir/pipeline_manifest.json` y artefactos en `work_dir/pipeline/`.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import os
import re
from pathlib import Path
from typing import Any, cast

from videomaker.core.models import ScriptBlueprint
from videomaker.core.script_bundle import write_script_bundle
from videomaker.llm.prompt_templates_store import get_prompt_template
from videomaker.llm.script_fragmentation import (
    FragmentLLMAddon,
    assemble_guion,
    build_fragment_user_addon,
    chunk_file,
    chunks_dir,
    default_fragment_index_to_generate,
    ensure_state_matches_template,
    extract_outline_and_script_body,
    fragment_plan,
    minutes_for_sequential_fragment,
    normalize_structure_preset,
    normalized_minute_weights,
    outline_path,
    reset_fragmentation_artifacts,
    save_state,
    set_step_status,
    strip_fin_marker,
)
from videomaker.llm.script_writer_templates_store import (
    chunk_outline_act1_only,
    effective_chunk_target_minutes,
    extras_from_template_row,
    get_script_writer_template,
    sequential_fragments_enabled,
)
from videomaker.audio.narration import build_narration_wav
from videomaker.llm.script_gen import generate_script, segment_word_target
from videomaker.web.io_util import parse_locale, set_status, voice_profile_for_work

from .models import (
    PIPELINE_RUN_ORDER,
    PIPELINE_STEPS,
    PipelineInputs,
    PipelineState,
    PipelineStatus,
)

_LOCK = threading.Lock()
_LOG = logging.getLogger(__name__)
# _set_pipeline_state: distingue «no actualizar last_error» de «borrar last_error» (None).
_PIPELINE_LAST_ERROR_OMIT = object()


def _manifest_path(work_dir: Path) -> Path:
    return work_dir / "pipeline_manifest.json"

def _stop_flag_path(work_dir: Path) -> Path:
    return work_dir / "pipeline_stop.flag"


def request_pipeline_stop(work_dir: Path) -> None:
    """Best-effort cooperative stop request for the running pipeline."""
    work_dir.mkdir(parents=True, exist_ok=True)
    _stop_flag_path(work_dir).write_text("stop", encoding="utf-8")


def clear_pipeline_stop(work_dir: Path) -> None:
    try:
        _stop_flag_path(work_dir).unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass


def reset_pipeline(work_dir: Path) -> None:
    """Reset manifest and stop flag; keeps inputs/assets untouched."""
    clear_pipeline_stop(work_dir)
    write_pipeline_state(work_dir, _default_state())
    set_status(work_dir, state="idle", step="pipeline", detail="Pipeline reiniciada.")

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_state() -> PipelineState:
    steps = [
        {"id": sid, "title": title, "state": "idle", "detail": "", "updated_at": ""}
        for sid, title in PIPELINE_STEPS
    ]
    return {
        "state": "idle",
        "current_step": None,
        "steps": steps,
        "last_error": None,
        "updated_at": _now_iso(),
    }


def _expected_artifact_paths(work_dir: Path) -> dict[str, Path]:
    d = work_dir / "pipeline"
    return {
        "topic_generator": d / "topic_generator.json",
        "narrative_angle": d / "narrative_angle.json",
        "packaging": d / "packaging.json",
        "prompt": d / "prompt.json",
        "script_writer": d / "script.txt",
        "editorial_analyzer": d / "editorial_analysis.json",
        "narrative_pacing_pass": d / "script.txt",
        "subtitle_engine": d / "subtitles_plan.json",
        "music_engine": d / "music_plan.json",
        "voiceover_engine": d / "voiceover_plan.json",
        "metadata": d / "metadata.json",
        "hook_scene_router": d / "hook_scene_router.json",
        "body_scene_router": d / "body_scene_router.json",
        "image_prompt_writer": d / "image_prompts.json",
        "images_generation": d / "images_generation.json",
        "voiceovers_generation": d / "voiceovers.json",
        "render_draft": work_dir / "draft.mp4",
    }


def _step_artifact_satisfied(work_dir: Path, step_id: str) -> bool:
    """Comprueba si hay salida real del paso (incluye rutas alternativas del flujo actual)."""
    primary = _expected_artifact_paths(work_dir).get(step_id)
    if primary is not None and primary.is_file():
        if step_id == "script_writer":
            return (work_dir / "guion.txt").is_file() or primary.is_file()
        return True

    d = work_dir / "pipeline"
    if step_id == "script_writer":
        return (work_dir / "guion.txt").is_file() or (d / "script.txt").is_file()
    if step_id == "narrative_pacing_pass":
        return (work_dir / "guion.txt").is_file() or (d / "script.txt").is_file()
    if step_id == "voiceovers_generation":
        if (work_dir / "narracion.wav").is_file():
            return True
        if (d / "scene_editor.json").is_file():
            return True
        scene_audio = work_dir / "scene_audio"
        if scene_audio.is_dir() and any(scene_audio.glob("*.mp3")):
            return True
        return (d / "voiceovers.json").is_file()
    if step_id == "images_generation":
        if (d / "images_generation.json").is_file():
            return True
        images = d / "images"
        return images.is_dir() and any(images.glob("*.png"))
    if step_id == "render_draft":
        if (work_dir / "draft.mp4").is_file():
            return True
        meta = d / "render_draft.json"
        return meta.is_file() and meta.stat().st_size > 32
    return False


def _parse_iso_timestamp(iso: str) -> float | None:
    if not iso or not str(iso).strip():
        return None
    try:
        from datetime import datetime

        s = str(iso).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def _render_draft_completed_after_step_start(work_dir: Path, step: dict[str, Any]) -> bool:
    """True si draft.mp4 / render_draft.json se escribieron tras iniciar este paso."""
    started_ts = _parse_iso_timestamp(str(step.get("updated_at") or ""))
    if started_ts is None:
        return False
    meta_p = work_dir / "pipeline" / "render_draft.json"
    if meta_p.is_file():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            done_ts = _parse_iso_timestamp(str(meta.get("completed_at") or ""))
            if done_ts is not None and done_ts + 1.0 >= started_ts:
                return True
        except Exception:
            pass
    draft_p = work_dir / "draft.mp4"
    if draft_p.is_file():
        return draft_p.stat().st_mtime + 1.0 >= started_ts
    return False


_RENDER_PROGRESS_ACTIVE_SEC = 180  # sin actualizar progreso → render muerto (eased ~15–20 s/plano)
_RENDER_PROGRESS_STALE_SEC = 1800  # tope duro si no hay render_progress.json
_RENDER_DRAFT_MAX_RUNNING_SEC = 6 * 3600  # tope duro (92 planos ~1–2 h)


def _render_progress_last_update_ts(work_dir: Path) -> float | None:
    p = work_dir / "pipeline" / "render_progress.json"
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return _parse_iso_timestamp(str(raw.get("updated_at") or ""))
    except Exception:
        pass
    return None


def _render_progress_is_recent(
    work_dir: Path, *, max_age_sec: float = _RENDER_PROGRESS_ACTIVE_SEC
) -> bool:
    """True si el render sigue reportando progreso (evita falso «interrumpido»)."""
    ts = _render_progress_last_update_ts(work_dir)
    if ts is None:
        return False
    return (time.time() - ts) <= max_age_sec


def _recover_render_draft_active_progress(work_dir: Path, st: PipelineState) -> None:
    """Si el paso quedó en error pero el progreso en disco sigue avanzando, vuelve a running."""
    if not _render_progress_is_recent(work_dir):
        return
    for s in st.get("steps", []):
        if s.get("id") != "render_draft":
            continue
        if s.get("state") not in ("error", "idle"):
            continue
        prog_ts = _render_progress_last_update_ts(work_dir)
        started_ts = _parse_iso_timestamp(str(s.get("updated_at") or ""))
        if prog_ts is not None and started_ts is not None and prog_ts + 2.0 < started_ts:
            return
        s["state"] = "running"
        s["detail"] = "Render en curso (progreso detectado en disco)."
        s["updated_at"] = _now_iso()
        st["state"] = "running"
        st["current_step"] = "render_draft"
        st["last_error"] = None


def _heal_stuck_running_steps(work_dir: Path, st: PipelineState) -> None:
    """Recupera «running» huérfanos: render ya terminó o el proceso murió hace rato."""
    _recover_render_draft_active_progress(work_dir, st)
    now = time.time()
    for s in st.get("steps", []):
        if s.get("state") != "running":
            continue
        sid = str(s.get("id") or "")
        started_ts = _parse_iso_timestamp(str(s.get("updated_at") or ""))

        if sid == "render_draft" and _render_draft_completed_after_step_start(work_dir, s):
            s["state"] = "done"
            s["detail"] = "Completado (estado recuperado tras el render)."
            s["updated_at"] = _now_iso()
            set_status(
                work_dir,
                state="done",
                step="pipeline",
                detail="Render draft listo (draft.mp4).",
            )
            continue

        if sid != "render_draft":
            continue

        if _render_progress_is_recent(work_dir):
            continue
        prog_ts = _render_progress_last_update_ts(work_dir)
        stale_ref = prog_ts if prog_ts is not None else started_ts
        stale_limit = (
            _RENDER_PROGRESS_STALE_SEC if prog_ts is None else _RENDER_PROGRESS_ACTIVE_SEC
        )
        if stale_ref is None or (now - stale_ref) < stale_limit:
            continue

        msg = (
            "Render detenido o sin progreso reciente (~3 min). "
            "Pulsa «Start step» para reanudar (se reutilizan planos en disco si existen). "
            "Comprueba que draft.mp4 no se haya actualizado antes de repetir."
        )
        s["state"] = "error"
        s["detail"] = msg
        s["updated_at"] = _now_iso()
        st["state"] = "error"
        st["current_step"] = None
        st["last_error"] = msg
        set_status(work_dir, state="error", step="pipeline", detail=msg)


def _reconcile_state_with_artifacts(work_dir: Path, st: PipelineState) -> PipelineState:
    """
    Ensure "done" reflects reality. If a step is marked done but its expected artifact
    doesn't exist, downgrade it to idle.
    """
    _heal_stuck_running_steps(work_dir, st)
    any_done = False
    any_running = False
    any_error = False

    for s in st.get("steps", []):
        sid = s.get("id") or ""
        state = s.get("state") or "idle"
        if state == "running":
            any_running = True
        if state == "error":
            any_error = True
        if state == "done":
            if not _step_artifact_satisfied(work_dir, sid):
                s["state"] = "idle"
                s["detail"] = "Pending."
                s["updated_at"] = s.get("updated_at") or ""
            else:
                any_done = True

    # Global pipeline state
    if any_running:
        st["state"] = "running"
    elif any_error:
        st["state"] = "error"
    elif any_done:
        st["state"] = "done"
    else:
        st["state"] = "idle"

    if st.get("state") != "running":
        st["current_step"] = None
    return st


def read_pipeline_state(work_dir: Path) -> PipelineState:
    p = _manifest_path(work_dir)
    if not p.is_file():
        return _default_state()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("steps"), list):
            raw = _merge_pipeline_step_defs(raw)
            before = json.dumps(raw.get("steps", []), sort_keys=True) + str(raw.get("state"))
            healed = _reconcile_state_with_artifacts(work_dir, raw)  # type: ignore[arg-type]
            after = json.dumps(healed.get("steps", []), sort_keys=True) + str(healed.get("state"))
            if after != before:
                write_pipeline_state(work_dir, healed)
            return healed  # type: ignore[return-value]
    except Exception:
        pass
    return _default_state()


def _merge_pipeline_step_defs(raw: dict[str, Any]) -> dict[str, Any]:
    """Añade pasos nuevos de PIPELINE_STEPS sin perder estado de los existentes (migración suave)."""
    old = [s for s in raw.get("steps", []) if isinstance(s, dict) and s.get("id")]
    by_id = {str(s["id"]): s for s in old}
    merged: list[dict[str, Any]] = []
    for sid, title in PIPELINE_STEPS:
        prev = by_id.get(sid)
        if prev:
            if prev.get("title") != title:
                prev = {**prev, "title": title}
            merged.append(prev)
        else:
            merged.append({"id": sid, "title": title, "state": "idle", "detail": "", "updated_at": ""})
    raw["steps"] = merged
    return raw


def write_pipeline_state(work_dir: Path, state: PipelineState) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now_iso()
    _manifest_path(work_dir).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_step(work_dir: Path, step_id: str, *, state: PipelineStatus, detail: str = "") -> PipelineState:
    st = read_pipeline_state(work_dir)
    for s in st.get("steps", []):
        if s.get("id") == step_id:
            s["state"] = state
            s["detail"] = detail
            s["updated_at"] = _now_iso()
            break
    if state == "running":
        st["current_step"] = step_id
    elif state in ("done", "idle") and st.get("current_step") == step_id:
        st["current_step"] = None
    if state == "error":
        st["state"] = "error"
        st["last_error"] = detail
    write_pipeline_state(work_dir, st)
    return st


def _sync_global_state_from_steps(st: PipelineState) -> None:
    """Estado global coherente con los pasos (evita marcar toda la pipeline «done» tras un solo Start step)."""
    any_running = any((s.get("state") or "") == "running" for s in st.get("steps", []))
    any_error = any((s.get("state") or "") == "error" for s in st.get("steps", []))
    any_done = any((s.get("state") or "") == "done" for s in st.get("steps", []))
    if any_running:
        st["state"] = "running"
        for s in st.get("steps", []):
            if s.get("state") == "running":
                st["current_step"] = s.get("id")
                break
    elif any_error:
        st["state"] = "error"
        st["current_step"] = None
    elif any_done:
        st["state"] = "done"
        st["current_step"] = None
    else:
        st["state"] = "idle"
        st["current_step"] = None


def _set_pipeline_state(
    work_dir: Path,
    *,
    state: PipelineStatus,
    current_step: str | None = None,
    last_error: str | None | object = _PIPELINE_LAST_ERROR_OMIT,
) -> None:
    st = read_pipeline_state(work_dir)
    st["state"] = state
    st["current_step"] = current_step
    if last_error is not _PIPELINE_LAST_ERROR_OMIT:
        st["last_error"] = last_error  # None borra el mensaje rojo en la UI tras un rerun OK
    write_pipeline_state(work_dir, st)


def _pipeline_dir(work_dir: Path) -> Path:
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_script_text(work_dir: Path, script_path: Path | None) -> str:
    """Texto del guion para pasos posteriores al Script Writer (rerun solo metadata, etc.)."""
    text, _src, _ok = _resolve_script_for_metadata(work_dir, script_path)
    return text


def _resolve_script_for_metadata(
    work_dir: Path, script_path: Path | None
) -> tuple[str, str, bool]:
    """(texto, ruta_relativa_origen, existe_con_contenido)."""
    if script_path is not None and script_path.is_file():
        t = script_path.read_text(encoding="utf-8")
        if t.strip():
            rel = script_path.name
            if script_path.parent.name == "pipeline":
                rel = f"pipeline/{rel}"
            return t, rel, True
    guion = work_dir / "guion.txt"
    if guion.is_file():
        t = guion.read_text(encoding="utf-8")
        if t.strip():
            return t, "guion.txt", True
    pipe = work_dir / "pipeline" / "script.txt"
    if pipe.is_file():
        t = pipe.read_text(encoding="utf-8")
        if t.strip():
            return t, "pipeline/script.txt", True
    return "", "none", False


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_prompt_artifact(work_dir: Path) -> dict[str, Any]:
    p = work_dir / "pipeline" / "prompt.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _pipeline_inputs_with_resolved_lang(work_dir: Path, inputs: PipelineInputs) -> PipelineInputs:
    """Aplica idioma canónico del Topic Generator a la sesión de pipeline."""
    from videomaker.llm.output_language import resolve_pipeline_lang

    lang = resolve_pipeline_lang(work_dir, request_lang=inputs.lang)
    if lang == inputs.lang:
        return inputs
    return PipelineInputs(
        keywords=inputs.keywords,
        context=inputs.context,
        lang=lang,
        minutes=inputs.minutes,
        provider=inputs.provider,
        model=inputs.model,
        voice_preset=inputs.voice_preset,
        prompt_template_id=inputs.prompt_template_id,
        prompt_topic=inputs.prompt_topic,
        prompt_video_restrictions=inputs.prompt_video_restrictions,
        script_writer_template_id=inputs.script_writer_template_id,
        script_fragment_index=inputs.script_fragment_index,
        render_no_music=inputs.render_no_music,
        topic_generator_transcript=inputs.topic_generator_transcript,
        topic_generator_niche_trends=inputs.topic_generator_niche_trends,
        topic_generator_topic_count=inputs.topic_generator_topic_count,
    )


def _sync_prompt_json_lang(work_dir: Path, lang: str) -> None:
    """Mantiene ``prompt.json`` alineado con el idioma canónico (mejor rehidratación)."""
    p = _pipeline_dir(work_dir) / "prompt.json"
    if not p.is_file():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(raw, dict):
        return
    if str(raw.get("lang") or "").strip().lower() == lang:
        return
    raw["lang"] = lang
    _write_json(p, raw)


def set_topic_generator_output_language(work_dir: Path, lang: str) -> dict[str, Any]:
    """Persiste «Idioma de salida» antes o después de generar temas."""
    from videomaker.llm.output_language import normalize_language_code

    code = normalize_language_code(lang)
    if code not in ("en", "es"):
        raise ValueError("output_language debe ser 'en' o 'es'")
    data = read_topic_generator_artifact(work_dir) or {}
    data["output_language"] = code
    write_topic_generator_artifact(work_dir, data)
    _sync_prompt_json_lang(work_dir, code)
    return data


def _merged_inputs_for_script(work_dir: Path, inputs: PipelineInputs) -> PipelineInputs:
    """Combina la petición actual con `prompt.json` (paso Prompt previo) cuando hay huecos."""
    inputs = _pipeline_inputs_with_resolved_lang(work_dir, inputs)
    art = _load_prompt_artifact(work_dir)
    kw = (inputs.keywords or "").strip() or str(art.get("keywords") or "")
    ctx = (inputs.context or "").strip() or str(art.get("context") or "")
    lang = inputs.lang
    from videomaker.pipeline.duration_policy import clamp_pipeline_minutes

    try:
        minutes = float(inputs.minutes)
    except (TypeError, ValueError):
        minutes = 10.0
    if minutes <= 0:
        try:
            minutes = float(art.get("minutes") or 10.0)
        except (TypeError, ValueError):
            minutes = 10.0
    minutes = clamp_pipeline_minutes(minutes)
    provider = (inputs.provider or "").strip() or str(art.get("provider") or "")
    model = (inputs.model or "").strip() or str(art.get("model") or "")
    tid = (inputs.prompt_template_id or "").strip() or None
    if not tid:
        cat = art.get("catalog")
        if isinstance(cat, dict):
            tid = str(cat.get("prompt_template_id") or "").strip() or None
    topic = (inputs.prompt_topic or "").strip() or str(art.get("topic") or "")
    video_restrictions = (inputs.prompt_video_restrictions or "").strip() or str(
        art.get("video_restrictions") or ""
    ).strip()
    sw_tid = (inputs.script_writer_template_id or "").strip()
    if not sw_tid:
        cat = art.get("catalog")
        if isinstance(cat, dict):
            sw_tid = str(cat.get("script_writer_template_id") or "").strip()
    sw_tid = sw_tid or None
    return PipelineInputs(
        keywords=kw,
        context=ctx,
        lang=lang,
        minutes=minutes,
        provider=provider,
        model=model,
        voice_preset=inputs.voice_preset,
        prompt_template_id=tid,
        prompt_topic=topic,
        prompt_video_restrictions=video_restrictions,
        script_writer_template_id=sw_tid,
        script_fragment_index=inputs.script_fragment_index,
        render_no_music=inputs.render_no_music,
    )


def _prompt_template_params_user_addon(row: dict[str, Any]) -> str:
    """Añade a user_extra lo guardado en params_json de la plantilla Prompt."""
    pj = row.get("params_json") or {}
    if not isinstance(pj, dict):
        pj = {}
    parts: list[str] = []
    ta = str(pj.get("target_audience") or "").strip()
    if ta:
        parts.append(f"Público objetivo (plantilla Prompt):\n{ta}")
    ns = pj.get("narrative_structure")
    if isinstance(ns, dict):
        ht = str(ns.get("hook_type") or "").strip()
        if ht:
            parts.append(f"Hook type inferido del canal (transcripciones):\n{ht}")
        nt = str(ns.get("tone") or "").strip()
        if nt:
            parts.append(f"Tono narrativo inferido (transcripciones):\n{nt}")
        cta = str(ns.get("cta_type") or "").strip()
        if cta:
            parts.append(f"Tipo de CTA inferido (transcripciones):\n{cta}")
    return "\n\n".join(parts).strip()


def _script_writer_catalog_addon(row: dict[str, Any]) -> str:
    """Mínimo desde catálogo Prompt — sin hook/CTA/audiencia (edición)."""
    pj = row.get("params_json") or {}
    if not isinstance(pj, dict):
        return ""
    ns = pj.get("narrative_structure")
    if isinstance(ns, dict):
        nt = str(ns.get("tone") or "").strip()
        if nt:
            return f"Tono canal: {nt}"
    return ""


def _template_extras_from_catalog(work_dir: Path, merged: PipelineInputs) -> tuple[str, str]:
    """Instrucciones del template del catálogo para `generate_script` (system_extra / user_extra)."""
    tid = (merged.prompt_template_id or "").strip()
    if not tid:
        return "", ""
    try:
        row = get_prompt_template(tid)
    except Exception:
        return "", ""
    if not row:
        return "", ""
    from videomaker.llm.prompt_instruction_contract import merged_user_instructions_for_pipeline

    from videomaker.llm.script_writer_voice import prepare_script_writer_system_prompt

    sys_e = prepare_script_writer_system_prompt(str(row.get("system_instructions") or "").strip())
    tema = (merged.prompt_topic or "").strip() or (merged.keywords or "").strip()
    angulo_eff = (merged.context or "").strip()
    na_ctx = _narrative_angle_context_text(read_narrative_angle_artifact(work_dir))
    if na_ctx:
        angulo_eff = (angulo_eff + "\n\n" if angulo_eff else "") + na_ctx
    pkg_ctx = _packaging_context_text(work_dir)
    if pkg_ctx:
        angulo_eff = (angulo_eff + "\n\n" if angulo_eff else "") + pkg_ctx
    usr_e = merged_user_instructions_for_pipeline(
        row,
        language_code=(merged.lang or "").strip(),
        duration_minutes=float(merged.minutes or 10),
        tema=tema,
        angulo=angulo_eff,
        restricciones=str(merged.prompt_video_restrictions or "").strip(),
        fuentes="",
    )
    addon = _script_writer_catalog_addon(row)
    if addon:
        usr_e = (usr_e + "\n\n" if usr_e else "") + addon
    return sys_e, usr_e.strip()


def _script_writer_template_extras(merged: PipelineInputs) -> tuple[str, str, dict[str, Any] | None]:
    """Overlay del Script Writer + fila de catálogo (para chunking / overrides)."""
    sw = (merged.script_writer_template_id or "").strip()
    if not sw:
        return "", "", None
    try:
        row = get_script_writer_template(sw)
    except Exception:
        return "", "", None
    if not row:
        return "", "", None
    sys_e, usr_e = extras_from_template_row(row, merged.lang or "")
    return sys_e, usr_e, row


def _persist_script_writer_template_to_prompt_artifact(work_dir: Path, template_id: str | None) -> None:
    """Guarda `script_writer_template_id` en `pipeline/prompt.json` → catalog (rehidratación UI)."""
    p = work_dir / "pipeline" / "prompt.json"
    raw: dict[str, Any]
    if p.is_file():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
            raw = loaded if isinstance(loaded, dict) else {}
        except Exception:
            raw = {}
    else:
        raw = {}
    cat = raw.get("catalog")
    if not isinstance(cat, dict):
        cat = {}
        raw["catalog"] = cat
    tid = (template_id or "").strip()
    if tid:
        cat["script_writer_template_id"] = tid
        try:
            row = get_script_writer_template(tid)
            if row:
                cat["script_writer_template_name"] = row.get("name")
        except Exception:
            cat["script_writer_template_resolution"] = "lookup_failed"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def read_topic_generator_artifact(work_dir: Path) -> dict[str, Any]:
    p = _pipeline_dir(work_dir) / "topic_generator.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def write_topic_generator_artifact(work_dir: Path, data: dict[str, Any]) -> None:
    _write_json(_pipeline_dir(work_dir) / "topic_generator.json", data)


def read_narrative_angle_artifact(work_dir: Path) -> dict[str, Any]:
    p = _pipeline_dir(work_dir) / "narrative_angle.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_narrative_angle_artifact(work_dir: Path, data: dict[str, Any]) -> None:
    _write_json(_pipeline_dir(work_dir) / "narrative_angle.json", data)


def confirm_narrative_angle_bundle(work_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Valida, guarda y marca Narrative Angle como confirmado (sin re-ejecutar el LLM)."""
    if not isinstance(data, dict):
        raise ValueError("narrative_angle debe ser un objeto JSON")
    from videomaker.llm.narrative_angle_builder import normalize_narrative_angle

    norm = normalize_narrative_angle(data)
    if not any(
        norm.get(k)
        for k in ("core_tension", "central_question", "main_mechanism", "narrative_promise")
    ):
        raise ValueError(
            "El JSON no tiene ángulo narrativo (falta tensión, pregunta, mecanismo o promesa)."
        )
    out = {**data, **norm, "confirmed": True, "confirmed_at": _now_iso()}
    write_narrative_angle_artifact(work_dir, out)

    prompt_path = _pipeline_dir(work_dir) / "prompt.json"
    if prompt_path.is_file():
        try:
            payload = json.loads(prompt_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                _attach_narrative_angle_to_prompt_payload(work_dir, payload)
                _write_json(prompt_path, payload)
        except (OSError, json.JSONDecodeError):
            pass

    _set_step(work_dir, "narrative_angle", state="done", detail="Ángulo confirmado (bloqueado).")
    st = read_pipeline_state(work_dir)
    _sync_global_state_from_steps(st)
    st["last_error"] = None
    write_pipeline_state(work_dir, st)
    return out


def read_prompt_artifact(work_dir: Path) -> dict[str, Any]:
    return _load_prompt_artifact(work_dir)


def _prompt_artifact_usable(art: dict[str, Any]) -> bool:
    if not art:
        return False
    if str(art.get("topic") or art.get("keywords") or art.get("context") or "").strip():
        return True
    cat = art.get("catalog")
    if isinstance(cat, dict) and str(cat.get("prompt_template_id") or "").strip():
        return True
    return len(art) >= 3


def confirm_prompt_bundle(work_dir: Path, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Marca Prompt como done usando `pipeline/prompt.json` (sin re-ejecutar el LLM)."""
    if data is not None and not isinstance(data, dict):
        raise ValueError("prompt debe ser un objeto JSON")
    raw = data if isinstance(data, dict) and data else read_prompt_artifact(work_dir)
    if not _prompt_artifact_usable(raw):
        raise ValueError(
            "No hay pipeline/prompt.json utilizable. Ejecuta Start step o guarda un prompt válido."
        )
    out = {**raw, "confirmed": True, "confirmed_at": _now_iso()}
    _write_json(_pipeline_dir(work_dir) / "prompt.json", out)
    _set_step(work_dir, "prompt", state="done", detail="Prompt confirmado (bloqueado).")
    st = read_pipeline_state(work_dir)
    _sync_global_state_from_steps(st)
    st["last_error"] = None
    write_pipeline_state(work_dir, st)
    return out


def _resolve_script_text_for_confirm(work_dir: Path) -> tuple[Path, str]:
    candidates = (work_dir / "guion.txt", _pipeline_dir(work_dir) / "script.txt")
    for p in candidates:
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return p, text
    raise ValueError(
        "No hay guion.txt ni pipeline/script.txt con texto. Ejecuta Start step o pega el guion."
    )


def confirm_script_writer_from_disk(work_dir: Path) -> dict[str, Any]:
    """Marca Script Writer como done si ya existe guion en disco (sin LLM)."""
    path, text = _resolve_script_text_for_confirm(work_dir)
    guion = work_dir / "guion.txt"
    pipe_script = _pipeline_dir(work_dir) / "script.txt"
    if path != guion and not guion.is_file():
        guion.parent.mkdir(parents=True, exist_ok=True)
        guion.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    if path != pipe_script and not pipe_script.is_file():
        pipe_script.parent.mkdir(parents=True, exist_ok=True)
        pipe_script.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    rel = path.relative_to(work_dir).as_posix()
    _set_step(
        work_dir,
        "script_writer",
        state="done",
        detail=f"Guion confirmado ({rel}).",
    )
    st = read_pipeline_state(work_dir)
    _sync_global_state_from_steps(st)
    st["last_error"] = None
    write_pipeline_state(work_dir, st)
    return {"source": rel, "chars": len(text)}


def confirm_narrative_pacing_pass_manual(work_dir: Path, text: str) -> dict[str, Any]:
    """Guarda guion editado a mano y marca Narrative Pacing Pass como done (sin LLM)."""
    from videomaker.core.saved_guiones_store import write_guion_to_session_work_dir
    from videomaker.llm.script_gen import _count_narrable_words, _wpm_default

    raw = (text or "").replace("\r\n", "\n").strip()
    if len(raw) < 200:
        raise ValueError("Guion demasiado corto (mínimo ~200 caracteres).")

    write_guion_to_session_work_dir(work_dir, raw)
    words = _count_narrable_words(raw)
    wpm = _wpm_default()
    mins = round(words / wpm, 1) if wpm > 0 else 0.0
    meta: dict[str, Any] = {
        "source": "manual",
        "words_before": words,
        "words_after": words,
        "minutes_before_est": mins,
        "minutes_after_est": mins,
        "generated_at": _now_iso(),
    }
    _write_json(_pipeline_dir(work_dir) / "pacing_pass_result.json", meta)
    _set_step(
        work_dir,
        "narrative_pacing_pass",
        state="done",
        detail=f"Guion manual aplicado (guion.txt, ~{mins} min narrables).",
    )
    st = read_pipeline_state(work_dir)
    _sync_global_state_from_steps(st)
    st["last_error"] = None
    write_pipeline_state(work_dir, st)
    return {
        "source": "guion.txt",
        "chars": len(raw),
        "narrable_words": words,
        "estimated_minutes": mins,
        "pacing_result": meta,
    }


_STEP_TITLE_BY_ID = dict(PIPELINE_STEPS)

MANUAL_CONFIRM_STEP_IDS = frozenset({
    "narrative_angle",
    "prompt",
    "script_writer",
    "editorial_analyzer",
    "narrative_pacing_pass",
    "hook_scene_router",
    "body_scene_router",
    "image_prompt_writer",
    "voiceovers_generation",
    "images_generation",
    "music_engine",
    "metadata",
    "subtitle_engine",
    "render_draft",
})

STEP_ARTIFACT_HINTS: dict[str, str] = {
    "editorial_analyzer": "pipeline/editorial_analysis.json",
    "narrative_pacing_pass": "guion.txt o pipeline/script.txt",
    "hook_scene_router": "pipeline/hook_scene_router.json",
    "body_scene_router": "pipeline/body_scene_router.json",
    "image_prompt_writer": "pipeline/image_prompts.json",
    "voiceovers_generation": "narracion.wav, scene_audio/*.mp3 o pipeline/voiceovers.json",
    "images_generation": "pipeline/images/*.png o pipeline/images_generation.json",
    "music_engine": "pipeline/music_plan.json",
    "metadata": "pipeline/metadata.json",
    "subtitle_engine": "pipeline/subtitles_plan.json",
    "render_draft": "draft.mp4 o pipeline/render_draft.json",
}


def _artifact_source_for_step(work_dir: Path, step_id: str) -> str | None:
    """Ruta relativa del artefacto principal detectado (para UI de confirmación)."""
    d = _pipeline_dir(work_dir)
    if step_id in ("script_writer", "narrative_pacing_pass"):
        for p in (work_dir / "guion.txt", d / "script.txt"):
            if p.is_file():
                try:
                    if p.read_text(encoding="utf-8").strip():
                        return p.relative_to(work_dir).as_posix()
                except OSError:
                    continue
        return None
    if step_id == "voiceovers_generation":
        if (work_dir / "narracion.wav").is_file():
            return "narracion.wav"
        scene_audio = work_dir / "scene_audio"
        if scene_audio.is_dir():
            mp3 = next(scene_audio.glob("*.mp3"), None)
            if mp3 is not None:
                return f"scene_audio/{mp3.name}"
        if (d / "scene_editor.json").is_file():
            return "pipeline/scene_editor.json"
        if (d / "voiceovers.json").is_file():
            return "pipeline/voiceovers.json"
        return None
    if step_id == "images_generation":
        if (d / "images_generation.json").is_file():
            return "pipeline/images_generation.json"
        images = d / "images"
        if images.is_dir():
            png = next(images.glob("*.png"), None)
            if png is not None:
                return f"pipeline/images/{png.name}"
        return None
    if step_id == "render_draft":
        if (work_dir / "draft.mp4").is_file():
            return "draft.mp4"
        meta = d / "render_draft.json"
        if meta.is_file() and meta.stat().st_size > 32:
            return "pipeline/render_draft.json"
        return None
    primary = _expected_artifact_paths(work_dir).get(step_id)
    if primary is not None and primary.is_file():
        return primary.relative_to(work_dir).as_posix()
    return None


def _stamp_step_artifact_confirmed(work_dir: Path, step_id: str) -> None:
    """Marca `confirmed` en JSON del paso cuando aplica."""
    p = _expected_artifact_paths(work_dir).get(step_id)
    if p is None or p.suffix.lower() != ".json" or not p.is_file():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    raw["confirmed"] = True
    raw["confirmed_at"] = _now_iso()
    _write_json(p, raw)


def get_pipeline_step_confirm_status(work_dir: Path, step_id: str) -> dict[str, Any]:
    sid = (step_id or "").strip()
    if sid not in MANUAL_CONFIRM_STEP_IDS:
        raise ValueError(f"Paso no admite confirmación manual: {step_id!r}")
    st = read_pipeline_state(work_dir)
    step = next((s for s in st.get("steps", []) if s.get("id") == sid), None)
    step_done = (step or {}).get("state") == "done"
    exists = _step_artifact_satisfied(work_dir, sid)
    return {
        "step_id": sid,
        "exists": exists,
        "step_done": step_done,
        "source": _artifact_source_for_step(work_dir, sid) if exists else None,
        "artifact_hint": STEP_ARTIFACT_HINTS.get(sid, ""),
        "title": _STEP_TITLE_BY_ID.get(sid, sid),
    }


def confirm_pipeline_step_from_disk(work_dir: Path, step_id: str) -> dict[str, Any]:
    """Marca un paso como done si su artefacto ya existe (sin LLM)."""
    sid = (step_id or "").strip()
    if sid not in MANUAL_CONFIRM_STEP_IDS:
        raise ValueError(f"Paso no admite confirmación manual: {step_id!r}")
    if sid == "narrative_angle":
        na = read_narrative_angle_artifact(work_dir)
        if not na:
            raise ValueError(
                "No hay pipeline/narrative_angle.json. Ejecuta Start step o pega un JSON válido."
            )
        out = confirm_narrative_angle_bundle(work_dir, na)
        return {"step_id": sid, "confirmed": True, "source": "pipeline/narrative_angle.json", "detail": out}
    if sid == "prompt":
        out = confirm_prompt_bundle(work_dir, None)
        return {"step_id": sid, "confirmed": True, "source": "pipeline/prompt.json", "detail": out}
    if sid == "script_writer":
        meta = confirm_script_writer_from_disk(work_dir)
        return {"step_id": sid, "confirmed": True, **meta}
    if not _step_artifact_satisfied(work_dir, sid):
        hint = STEP_ARTIFACT_HINTS.get(sid, "artefacto esperado")
        raise ValueError(
            f"No hay salida en disco para «{_STEP_TITLE_BY_ID.get(sid, sid)}». "
            f"Se espera: {hint}. Ejecuta Start step o restaura el archivo."
        )
    _stamp_step_artifact_confirmed(work_dir, sid)
    title = _STEP_TITLE_BY_ID.get(sid, sid)
    source = _artifact_source_for_step(work_dir, sid)
    _set_step(
        work_dir,
        sid,
        state="done",
        detail=f"{title} confirmado ({source or 'bloqueado'}).",
    )
    st = read_pipeline_state(work_dir)
    _sync_global_state_from_steps(st)
    st["last_error"] = None
    write_pipeline_state(work_dir, st)
    return {"step_id": sid, "confirmed": True, "source": source}


def read_editorial_analysis_artifact(work_dir: Path) -> dict[str, Any]:
    p = _pipeline_dir(work_dir) / "editorial_analysis.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_editorial_analysis_artifact(work_dir: Path, data: dict[str, Any]) -> None:
    _write_json(_pipeline_dir(work_dir) / "editorial_analysis.json", data)


def _narrative_angle_context_text(na: dict[str, Any]) -> str:
    from videomaker.llm.narrative_angle_builder import narrative_angle_context_text

    return narrative_angle_context_text(na)


def _attach_narrative_angle_to_prompt_payload(work_dir: Path, payload: dict[str, Any]) -> None:
    na = read_narrative_angle_artifact(work_dir)
    if not na:
        return
    payload["narrative_angle"] = na
    ctx = _narrative_angle_context_text(na)
    if ctx and not str(payload.get("context") or "").strip():
        payload["context"] = ctx


def read_packaging_artifact(work_dir: Path) -> dict[str, Any]:
    p = _pipeline_dir(work_dir) / "packaging.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def write_packaging_artifact(work_dir: Path, data: dict[str, Any]) -> None:
    _write_json(_pipeline_dir(work_dir) / "packaging.json", data)


def _packaging_context_text(work_dir: Path) -> str:
    from videomaker.llm.packaging_ideation import packaging_context_text

    return packaging_context_text(read_packaging_artifact(work_dir))


def _attach_packaging_to_prompt_payload(work_dir: Path, payload: dict[str, Any]) -> None:
    pkg = read_packaging_artifact(work_dir)
    if not pkg:
        return
    payload["packaging"] = pkg
    plat = pkg.get("platform") if isinstance(pkg.get("platform"), dict) else {}
    title = str(plat.get("title") or "").strip()
    if title:
        if not str(payload.get("topic") or "").strip():
            payload["topic"] = title
        payload["packaging_title"] = title
    tn = pkg.get("thumbnail_narrative")
    if isinstance(tn, dict) and tn:
        payload["thumbnail_narrative"] = tn
    ctx = _packaging_context_text(work_dir)
    if ctx:
        prev = str(payload.get("context") or "").strip()
        payload["context"] = (prev + "\n\n" + ctx).strip() if prev else ctx


def _narrative_angle_channel_context(work_dir: Path, inputs: PipelineInputs) -> tuple[str, str]:
    """Audiencia + estilo de canal desde plantilla Prompt (mínimo)."""
    audience = ""
    tone = ""
    tid = (inputs.prompt_template_id or "").strip()
    if not tid:
        try:
            p = _pipeline_dir(work_dir) / "prompt.json"
            if p.is_file():
                raw = json.loads(p.read_text(encoding="utf-8"))
                cat = raw.get("catalog") if isinstance(raw, dict) else {}
                if isinstance(cat, dict):
                    tid = str(cat.get("prompt_template_id") or "").strip()
        except Exception:
            tid = ""
    if tid:
        try:
            row = get_prompt_template(tid)
        except Exception:
            row = None
        if row:
            pj = row.get("params_json") or {}
            if isinstance(pj, dict):
                audience = str(pj.get("target_audience") or "").strip()
                ns = pj.get("narrative_structure")
                if isinstance(ns, dict):
                    tone = str(ns.get("tone") or "").strip()
    return audience, tone or "—"


def _run_step_packaging(work_dir: Path, inputs: PipelineInputs) -> None:
    from videomaker.core.metadata_settings_store import read_metadata_settings
    from videomaker.llm.packaging_ideation import (
        generate_packaging_ideation,
        wrap_packaging_bundle,
    )
    from videomaker.pipeline.topic_generator_selection import (
        resolve_topic_generator_artifact,
    )

    na = read_narrative_angle_artifact(work_dir)
    if not na:
        raise RuntimeError(
            "Packaging: ejecuta Narrative Angle y elige tema en Topic Generator antes."
        )
    st = read_metadata_settings(work_dir)
    tp = str(st.get("target_platform") or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    tg = resolve_topic_generator_artifact(
        work_dir, read_topic_generator_artifact(work_dir), persist_if_inferred=False
    )
    from videomaker.llm.metadata_gen import resolve_metadata_llm

    meta_prov, meta_model = resolve_metadata_llm(inputs.provider, inputs.model)
    inner = generate_packaging_ideation(
        keywords=inputs.keywords,
        context=inputs.context,
        lang=inputs.lang,
        provider=meta_prov,
        model=meta_model,
        target_platform=tp,
        minutes_session=float(inputs.minutes) if inputs.minutes and inputs.minutes > 0 else None,
        topic_artifact=tg or None,
        narrative_angle=na,
    )
    write_packaging_artifact(work_dir, wrap_packaging_bundle(inner))


def _run_step_narrative_angle(work_dir: Path, inputs: PipelineInputs) -> None:
    from videomaker.llm.narrative_angle_builder import (
        build_narrative_angle,
        build_narrative_angle_input,
    )
    from videomaker.pipeline.topic_generator_selection import get_selected_topic

    tg = read_topic_generator_artifact(work_dir)
    selected = get_selected_topic(tg)
    if not isinstance(selected, dict):
        raise RuntimeError("Elige un tema en Topic Generator antes de construir el ángulo narrativo.")
    title = str(selected.get("title") or inputs.keywords or "").strip()
    if not title:
        raise RuntimeError("El tema seleccionado no tiene título.")
    from videomaker.llm.output_language import resolve_pipeline_lang

    out_lang = resolve_pipeline_lang(work_dir, request_lang=inputs.lang)
    audience, channel_style = _narrative_angle_channel_context(work_dir, inputs)
    tone = channel_style if channel_style != "—" else ""
    from videomaker.pipeline.duration_policy import clamp_pipeline_minutes

    session_minutes = clamp_pipeline_minutes(inputs.minutes)
    angle_input = build_narrative_angle_input(
        topic=title,
        audience=audience,
        channel_style=channel_style,
        duration_minutes=session_minutes,
        tone=tone,
    )
    na = build_narrative_angle(
        angle_input,
        output_language=out_lang,
    )
    na["generated_at"] = _now_iso()
    write_narrative_angle_artifact(work_dir, na)


def _run_step_editorial_analyzer(work_dir: Path, inputs: PipelineInputs) -> None:
    from videomaker.llm.editorial_analyzer import analyze_script

    txt, _ = _load_script_text_with_source(work_dir, None)
    if not txt.strip():
        raise RuntimeError("No hay guion. Ejecuta Script Writer primero.")
    pj = _pipeline_dir(work_dir) / "prompt.json"
    topic = inputs.keywords
    na_ctx = ""
    if pj.is_file():
        try:
            pr = json.loads(pj.read_text(encoding="utf-8"))
            topic = str(pr.get("topic") or pr.get("keywords") or topic)
            na = pr.get("narrative_angle")
            if isinstance(na, dict):
                na_ctx = _narrative_angle_context_text(na)
        except Exception:
            pass
    report = analyze_script(
        txt,
        topic_title=topic,
        narrative_context=na_ctx,
        target_minutes=float(inputs.minutes or 10.0),
        output_language=inputs.lang,
    )
    report["generated_at"] = _now_iso()
    write_editorial_analysis_artifact(work_dir, report)


def _run_step_narrative_pacing_pass(work_dir: Path, inputs: PipelineInputs) -> None:
    from videomaker.core.pacing_pass_settings_store import (
        read_pacing_pass_settings,
        resolve_target_minutes,
    )
    from videomaker.llm.narrative_pacing_pass import apply_narrative_pacing_pass

    txt, _ = _load_script_text_with_source(work_dir, None)
    if not txt.strip():
        raise RuntimeError("No hay guion. Ejecuta Script Writer primero.")
    analysis = read_editorial_analysis_artifact(work_dir)
    st = read_pacing_pass_settings(work_dir)
    target_m = resolve_target_minutes(work_dir, session_minutes=float(inputs.minutes or 10))
    trim = bool(st.get("trim_to_duration", True))
    user_dirs = str(st.get("user_directives") or "").strip()

    topic = inputs.keywords
    pj = _pipeline_dir(work_dir) / "prompt.json"
    if pj.is_file():
        try:
            pr = json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(pr, dict):
                topic = str(pr.get("topic") or pr.get("keywords") or topic)
        except Exception:
            pass

    revised, meta = apply_narrative_pacing_pass(
        txt,
        analysis or None,
        topic_title=topic,
        output_language=inputs.lang,
        target_minutes=target_m,
        trim_to_duration=trim,
        user_directives=user_dirs,
    )
    from videomaker.core.saved_guiones_store import write_guion_to_session_work_dir

    write_guion_to_session_work_dir(work_dir, revised)
    meta["generated_at"] = _now_iso()
    _write_json(_pipeline_dir(work_dir) / "pacing_pass_result.json", meta)


def _load_script_text_with_source(work_dir: Path, script_path: Path | None) -> tuple[str, Path | None]:
    if script_path is not None and script_path.is_file():
        return script_path.read_text(encoding="utf-8"), script_path
    text = _load_script_text(work_dir, None)
    return text, work_dir / "guion.txt" if (work_dir / "guion.txt").is_file() else None


def _run_step_topic_generator(
    work_dir: Path,
    inputs: PipelineInputs,
    *,
    rerun_step_id: str | None = None,
) -> None:
    from videomaker.llm.topic_generator import generate_topic_ideas
    from videomaker.pipeline.session_spawn import should_skip_topic_generator_llm
    from videomaker.web.transcripts_session import get_combined_text

    if should_skip_topic_generator_llm(work_dir, rerun_step_id=rerun_step_id):
        tg = read_topic_generator_artifact(work_dir)
        idx = tg.get("selected_index")
        topics = tg.get("topics") if isinstance(tg.get("topics"), list) else []
        if isinstance(idx, int) and 0 <= idx < len(topics):
            t = topics[idx] if isinstance(topics[idx], dict) else {}
            title = str(t.get("title") or "").strip() or f"Tema #{idx + 1}"
            detail = f"Tema reutilizado (banco): {title[:120]}"
        else:
            detail = "Temas reutilizados del banco (sin LLM)."
        _set_step(work_dir, "topic_generator", state="done", detail=detail)
        return

    transcript = (inputs.topic_generator_transcript or "").strip()
    if len(transcript) < 50:
        transcript = get_combined_text(work_dir)
    if len(transcript) < 50:
        raise RuntimeError(
            "Topic Generator: carga transcripciones en sesión (Analyse) o pega texto (mín. ~50 caracteres)."
        )
    channel_lang: str | None = None
    try:
        from videomaker.web.transcripts_session import read_transcripts_session

        sess = read_transcripts_session(work_dir)
        ch = sess.get("channel") if isinstance(sess.get("channel"), dict) else {}
        channel_lang = str(ch.get("language") or "").strip() or None
    except Exception:
        channel_lang = None

    previous = read_topic_generator_artifact(work_dir)
    from videomaker.llm.output_language import normalize_language_code, resolve_pipeline_lang

    out_lang = normalize_language_code(
        str(previous.get("output_language") or "")
    ) or resolve_pipeline_lang(work_dir, request_lang=inputs.lang)
    payload = generate_topic_ideas(
        transcript_text=transcript,
        niche_trends=inputs.topic_generator_niche_trends or "",
        topic_count=inputs.topic_generator_topic_count or 8,
        output_language=out_lang,
        channel_language=channel_lang,
        provider=inputs.provider or "anthropic",
        model=inputs.model or "",
    )
    from videomaker.pipeline.topic_generator_selection import apply_topic_selection

    from videomaker.pipeline.duration_policy import apply_duration_policy_to_topic_payload

    payload = apply_topic_selection(
        payload,
        previous=previous,
        session_keywords=inputs.keywords or "",
        session_context=inputs.context or "",
    )
    write_topic_generator_artifact(work_dir, apply_duration_policy_to_topic_payload(payload))


def _run_step_prompt(work_dir: Path, inputs: PipelineInputs) -> None:
    def _ensure_legacy_spines_defaults(payload: dict[str, Any]) -> None:
        """
        Solución rápida (deuda técnica):
        Los engines downstream (Subtitle/Music/Voiceover) aún leen spines legacy
        desde `pipeline/prompt.json` (energy_curve, visual_density, etc.).
        Las plantillas nuevas (Prompt Writer §1–10) no siempre los generan, así que
        garantizamos defaults estables para no romper Módulo 2.
        """

        if not isinstance(payload.get("energy_curve"), list):
            payload["energy_curve"] = [
                "hook_tension",
                "validation",
                "data_reveal",
                "relief",
                "empowerment",
            ]

        vd = payload.get("visual_density")
        if not isinstance(vd, dict):
            vd = {}
        if not str(vd.get("hook") or "").strip():
            vd["hook"] = "high"
        if not str(vd.get("middle_explanation") or "").strip():
            vd["middle_explanation"] = "medium"
        if not str(vd.get("emotional_reveal") or "").strip():
            vd["emotional_reveal"] = "low + intimate"
        payload["visual_density"] = vd

        cr = payload.get("credibility_rules")
        if not isinstance(cr, dict):
            cr = {}
        cr.setdefault("avoid_totalizing_claims", True)
        cr.setdefault("include_counterarguments", True)
        cr.setdefault("end_with_empowerment", True)
        payload["credibility_rules"] = cr

        arc = payload.get("emotional_arc")
        if not isinstance(arc, dict):
            arc = {}
        arc.setdefault("start", "tension")
        arc.setdefault("mid", "clarity")
        arc.setdefault("end", "agency")
        payload["emotional_arc"] = arc

        ssf = payload.get("scroll_stop_factors")
        if not isinstance(ssf, list):
            payload["scroll_stop_factors"] = [
                "identity threat",
                "status anxiety",
                "curiosity contradiction",
            ]

        vsa = payload.get("viewer_state_after_video")
        if not isinstance(vsa, dict):
            vsa = {}
        vsa.setdefault("clarity", 80)
        vsa.setdefault("agency", 70)
        vsa.setdefault("calm", 60)
        payload["viewer_state_after_video"] = vsa

    out = _pipeline_dir(work_dir) / "prompt.json"
    catalog: dict[str, Any] = {}
    tid = (inputs.prompt_template_id or "").strip()
    if tid:
        catalog["prompt_template_id"] = tid
        row = None
        try:
            row = get_prompt_template(tid)
        except Exception:
            catalog["resolution"] = "template_lookup_failed"
        if row:
            catalog["prompt_template_name"] = row.get("name")
            if row.get("updated_at") is not None:
                catalog["catalog_record_updated_at"] = str(row["updated_at"])
        elif catalog.get("resolution") != "template_lookup_failed":
            catalog["resolution"] = "template_not_found"

    from videomaker.pipeline.duration_policy import clamp_pipeline_minutes

    payload: dict[str, Any] = {
        "keywords": inputs.keywords,
        "context": inputs.context,
        "lang": inputs.lang,
        "minutes": clamp_pipeline_minutes(inputs.minutes),
        "provider": inputs.provider,
        "model": inputs.model,
        "topic": (inputs.prompt_topic or "").strip() or (inputs.keywords or "").strip(),
        "video_restrictions": (inputs.prompt_video_restrictions or "").strip(),
        "created_at": _now_iso(),
    }
    _attach_narrative_angle_to_prompt_payload(work_dir, payload)
    _attach_packaging_to_prompt_payload(work_dir, payload)
    _ensure_legacy_spines_defaults(payload)
    if catalog:
        payload["catalog"] = catalog
    _write_json(out, payload)


def _run_step_script_writer_sequential(
    work_dir: Path,
    merged: PipelineInputs,
    sys_x: str,
    usr_x: str,
    sw_row: dict[str, Any],
) -> Path:
    pjsw = sw_row.get("params_json") or {}
    if not isinstance(pjsw, dict):
        pjsw = {}
    sp = normalize_structure_preset(str(pjsw.get("structure_preset") or ""))
    plan = fragment_plan(sp)
    state = ensure_state_matches_template(work_dir, sp)

    idx_opt = merged.script_fragment_index
    if idx_opt is None:
        idx_guess = default_fragment_index_to_generate(state)
        if idx_guess is None:
            # Si el template actual cambia con respecto a la sesión anterior,
            # no reutilizamos fragmentos ya generados de la sesión vieja.
            prev_artifact = _load_prompt_artifact(work_dir)
            prev_cat = prev_artifact.get("catalog") if isinstance(prev_artifact, dict) else None
            prev_sw_tid = (
                str(prev_cat.get("script_writer_template_id") or "").strip()
                if isinstance(prev_cat, dict)
                else ""
            )
            current_sw_tid = (merged.script_writer_template_id or "").strip()
            if prev_sw_tid != current_sw_tid and (prev_sw_tid or current_sw_tid):
                reset_fragmentation_artifacts(work_dir)
                state = ensure_state_matches_template(work_dir, sp)
                idx = 0
            else:
                # No hay fragmentos pendientes. Si ya existen fragmentos generados
                # en disco (estado `generated` o `done`) asumimos que la fragmentación
                # fue completada por IA previamente y ensamblamos el guion completo
                # en lugar de fallar.
                steps = state.get("steps") or []
                any_generated = any(
                    isinstance(s, dict) and s.get("status") in {"generated", "done"} for s in steps
                )
                complete_chunks = all(
                    chunk_file(work_dir, i).is_file() and chunk_file(work_dir, i).stat().st_size > 0
                    for i in range(len(plan))
                )
                if any_generated and complete_chunks:
                    full_text = assemble_guion(work_dir, state)
                    out = _pipeline_dir(work_dir) / "script.txt"
                    out.write_text(full_text, encoding="utf-8")
                    guion = work_dir / "guion.txt"
                    guion.write_text(full_text, encoding="utf-8")
                    write_script_bundle(work_dir, full_text)
                    _persist_script_writer_template_to_prompt_artifact(
                        work_dir, current_sw_tid or None
                    )
                    return out
                raise RuntimeError(
                    "Fragmentación secuencial: no hay fragmentos pendientes. "
                    "Marca un paso como no completado en la UI o pasa un índice explícito para regenerar."
                )
        else:
            idx = idx_guess
    else:
        idx = int(idx_opt)

    if idx < 0 or idx >= len(plan):
        raise ValueError("Índice de fragmento fuera de rango.")

    try:
        pm = float(merged.minutes)
    except (TypeError, ValueError):
        pm = 10.0
    target_m = minutes_for_sequential_fragment(
        pipeline_minutes=pm,
        fragment_index=idx,
        structure_preset=sp,
        params_json=pjsw,
    )
    w_used = normalized_minute_weights(sp, pjsw)

    _fid, label = plan[idx]
    outline_txt = str(state.get("outline_text") or "").strip()
    if not outline_txt:
        op = outline_path(work_dir)
        if op.is_file():
            outline_txt = op.read_text(encoding="utf-8").strip()

    parts_prior: list[str] = []
    for i in range(idx):
        cf = chunk_file(work_dir, i)
        if cf.is_file():
            parts_prior.append(cf.read_text(encoding="utf-8").strip())
    prior_tail = "\n\n".join(parts_prior)
    prior_tail = prior_tail[-6000:] if len(prior_tail) > 6000 else prior_tail

    seg_target_words = segment_word_target(float(target_m))
    addon = build_fragment_user_addon(
        FragmentLLMAddon(
            index=idx,
            total=len(plan),
            label=label,
            outline_text=outline_txt,
            prior_tail=prior_tail if idx > 0 else "",
            is_first=(idx == 0),
            segment_minutes=float(target_m),
            target_narrable_words=seg_target_words,
            total_pipeline_minutes=float(pm),
            fragment_labels=tuple(lbl for _fid, lbl in plan),
        )
    )
    usr_eff = ((usr_x + "\n\n") if usr_x else "") + addon

    bp = ScriptBlueprint(
        keywords=[k.strip() for k in (merged.keywords or "").split(",") if k.strip()],
        extra_context=merged.context or "",
        locale=parse_locale(merged.lang),
        target_minutes=float(target_m),
        prompt_duration_minutes=float(pm),
    )

    def _script_progress(detail: str) -> None:
        set_status(work_dir, state="running", step="script", detail=detail[:240])

    text = generate_script(
        bp,
        provider=(merged.provider.strip() or None),
        model=(merged.model.strip() or None),
        system_extra=sys_x,
        user_extra=usr_eff.strip(),
        force_single_pass=True,
        per_fragment_segment=True,
        include_broll=False,
        on_progress=_script_progress,
    )
    text = strip_fin_marker(text)

    chunks_dir(work_dir).mkdir(parents=True, exist_ok=True)

    if idx == 0:
        outline_part, body_part = extract_outline_and_script_body(text)
        if outline_part.strip():
            state["outline_text"] = outline_part.strip()
            outline_path(work_dir).parent.mkdir(parents=True, exist_ok=True)
            outline_path(work_dir).write_text(outline_part.strip(), encoding="utf-8")
        chunk_body = body_part.strip() if body_part.strip() else text.strip()
        chunk_file(work_dir, 0).write_text(chunk_body, encoding="utf-8")
    else:
        chunk_file(work_dir, idx).write_text(text.strip(), encoding="utf-8")

    set_step_status(state, idx, "generated")
    save_state(work_dir, state)

    full_text = assemble_guion(work_dir, state)

    try:
        from videomaker.llm import script_gen as _sg

        narrable_words = _sg._count_narrable_words(full_text)  # type: ignore[attr-defined]
        sentences = _sg._count_sentences_narrable(full_text)  # type: ignore[attr-defined]
        broll = _sg._count_broll_tags(full_text)  # type: ignore[attr-defined]
        target_words_frag = segment_word_target(float(target_m))
        target_words_full = segment_word_target(float(pm))
        cf_done = chunk_file(work_dir, idx)
        frag_txt = cf_done.read_text(encoding="utf-8") if cf_done.is_file() else ""
        frag_words = _sg._count_narrable_words(frag_txt)  # type: ignore[attr-defined]
        from videomaker.llm.llm_routing import CREATIVE_PROVIDER, resolve_creative_model

        debug: dict[str, Any] = {
            "provider": CREATIVE_PROVIDER,
            "model": resolve_creative_model(merged.model),
            "sequential_fragments": True,
            "fragment_index": idx,
            "fragment_label": label,
            "fragment_minute_weights": w_used,
            "target_minutes": float(merged.minutes),
            "effective_target_minutes": float(target_m),
            "chunk_outline_act1_only": False,
            "narrable_words": narrable_words,
            "fragment_narrable_words": frag_words,
            "target_min_words_fragment": target_words_frag,
            "target_min_words_full_script": target_words_full,
            "sentences_narrable": sentences,
            "broll_tags": broll,
            "broll_per_sentence_ratio": (broll / max(1, sentences)),
        }
        _write_json(_pipeline_dir(work_dir) / "script_writer_debug.json", debug)

        if (os.environ.get("VIDEOMAKER_SCRIPT_FAIL_ON_SHORT", "") or "").strip().lower() in {"1", "true", "yes", "on"}:
            if frag_words < target_words_frag:
                raise RuntimeError(
                    f"Fragmento demasiado corto: {frag_words} palabras narrables (objetivo mínimo {target_words_frag} para este fragmento)."
                )
    except Exception:
        pass

    out = _pipeline_dir(work_dir) / "script.txt"
    out.write_text(full_text, encoding="utf-8")
    guion = work_dir / "guion.txt"
    guion.write_text(full_text, encoding="utf-8")
    write_script_bundle(work_dir, full_text)
    _persist_script_writer_template_to_prompt_artifact(work_dir, (merged.script_writer_template_id or "").strip() or None)
    return out


def _run_step_script_writer(work_dir: Path, inputs: PipelineInputs) -> Path:
    merged = _merged_inputs_for_script(work_dir, inputs)
    sys_p, usr_p = _template_extras_from_catalog(work_dir, merged)
    sys_s, usr_s, sw_row = _script_writer_template_extras(merged)
    sys_x = "\n\n".join(x for x in (sys_p, sys_s) if x).strip()
    usr_x = "\n\n".join(x for x in (usr_p, usr_s) if x).strip()
    pkg_ctx = _packaging_context_text(work_dir)
    if pkg_ctx:
        usr_x = (usr_x + "\n\n" if usr_x else "") + pkg_ctx
    if sw_row and sequential_fragments_enabled(sw_row):
        return _run_step_script_writer_sequential(work_dir, merged, sys_x, usr_x, sw_row)

    try:
        pm = float(merged.minutes)
    except (TypeError, ValueError):
        pm = 10.0
    target_m = effective_chunk_target_minutes(sw_row, pm) if sw_row else pm
    chunk_single = chunk_outline_act1_only(sw_row) if sw_row else False
    bp = ScriptBlueprint(
        keywords=[k.strip() for k in (merged.keywords or "").split(",") if k.strip()],
        extra_context=merged.context or "",
        locale=parse_locale(merged.lang),
        target_minutes=float(target_m),
    )

    def _script_progress(detail: str) -> None:
        set_status(work_dir, state="running", step="script", detail=detail[:240])

    text = generate_script(
        bp,
        provider=(merged.provider.strip() or None),
        model=(merged.model.strip() or None),
        system_extra=sys_x,
        user_extra=usr_x,
        force_single_pass=chunk_single,
        include_broll=False,
        on_progress=_script_progress,
    )

    # Debug de calidad/longitud: deja trazas en disco para diagnosticar por qué sale corto.
    try:
        from videomaker.llm import script_gen as _sg

        narrable_words = _sg._count_narrable_words(text)  # type: ignore[attr-defined]
        sentences = _sg._count_sentences_narrable(text)  # type: ignore[attr-defined]
        broll = _sg._count_broll_tags(text)  # type: ignore[attr-defined]
        target_words = _sg._target_words_for_minutes(float(target_m))  # type: ignore[attr-defined]
        from videomaker.llm.llm_routing import CREATIVE_PROVIDER, resolve_creative_model

        debug: dict[str, Any] = {
            "provider": CREATIVE_PROVIDER,
            "model": resolve_creative_model(merged.model),
            "target_minutes": float(merged.minutes),
            "effective_target_minutes": float(target_m),
            "chunk_outline_act1_only": bool(chunk_single),
            "narrable_words": narrable_words,
            "target_min_words": target_words,
            "sentences_narrable": sentences,
            "broll_tags": broll,
            "broll_per_sentence_ratio": (broll / max(1, sentences)),
        }
        # Señales (mejor esfuerzo; no deben impedir escribir el debug).
        try:
            debug["has_outline"] = bool(re.search(r"(?im)^\\s*OUTLINE\\s*$", text or ""))
            debug["has_guion_header"] = bool(re.search(r"(?im)^\\s*(GUI[ÓO]N|GUION)\\s*$", text or ""))
        except Exception:
            pass
        _write_json(_pipeline_dir(work_dir) / "script_writer_debug.json", debug)

        # Opcional: si quieres que el step falle cuando sale corto.
        if (os.environ.get("VIDEOMAKER_SCRIPT_FAIL_ON_SHORT", "") or "").strip().lower() in {"1", "true", "yes", "on"}:
            if narrable_words < target_words:
                raise RuntimeError(
                    f"Guion demasiado corto: {narrable_words} palabras narrables (objetivo mínimo {target_words})."
                )
    except Exception:
        pass

    out = _pipeline_dir(work_dir) / "script.txt"
    out.write_text(text, encoding="utf-8")
    # Raíz de sesión: editor legacy, TTS y `/api/script`.
    guion = work_dir / "guion.txt"
    guion.write_text(text, encoding="utf-8")
    write_script_bundle(work_dir, text)
    _persist_script_writer_template_to_prompt_artifact(work_dir, (merged.script_writer_template_id or "").strip() or None)
    return out


def build_metadata_input_preview(work_dir: Path, inputs: PipelineInputs) -> dict[str, Any]:
    """Entradas que recibiría el paso Metadata (sin llamar al LLM)."""
    from videomaker.core.metadata_settings_store import (
        effective_system_prompt_override,
        effective_target_keywords,
        read_metadata_settings,
    )
    from videomaker.llm.metadata_gen import build_metadata_input_preview as build_preview
    from videomaker.pipeline.topic_generator_selection import (
        resolve_topic_generator_artifact,
    )

    script_text, script_source, script_exists = _resolve_script_for_metadata(work_dir, None)
    st = read_metadata_settings(work_dir)
    tp = str(st.get("target_platform") or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    tk = effective_target_keywords(st)
    kw_src = str(st.get("target_keywords_source") or "").strip().lower() or None
    sys_ov = effective_system_prompt_override(st)
    sp_src = str(st.get("system_prompt_source") or "").strip().lower() or None
    tg = resolve_topic_generator_artifact(
        work_dir, read_topic_generator_artifact(work_dir), persist_if_inferred=False
    )
    from videomaker.llm.metadata_gen import resolve_metadata_llm

    meta_prov, meta_model = resolve_metadata_llm(inputs.provider, inputs.model)
    return build_preview(
        script_text=script_text,
        script_source=script_source,
        script_exists=script_exists,
        keywords=inputs.keywords,
        context=inputs.context,
        session_lang=inputs.lang,
        target_platform=tp,
        target_keywords=tk,
        target_keywords_source=kw_src,
        system_prompt_override=sys_ov,
        stored_system_prompt=str(st.get("system_prompt") or ""),
        system_prompt_source=sp_src,
        minutes_session=float(inputs.minutes) if inputs.minutes and inputs.minutes > 0 else None,
        topic_artifact=tg or None,
        llm_provider=meta_prov,
        llm_model=meta_model,
    )


def _run_step_metadata(work_dir: Path, inputs: PipelineInputs, script_text: str) -> None:
    from videomaker.core.metadata_settings_store import (
        effective_system_prompt_override,
        effective_target_keywords,
        persist_inferred_target_keywords,
        read_metadata_settings,
    )
    from videomaker.llm.metadata_gen import generate_video_metadata, wrap_metadata_bundle
    from videomaker.pipeline.topic_generator_selection import (
        resolve_topic_generator_artifact,
    )

    st = read_metadata_settings(work_dir)
    tp = str(st.get("target_platform") or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    tk = effective_target_keywords(st)
    sys_ov = effective_system_prompt_override(st)
    tg = resolve_topic_generator_artifact(
        work_dir, read_topic_generator_artifact(work_dir), persist_if_inferred=False
    )

    from videomaker.llm.metadata_gen import resolve_metadata_llm

    meta_prov, meta_model = resolve_metadata_llm(inputs.provider, inputs.model)
    packaging = read_packaging_artifact(work_dir)
    plat_pkg = (
        packaging.get("platform") if isinstance(packaging.get("platform"), dict) else {}
    )
    packaging_title = str(plat_pkg.get("title") or "").strip() or None

    if packaging:
        from videomaker.llm.metadata_gen import generate_publication_metadata
        from videomaker.llm.packaging_ideation import merge_packaging_into_metadata

        pub = generate_publication_metadata(
            script_text=script_text,
            keywords=inputs.keywords,
            context=inputs.context,
            lang=inputs.lang,
            provider=meta_prov,
            model=meta_model,
            target_platform=tp,
            target_keywords=tk,
            minutes_session=float(inputs.minutes) if inputs.minutes and inputs.minutes > 0 else None,
            packaging_title=packaging_title,
        )
        inner = merge_packaging_into_metadata(packaging, pub)
        gen = inner.get("_gen") if isinstance(inner.get("_gen"), dict) else {}
        inner["_gen"] = {
            **gen,
            "packaging_hook_first": True,
            "topic_title": packaging_title,
        }
    else:
        inner = generate_video_metadata(
            script_text=script_text,
            keywords=inputs.keywords,
            context=inputs.context,
            lang=inputs.lang,
            provider=meta_prov,
            model=meta_model,
            target_platform=tp,
            target_keywords=tk,
            system_prompt_override=sys_ov,
            minutes_session=float(inputs.minutes) if inputs.minutes and inputs.minutes > 0 else None,
            topic_artifact=tg or None,
        )
    out = _pipeline_dir(work_dir) / "metadata.json"
    _write_json(out, wrap_metadata_bundle(inner))
    if not tk:
        plat = inner.get("platform") if isinstance(inner.get("platform"), dict) else {}
        tags = plat.get("tags") if isinstance(plat, dict) else None
        if isinstance(tags, list):
            persist_inferred_target_keywords(work_dir, tags, st)


def _infer_thumbnail_expression(text: str) -> str:
    """Infiere la expresión del avatar más adecuada para una idea de miniatura."""
    t = text.lower()
    if any(w in t for w in ("shock", "sorpresa", "increíble", "?!", "¿por qué", "error", "coste", "pérdida", "pierde", "pierdes")):
        return "surprised"
    if any(w in t for w in ("gráfica", "dato", "estadística", "número", "porcentaje", "%", "cómo", "explica", "guía")):
        return "explaining"
    if any(w in t for w in ("reflexi", "pensand", "¿", "mira", "seria", "documental", "cámara")):
        return "thinking"
    if any(w in t for w in ("éxito", "libre", "logr", "independencia", "objetivo", "meta")):
        return "excited"
    return "neutral"


def push_thumbnail_ideas_to_image_prompts(
    work_dir: Path,
    *,
    include_avatar: bool = False,
    merge: bool = True,
) -> dict[str, Any]:
    from videomaker.pipeline.thumbnail_from_metadata import push_thumbnail_ideas_to_image_prompts as _push

    return _push(work_dir, include_avatar=include_avatar, merge=merge)


def _run_step_scene_router(
    work_dir: Path, *, step_id: str, script_text: str, inputs: PipelineInputs
) -> None:
    if step_id == "hook_scene_router":
        from videomaker.llm.hook_scene_router import run_hook_scene_router_step

        run_hook_scene_router_step(work_dir, script_text, inputs)
        return
    if step_id == "body_scene_router":
        from videomaker.llm.body_scene_router import run_body_scene_router_step

        run_body_scene_router_step(work_dir, script_text, inputs)
        return
    out = _pipeline_dir(work_dir) / f"{step_id}.json"
    _write_json(
        out,
        {"version": 1, "notes": f"{step_id} (placeholder)", "has_broll": "[B-ROLL" in script_text},
    )


def _run_step_image_prompt_writer(work_dir: Path, inputs: PipelineInputs | None = None) -> None:
    from videomaker.core.image_prompt_writer_settings_store import read_image_prompt_writer_settings

    st = read_image_prompt_writer_settings(work_dir)
    from videomaker.llm.router_driven_image_prompts import (
        build_image_prompts_from_routers,
        router_driven_ipw_enabled,
    )

    if router_driven_ipw_enabled(work_dir):
        ctx = None
        if st.get("use_avatar"):
            from videomaker.core.visual_style_presets_store import prepare_avatar_mode_for_work

            ctx = prepare_avatar_mode_for_work(work_dir)
        build_image_prompts_from_routers(
            work_dir,
            use_avatar=bool(st.get("use_avatar")),
            avatar_description=str((ctx or {}).get("avatar_description") or ""),
            scene_visual_settings=(ctx or {}).get("scene_visual_settings"),
            intro_enabled=bool((ctx or {}).get("intro_enabled")),
            intro_character_name=str((ctx or {}).get("intro_character_name") or ""),
            outro_enabled=bool((ctx or {}).get("outro_enabled")),
            outro_character_name=str((ctx or {}).get("outro_character_name") or ""),
            target_generator=str(st.get("target_generator") or "midjourney"),
            provider=(inputs.provider if inputs else None) or None,
            model=(inputs.model if inputs else None) or None,
        )
        return

    if st.get("use_avatar"):
        from videomaker.core.visual_style_presets_store import prepare_avatar_mode_for_work
        from videomaker.llm.avatar_prompt_writer import generate_avatar_image_prompts

        ctx = prepare_avatar_mode_for_work(work_dir)
        generate_avatar_image_prompts(
            work_dir,
            avatar_description=ctx["avatar_description"],
            scene_visual_settings=ctx.get("scene_visual_settings"),
            intro_enabled=bool(ctx.get("intro_enabled")),
            intro_character_name=str(ctx.get("intro_character_name") or ""),
            outro_enabled=bool(ctx.get("outro_enabled")),
            outro_character_name=str(ctx.get("outro_character_name") or ""),
            secs_per_image=float(ctx["secs_per_image"]),
            max_images=int(ctx["max_images"]),
            target_generator=str(st.get("target_generator") or "midjourney"),
            provider=(inputs.provider if inputs else None) or None,
            model=(inputs.model if inputs else None) or None,
        )
        from videomaker.llm.image_prompt_hybrid import merge_avatar_hybrid_with_hook

        merge_avatar_hybrid_with_hook(work_dir)
        return

    from videomaker.llm.hook_scene_router import merge_hook_router_into_image_prompts

    try:
        merge_hook_router_into_image_prompts(work_dir)
    except ValueError:
        out = _pipeline_dir(work_dir) / "image_prompts.json"
        _write_json(
            out,
            {
                "version": 1,
                "source": "fallback",
                "prompts": [],
                "notes": "Ejecuta Hook Scene Router antes para generar prompts desde la ruta visual.",
            },
        )
        return

    # Post-process: attach visual symbol system if present in prompt.json.
    try:
        out = _pipeline_dir(work_dir) / "image_prompts.json"
        if out.is_file():
            blob = json.loads(out.read_text(encoding="utf-8"))
            art = _load_prompt_artifact(work_dir)
            vs = art.get("visual_symbols") if isinstance(art, dict) else None
            if isinstance(blob, dict):
                blob.setdefault("global_style", {})
                if isinstance(blob["global_style"], dict):
                    if isinstance(vs, list) and vs:
                        blob["global_style"]["visual_symbols"] = [v for v in vs if isinstance(v, dict)][:8]
                    # Propagate additional spines for downstream visual systems.
                    tn = art.get("thumbnail_narrative") if isinstance(art, dict) else None
                    if isinstance(tn, dict):
                        blob["global_style"]["thumbnail_narrative"] = tn
                    vd = art.get("visual_density") if isinstance(art, dict) else None
                    if isinstance(vd, dict) and vd:
                        blob["global_style"]["visual_density"] = vd
                    ec = art.get("energy_curve") if isinstance(art, dict) else None
                    if isinstance(ec, list) and ec:
                        blob["global_style"]["energy_curve"] = [str(x).strip() for x in ec if str(x).strip()][:12]
                    ssf = art.get("scroll_stop_factors") if isinstance(art, dict) else None
                    if isinstance(ssf, list) and ssf:
                        blob["global_style"]["scroll_stop_factors"] = [str(x).strip() for x in ssf if str(x).strip()][:10]
                    tribe = str(art.get("tribe_boundary") or "").strip() if isinstance(art, dict) else ""
                    if tribe:
                        blob["global_style"]["tribe_boundary"] = tribe
                    cp = str(art.get("color_psychology") or "").strip() if isinstance(art, dict) else ""
                    if cp:
                        blob["global_style"]["color_psychology"] = cp
                    va = str(art.get("visual_anchor") or "").strip() if isinstance(art, dict) else ""
                    if va:
                        blob["global_style"]["visual_anchor"] = va
                _write_json(out, blob)
    except Exception:
        pass


def _run_step_images_generation(work_dir: Path) -> None:
    out = _pipeline_dir(work_dir) / "images_generation.json"
    _write_json(out, {"notes": "placeholder", "generated": 0})


def _run_step_voiceovers_generation(work_dir: Path, inputs: PipelineInputs, script_path: Path) -> None:
    # Prefer voiceover-engine transformed script if present.
    tts_script = work_dir / "pipeline" / "script_for_tts.txt"
    if tts_script.is_file():
        script_text = tts_script.read_text(encoding="utf-8")
    else:
        script_text = script_path.read_text(encoding="utf-8")
    # If Voiceover Engine produced explicit pacing controls, apply them here.
    paragraph_pause_s = None
    try:
        vp = work_dir / "pipeline" / "voiceover_plan.json"
        if vp.is_file():
            raw = json.loads(vp.read_text(encoding="utf-8"))
            plan = raw.get("plan") if isinstance(raw, dict) else None
            tts = plan.get("tts_controls") if isinstance(plan, dict) else None
            if isinstance(tts, dict) and tts.get("paragraph_pause_s") is not None:
                paragraph_pause_s = float(tts.get("paragraph_pause_s"))
    except Exception:
        paragraph_pause_s = None

    out_wav, audio_s = build_narration_wav(
        script_text,
        voice_profile_for_work(work_dir, inputs.voice_preset),
        work_dir,
        paragraph_pause_s=paragraph_pause_s,
    )
    _write_json(_pipeline_dir(work_dir) / "voiceovers.json", {"wav": out_wav.name, "duration_s": audio_s})


def _run_step_render_draft(work_dir: Path, inputs: PipelineInputs) -> None:
    from videomaker.video.render import render_draft_video
    from videomaker.video.render_progress import clear_render_progress, update_render_progress

    narr = work_dir / "narracion.wav"
    stock_dir = work_dir / "stock"
    if not narr.is_file():
        raise RuntimeError(
            "Falta narracion.wav. Ejecuta Voiceovers Generation (o copia una narración a narracion.wav)."
        )
    out_mp4 = work_dir / "draft.mp4"
    clear_render_progress(work_dir)

    def _on_progress(phase: str, current: int, total: int, message: str) -> None:
        update_render_progress(
            work_dir,
            kind="draft_mp4",
            phase=phase,
            current=current,
            total=total,
            message=message,
        )
        if phase == "segment" and total > 0:
            set_status(
                work_dir,
                state="running",
                step="pipeline:render_draft",
                detail=f"Render draft: plano {current}/{total} — {message}",
            )
        elif phase != "done":
            set_status(
                work_dir,
                state="running",
                step="pipeline:render_draft",
                detail=f"Render draft — {message}",
            )

    render_draft_video(
        narr,
        stock_dir,
        out_mp4,
        work_dir=work_dir,
        pick_music_from_project=not bool(inputs.render_no_music),
        render_no_music=bool(inputs.render_no_music),
        on_progress=_on_progress,
    )
    update_render_progress(
        work_dir,
        kind="draft_mp4",
        phase="done",
        current=1,
        total=1,
        message="Completado",
    )


def run_pipeline(work_dir: Path, inputs: PipelineInputs, *, rerun_step_id: str | None = None) -> None:
    inputs = _pipeline_inputs_with_resolved_lang(work_dir, inputs)
    _sync_prompt_json_lang(work_dir, inputs.lang)

    with _LOCK:
        # Ensure manifest exists
        st = read_pipeline_state(work_dir)
        write_pipeline_state(work_dir, st)

    set_status(work_dir, state="running", step="pipeline", detail="Iniciando pipeline…")
    _set_pipeline_state(work_dir, state="running", current_step=None, last_error=None)
    # Clear any previous stop request at start.
    clear_pipeline_stop(work_dir)

    try:
        script_path: Path | None = None
        for sid in PIPELINE_RUN_ORDER:
            if rerun_step_id and sid != rerun_step_id:
                continue

            # Cooperative stop: checked between steps.
            if _stop_flag_path(work_dir).exists():
                _set_step(work_dir, sid, state="idle", detail="Stopped by user.")
                _set_pipeline_state(work_dir, state="idle", current_step=None, last_error="Stopped by user.")
                set_status(work_dir, state="idle", step="pipeline", detail="Stopped by user.")
                return

            _set_step(work_dir, sid, state="running", detail="Ejecutando…")
            set_status(work_dir, state="running", step=f"pipeline:{sid}", detail="Ejecutando step…")

            if sid == "topic_generator":
                _run_step_topic_generator(work_dir, inputs, rerun_step_id=rerun_step_id)
            elif sid == "narrative_angle":
                _run_step_narrative_angle(work_dir, inputs)
            elif sid == "packaging":
                _run_step_packaging(work_dir, inputs)
            elif sid == "prompt":
                _run_step_prompt(work_dir, inputs)
            elif sid == "script_writer":
                script_path = _run_step_script_writer(work_dir, inputs)
            elif sid == "editorial_analyzer":
                _run_step_editorial_analyzer(work_dir, inputs)
            elif sid == "narrative_pacing_pass":
                script_path = _pipeline_dir(work_dir) / "script.txt"
                _run_step_narrative_pacing_pass(work_dir, inputs)
            elif sid == "subtitle_engine":
                from videomaker.engines.subtitle_engine import run_subtitle_engine_step

                txt = _load_script_text(work_dir, script_path)
                if not txt.strip():
                    raise RuntimeError("No hay guion para Subtitle Engine. Ejecuta Script Writer o importa un guion.")
                run_subtitle_engine_step(work_dir, minutes=float(inputs.minutes or 10.0))
            elif sid == "music_engine":
                from videomaker.engines.music_engine import run_music_engine_step

                # Music plan is spine-driven; still best after Prompt.
                run_music_engine_step(work_dir, minutes=float(inputs.minutes or 10.0))
            elif sid == "voiceover_engine":
                from videomaker.engines.voiceover_engine import run_voiceover_engine_step

                txt = _load_script_text(work_dir, script_path)
                if not txt.strip():
                    raise RuntimeError("No hay guion para Voiceover Engine. Ejecuta Script Writer o importa un guion.")
                run_voiceover_engine_step(work_dir, minutes=float(inputs.minutes or 10.0))
            elif sid == "metadata":
                txt = _load_script_text(work_dir, script_path)
                if not txt.strip():
                    raise RuntimeError("No hay guion (guion.txt / pipeline/script.txt). Ejecuta Script Writer o importa un guion.")
                _run_step_metadata(work_dir, inputs, txt)
            elif sid == "hook_scene_router":
                txt = _load_script_text(work_dir, script_path)
                _run_step_scene_router(
                    work_dir, step_id="hook_scene_router", script_text=txt, inputs=inputs
                )
            elif sid == "body_scene_router":
                txt = _load_script_text(work_dir, script_path)
                _run_step_scene_router(
                    work_dir, step_id="body_scene_router", script_text=txt, inputs=inputs
                )
            elif sid == "image_prompt_writer":
                _run_step_image_prompt_writer(work_dir, inputs)
            elif sid == "images_generation":
                _run_step_images_generation(work_dir)
            elif sid == "voiceovers_generation":
                if not script_path:
                    script_path = _pipeline_dir(work_dir) / "script.txt"
                if not script_path.is_file():
                    raise RuntimeError("Falta script.txt para generar voiceovers.")
                _run_step_voiceovers_generation(work_dir, inputs, script_path)
            elif sid == "render_draft":
                _run_step_render_draft(work_dir, inputs)
            else:
                # forward-compat
                pass

            if sid == "topic_generator":
                tg = read_topic_generator_artifact(work_dir)
                if tg.get("selected_index") is None:
                    detail = "Temas generados — elige uno con «Usar este tema»."
                else:
                    detail = "Tema seleccionado."
            else:
                detail = "Approved."
            _set_step(work_dir, sid, state="done", detail=detail)

            if rerun_step_id:
                break

        st = read_pipeline_state(work_dir)
        if rerun_step_id:
            _sync_global_state_from_steps(st)
            st["last_error"] = None
            write_pipeline_state(work_dir, st)
            set_status(
                work_dir,
                state=st.get("state") or "done",
                step="pipeline",
                detail=f"Paso «{rerun_step_id}» listo.",
            )
        else:
            _set_pipeline_state(work_dir, state="done", current_step=None, last_error=None)
            set_status(work_dir, state="done", step="pipeline", detail="Pipeline lista.")
    except Exception as e:
        _set_step(work_dir, rerun_step_id or (read_pipeline_state(work_dir).get("current_step") or "pipeline"), state="error", detail=str(e))
        _set_pipeline_state(work_dir, state="error", current_step=None, last_error=str(e))
        set_status(work_dir, state="error", step="pipeline", detail=str(e))
        _LOG.exception("pipeline failed: %s", e)


def save_manual_packaging_bundle(work_dir: Path, data: dict[str, Any]) -> None:
    """Persistir ``pipeline/packaging.json`` desde la UI."""
    if not isinstance(data, dict):
        raise ValueError("packaging debe ser un objeto JSON")
    write_packaging_artifact(work_dir, data)
    _set_step(work_dir, "packaging", state="done", detail="Guardado desde el editor.")
    st = read_pipeline_state(work_dir)
    gs_raw = st.get("state") or "idle"
    gs = cast(
        PipelineStatus,
        gs_raw if gs_raw in ("idle", "running", "done", "error") else "idle",
    )
    _set_pipeline_state(work_dir, state=gs, current_step=None, last_error=None)


def save_manual_metadata_bundle(work_dir: Path, data: dict[str, Any]) -> None:
    """Persistir `pipeline/metadata.json` desde la UI y marcar el paso como listo."""
    if not isinstance(data, dict):
        raise ValueError("metadata debe ser un objeto JSON")
    out = _pipeline_dir(work_dir) / "metadata.json"
    _write_json(out, data)
    _set_step(work_dir, "metadata", state="done", detail="Guardado desde el editor.")
    st = read_pipeline_state(work_dir)
    gs_raw = st.get("state") or "idle"
    gs = cast(
        PipelineStatus,
        gs_raw if gs_raw in ("idle", "running", "done", "error") else "idle",
    )
    _set_pipeline_state(work_dir, state=gs, current_step=None, last_error=None)


def save_manual_image_prompts_bundle(work_dir: Path, data: dict[str, Any]) -> None:
    """Persistir `pipeline/image_prompts.json` desde la UI y marcar el paso como listo."""
    if not isinstance(data, dict):
        raise ValueError("bundle debe ser un objeto JSON")
    out = _pipeline_dir(work_dir) / "image_prompts.json"
    _write_json(out, data)
    _set_step(work_dir, "image_prompt_writer", state="done", detail="Guardado desde el editor.")
    st = read_pipeline_state(work_dir)
    gs_raw = st.get("state") or "idle"
    gs = cast(
        PipelineStatus,
        gs_raw if gs_raw in ("idle", "running", "done", "error") else "idle",
    )
    _set_pipeline_state(work_dir, state=gs, current_step=None, last_error=None)


def save_manual_body_router_bundle(work_dir: Path, data: dict[str, Any]) -> None:
    """Persistir `pipeline/body_scene_router.json` desde la UI y marcar el paso como listo."""
    if not isinstance(data, dict):
        raise ValueError("artifact debe ser un objeto JSON")
    out = _pipeline_dir(work_dir) / "body_scene_router.json"
    _write_json(out, data)
    _set_step(work_dir, "body_scene_router", state="done", detail="Guardado desde el editor.")
    st = read_pipeline_state(work_dir)
    gs_raw = st.get("state") or "idle"
    gs = cast(
        PipelineStatus,
        gs_raw if gs_raw in ("idle", "running", "done", "error") else "idle",
    )
    _set_pipeline_state(work_dir, state=gs, current_step=None, last_error=None)


def save_manual_hook_router_bundle(work_dir: Path, data: dict[str, Any]) -> None:
    """Persistir `pipeline/hook_scene_router.json` desde la UI y marcar el paso como listo."""
    if not isinstance(data, dict):
        raise ValueError("artifact debe ser un objeto JSON")
    out = _pipeline_dir(work_dir) / "hook_scene_router.json"
    _write_json(out, data)
    _set_step(work_dir, "hook_scene_router", state="done", detail="Guardado desde el editor.")
    st = read_pipeline_state(work_dir)
    gs_raw = st.get("state") or "idle"
    gs = cast(
        PipelineStatus,
        gs_raw if gs_raw in ("idle", "running", "done", "error") else "idle",
    )
    _set_pipeline_state(work_dir, state=gs, current_step=None, last_error=None)


def save_manual_images_generation_bundle(work_dir: Path, data: dict[str, Any]) -> None:
    """Persistir `pipeline/images_generation.json` desde la UI y marcar el paso como listo."""
    if not isinstance(data, dict):
        raise ValueError("manifest debe ser un objeto JSON")
    out = _pipeline_dir(work_dir) / "images_generation.json"
    _write_json(out, data)
    _set_step(work_dir, "images_generation", state="done", detail="Guardado desde el editor.")
    st = read_pipeline_state(work_dir)
    gs_raw = st.get("state") or "idle"
    gs = cast(
        PipelineStatus,
        gs_raw if gs_raw in ("idle", "running", "done", "error") else "idle",
    )
    _set_pipeline_state(work_dir, state=gs, current_step=None, last_error=None)


def apply_imported_guion_to_work(
    work_dir: Path,
    text: str,
    *,
    detail: str = "Guion aplicado (biblioteca o archivo).",
) -> None:
    """Escribe guion + pipeline/script + script.json y marca Script Writer como listo."""
    from videomaker.core.saved_guiones_store import write_guion_to_session_work_dir

    write_guion_to_session_work_dir(work_dir, text)
    _set_step(work_dir, "script_writer", state="done", detail=(detail or "Importado.")[:800])
    st = read_pipeline_state(work_dir)
    gs_raw = st.get("state") or "idle"
    gs = cast(
        PipelineStatus,
        gs_raw if gs_raw in ("idle", "running", "done", "error") else "idle",
    )
    _set_pipeline_state(work_dir, state=gs, current_step=None, last_error=None)

