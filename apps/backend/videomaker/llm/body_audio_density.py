"""Densidad de macro_beats / prompts según plan de sección y audio."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from videomaker.llm.body_macro_beats import (
    _anchor_covered,
    _beat_row,
    _infer_track,
    _word_count,
    contextual_composition_hint,
    expand_block_with_max_hold,
)
from videomaker.llm.section_density_plan import (
    SectionDensityPlan,
    build_section_density_plan,
    estimate_body_audio_pool_s,
)
from videomaker.scene_editor.visual_hold_policy import max_visual_hold_s, shots_needed_for_duration


def target_macro_beat_count(work_dir: Path, body_text: str) -> int:
    """Plano objetivo del cuerpo según audio y ~6.5s por imagen (sin tope 48)."""
    plan = build_section_density_plan(work_dir, body_text=body_text)
    return plan.body_target_images


def _extract_narrative_sentences(body_text: str) -> list[str]:
    """Frases narrables del guion (prosa + bullets), sin cabeceras de outline."""
    raw = (body_text or "").strip()
    if not raw:
        return []
    sentences: list[str] = []
    for para in re.split(r"\n\s*\n+", raw):
        p = para.strip()
        if not p:
            continue
        if re.match(r"^#{1,6}\s", p) or re.match(r"^\*\*[^*]+\*\*", p):
            continue
        if re.match(r"^[-•*]\s+", p):
            bullet = re.sub(r"^[-•*]\s+", "", p).strip()
            if _word_count(bullet) >= 6:
                sentences.append(bullet)
            continue
        for s in re.split(r"(?<=[.!?…])\s+", p):
            s = s.strip()
            if _word_count(s) >= 5:
                sentences.append(s)
    return sentences


def build_timed_macro_beats_from_script(
    body_text: str,
    *,
    target_count: int,
    hold_s: float,
    act: str = "body",
    ia_kw: str = "",
    lighting: str = "cinematic",
    default_composition: str = "",
) -> list[dict[str, Any]]:
    """Agrupa frases del guion en bloques de ~hold_s segundos de narración → inserts."""
    sents = _extract_narrative_sentences(body_text)
    if not sents:
        return []
    groups: list[str] = []
    buf: list[str] = []
    buf_dur = 0.0
    for s in sents:
        buf.append(s)
        buf_dur += _word_count(s) / 2.5
        if buf_dur >= hold_s:
            groups.append(" ".join(buf).strip())
            buf, buf_dur = [], 0.0
    if buf:
        groups.append(" ".join(buf).strip())

    beats: list[dict[str, Any]] = []
    for i, anchor in enumerate(groups):
        if not anchor:
            continue
        track, vis = _infer_track(anchor)
        if track != "avatar":
            track, vis = "insert", False
        beats.append(
            _beat_row(
                index=i,
                act=act,
                anchor=anchor,
                track=track,
                vis=vis,
                weight=_word_count(anchor) / 2.5,
                ia_kw=ia_kw,
                lighting=lighting,
                composition_hint=contextual_composition_hint(anchor, default_composition),
            )
        )
        beats[-1]["beat_source"] = "timed_script_slot"
    return beats


def fill_timed_macro_beats_to_target(
    beats: list[dict[str, Any]],
    body_text: str,
    plan: SectionDensityPlan,
    *,
    ia_kw: str = "",
    lighting: str = "cinematic",
    default_composition: str = "",
) -> list[dict[str, Any]]:
    """Completa hasta ``plan.body_target_images`` con slots temporales del guion."""
    out = list(beats)
    target = plan.body_target_images
    if len(out) >= target:
        return out

    timed = build_timed_macro_beats_from_script(
        body_text,
        target_count=target,
        hold_s=plan.body_target_hold_s,
        ia_kw=ia_kw,
        lighting=lighting,
        default_composition=default_composition,
    )
    for row in timed:
        if len(out) >= target:
            break
        anchor = str(row.get("text_anchor") or "")
        # Con gran déficit priorizamos densidad de cortes sobre deduplicar viñetas parecidas.
        if len(out) >= target * 0.85 and _anchor_covered_loose(anchor, out):
            continue
        if len(out) >= target * 0.95 and _anchor_covered(anchor, out):
            continue
        row = dict(row)
        row["index"] = len(out)
        out.append(row)

    return out


def _anchor_covered_loose(anchor: str, existing: list[dict[str, Any]]) -> bool:
    """Solo descarta duplicados casi idénticos (no viñetas parecidas)."""
    a = re.sub(r"\s+", " ", (anchor or "").lower().strip())[:70]
    if len(a) < 24:
        return False
    for b in existing:
        ex = re.sub(r"\s+", " ", str(b.get("text_anchor") or "").lower().strip())[:70]
        if a == ex or (len(a) > 30 and a in ex) or (len(ex) > 30 and ex in a):
            return True
    return False


def densify_macro_beats_for_audio_hold(
    work_dir: Path,
    beats: list[dict[str, Any]],
    body_text: str,
    *,
    ia_kw: str = "",
    lighting: str = "cinematic",
    default_composition: str = "",
    plan: SectionDensityPlan | None = None,
) -> list[dict[str, Any]]:
    """Parte inserts y rellena slots temporales hasta la densidad del plan."""
    plan = plan or build_section_density_plan(work_dir, body_text=body_text)
    out = list(beats)
    target = plan.body_target_images
    hold = plan.body_max_hold_s
    guard = 0

    while len(out) < target and guard < 200:
        guard += 1
        candidates = sorted(
            range(len(out)),
            key=lambda i: _word_count(str(out[i].get("text_anchor") or "")),
            reverse=True,
        )
        split_done = False
        for idx in candidates:
            b = out[idx]
            anchor = str(b.get("text_anchor") or "").strip()
            if _word_count(anchor) < 8:
                continue
            track = str(b.get("track") or "insert").strip().lower()
            if track == "avatar":
                continue
            need = min(6, max(2, target - len(out) + 1, int(math.ceil(_word_count(anchor) / 14))))
            slices = _split_anchor_for_cuts(anchor, need)
            expanded: list[dict[str, Any]] = []
            for sl in slices:
                if not sl.strip():
                    continue
                expanded.extend(
                    expand_block_with_max_hold(
                        sl,
                        max_hold_s=hold,
                        act=str(b.get("act") or "body"),
                        start_index=0,
                        ia_kw=ia_kw,
                        lighting=lighting,
                        parent_track="insert",
                        parent_ai_prompt=str(b.get("ai_prompt") or "").strip() or None,
                        default_composition=default_composition,
                    )
                )
            if len(expanded) <= 1:
                continue
            out[idx : idx + 1] = expanded
            for part in expanded:
                part["beat_source"] = part.get("beat_source") or "audio_density_split"
            split_done = True
            break
        if not split_done:
            break

    out = fill_timed_macro_beats_to_target(
        out,
        body_text,
        plan,
        ia_kw=ia_kw,
        lighting=lighting,
        default_composition=default_composition,
    )

    if len(out) > target * 1.15:
        deduped: list[dict[str, Any]] = []
        for b in out:
            if not _anchor_covered(str(b.get("text_anchor") or ""), deduped):
                deduped.append(b)
        out = deduped
    for i, b in enumerate(out):
        b["index"] = i
    return out


def split_oversized_prompt_assignments(
    work_dir: Path,
    prompts: list[dict[str, Any]],
    ms_list: list[int],
    *,
    section: str = "body",
    plan: SectionDensityPlan | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    """Divide prompts que superan el max_hold de su sección."""
    if len(prompts) != len(ms_list):
        return prompts, ms_list
    if plan is None:
        from videomaker.llm.section_density_plan import build_section_density_plan

        plan = build_section_density_plan(work_dir)
    max_ms = int(max_hold_for_prompt_section(plan, section) * 1000)
    if max_ms < 1500:
        max_ms = 5000

    out_p: list[dict[str, Any]] = []
    out_ms: list[int] = []
    for p, ms in zip(prompts, ms_list, strict=False):
        if ms <= max_ms:
            out_p.append(p)
            out_ms.append(ms)
            continue
        n = min(10, max(2, shots_needed_for_duration(ms / 1000.0, max_ms / 1000.0)))
        base_id = str(p.get("id") or "body")
        anchor = str(p.get("text_anchor") or p.get("segment_text") or "")
        slices = _split_anchor_for_cuts(anchor, n)
        chunk_ms = ms // n
        remainder = ms - chunk_ms * n
        for i in range(n):
            clone = deepcopy(p)
            clone["id"] = f"{base_id}_hold{i + 1}"
            if slices[i]:
                clone["text_anchor"] = slices[i][:500]
                clone["segment_text"] = slices[i][:500]
            clone["density_split"] = True
            clone["density_split_index"] = i + 1
            clone["density_split_total"] = n
            part_ms = chunk_ms + (remainder if i == n - 1 else 0)
            out_p.append(clone)
            out_ms.append(max(50, part_ms))
    return out_p, out_ms


def max_hold_for_prompt_section(plan: SectionDensityPlan, section: str) -> float:
    from videomaker.llm.section_density_plan import max_hold_for_section

    return max_hold_for_section(plan, section)


def _split_anchor_for_cuts(anchor: str, n: int) -> list[str]:
    t = re.sub(r"\s+", " ", (anchor or "").strip())
    if not t or n <= 1:
        return [t] if t else [""]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", t) if s.strip()]
    if len(sentences) >= n:
        buckets: list[list[str]] = [[] for _ in range(n)]
        for i, sent in enumerate(sentences):
            buckets[i % n].append(sent)
        return [" ".join(b).strip() for b in buckets if " ".join(b).strip()]
    words = t.split()
    size = max(1, len(words) // n)
    out: list[str] = []
    i = 0
    while i < len(words) and len(out) < n - 1:
        out.append(" ".join(words[i : i + size]).strip())
        i += size
    out.append(" ".join(words[i:]).strip())
    return out[:n] if out else [t]


# Re-export for diagnostics
estimate_body_audio_pool_s = estimate_body_audio_pool_s
