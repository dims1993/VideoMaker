"""Contrapunto visual para prompts del gancho (ensayo en vídeo — imagen ≠ ilustración literal)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

_COUNTERPOINT_SYSTEM = """You write STILL IMAGE prompts for essay-style YouTube hooks (Midjourney/Flux).

DOCUMENTARY SEQUENCE (when sequence_context is provided):
- Output prompts for ONE ordered sequence, not isolated stock shots.
- You may receive a BATCH slice of a longer sequence; match continuity with prior shots/prompts listed.
- Follow each beat's sequence_block, shot_distance, and shot_angle exactly.
- Never two consecutive beats with the same distance+angle pair.
- Each prompt must deliver the beat's new_information_layer — do not repeat the previous subject/framing.
- Arc: intimate_close → medium_space → contrast_world → intimate_weight (close → medium → contrast cut → close with weight).

COLOR & LIGHT (mandatory in EVERY prompt string):
- Protagonist blocks (intimate_close, medium_space, intimate_weight): cool blue artificial light, harsh fluorescent, screen glow, deep shadows — NEVER warm amber.
- contrast_world block: warm amber interior, natural golden light, soft tungsten — NEVER cool blue phone glow.
- Each prompt MUST include one explicit temperature phrase from the beat's light_quality / color_temperature (e.g. "cool blue light", "warm amber interior", "harsh fluorescent").
- Match camera_motion_note when present (push-in vs pull-back vs static framing language in the still description).
- If is_anchor_shot: this is THE remembered hook image — decisive, simple, maximum clarity (app close / screen dark); static framing; do not clutter.

CRITICAL — DUAL CHANNEL:
- Voice carries the argument (facts, objects named in speech). The viewer HEARS that.
- Images carry emotion, subtext, or contrast. The viewer FEELS something the voice does NOT say.
- NEVER illustrate the spoken object literally. If narration mentions a calculator, the image must NOT be "person using calculator".
- FORBIDDEN: repeating the same information as the voice (redundant illustration).

THREE STRATEGIES (use the one given per beat):
1. counterpoint — show what CONTRASTS with the line (discipline spoken → affluent suburb; saving spoken → luxury cues).
2. intimate_subtext — solitude, fatigue, quiet stakes (window at night, unmade bed, still hands on table) without naming props from speech.
3. scale_escalation — move from intimate human detail toward systemic scale (street → blocks → city texture → abstract data mood) as hook progresses.
4. motif_echo — sparse, weighted recurrence of ONE visual motif (closed door, empty chair, dim screen glow) — not every scene.

OUTPUT RULES:
- English only. 28–48 words. One cinematic still frame.
- Include: place + explicit color temperature + light source + emotional micro-detail + lens feel (shallow DOF, 35mm, etc.).
- No stock phrases, no "B-roll of", no generic office/laptop/calculator unless strategy is counterpoint AND the CONTRAST requires it indirectly.
- Return ONLY a JSON array of strings, same length and order as input beats. No markdown."""


def counterpoint_llm_enabled() -> bool:
    raw = (os.environ.get("VIDEOMAKER_HOOK_COUNTERPOINT_LLM") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _strategy_for_beat(beat_index: int, total: int, beat: dict[str, Any] | None = None) -> str:
    if beat and beat.get("is_anchor_shot"):
        return "motif_echo"
    if total <= 1:
        return "intimate_subtext"
    t = beat_index / max(total - 1, 1)
    if t < 0.28:
        return "intimate_subtext"
    if t < 0.55:
        return "counterpoint"
    if t < 0.82:
        return "scale_escalation"
    return "motif_echo"


def _beat_brief(beat: dict[str, Any], *, beat_index: int, total: int) -> dict[str, Any]:
    return {
        "beat_index": beat_index,
        "strategy": _strategy_for_beat(beat_index, total, beat),
        "sequence_block": str(beat.get("sequence_block") or "").strip()[:40],
        "shot_distance": str(beat.get("shot_distance") or "").strip()[:30],
        "shot_angle": str(beat.get("shot_angle") or "").strip()[:30],
        "new_information_layer": str(beat.get("new_information_layer") or "").strip()[:120],
        "purpose": str(beat.get("purpose") or "").strip()[:80],
        "emotion": str(beat.get("emotion") or "").strip()[:40],
        "intensity": beat.get("intensity"),
        "pacing_role": str(beat.get("pacing_role") or "").strip()[:60],
        "retention_pattern": str(beat.get("retention_pattern") or "").strip()[:60],
        "hook_class": str(beat.get("hook_class") or "").strip()[:40],
        "scene_type": str(beat.get("scene_type") or "").strip()[:40],
        "color_temperature": str(beat.get("color_temperature") or "").strip()[:20],
        "light_quality": str(beat.get("light_quality") or "").strip()[:100],
        "required_light_phrase": str(
            beat.get("light_quality")
            or (beat.get("camera") or {}).get("lighting")
            or ""
        ).strip()[:100],
        "camera_motion": str(beat.get("camera_motion") or beat.get("motion") or "").strip()[:30],
        "camera_motion_note": str(beat.get("camera_motion_note") or "").strip()[:80],
        "shot_hierarchy": str(beat.get("shot_hierarchy") or "support").strip()[:20],
        "is_anchor_shot": bool(beat.get("is_anchor_shot")),
    }


def _fallback_prompt(brief: dict[str, Any], *, motif_hint: str = "") -> str:
    from videomaker.llm.hook_visual_sequence import merge_color_language_into_prompt
    from videomaker.llm.section_anchor_shot import _DEFAULT_HOOK_ANCHOR_VISUAL

    if brief.get("is_anchor_shot"):
        block = str(brief.get("sequence_block") or "intimate_weight").strip().lower()
        return merge_color_language_into_prompt(_DEFAULT_HOOK_ANCHOR_VISUAL, block, beat_index=0)

    block = str(brief.get("sequence_block") or "intimate_close").strip().lower()
    light = str(brief.get("required_light_phrase") or brief.get("light_quality") or "").strip()
    strategy = brief.get("strategy") or "intimate_subtext"
    emotion = str(brief.get("emotion") or "tension").lower()
    warm = block == "contrast_world"
    if strategy == "counterpoint" or warm:
        base = (
            "Wide suburban street at dusk, well-kept lawns and new cars in driveways, "
            "quiet material comfort, warm amber porch glow, natural golden window light, "
            "cinematic 35mm, shallow depth of field, chromatic contrast to cool isolation"
        )
    elif strategy == "scale_escalation":
        base = (
            "Elevated view of residential blocks fading into city grid at dusk, cool blue haze, "
            "harsh distant fluorescent grids, systems-scale mood, editorial documentary still, 35mm"
        )
    elif strategy == "motif_echo" and motif_hint:
        m = motif_hint[:60]
        base = (
            f"Cinematic still revisiting motif: {m}, accumulated weight, "
            "empty negative space, photorealistic, emotional restraint"
        )
    elif "fear" in emotion or "tension" in emotion:
        base = (
            "Small apartment kitchen late at night, person alone with still hands on table, "
            "quiet exhaustion, shallow DOF, film grain"
        )
    else:
        base = (
            "Bedroom window facing dark city, unmade bed edge in frame, "
            "solitude and mental fatigue, cinematic still, no literal props from speech"
        )
    if light and light.lower() not in base.lower():
        base = f"{base}, {light}"
    return merge_color_language_into_prompt(base, block, beat_index=int(brief.get("beat_index") or 0))


def _motif_from_router(router: dict[str, Any]) -> str:
    ret = router.get("retention_analysis") if isinstance(router.get("retention_analysis"), dict) else {}
    rationale = str(ret.get("scroll_stop_rationale") or "").strip()
    if rationale:
        return rationale[:120]
    patterns = ret.get("patterns_detected")
    if isinstance(patterns, list) and patterns:
        return ", ".join(str(p) for p in patterns[:3])
    return "closed door or dim screen glow"


def _call_counterpoint_llm(
    briefs: list[dict[str, Any]],
    *,
    provider: str | None,
    model: str | None,
    motif_hint: str,
    sequence_context: str = "",
) -> list[str]:
    from videomaker.llm.avatar_prompt_writer import _call_llm, _parse_llm_array

    payload: dict[str, Any] = {
        "motif_for_echo_beats": motif_hint,
        "beats": briefs,
        "reminder": (
            "Do NOT use narration objects literally. Match shot_distance/angle AND required_light_phrase "
            "per beat. Every string MUST include explicit color temperature. Output JSON string array only."
        ),
    }
    if sequence_context.strip():
        payload["sequence_context"] = sequence_context.strip()[:4000]
    user = json.dumps(payload, ensure_ascii=False)
    resolved_provider = (provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER", "openai")).lower()
    resolved_model = model or (
        os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
        if resolved_provider == "ollama"
        else os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    )
    try:
        temp = float(os.environ.get("VIDEOMAKER_HOOK_COUNTERPOINT_TEMPERATURE", "0.75"))
    except ValueError:
        temp = 0.75
    raw = _call_llm(
        system=_COUNTERPOINT_SYSTEM,
        user=user,
        provider=resolved_provider,
        model=resolved_model,
        temperature=temp,
    )
    parsed = _parse_llm_array(raw)
    out: list[str] = []
    from videomaker.llm.hook_visual_sequence import merge_color_language_into_prompt

    for i, item in enumerate(parsed):
        if isinstance(item, str) and item.strip():
            block = str(briefs[i].get("sequence_block") or "intimate_close")
            out.append(
                merge_color_language_into_prompt(
                    item.strip(),
                    block,
                    beat_index=int(briefs[i].get("beat_index") or i),
                )[:900]
            )
        elif isinstance(item, dict):
            p = str(item.get("prompt") or item.get("ai_prompt") or item.get("image_prompt") or "").strip()
            if p:
                block = str(briefs[i].get("sequence_block") or "intimate_close")
                out.append(
                    merge_color_language_into_prompt(
                        p,
                        block,
                        beat_index=int(briefs[i].get("beat_index") or i),
                    )[:900]
                )
        if len(out) > i:
            continue
        out.append(_fallback_prompt(briefs[i], motif_hint=motif_hint))
    while len(out) < len(briefs):
        out.append(_fallback_prompt(briefs[len(out)], motif_hint=motif_hint))
    return out[: len(briefs)]


def _is_literal_stock(text: str) -> bool:
    t = (text or "").lower()
    if _is_stock_phrase(t):
        return True
    literal = (
        r"\bcalculator\b",
        r"\bmortgage\b",
        r"\bzillow\b",
        r"\bspreadsheet\b",
        r"\bopening\b.*\bapp\b",
        r"\bphone screen showing\b",
        r"\bperson (using|opening|checking)\b",
    )
    return any(re.search(p, t) for p in literal)


def _is_stock_phrase(t: str) -> bool:
    from videomaker.llm.hook_retention_router import _is_stock_footage_prompt

    return _is_stock_footage_prompt(t)


def enrich_hook_image_prompt_rows(
    rows: list[dict[str, Any]],
    router: dict[str, Any],
    *,
    provider: str | None = None,
    model: str | None = None,
    use_llm: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Reescribe ``ai_prompt`` de filas hook insert (y situación avatar del gancho) con contrapunto.
    No pasa el texto narrado al LLM — solo metadata emocional del beat.
    """
    targets = [
        (i, r)
        for i, r in enumerate(rows)
        if isinstance(r, dict)
        and str(r.get("act") or "") == "hook"
        and str(r.get("track") or "") != "avatar"
    ]
    if not targets:
        return rows, {"applied": False, "reason": "no_hook_rows"}

    beats_raw = router.get("micro_beats") if isinstance(router.get("micro_beats"), list) else []
    beat_by_idx: dict[int, dict[str, Any]] = {}
    for b in beats_raw:
        if isinstance(b, dict):
            beat_by_idx[int(b.get("index", len(beat_by_idx)))] = b

    motif = _motif_from_router(router)
    seq_plan = router.get("visual_sequence_plan") if isinstance(router.get("visual_sequence_plan"), dict) else None
    from videomaker.llm.hook_visual_sequence import sequence_context_for_counterpoint_batch

    n = len(targets)
    briefs = []
    index_map: list[tuple[int, int]] = []
    ordered_beats: list[dict[str, Any]] = []
    for seq, (row_i, row) in enumerate(targets):
        role = str(row.get("role") or "")
        m = re.search(r"hook_(?:beat|avatar)_(\d+)", role)
        beat_idx = int(m.group(1)) if m else seq
        beat = beat_by_idx.get(beat_idx, {})
        ordered_beats.append(beat if isinstance(beat, dict) else {})
        briefs.append(_beat_brief(beat, beat_index=seq, total=n))
        index_map.append((row_i, seq))

    llm_on = counterpoint_llm_enabled() if use_llm is None else bool(use_llm)
    prompts: list[str]
    method = "fallback"
    if llm_on and briefs:
        batch_size = 10
        prompts = []
        try:
            for start in range(0, len(briefs), batch_size):
                end = min(start + batch_size, len(briefs))
                chunk = briefs[start:end]
                batch_ctx = sequence_context_for_counterpoint_batch(
                    ordered_beats,
                    seq_plan,
                    batch_start=start,
                    batch_end=end,
                    prior_prompts=prompts if start > 0 else None,
                )
                prompts.extend(
                    _call_counterpoint_llm(
                        chunk,
                        provider=provider,
                        model=model,
                        motif_hint=motif,
                        sequence_context=batch_ctx,
                    )
                )
            method = "llm_counterpoint"
        except Exception:
            prompts = [_fallback_prompt(b, motif_hint=motif) for b in briefs]
            method = "fallback_after_error"
    else:
        prompts = [_fallback_prompt(b, motif_hint=motif) for b in briefs]

    from videomaker.llm.hook_visual_sequence import merge_color_language_into_prompt

    out = [dict(r) if isinstance(r, dict) else r for r in rows]
    fixes = 0
    for (row_i, seq), prompt in zip(index_map, prompts, strict=False):
        row = out[row_i]
        if not isinstance(row, dict):
            continue
        old = str(row.get("ai_prompt") or row.get("text") or "").strip()
        if old and not _is_literal_stock(old) and method != "llm_counterpoint":
            continue
        block = str(briefs[seq].get("sequence_block") or "intimate_close")
        prompt = merge_color_language_into_prompt(
            prompt,
            block,
            beat_index=int(briefs[seq].get("beat_index") or seq),
        )
        row["ai_prompt"] = prompt
        row["text"] = prompt
        row["scene_prompt_en"] = prompt
        row["prompt_style"] = "essay_counterpoint"
        row["visual_strategy"] = briefs[seq].get("strategy")
        if old:
            row["ai_prompt_literal_source"] = old[:400]
        fixes += 1

    meta = {
        "applied": True,
        "method": method,
        "beats_rewritten": fixes,
        "motif_hint": motif,
        "strategies": [b.get("strategy") for b in briefs],
        "sequence_context_batches": (len(briefs) + 9) // 10 if briefs else 0,
    }
    return out, meta


def enrich_hook_router_beats(router: dict[str, Any], *, provider: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Opcional: reescribe micro_beats del router antes de IPW (útil si regeneras hook)."""
    beats = router.get("micro_beats")
    if not isinstance(beats, list):
        return router
    rows = [
        {
            "act": "hook",
            "track": "insert",
            "role": f"hook_beat_{int(b.get('index', i))}",
            "ai_prompt": str(b.get("image_prompt_seed") or b.get("visual_description") or ""),
        }
        for i, b in enumerate(beats)
        if isinstance(b, dict)
    ]
    new_rows, meta = enrich_hook_image_prompt_rows(rows, router, provider=provider, model=model)
    out = dict(router)
    out_beats = []
    for i, b in enumerate(beats):
        if not isinstance(b, dict):
            continue
        nb = dict(b)
        if i < len(new_rows) and isinstance(new_rows[i], dict):
            p = str(new_rows[i].get("ai_prompt") or "").strip()
            if p:
                nb["visual_description"] = p
                nb["image_prompt_seed"] = p
                nb["prompt_style"] = "essay_counterpoint"
        out_beats.append(nb)
    out["micro_beats"] = out_beats
    out["hook_counterpoint_meta"] = meta
    return out
