"""Macro-beats narrativos del cuerpo (Actos 2-4) con regla max_hold."""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

from videomaker.scene_editor.visual_hold_policy import max_visual_hold_s

_WORDS_PER_SEC = 2.5
_BROLL_TAG = re.compile(r"(?i)\[B-ROLL\s*:?\s*([^\]]+)\]")
_DATA_HINTS = re.compile(
    r"(?i)\b("
    r"gráfico|chart|datos|data|inflaci[oó]n|porcentaje|%|número|"
    r"calculadora|calculator|pantalla|screen|excel|tabla|spreadsheet|"
    r"zillow|reddit|article|artículo|comment|thread|hilo|"
    r"mortgage|hipoteca|down payment|equity|patrimonio|net worth|"
    r"meeting|reunión|council|consejo|testif|yard sign|cartel|"
    r"duplex|fourplex|group chat|chat|notification|app\b|phone|móvil"
    r")\b"
)
_OUTLINE_BULLET = re.compile(r"^\s*[-•*]\s+(.+)$", re.M)
_ACT_HEADER = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?"
    r"(?:Acto\s*([2-9])|Act\s*([2-9])|Parte\s*([2-9])|"
    r"PILLAR\s*([1-9])|INTRODUCTION)"
    r"(?:\*\*)?\b",
)
_MIN_MACRO_BEATS_DEFAULT = 12


def _min_macro_beats_target() -> int:
    raw = (os.environ.get("VIDEOMAKER_BODY_MIN_MACRO_BEATS") or "").strip()
    if raw:
        try:
            return max(8, int(raw))
        except ValueError:
            pass
    return _MIN_MACRO_BEATS_DEFAULT


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or "", flags=re.UNICODE))


def _estimated_duration_s(text: str) -> float:
    w = _word_count(text)
    return max(1.0, w / _WORDS_PER_SEC) if w else 1.0


def _is_complete_sentence(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r'[.!?…]["\']?\s*$', t):
        return True
    return _word_count(t) >= 14 and not re.search(r"\b(and|or|the|a|an|de|el|la)\s*$", t, re.I)


def _split_into_slices(text: str, n: int) -> list[str]:
    t = re.sub(r"\[B-ROLL[^\]]*\]", " ", text or "", flags=re.I)
    t = re.sub(r"\[CATEGORIA[^\]]*\]", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
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
    while len(out) < n:
        out.append("")
    return out[:n]


def _extract_broll_prompt(text: str) -> str | None:
    m = _BROLL_TAG.search(text or "")
    if not m:
        return None
    hint = (m.group(1) or "").strip()
    return hint[:500] if hint else None


def _infer_track(text: str, *, prefer_insert: bool = False) -> tuple[str, bool]:
    broll = _extract_broll_prompt(text)
    if broll:
        return "insert", False
    if prefer_insert or _DATA_HINTS.search(text or ""):
        return "insert", False
    return "avatar", True


def _resolve_track(
    text: str,
    *,
    parent_track: str | None = None,
    prefer_insert: bool = False,
) -> tuple[str, bool]:
    pt = (parent_track or "").strip().lower()
    if pt == "insert":
        return "insert", False
    if pt == "avatar":
        return "avatar", True
    return _infer_track(text, prefer_insert=prefer_insert)


def contextual_composition_hint(anchor: str, default: str) -> str:
    """Encuadre por tipo de escena; evita forzar escritorio en todo el cuerpo."""
    s = (anchor or "").lower()
    if re.search(
        r"(?i)\b(council|consejo|meeting|reunión|yard sign|cartel|duplex|fourplex|"
        r"neighborhood|vecino|testif|manifest|protest)\b",
        s,
    ):
        return (
            "Plano medio o general en espacio cívico o calle residencial; "
            "carteles, fachadas o sala de reuniones. Sin macro de teclado en escritorio."
        )
    if re.search(r"(?i)\b(dinner|family|parent|mom|dad|cena|familia|child|hijo)\b", s):
        return (
            "Interior cálido (mesa, salón); luz natural o velas. "
            "Evitar oficina y monitor como foco principal."
        )
    if re.search(r"(?i)\b(reddit|comment|thread|article|artículo|group chat|chat)\b", s):
        return (
            "Detalle de pantalla móvil o hilo de texto legible; "
            "composición editorial, no avatar en escritorio."
        )
    if re.search(r"(?i)\b(zillow|calculator|spreadsheet|retirement|mortgage|budget)\b", s):
        return (
            "Plano detalle de UI, calculadora o documentos en manos; "
            "variar ángulo (POV, over-shoulder), no siempre el mismo escritorio frontal."
        )
    if re.search(r"(?i)\b(city|street|billboard|urban|ciudad|calle)\b", s):
        return "Plano general urbano o exterior; profundidad de campo media."
    return default


def _insert_prompt_from_anchor(anchor: str, *, ia_kw: str, lighting: str) -> str:
    broll = _extract_broll_prompt(anchor)
    if broll:
        return f"{broll}, cinematic B-roll, {lighting}, no talking head, no presenter face"
    snippet = (anchor or "")[:220].strip()
    kw = f", {ia_kw}" if ia_kw else ""
    comp = contextual_composition_hint(anchor, "")
    comp_bit = f" {comp}." if comp and comp not in snippet else ""
    return (
        f"Cinematic illustrative B-roll for narration: {snippet}{kw}.{comp_bit} "
        f"{lighting}. Shallow depth of field, editorial finance video, no avatar, no presenter."
    )


def _beat_row(
    *,
    index: int,
    act: str,
    anchor: str,
    track: str,
    vis: bool,
    weight: float,
    ia_kw: str,
    lighting: str,
    ai_prompt: str | None = None,
    split_reason: str | None = None,
    composition_hint: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "index": index,
        "act": act,
        "text_anchor": anchor[:800],
        "track": track,
        "narrator_visible": vis,
        "weight": round(weight, 3),
    }
    if split_reason:
        row["split_reason"] = split_reason
    if composition_hint:
        row["composition_hint"] = composition_hint
    if track == "insert":
        row["ai_prompt"] = (ai_prompt or "").strip() or _insert_prompt_from_anchor(
            anchor, ia_kw=ia_kw, lighting=lighting
        )
    return row


def expand_block_with_max_hold(
    text_anchor: str,
    *,
    max_hold_s: float,
    act: str = "body",
    start_index: int = 0,
    ia_kw: str = "",
    lighting: str = "cinematic motivated light",
    parent_track: str | None = None,
    parent_ai_prompt: str | None = None,
    default_composition: str = "",
) -> list[dict[str, Any]]:
    """Parte un bloque largo en macro-beats; respeta ``parent_track`` del LLM."""
    anchor = (text_anchor or "").strip()
    if not anchor:
        return []

    pt = (parent_track or "").strip().lower()
    comp = contextual_composition_hint(anchor, default_composition)

    # Avatar del LLM: un plano por beat, frase completa, sin trocear.
    if pt == "avatar":
        return [
            _beat_row(
                index=start_index,
                act=act,
                anchor=anchor,
                track="avatar",
                vis=True,
                weight=_estimated_duration_s(anchor),
                ia_kw=ia_kw,
                lighting=lighting,
                composition_hint=comp,
            )
        ]

    dur = _estimated_duration_s(anchor)
    inherited_prompt = (parent_ai_prompt or "").strip() or None

    def _single_insert(split_reason: str | None = None) -> list[dict[str, Any]]:
        return [
            _beat_row(
                index=start_index,
                act=act,
                anchor=anchor,
                track="insert",
                vis=False,
                weight=dur,
                ia_kw=ia_kw,
                lighting=lighting,
                ai_prompt=inherited_prompt,
                split_reason=split_reason,
                composition_hint=comp,
            )
        ]

    # Insert: no partir si la frase ya es corta o está completa (evita fragmentos).
    if pt == "insert" and (dur <= max_hold_s + 0.25 or _is_complete_sentence(anchor)):
        return _single_insert()

    if dur <= max_hold_s + 0.25:
        track, vis = _resolve_track(anchor, parent_track=parent_track)
        return [
            _beat_row(
                index=start_index,
                act=act,
                anchor=anchor,
                track=track,
                vis=vis,
                weight=dur,
                ia_kw=ia_kw,
                lighting=lighting,
                ai_prompt=inherited_prompt if track == "insert" else None,
                composition_hint=comp,
            )
        ]

    # Solo los inserts largos se dividen; todos los hijos siguen siendo insert.
    if pt == "insert":
        n = min(4, max(2, int(math.ceil(dur / max_hold_s))))
        slices = _split_into_slices(anchor, n)
        beats: list[dict[str, Any]] = []
        for sl in slices:
            if not sl.strip():
                continue
            beats.append(
                _beat_row(
                    index=start_index + len(beats),
                    act=act,
                    anchor=sl,
                    track="insert",
                    vis=False,
                    weight=_estimated_duration_s(sl),
                    ia_kw=ia_kw,
                    lighting=lighting,
                    ai_prompt=inherited_prompt,
                    split_reason="max_hold",
                    composition_hint=contextual_composition_hint(sl, default_composition),
                )
            )
        return beats or _single_insert()

    n = min(6, max(2, int(math.ceil(dur / max_hold_s))))
    slices = _split_into_slices(anchor, n)
    beats = []
    for i, sl in enumerate(slices):
        if not sl.strip():
            continue
        prefer_ins = i % 2 == 1 and i < n - 1
        track, vis = _resolve_track(sl, parent_track=parent_track, prefer_insert=prefer_ins)
        beats.append(
            _beat_row(
                index=start_index + len(beats),
                act=act,
                anchor=sl,
                track=track,
                vis=vis,
                weight=_estimated_duration_s(sl),
                ia_kw=ia_kw,
                lighting=lighting,
                ai_prompt=inherited_prompt if track == "insert" else None,
                split_reason="max_hold",
                composition_hint=contextual_composition_hint(sl, default_composition),
            )
        )
    return beats


def _anchor_covered(anchor: str, existing: list[dict[str, Any]]) -> bool:
    a = re.sub(r"\s+", " ", (anchor or "").lower().strip())
    a = re.sub(r"[^\w\s]", "", a)
    if len(a) < 20:
        return False
    prefix = a[:55]
    for b in existing:
        ex = re.sub(r"\s+", " ", str(b.get("text_anchor") or "").lower().strip())
        ex = re.sub(r"[^\w\s]", "", ex)
        if not ex:
            continue
        if a in ex or ex in a:
            return True
        if prefix and (prefix in ex or ex[:55] in a):
            return True
        # Misma escena con redacción distinta (outline vs guion)
        aw = set(a.split())
        ew = set(ex.split())
        if len(aw & ew) >= min(8, len(aw) // 2, len(ew) // 2):
            return True
    return False


def extract_outline_bullets(body_text: str) -> list[tuple[str, str]]:
    """(act_label, bullet_text) desde outline del guion."""
    raw = (body_text or "").strip()
    if not raw:
        return []
    current_act = "acto_2"
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        hm = _ACT_HEADER.match(line.strip())
        if hm:
            g = next((x for x in hm.groups() if x), None)
            if g:
                current_act = f"acto_{g}"
            elif "INTRODUCTION" in line.upper():
                current_act = "acto_2"
            continue
        bm = _OUTLINE_BULLET.match(line)
        if not bm:
            continue
        bullet = (bm.group(1) or "").strip()
        if _word_count(bullet) >= 8:
            out.append((current_act, bullet))
    return out


def extract_broll_beats(body_text: str) -> list[tuple[str, str]]:
    """(act, anchor con tag B-ROLL) desde párrafos del guion."""
    out: list[tuple[str, str]] = []
    current_act = "body"
    for act, para in _split_body_paragraphs(body_text):
        current_act = act
        if _BROLL_TAG.search(para):
            out.append((current_act, para[:800]))
    return out


def supplement_macro_beats_from_script(
    beats: list[dict[str, Any]],
    body_text: str,
    *,
    ia_kw: str = "",
    lighting: str = "cinematic",
    default_composition: str = "",
) -> list[dict[str, Any]]:
    """Añade bullets del outline y bloques B-ROLL si faltan beats."""
    out = list(beats)
    target = _min_macro_beats_target()

    candidates: list[tuple[str, str, str]] = []
    for act, bullet in extract_outline_bullets(body_text):
        candidates.append((act, bullet, "outline_bullet"))
    for act, para in extract_broll_beats(body_text):
        candidates.append((act, para, "broll_paragraph"))

    for act, text, source in candidates:
        if _anchor_covered(text, out):
            continue
        track, vis = _infer_track(text)
        if source == "outline_bullet" and track == "avatar" and _DATA_HINTS.search(text):
            track, vis = "insert", False
        row = _beat_row(
            index=len(out),
            act=act,
            anchor=text,
            track=track,
            vis=vis,
            weight=_estimated_duration_s(text),
            ia_kw=ia_kw,
            lighting=lighting,
            composition_hint=contextual_composition_hint(text, default_composition),
        )
        row["beat_source"] = source
        out.append(row)

    if len(out) < target:
        for act, para in _split_body_paragraphs(body_text):
            if _word_count(para) < 25 or _anchor_covered(para, out):
                continue
            track, vis = _infer_track(para)
            out.append(
                _beat_row(
                    index=len(out),
                    act=act,
                    anchor=para[:800],
                    track=track,
                    vis=vis,
                    weight=_estimated_duration_s(para),
                    ia_kw=ia_kw,
                    lighting=lighting,
                    composition_hint=contextual_composition_hint(para, default_composition),
                )
            )
            out[-1]["beat_source"] = "paragraph_fallback"
            if len(out) >= target:
                break

    for i, b in enumerate(out):
        b["index"] = i
    return out


def enrich_macro_beats_metadata(
    beats: list[dict[str, Any]],
    *,
    default_composition: str = "",
) -> list[dict[str, Any]]:
    for b in beats:
        anchor = str(b.get("text_anchor") or "")
        if not b.get("composition_hint"):
            b["composition_hint"] = contextual_composition_hint(anchor, default_composition)
    return beats


def _split_body_paragraphs(body_text: str) -> list[tuple[str, str]]:
    """(act_label, paragraph_text)"""
    raw = (body_text or "").strip()
    if not raw:
        return []
    parts = re.split(
        r"(?im)(?=^(?:#{1,6}\s*)?(?:\*\*)?(?:Acto\s*[2-9]|Act\s*[2-9]|Parte\s*[2-9])(?:\*\*)?\b)",
        raw,
    )
    out: list[tuple[str, str]] = []
    current_act = "body"
    for part in parts:
        p = part.strip()
        if not p:
            continue
        m = re.match(
            r"^(?:#{1,6}\s*)?(?:\*\*)?(Acto\s*[2-9]|Act\s*[2-9]|Parte\s*[2-9])(?:\*\*)?\b",
            p,
            re.I,
        )
        if m:
            current_act = re.sub(r"\s+", "_", m.group(1).lower())
            p = re.sub(
                r"^(?:#{1,6}\s*)?(?:\*\*)?(?:Acto\s*[2-9]|Act\s*[2-9]|Parte\s*[2-9])(?:\*\*)?\b\s*",
                "",
                p,
                count=1,
                flags=re.I,
            ).strip()
        chunks = [c.strip() for c in re.split(r"\n\s*\n+", p) if c.strip()]
        for c in chunks:
            if _word_count(c) >= 8:
                out.append((current_act, c))
    if not out and raw:
        for c in [x.strip() for x in re.split(r"\n\s*\n+", raw) if x.strip()]:
            if _word_count(c) >= 8:
                out.append(("body", c))
    return out


def build_macro_beats_rule_based(
    work_dir: Path,
    body_text: str,
    *,
    style: dict[str, Any] | None = None,
    ia_kw: str = "",
) -> list[dict[str, Any]]:
    from pathlib import Path as _Path

    work_dir = _Path(work_dir)
    sc = style or {}
    lighting = str(sc.get("lighting") or "cinematic, motivated key light").strip()
    default_comp = str(sc.get("composition") or "").strip()
    max_hold = max_visual_hold_s(work_dir, section="body")
    paragraphs = _split_body_paragraphs(body_text)
    beats: list[dict[str, Any]] = []
    idx = 0
    for act, para in paragraphs:
        expanded = expand_block_with_max_hold(
            para,
            max_hold_s=max_hold,
            act=act,
            start_index=idx,
            ia_kw=ia_kw,
            lighting=lighting,
            default_composition=default_comp,
        )
        beats.extend(expanded)
        idx = len(beats)
    beats = supplement_macro_beats_from_script(
        beats,
        body_text,
        ia_kw=ia_kw,
        lighting=lighting,
        default_composition=default_comp,
    )
    from videomaker.llm.body_audio_density import densify_macro_beats_for_audio_hold
    from videomaker.llm.section_density_plan import build_section_density_plan

    plan = build_section_density_plan(work_dir, body_text=body_text)
    beats = densify_macro_beats_for_audio_hold(
        work_dir,
        beats,
        body_text,
        ia_kw=ia_kw,
        lighting=lighting,
        default_composition=default_comp,
        plan=plan,
    )
    return enrich_macro_beats_metadata(beats, default_composition=default_comp)


def normalize_macro_beats(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        anchor = str(item.get("text_anchor") or item.get("narration") or "").strip()
        if not anchor:
            continue
        track = str(item.get("track") or "").strip().lower()
        if track not in ("avatar", "insert"):
            track, vis = _infer_track(anchor)
        else:
            vis = bool(item.get("narrator_visible", track == "avatar"))
        row: dict[str, Any] = {
            "index": int(item.get("index", i)),
            "act": str(item.get("act") or "body").strip() or "body",
            "text_anchor": anchor[:800],
            "track": track,
            "narrator_visible": vis,
            "weight": float(item.get("weight") or _estimated_duration_s(anchor)),
        }
        if track == "insert":
            ap = str(item.get("ai_prompt") or "").strip()
            row["ai_prompt"] = ap or _insert_prompt_from_anchor(anchor, ia_kw="", lighting="cinematic")
        ch = str(item.get("composition_hint") or "").strip()
        if ch:
            row["composition_hint"] = ch
        out.append(row)
    return out


def finalize_macro_beats(
    work_dir: Path,
    bundle: dict[str, Any],
    body_text: str,
) -> dict[str, Any]:
    """Garantiza ``macro_beats`` en el bundle (LLM + expansión max_hold)."""
    from pathlib import Path as _Path

    work_dir = _Path(work_dir)
    sc = bundle.get("style_consistency") if isinstance(bundle.get("style_consistency"), dict) else {}
    ia_raw = bundle.get("ia_keywords_body")
    ia_kw = ""
    if isinstance(ia_raw, list):
        ia_kw = ", ".join(str(x).strip() for x in ia_raw[:6] if str(x).strip())
    elif isinstance(ia_raw, str):
        ia_kw = ia_raw.strip()
    lighting = str(sc.get("lighting") or "cinematic").strip()
    default_comp = str(sc.get("composition") or "").strip()

    llm = bundle.get("llm_enrichment") if isinstance(bundle.get("llm_enrichment"), dict) else {}
    raw_beats = llm.get("macro_beats") or llm.get("acts") or bundle.get("macro_beats")
    beats = normalize_macro_beats(raw_beats)
    source_tag = "llm+max_hold_expand"

    if not beats:
        beats = build_macro_beats_rule_based(
            work_dir, body_text, style=sc, ia_kw=ia_kw
        )
        source_tag = "rule_max_hold"
    else:
        max_hold = max_visual_hold_s(work_dir, section="body")
        expanded: list[dict[str, Any]] = []
        for b in beats:
            anchor = str(b.get("text_anchor") or "")
            track = str(b.get("track") or "").strip().lower()
            act = str(b.get("act") or "body")
            parent_prompt = str(b.get("ai_prompt") or "").strip() or None

            if track == "avatar":
                expanded.append(
                    _beat_row(
                        index=len(expanded),
                        act=act,
                        anchor=anchor,
                        track="avatar",
                        vis=True,
                        weight=float(b.get("weight") or _estimated_duration_s(anchor)),
                        ia_kw=ia_kw,
                        lighting=lighting,
                        composition_hint=str(b.get("composition_hint") or "")
                        or contextual_composition_hint(anchor, default_comp),
                    )
                )
                continue

            need_split = (
                track == "insert"
                and _estimated_duration_s(anchor) > max_hold + 0.25
                and not _is_complete_sentence(anchor)
            )
            if track == "insert" and not need_split:
                expanded.append(
                    _beat_row(
                        index=len(expanded),
                        act=act,
                        anchor=anchor,
                        track="insert",
                        vis=False,
                        weight=float(b.get("weight") or _estimated_duration_s(anchor)),
                        ia_kw=ia_kw,
                        lighting=lighting,
                        ai_prompt=parent_prompt,
                        composition_hint=str(b.get("composition_hint") or "")
                        or contextual_composition_hint(anchor, default_comp),
                    )
                )
                continue

            expanded.extend(
                expand_block_with_max_hold(
                    anchor,
                    max_hold_s=max_hold,
                    act=act,
                    start_index=len(expanded),
                    ia_kw=ia_kw,
                    lighting=lighting,
                    parent_track=track if track in ("avatar", "insert") else None,
                    parent_ai_prompt=parent_prompt,
                    default_composition=default_comp,
                )
            )
        beats = expanded
        beats = supplement_macro_beats_from_script(
            beats,
            body_text,
            ia_kw=ia_kw,
            lighting=lighting,
            default_composition=default_comp,
        )
        from videomaker.llm.body_audio_density import densify_macro_beats_for_audio_hold
        from videomaker.llm.body_scene_router import _extract_hook_text_for_plan
        from videomaker.llm.section_density_plan import build_section_density_plan

        script_txt = ""
        sp = work_dir / "pipeline" / "script.txt"
        if sp.is_file():
            try:
                script_txt = sp.read_text(encoding="utf-8")
            except OSError:
                script_txt = ""
        plan = build_section_density_plan(
            work_dir,
            script_text=script_txt,
            hook_text=_extract_hook_text_for_plan(script_txt),
            body_text=body_text,
        )
        beats = densify_macro_beats_for_audio_hold(
            work_dir,
            beats,
            body_text,
            ia_kw=ia_kw,
            lighting=lighting,
            default_composition=default_comp,
            plan=plan,
        )
        beats = enrich_macro_beats_metadata(beats, default_composition=default_comp)
        for i, b in enumerate(beats):
            b["index"] = i
        source_tag = "llm+preserve_track+script_supplement"

    script_txt = ""
    sp = work_dir / "pipeline" / "script.txt"
    if sp.is_file():
        try:
            script_txt = sp.read_text(encoding="utf-8")
        except OSError:
            script_txt = ""
    from videomaker.llm.body_scene_router import _extract_hook_text_for_plan
    from videomaker.llm.body_visual_language import apply_body_visual_pipeline, merge_llm_visual_fields
    from videomaker.llm.section_density_plan import build_section_density_plan

    rhythm_plan = build_section_density_plan(
        work_dir,
        script_text=script_txt,
        hook_text=_extract_hook_text_for_plan(script_txt),
        body_text=body_text,
    )
    llm_raw: list[dict[str, Any]] = []
    llm_enrich = bundle.get("llm_enrichment") if isinstance(bundle.get("llm_enrichment"), dict) else {}
    if isinstance(llm_enrich.get("macro_beats"), list):
        llm_raw = [x for x in llm_enrich["macro_beats"] if isinstance(x, dict)]
    beats = merge_llm_visual_fields(beats, llm_raw)
    beats, body_visual_plan = apply_body_visual_pipeline(beats, body_pool_s=rhythm_plan.body_pool_s)
    bundle["body_visual_plan"] = body_visual_plan
    bundle["narrative_rhythm"] = body_visual_plan.get("narrative_rhythm")
    bundle["anchor_shot"] = body_visual_plan.get("anchor_shots")

    bundle.setdefault("_gen", {})["macro_beats_source"] = source_tag
    bundle["version"] = 2
    bundle["macro_beats"] = beats
    bundle["macro_beat_count"] = len(beats)
    bundle["macro_beat_track_summary"] = {
        "avatar": sum(1 for b in beats if b.get("track") == "avatar"),
        "insert": sum(1 for b in beats if b.get("track") == "insert"),
    }
    try:
        from videomaker.llm.body_router_diagnostics import analyze_body_router_bundle
        from videomaker.llm.body_scene_router import (
            _extract_hook_text_for_plan,
        )
        from videomaker.llm.section_density_plan import build_section_density_plan

        script_txt = ""
        sp = work_dir / "pipeline" / "script.txt"
        if sp.is_file():
            try:
                script_txt = sp.read_text(encoding="utf-8")
            except OSError:
                script_txt = ""
        plan = build_section_density_plan(
            work_dir,
            script_text=script_txt,
            hook_text=_extract_hook_text_for_plan(script_txt),
            body_text=body_text,
        )
        bundle["visual_density_plan"] = plan.to_dict()
        bundle["density_target"] = {
            "body_target_images": plan.body_target_images,
            "hook_target_images": plan.hook_target_images,
            "total_target_images": plan.total_target_images,
            "actual": len(beats),
        }
        bundle["diagnostics"] = analyze_body_router_bundle(
            bundle, work_dir=work_dir, body_text=body_text, plan=plan
        )
    except Exception:
        pass
    return bundle
