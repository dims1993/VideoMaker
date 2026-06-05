"""Muestra de validación: pocos prompts avatar desde routers → image_prompts.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from videomaker.llm.body_scene_router import read_body_macro_beats
from videomaker.llm.router_driven_image_prompts import (
    _beat_weight,
    _macro_beat_to_prompt_row,
    build_hook_prompt_rows,
)


def _body_router_context(work_dir: Path) -> tuple[str, str]:
    br_path = work_dir / "pipeline" / "body_scene_router.json"
    router: dict[str, Any] = {}
    if br_path.is_file():
        try:
            router = json.loads(br_path.read_text(encoding="utf-8"))
        except Exception:
            router = {}
    ia_kw = ""
    raw_kw = router.get("ia_keywords_body")
    if isinstance(raw_kw, list):
        ia_kw = ", ".join(str(x).strip() for x in raw_kw[:6] if str(x).strip())
    elif isinstance(raw_kw, str):
        ia_kw = raw_kw.strip()
    label = str(router.get("visual_style_inherited") or "").strip()
    return ia_kw, label


def list_validation_candidates(work_dir: Path, *, limit: int = 24) -> list[dict[str, Any]]:
    """Candidatos avatar ordenados: gancho primero, luego cuerpo (macro_beats)."""
    out: list[dict[str, Any]] = []
    st = _read_ipw_settings(work_dir)
    use_avatar = bool(st.get("use_avatar"))

    try:
        hook_rows, _ = build_hook_prompt_rows(work_dir, use_avatar=use_avatar)
        for row in hook_rows:
            if str(row.get("track") or "").lower() == "avatar":
                out.append(_candidate_from_row(row, source="hook"))
    except ValueError:
        pass

    beats = read_body_macro_beats(work_dir)
    if beats:
        ia_kw, label = _body_router_context(work_dir)
        weights = [_beat_weight(b) for b in beats]
        for i, beat in enumerate(beats):
            if str(beat.get("track") or "avatar").strip().lower() != "avatar":
                continue
            row = _macro_beat_to_prompt_row(
                beat,
                beat_index=i,
                weights=weights,
                order=i + 1,
                ia_kw=ia_kw,
                label=label,
            )
            out.append(_candidate_from_row(row, source="body"))

    return out[: max(1, int(limit))]


def _candidate_from_row(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    anchor = str(row.get("text_anchor") or row.get("segment_text") or "").strip()
    return {
        "id": str(row.get("id") or ""),
        "source": source,
        "act": str(row.get("act") or ""),
        "track": str(row.get("track") or "avatar"),
        "text_anchor": anchor[:500],
        "has_ai_prompt": bool(str(row.get("ai_prompt") or "").strip()),
    }


def _read_ipw_settings(work_dir: Path) -> dict[str, Any]:
    from videomaker.core.image_prompt_writer_settings_store import read_image_prompt_writer_settings

    return read_image_prompt_writer_settings(work_dir)


def _global_style_from_work(work_dir: Path) -> dict[str, Any]:
    from videomaker.scene_editor.scene_visual_settings_store import read_scene_visual_settings

    vs = read_scene_visual_settings(work_dir)
    gs: dict[str, Any] = {}
    for key in (
        "base_style_en",
        "protagonist_en",
        "avoid_en",
        "aspect_ratio",
        "output_spec",
        "protagonist_action_rules_en",
    ):
        val = vs.get(key)
        if isinstance(val, str) and val.strip():
            gs[key] = val.strip()
    return gs


def _read_existing_bundle(work_dir: Path) -> dict[str, Any] | None:
    p = work_dir / "pipeline" / "image_prompts.json"
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _merge_validation_into_prompts(
    existing_prompts: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Fusiona filas de validación en el bundle existente.
    Mismo ``id`` → sustituye; ``id`` nuevo → añade al final.
    El resto de prompts (inserts, etc.) se conservan.
    """
    merged: list[dict[str, Any]] = [dict(p) for p in existing_prompts if isinstance(p, dict)]
    index_by_id: dict[str, int] = {}
    for i, p in enumerate(merged):
        pid = str(p.get("id") or "").strip()
        if pid:
            index_by_id[pid] = i

    replaced = 0
    added = 0
    for row in new_rows:
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        item = dict(row)
        item["selected"] = True
        if rid in index_by_id:
            merged[index_by_id[rid]] = item
            replaced += 1
        else:
            merged.append(item)
            index_by_id[rid] = len(merged) - 1
            added += 1

    for i, p in enumerate(merged, start=1):
        p["order"] = i

    return merged, replaced, added


def _rows_for_candidate_ids(work_dir: Path, candidate_ids: list[str], *, use_avatar: bool) -> list[dict[str, Any]]:
    wanted = {str(x).strip() for x in candidate_ids if str(x).strip()}
    if not wanted:
        raise ValueError("Indica al menos un candidato (candidate_ids).")

    by_id: dict[str, dict[str, Any]] = {}

    try:
        hook_rows, _ = build_hook_prompt_rows(work_dir, use_avatar=use_avatar)
        for row in hook_rows:
            rid = str(row.get("id") or "")
            if rid in wanted:
                by_id[rid] = dict(row)
    except ValueError:
        pass

    beats = read_body_macro_beats(work_dir)
    if beats:
        ia_kw, label = _body_router_context(work_dir)
        weights = [_beat_weight(b) for b in beats]
        for i, beat in enumerate(beats):
            row = _macro_beat_to_prompt_row(
                beat,
                beat_index=i,
                weights=weights,
                order=i + 1,
                ia_kw=ia_kw,
                label=label,
            )
            rid = str(row.get("id") or "")
            if rid in wanted:
                by_id[rid] = row

    missing = wanted - set(by_id)
    if missing:
        raise ValueError(f"Candidatos no encontrados en routers: {', '.join(sorted(missing))}")

    # Conservar orden de candidate_ids
    return [by_id[cid] for cid in candidate_ids if cid in by_id]


def build_validation_sample(
    work_dir: Path,
    candidate_ids: list[str],
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Genera LLM solo para filas avatar seleccionadas y escribe image_prompts.json (muestra).
    Cada fila lleva ``selected: true`` por defecto.
    """
    from videomaker.core.visual_style_presets_store import prepare_avatar_mode_for_work
    from videomaker.llm.avatar_prompt_writer import AVATAR_DEFAULT_DESCRIPTION
    from videomaker.llm.router_driven_image_prompts import _enrich_avatar_prompt_rows
    from videomaker.pipeline.runner import save_manual_image_prompts_bundle

    st = _read_ipw_settings(work_dir)
    if not st.get("use_avatar"):
        raise ValueError("Activa modo avatar y guarda ajustes antes de la muestra de validación.")

    ctx = prepare_avatar_mode_for_work(work_dir)
    use_avatar = True
    rows = _rows_for_candidate_ids(work_dir, candidate_ids, use_avatar=use_avatar)

    for row in rows:
        if str(row.get("track") or "").lower() == "avatar" and not str(row.get("ai_prompt") or "").strip():
            row["_needs_avatar_llm"] = True

    desc = str(ctx.get("avatar_description") or AVATAR_DEFAULT_DESCRIPTION).strip()
    _enrich_avatar_prompt_rows(
        work_dir,
        rows,
        avatar_description=desc,
        scene_visual_settings=ctx.get("scene_visual_settings"),
        target_generator=str(st.get("target_generator") or "gemini"),
        provider=provider,
        model=model,
    )

    for row in rows:
        row.pop("_needs_avatar_llm", None)

    existing = _read_existing_bundle(work_dir)
    if existing and isinstance(existing.get("prompts"), list):
        prev_prompts = [p for p in existing["prompts"] if isinstance(p, dict)]
        merged_prompts, replaced, added = _merge_validation_into_prompts(prev_prompts, rows)
        bundle: dict[str, Any] = dict(existing)
    else:
        merged_prompts, replaced, added = _merge_validation_into_prompts([], rows)
        bundle = {
            "version": 4,
            "hybrid_mode": True,
            "routing": {
                "hook": "pipeline/hook_scene_router.json",
                "body": "pipeline/body_scene_router.json",
            },
        }

    gs = bundle.get("global_style")
    if not isinstance(gs, dict) or not gs:
        bundle["global_style"] = _global_style_from_work(work_dir)
    bundle["target_generator"] = str(st.get("target_generator") or bundle.get("target_generator") or "gemini")
    bundle["prompts"] = merged_prompts
    bundle["total_prompts"] = len(merged_prompts)
    bundle["validation_sample"] = True
    bundle["validation_merges"] = bundle.get("validation_merges") or []
    if not isinstance(bundle["validation_merges"], list):
        bundle["validation_merges"] = []
    bundle["validation_merges"].append(
        {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "candidate_ids": list(candidate_ids),
            "added": added,
            "replaced": replaced,
            "total_after": len(merged_prompts),
        }
    )
    if bundle.get("source") not in ("router_driven", "avatar_hybrid", "validation_sample"):
        bundle.setdefault("source", "validation_sample")

    save_manual_image_prompts_bundle(work_dir, bundle)

    from videomaker.pipeline.runner import _set_step

    parts = []
    if added:
        parts.append(f"{added} añadido(s)")
    if replaced:
        parts.append(f"{replaced} actualizado(s)")
    detail_extra = f" ({', '.join(parts)})" if parts else ""
    _set_step(
        work_dir,
        "image_prompt_writer",
        state="done",
        detail=f"Salida fusionada: {len(merged_prompts)} prompts en total{detail_extra}.",
    )

    return {
        "path": "pipeline/image_prompts.json",
        "prompt_count": len(merged_prompts),
        "added": added,
        "replaced": replaced,
        "candidate_ids": candidate_ids,
        "validation_sample": True,
        "merged": bool(existing),
    }
