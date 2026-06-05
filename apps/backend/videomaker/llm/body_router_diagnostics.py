"""Diagnóstico de macro_beats del Body Scene Router."""

from __future__ import annotations

import re
from typing import Any

from videomaker.llm.body_macro_beats import _is_complete_sentence, _word_count
from videomaker.llm.section_density_plan import SectionDensityPlan, build_section_density_plan


def _normalize_anchor(a: str) -> str:
    t = re.sub(r"\s+", " ", (a or "").lower().strip())
    return re.sub(r"[^\w\s]", "", t)


def _find_fragment_beats(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for b in beats:
        anchor = str(b.get("text_anchor") or "").strip()
        if not anchor:
            continue
        if not _is_complete_sentence(anchor) and _word_count(anchor) < 14:
            out.append(
                {
                    "index": b.get("index"),
                    "track": b.get("track"),
                    "preview": anchor[:100],
                }
            )
    return out


def _find_duplicate_pairs(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    norms = [_normalize_anchor(str(b.get("text_anchor") or "")) for b in beats]
    for i in range(len(beats)):
        if not norms[i]:
            continue
        wi = set(norms[i].split())
        for j in range(i + 1, len(beats)):
            if not norms[j]:
                continue
            inter = len(wi & set(norms[j].split()))
            if inter >= min(8, len(wi) // 2, len(norms[j].split()) // 2):
                pairs.append(
                    {
                        "a": i,
                        "b": j,
                        "shared_words": inter,
                        "preview_a": str(beats[i].get("text_anchor") or "")[:80],
                        "preview_b": str(beats[j].get("text_anchor") or "")[:80],
                    }
                )
    return pairs[:12]


def analyze_body_router_bundle(
    bundle: dict[str, Any],
    *,
    work_dir: Any = None,
    body_text: str = "",
    plan: SectionDensityPlan | None = None,
) -> dict[str, Any]:
    beats = bundle.get("macro_beats") if isinstance(bundle.get("macro_beats"), list) else []
    beats = [b for b in beats if isinstance(b, dict)]
    tracks = {"avatar": 0, "insert": 0, "other": 0}
    for b in beats:
        t = str(b.get("track") or "").strip().lower()
        if t in tracks:
            tracks[t] += 1
        else:
            tracks["other"] += 1

    split_max_hold = sum(1 for b in beats if b.get("split_reason") == "max_hold")
    fragments = _find_fragment_beats(beats)
    duplicates = _find_duplicate_pairs(beats)

    density: dict[str, Any] = {}
    warnings: list[str] = []
    if work_dir is not None:
        from pathlib import Path

        wd = Path(work_dir)
        plan = plan or build_section_density_plan(wd, body_text=body_text)
        target = plan.body_target_images
        density = {
            "body_audio_pool_s": plan.body_pool_s,
            "body_audio_pool_min": round(plan.body_pool_s / 60, 1),
            "hook_target_images": plan.hook_target_images,
            "body_target_images": plan.body_target_images,
            "total_target_images": plan.total_target_images,
            "hook_target_hold_s": plan.hook_target_hold_s,
            "body_target_hold_s": plan.body_target_hold_s,
            "body_max_hold_s": plan.body_max_hold_s,
            "audio_source": plan.audio_source,
            "target_beat_count": target,
            "actual_beat_count": len(beats),
            "beats_deficit": max(0, target - len(beats)),
            "avg_sec_per_beat_if_equal": round(plan.body_pool_s / len(beats), 1) if beats else None,
            "plan_notes": plan.notes,
        }
        if len(beats) < target:
            warnings.append(
                f"Cuerpo: {len(beats)} beats vs objetivo {target} "
                f"(~{plan.body_target_hold_s}s/plano, {density['body_audio_pool_min']} min audio)."
            )
        avg = density.get("avg_sec_per_beat_if_equal")
        if isinstance(avg, (int, float)) and avg > plan.body_max_hold_s:
            warnings.append(
                f"Reparto equitativo daría ~{avg}s/plano; al reconciliar se parte por >{plan.body_max_hold_s}s."
            )
    if tracks["avatar"] > tracks["insert"]:
        warnings.append(
            f"Más avatares ({tracks['avatar']}) que inserts ({tracks['insert']}); "
            "prioriza B-roll en el cuerpo."
        )
    if split_max_hold > 0 and tracks["avatar"] > len(beats) // 2:
        warnings.append(
            f"{split_max_hold} beats partidos por max_hold; revisa si deberían ser insert."
        )
    if fragments:
        warnings.append(f"{len(fragments)} text_anchor parecen frases cortadas a mitad.")
    if duplicates:
        warnings.append(f"{len(duplicates)} pares de beats muy similares (posible duplicado).")

    comp = bundle.get("style_consistency")
    desk_bias = False
    if isinstance(comp, dict):
        c = str(comp.get("composition") or "").lower()
        desk_bias = "teclado" in c and "variar" not in c

    return {
        "macro_beat_count": len(beats),
        "track_summary": tracks,
        "macro_beat_track_summary": bundle.get("macro_beat_track_summary"),
        "macro_beats_source": (bundle.get("_gen") or {}).get("macro_beats_source"),
        "split_max_hold_count": split_max_hold,
        "fragment_beats": fragments,
        "duplicate_pairs": duplicates,
        "density": density,
        "composition_desk_bias": desk_bias,
        "warnings": warnings,
        "ok": len(warnings) == 0,
    }
