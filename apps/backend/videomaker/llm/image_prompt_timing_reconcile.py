"""Reconcilia duraciones de image_prompts con audio real (Scene Editor / audio_timeline)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from datetime import datetime, timezone

from videomaker.scene_editor.audio_service import _chunk_gap_ms

# Plano más corto legible (~0,8 s); por debajo se roba tiempo a vecinos (prioridad: avatar).
MIN_SHOT_DURATION_MS = 800
MIN_SHOT_DURATION_S = 0.8


def _section_is_hook(section: str | None) -> bool:
    s = (section or "").strip().lower()
    if not s:
        return False
    if s == "hook":
        return True
    return any(k in s for k in ("introducción", "introduccion", "gancho", "intro "))


def _prompt_weight(prompt: dict[str, Any]) -> float:
    timing = prompt.get("timing")
    if isinstance(timing, dict):
        w = timing.get("weight")
        if isinstance(w, (int, float)) and float(w) > 0:
            return float(w)
        est = timing.get("duration_sec_estimated") or timing.get("duration_sec")
        if isinstance(est, (int, float)) and float(est) > 0:
            return float(est)
    hint = prompt.get("duration_hint_s")
    if isinstance(hint, (int, float)) and float(hint) > 0:
        return float(hint)
    return 1.0


def _is_hook_micro_prompt(prompt: dict[str, Any]) -> bool:
    if str(prompt.get("layer") or "") == "hook_micro_beat":
        return True
    role = str(prompt.get("role") or "")
    return role.startswith("hook_beat_")


def _load_timeline(work_dir: Path) -> dict[str, Any] | None:
    path = work_dir / "pipeline" / "audio_timeline.json"
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("events"), list):
                return raw
        except (OSError, json.JSONDecodeError):
            pass
    try:
        from videomaker.scene_editor.audio_timeline import (
            build_audio_timeline,
            write_audio_timeline_artifact,
        )

        timeline = build_audio_timeline(work_dir)
        write_audio_timeline_artifact(work_dir, timeline)
        return timeline
    except ValueError:
        return None


def _chunk_events(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in timeline.get("events") or []:
        if isinstance(e, dict) and e.get("kind") == "chunk":
            out.append(e)
    return out


def _pool_ms_from_chunks(chunks: list[dict[str, Any]], *, gap_ms: int) -> int:
    if not chunks:
        return 0
    total = sum(int(float(c.get("duration_s") or 0) * 1000) for c in chunks)
    if len(chunks) > 1 and gap_ms > 0:
        total += gap_ms * (len(chunks) - 1)
    return max(0, total)


def _distribute_ms(total_ms: int, prompts: list[dict[str, Any]]) -> list[int]:
    if not prompts or total_ms <= 0:
        return [0] * len(prompts)
    weights = [_prompt_weight(p) for p in prompts]
    wsum = sum(weights) or float(len(prompts))
    out: list[int] = []
    assigned = 0
    for i, w in enumerate(weights):
        if i == len(prompts) - 1:
            ms = max(50, total_ms - assigned)
        else:
            ms = max(50, int(round(total_ms * (w / wsum))))
            assigned += ms
        out.append(ms)
    return out


def _is_avatar_track(prompt: dict[str, Any]) -> bool:
    return str(prompt.get("track") or "avatar").strip().lower() != "insert"


def _pick_duration_donor(
    short_index: int,
    ms: list[int],
    prompts: list[dict[str, Any]],
    *,
    min_ms: int,
) -> int | None:
    """Índice del plano que puede ceder ms; prioriza avatar adyacente a Alex."""
    n = len(ms)
    candidates: list[tuple[int, int, int]] = []
    for j in range(n):
        if j == short_index:
            continue
        surplus = ms[j] - min_ms
        if surplus <= 0:
            continue
        dist = abs(j - short_index)
        if dist == 1:
            tier = 0 if _is_avatar_track(prompts[j]) else 1
        elif _is_avatar_track(prompts[j]):
            tier = 2
        else:
            tier = 3
        candidates.append((tier, dist, -surplus, j))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][3]


def _enforce_min_durations_ms(
    ms_list: list[int],
    prompts: list[dict[str, Any]],
    *,
    pool_ms: int,
    min_ms: int = MIN_SHOT_DURATION_MS,
) -> list[int]:
    """
    Garantiza ``min_ms`` por plano sin cambiar la suma del pool.

    Si un insert queda demasiado corto (p. ej. peso 0,1), roba tiempo al vecino
    avatar cuando sea posible.
    """
    if not ms_list or pool_ms <= 0:
        return ms_list
    n = len(ms_list)
    if n * min_ms > pool_ms:
        # Pool insuficiente para todos los mínimos: reparto equitativo acotado.
        fair = max(50, pool_ms // n)
        ms = [fair] * n
        ms[-1] += pool_ms - sum(ms)
        return ms

    ms = list(ms_list)
    guard = 0
    while guard < n * 32:
        guard += 1
        short_indices = [i for i, v in enumerate(ms) if v < min_ms]
        if not short_indices:
            break
        i = short_indices[0]
        need = min_ms - ms[i]
        donor = _pick_duration_donor(i, ms, prompts, min_ms=min_ms)
        if donor is None:
            break
        give = min(need, ms[donor] - min_ms)
        if give <= 0:
            break
        ms[i] += give
        ms[donor] -= give

    drift = pool_ms - sum(ms)
    if drift and n:
        ms[-1] += drift
        if ms[-1] < min_ms and n > 1:
            for j in range(n - 2, -1, -1):
                if ms[j] > min_ms:
                    take = min(ms[j] - min_ms, min_ms - ms[-1])
                    ms[j] -= take
                    ms[-1] += take
                    break

    return ms


def _apply_ms_to_prompt(
    prompt: dict[str, Any],
    ms: int,
    *,
    audio_start_s: float | None = None,
    audio_end_s: float | None = None,
    chunk_id: str | None = None,
) -> None:
    prompt["duration_ms"] = ms
    prompt["duration_hint_s"] = max(1, int(round(ms / 1000.0)))
    timing = prompt.get("timing")
    if not isinstance(timing, dict):
        timing = {}
        prompt["timing"] = timing
    timing["mode"] = timing.get("mode") or "relative_hook"
    timing["reconciled"] = True
    timing["duration_sec"] = round(ms / 1000.0, 3)
    if audio_start_s is not None:
        timing["audio_start_s"] = round(audio_start_s, 3)
    if audio_end_s is not None:
        timing["audio_end_s"] = round(audio_end_s, 3)
    if chunk_id:
        prompt["chunk_id"] = chunk_id


def reconcile_image_prompts_with_audio(work_dir: Path, *, write: bool = True) -> dict[str, Any]:
    """
    Reparte duraciones reales del Scene Editor sobre prompts (gancho por peso relativo del router).

    Los ``start_sec`` del Hook Router son solo estimaciones; tras TTS se usan
    ``audio_timeline.json`` o chunks medidos.
    """
    ip_path = work_dir / "pipeline" / "image_prompts.json"
    if not ip_path.is_file():
        raise ValueError("Falta pipeline/image_prompts.json.")

    try:
        bundle = json.loads(ip_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(str(e)) from e
    if not isinstance(bundle, dict):
        raise ValueError("image_prompts.json inválido.")

    prompts_raw = bundle.get("prompts")
    if not isinstance(prompts_raw, list) or not prompts_raw:
        raise ValueError("image_prompts.json no contiene prompts.")

    timeline = _load_timeline(work_dir)
    if not timeline:
        raise ValueError(
            "No hay audio medido. Genera TTS en Scene Editor y unifica narracion.wav."
        )

    gap_ms = int(timeline.get("chunk_gap_ms") or _chunk_gap_ms(None))
    chunk_events = _chunk_events(timeline)
    if not chunk_events:
        raise ValueError("audio_timeline sin bloques de narración.")

    hook_chunks = [c for c in chunk_events if _section_is_hook(c.get("section"))]
    body_chunks = [c for c in chunk_events if not _section_is_hook(c.get("section"))]

    prompts = [deepcopy(p) for p in prompts_raw if isinstance(p, dict)]
    hook_prompts = [p for p in prompts if _is_hook_micro_prompt(p)]
    intro_prompts = [p for p in prompts if str(p.get("id") or "") == "intro"]
    outro_prompts = [p for p in prompts if str(p.get("id") or "") == "outro"]
    body_prompts = [
        p
        for p in prompts
        if p not in hook_prompts and p not in intro_prompts and p not in outro_prompts
    ]

    hook_pool_ms = _pool_ms_from_chunks(hook_chunks, gap_ms=gap_ms)
    body_pool_ms = _pool_ms_from_chunks(body_chunks, gap_ms=gap_ms)

    density_plan = None
    try:
        from videomaker.llm.body_scene_router import (
            _extract_body_text,
            _extract_hook_text_for_plan,
        )
        from videomaker.llm.section_density_plan import build_section_density_plan

        script_p = work_dir / "pipeline" / "script.txt"
        script_txt = script_p.read_text(encoding="utf-8") if script_p.is_file() else ""
        density_plan = build_section_density_plan(
            work_dir,
            script_text=script_txt,
            hook_text=_extract_hook_text_for_plan(script_txt),
            body_text=_extract_body_text(script_txt),
        )
    except Exception:
        density_plan = None

    hook_start_s = float(hook_chunks[0]["start_s"]) if hook_chunks else 0.0
    cursor_s = hook_start_s

    min_floor_adjustments = 0

    if hook_prompts and hook_pool_ms > 0:
        original_hook = list(hook_prompts)
        raw_hook_ms = _distribute_ms(hook_pool_ms, hook_prompts)
        hook_ms = _enforce_min_durations_ms(
            raw_hook_ms,
            hook_prompts,
            pool_ms=hook_pool_ms,
        )
        if density_plan:
            from videomaker.llm.body_audio_density import split_oversized_prompt_assignments

            hook_prompts, hook_ms = split_oversized_prompt_assignments(
                work_dir,
                hook_prompts,
                hook_ms,
                section="hook",
                plan=density_plan,
            )
            hook_indices = [i for i, p in enumerate(prompts) if p in original_hook]
            if hook_indices:
                first_hook = hook_indices[0]
                for i in reversed(hook_indices):
                    del prompts[i]
                for offset, (p, _ms) in enumerate(zip(hook_prompts, hook_ms, strict=False)):
                    prompts.insert(first_hook + offset, p)
        min_floor_adjustments += sum(1 for a, b in zip(hook_ms, raw_hook_ms, strict=True) if a != b)
        for p, ms in zip(hook_prompts, hook_ms, strict=False):
            end_s = cursor_s + ms / 1000.0
            _apply_ms_to_prompt(p, ms, audio_start_s=cursor_s, audio_end_s=end_s)
            cursor_s = end_s
    elif hook_prompts and body_pool_ms > 0:
        # Gancho sin sección hook en chunks: primer bloque del timeline
        first_ms = int(float(chunk_events[0].get("duration_s") or 0) * 1000)
        hook_ms = _enforce_min_durations_ms(
            _distribute_ms(first_ms, hook_prompts),
            hook_prompts,
            pool_ms=first_ms,
        )
        for p, ms in zip(hook_prompts, hook_ms, strict=False):
            _apply_ms_to_prompt(p, ms)

    body_cursor = float(body_chunks[0]["start_s"]) if body_chunks else cursor_s
    if intro_prompts and hook_chunks:
        intro_ms = int(float(hook_chunks[-1].get("duration_s") or 0) * 1000)
        intro_ms = min(intro_ms, max(1500, hook_pool_ms // max(1, len(hook_chunks))))
        for p in intro_prompts:
            _apply_ms_to_prompt(p, intro_ms, audio_start_s=body_cursor, audio_end_s=body_cursor + intro_ms / 1000.0)
    elif intro_prompts and body_pool_ms > 0:
        ms_list = _distribute_ms(min(body_pool_ms, 8000), intro_prompts)
        for p, ms in zip(intro_prompts, ms_list, strict=False):
            _apply_ms_to_prompt(p, ms)

    if body_prompts and body_pool_ms > 0:
        if len(body_prompts) == len(body_chunks):
            t = float(body_chunks[0]["start_s"])
            for p, ch in zip(body_prompts, body_chunks, strict=False):
                ms = max(50, int(float(ch.get("duration_s") or 0) * 1000))
                end = t + ms / 1000.0
                _apply_ms_to_prompt(
                    p,
                    ms,
                    audio_start_s=t,
                    audio_end_s=end,
                    chunk_id=str(ch.get("chunk_id") or "") or None,
                )
                t = end + gap_ms / 1000.0
        else:
            t = float(body_chunks[0]["start_s"]) if body_chunks else body_cursor
            original_body = list(body_prompts)
            raw_body_ms = _distribute_ms(body_pool_ms, body_prompts)
            body_ms = _enforce_min_durations_ms(
                raw_body_ms,
                body_prompts,
                pool_ms=body_pool_ms,
            )
            if density_plan:
                from videomaker.llm.body_audio_density import split_oversized_prompt_assignments

                body_prompts, body_ms = split_oversized_prompt_assignments(
                    work_dir,
                    body_prompts,
                    body_ms,
                    section="body",
                    plan=density_plan,
                )
            body_indices = [i for i, p in enumerate(prompts) if p in original_body]
            if body_indices:
                first_body = body_indices[0]
                for i in reversed(body_indices):
                    del prompts[i]
                for offset, (p, ms) in enumerate(zip(body_prompts, body_ms, strict=False)):
                    prompts.insert(first_body + offset, p)
            for p, ms in zip(body_prompts, body_ms, strict=False):
                end = t + ms / 1000.0
                _apply_ms_to_prompt(p, ms, audio_start_s=t, audio_end_s=end)
                t = end

    if outro_prompts and body_chunks:
        last = body_chunks[-1]
        ms = max(50, int(float(last.get("duration_s") or 0) * 1000))
        for p in outro_prompts:
            _apply_ms_to_prompt(
                p,
                ms,
                audio_start_s=float(last.get("start_s") or 0),
                audio_end_s=float(last.get("end_s") or 0),
                chunk_id=str(last.get("chunk_id") or "") or None,
            )

    bundle_out = deepcopy(bundle)
    bundle_out["prompts"] = prompts
    bundle_out["timing_reconciled"] = True
    bundle_out["timing_reconciled_source"] = str(timeline.get("source") or "audio_timeline")
    bundle_out["timing_reconciled_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if write:
        ip_path.write_text(json.dumps(bundle_out, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "hook_prompts": len(hook_prompts),
        "body_prompts": len(body_prompts),
        "hook_pool_ms": hook_pool_ms,
        "body_pool_ms": body_pool_ms,
        "hook_chunks": len(hook_chunks),
        "body_chunks": len(body_chunks),
        "min_shot_duration_s": MIN_SHOT_DURATION_S,
        "min_duration_floor_adjustments": min_floor_adjustments,
    }


def try_reconcile_image_prompts(work_dir: Path) -> dict[str, Any] | None:
    """Reconcilia si hay audio; devuelve None si aún no hay TTS."""
    try:
        return reconcile_image_prompts_with_audio(work_dir, write=True)
    except ValueError:
        return None


def reconcile_manifest_from_prompts(work_dir: Path) -> dict[str, Any] | None:
    """Actualiza images_generation.json tras reconciliar prompts."""
    from videomaker.pipeline.image_prompts_to_images import (
        build_images_generation_manifest,
        push_image_prompts_to_images_generation,
    )

    ip_path = work_dir / "pipeline" / "image_prompts.json"
    if not ip_path.is_file():
        return None
    try:
        bundle = json.loads(ip_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not bundle.get("timing_reconciled"):
        return None
    return push_image_prompts_to_images_generation(work_dir)
