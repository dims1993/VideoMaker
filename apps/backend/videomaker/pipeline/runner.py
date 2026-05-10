"""Runner de pipeline: estado en disco + ejecución por pasos.

Persistencia por sesión en `work_dir/pipeline_manifest.json` y artefactos en `work_dir/pipeline/`.
"""

from __future__ import annotations

import json
import threading
import time
import os
import re
from pathlib import Path
from typing import Any

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

from .models import PIPELINE_STEPS, PipelineInputs, PipelineState, PipelineStatus

_LOCK = threading.Lock()


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
        "prompt": d / "prompt.json",
        "script_writer": d / "script.txt",
        "metadata": d / "metadata.json",
        "hook_scene_router": d / "hook_scene_router.json",
        "body_scene_router": d / "body_scene_router.json",
        "image_prompt_writer": d / "image_prompts.json",
        "images_generation": d / "images_generation.json",
        "voiceovers_generation": d / "voiceovers.json",
    }


def _reconcile_state_with_artifacts(work_dir: Path, st: PipelineState) -> PipelineState:
    """
    Ensure "done" reflects reality. If a step is marked done but its expected artifact
    doesn't exist, downgrade it to idle.
    """
    expected = _expected_artifact_paths(work_dir)
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
            p = expected.get(sid)
            if p is not None and not p.is_file():
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
        # Only consider done if all expected artifacts exist for steps that claim done.
        # Otherwise it'll end up as idle once downgrades happen above.
        st["state"] = "done" if all((expected.get(s.get("id") or "") or Path("/")).is_file() or (s.get("state") != "done") for s in st.get("steps", [])) else "idle"
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
            return _reconcile_state_with_artifacts(work_dir, raw)  # type: ignore[return-value]
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


def _load_prompt_artifact(work_dir: Path) -> dict[str, Any]:
    p = work_dir / "pipeline" / "prompt.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _merged_inputs_for_script(work_dir: Path, inputs: PipelineInputs) -> PipelineInputs:
    """Combina la petición actual con `prompt.json` (paso Prompt previo) cuando hay huecos."""
    art = _load_prompt_artifact(work_dir)
    kw = (inputs.keywords or "").strip() or str(art.get("keywords") or "")
    ctx = (inputs.context or "").strip() or str(art.get("context") or "")
    lang = (inputs.lang or "").strip() or str(art.get("lang") or "es")
    try:
        minutes = float(inputs.minutes)
    except (TypeError, ValueError):
        minutes = 10.0
    if minutes <= 0:
        try:
            minutes = float(art.get("minutes") or 10.0)
        except (TypeError, ValueError):
            minutes = 10.0
    provider = (inputs.provider or "").strip() or str(art.get("provider") or "")
    model = (inputs.model or "").strip() or str(art.get("model") or "")
    tid = (inputs.prompt_template_id or "").strip() or None
    if not tid:
        cat = art.get("catalog")
        if isinstance(cat, dict):
            tid = str(cat.get("prompt_template_id") or "").strip() or None
    topic = (inputs.prompt_topic or "").strip() or str(art.get("topic") or "")
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
        script_writer_template_id=sw_tid,
        script_fragment_index=inputs.script_fragment_index,
    )


def _prompt_template_params_user_addon(row: dict[str, Any]) -> str:
    """Añade a user_extra lo guardado en params_json (público, key points) para que llegue al LLM."""
    pj = row.get("params_json") or {}
    if not isinstance(pj, dict):
        pj = {}
    parts: list[str] = []
    ta = str(pj.get("target_audience") or "").strip()
    if ta:
        parts.append(f"Público objetivo (plantilla Prompt):\n{ta}")
    kps = pj.get("key_points")
    if isinstance(kps, list) and kps:
        lines = [f"- {str(x).strip()}" for x in kps if str(x).strip()]
        if lines:
            parts.append(
                "Puntos clave temáticos que el guion debe cubrir o tocar (plantilla Prompt):\n" + "\n".join(lines)
            )
    return "\n\n".join(parts).strip()


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
    sys_e = str(row.get("system_instructions") or "").strip()
    usr_e = str(row.get("user_instructions") or "").strip()
    addon = _prompt_template_params_user_addon(row)
    if addon:
        usr_e = (usr_e + "\n\n" if usr_e else "") + "--- Catálogo Prompt (params_json) ---\n" + addon
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
    sys_e, usr_e = extras_from_template_row(row)
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


def _run_step_prompt(work_dir: Path, inputs: PipelineInputs) -> None:
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

    payload: dict[str, Any] = {
        "keywords": inputs.keywords,
        "context": inputs.context,
        "lang": inputs.lang,
        "minutes": inputs.minutes,
        "provider": inputs.provider,
        "model": inputs.model,
        "topic": (inputs.prompt_topic or "").strip(),
        "created_at": _now_iso(),
    }
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
            raise RuntimeError(
                "Fragmentación secuencial: no hay fragmentos pendientes. "
                "Marca un paso como no completado en la UI o pasa un índice explícito para regenerar."
            )
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
    text = generate_script(
        bp,
        provider=(merged.provider.strip() or None),
        model=(merged.model.strip() or None),
        system_extra=sys_x,
        user_extra=usr_eff.strip(),
        force_single_pass=True,
        per_fragment_segment=True,
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
        target_words = segment_word_target(float(target_m))
        cf_done = chunk_file(work_dir, idx)
        frag_txt = cf_done.read_text(encoding="utf-8") if cf_done.is_file() else ""
        frag_words = _sg._count_narrable_words(frag_txt)  # type: ignore[attr-defined]
        debug: dict[str, Any] = {
            "provider": merged.provider,
            "model": merged.model,
            "sequential_fragments": True,
            "fragment_index": idx,
            "fragment_label": label,
            "fragment_minute_weights": w_used,
            "target_minutes": float(merged.minutes),
            "effective_target_minutes": float(target_m),
            "chunk_outline_act1_only": False,
            "narrable_words": narrable_words,
            "fragment_narrable_words": frag_words,
            "target_min_words": target_words,
            "sentences_narrable": sentences,
            "broll_tags": broll,
            "broll_per_sentence_ratio": (broll / max(1, sentences)),
        }
        _write_json(_pipeline_dir(work_dir) / "script_writer_debug.json", debug)

        if (os.environ.get("VIDEOMAKER_SCRIPT_FAIL_ON_SHORT", "") or "").strip().lower() in {"1", "true", "yes", "on"}:
            if frag_words < target_words:
                raise RuntimeError(
                    f"Fragmento demasiado corto: {frag_words} palabras narrables (objetivo mínimo {target_words} para este fragmento)."
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
    text = generate_script(
        bp,
        provider=(merged.provider.strip() or None),
        model=(merged.model.strip() or None),
        system_extra=sys_x,
        user_extra=usr_x,
        force_single_pass=chunk_single,
    )

    # Debug de calidad/longitud: deja trazas en disco para diagnosticar por qué sale corto.
    try:
        from videomaker.llm import script_gen as _sg

        narrable_words = _sg._count_narrable_words(text)  # type: ignore[attr-defined]
        sentences = _sg._count_sentences_narrable(text)  # type: ignore[attr-defined]
        broll = _sg._count_broll_tags(text)  # type: ignore[attr-defined]
        target_words = _sg._target_words_for_minutes(float(target_m))  # type: ignore[attr-defined]
        debug: dict[str, Any] = {
            "provider": merged.provider,
            "model": merged.model,
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
    # Raíz de sesión: editor legacy, TTS/stock y `/api/script`.
    guion = work_dir / "guion.txt"
    guion.write_text(text, encoding="utf-8")
    write_script_bundle(work_dir, text)
    _persist_script_writer_template_to_prompt_artifact(work_dir, (merged.script_writer_template_id or "").strip() or None)
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
    # Clear any previous stop request at start.
    clear_pipeline_stop(work_dir)

    try:
        script_path: Path | None = None
        for sid, _title in PIPELINE_STEPS:
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

