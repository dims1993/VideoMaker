"""Runner de pipeline: estado en disco + ejecución por pasos.

Persistencia por sesión en `work_dir/pipeline_manifest.json` y artefactos en `work_dir/pipeline/`.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from videomaker.core.models import ScriptBlueprint
from videomaker.audio.narration import build_narration_wav
from videomaker.llm.script_gen import generate_script
from videomaker.web.io_util import parse_locale, set_status, voice_profile_for_work

from .models import PIPELINE_STEPS, PipelineInputs, PipelineState, PipelineStatus

_LOCK = threading.Lock()


def _manifest_path(work_dir: Path) -> Path:
    return work_dir / "pipeline_manifest.json"


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


def read_pipeline_state(work_dir: Path) -> PipelineState:
    p = _manifest_path(work_dir)
    if not p.is_file():
        return _default_state()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("steps"), list):
            return raw  # type: ignore[return-value]
    except Exception:
        pass
    return _default_state()


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
    st["current_step"] = step_id if state == "running" else st.get("current_step")
    if state == "error":
        st["state"] = "error"
        st["last_error"] = detail
    write_pipeline_state(work_dir, st)
    return st


def _set_pipeline_state(work_dir: Path, *, state: PipelineStatus, current_step: str | None = None, last_error: str | None = None) -> None:
    st = read_pipeline_state(work_dir)
    st["state"] = state
    st["current_step"] = current_step
    if last_error is not None:
        st["last_error"] = last_error
    write_pipeline_state(work_dir, st)


def _pipeline_dir(work_dir: Path) -> Path:
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_step_prompt(work_dir: Path, inputs: PipelineInputs) -> None:
    out = _pipeline_dir(work_dir) / "prompt.json"
    payload = {
        "keywords": inputs.keywords,
        "context": inputs.context,
        "lang": inputs.lang,
        "minutes": inputs.minutes,
        "provider": inputs.provider,
        "model": inputs.model,
        "created_at": _now_iso(),
    }
    _write_json(out, payload)


def _run_step_script_writer(work_dir: Path, inputs: PipelineInputs) -> Path:
    bp = ScriptBlueprint(
        keywords=[k.strip() for k in (inputs.keywords or "").split(",") if k.strip()],
        extra_context=inputs.context or "",
        locale=parse_locale(inputs.lang),
        target_minutes=float(inputs.minutes),
    )
    text = generate_script(
        bp,
        provider=(inputs.provider.strip() or None),
        model=(inputs.model.strip() or None),
    )
    out = _pipeline_dir(work_dir) / "script.txt"
    out.write_text(text, encoding="utf-8")
    return out


def _run_step_metadata(work_dir: Path, script_text: str) -> None:
    # Placeholder: en una iteración posterior esto derivará metadata estructurada vía LLM.
    out = _pipeline_dir(work_dir) / "metadata.json"
    _write_json(out, {"notes": "placeholder", "chars": len(script_text)})


def _run_step_scene_router(work_dir: Path, *, step_id: str, script_text: str) -> None:
    # Placeholder: usa B-ROLL tags como “cambios” y produce una lista simple.
    out = _pipeline_dir(work_dir) / f"{step_id}.json"
    _write_json(out, {"notes": "placeholder", "has_broll": "[B-ROLL" in script_text})


def _run_step_image_prompt_writer(work_dir: Path) -> None:
    out = _pipeline_dir(work_dir) / "image_prompts.json"
    _write_json(out, {"notes": "placeholder", "prompts": []})


def _run_step_images_generation(work_dir: Path) -> None:
    out = _pipeline_dir(work_dir) / "images_generation.json"
    _write_json(out, {"notes": "placeholder", "generated": 0})


def _run_step_voiceovers_generation(work_dir: Path, inputs: PipelineInputs, script_path: Path) -> None:
    script_text = script_path.read_text(encoding="utf-8")
    out_wav, audio_s = build_narration_wav(
        script_text,
        voice_profile_for_work(work_dir, inputs.voice_preset),
        _pipeline_dir(work_dir),
    )
    _write_json(_pipeline_dir(work_dir) / "voiceovers.json", {"wav": out_wav.name, "duration_s": audio_s})


def run_pipeline(work_dir: Path, inputs: PipelineInputs, *, rerun_step_id: str | None = None) -> None:
    with _LOCK:
        # Ensure manifest exists
        st = read_pipeline_state(work_dir)
        write_pipeline_state(work_dir, st)

    set_status(work_dir, state="running", step="pipeline", detail="Iniciando pipeline…")
    _set_pipeline_state(work_dir, state="running", current_step=None, last_error=None)

    try:
        script_path: Path | None = None
        for sid, _title in PIPELINE_STEPS:
            if rerun_step_id and sid != rerun_step_id:
                continue

            _set_step(work_dir, sid, state="running", detail="Ejecutando…")
            set_status(work_dir, state="running", step=f"pipeline:{sid}", detail="Ejecutando step…")

            if sid == "prompt":
                _run_step_prompt(work_dir, inputs)
            elif sid == "script_writer":
                script_path = _run_step_script_writer(work_dir, inputs)
            elif sid == "metadata":
                txt = (script_path.read_text(encoding="utf-8") if script_path else "")
                _run_step_metadata(work_dir, txt)
            elif sid == "hook_scene_router":
                txt = (script_path.read_text(encoding="utf-8") if script_path else "")
                _run_step_scene_router(work_dir, step_id="hook_scene_router", script_text=txt)
            elif sid == "body_scene_router":
                txt = (script_path.read_text(encoding="utf-8") if script_path else "")
                _run_step_scene_router(work_dir, step_id="body_scene_router", script_text=txt)
            elif sid == "image_prompt_writer":
                _run_step_image_prompt_writer(work_dir)
            elif sid == "images_generation":
                _run_step_images_generation(work_dir)
            elif sid == "voiceovers_generation":
                if not script_path:
                    script_path = _pipeline_dir(work_dir) / "script.txt"
                if not script_path.is_file():
                    raise RuntimeError("Falta script.txt para generar voiceovers.")
                _run_step_voiceovers_generation(work_dir, inputs, script_path)
            else:
                # forward-compat
                pass

            _set_step(work_dir, sid, state="done", detail="Approved.")

            if rerun_step_id:
                break

        # Si fue rerun, respetamos estado global previo si estaba en error; para MVP lo dejamos done.
        _set_pipeline_state(work_dir, state="done", current_step=None)
        set_status(work_dir, state="done", step="pipeline", detail="Pipeline lista.")
    except Exception as e:
        _set_step(work_dir, rerun_step_id or (read_pipeline_state(work_dir).get("current_step") or "pipeline"), state="error", detail=str(e))
        _set_pipeline_state(work_dir, state="error", current_step=None, last_error=str(e))
        set_status(work_dir, state="error", step="pipeline", detail=str(e))
        raise

