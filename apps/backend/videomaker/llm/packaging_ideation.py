"""Empaquetado hook-first: título + promesa de miniatura ANTES del guion (sin script)."""

from __future__ import annotations

import json
import os
from typing import Any

from videomaker.llm.metadata_gen import (
    _parse_json_object,
    resolve_metadata_language,
    resolve_metadata_llm,
)
from videomaker.llm.output_language import language_label
from videomaker.llm.narrative_angle_builder import narrative_angle_context_text
from videomaker.pipeline.topic_generator_selection import get_selected_topic


_PACKAGING_SCHEMA = """\
JSON schema (single object):
- platform: title, title_variants[2]
- editorial: one_liner, bullets[3], thumbnail_ideas[2-4], hook_summary, hook_type
- marketing: thumbnail_hook_text, target_audience
- thumbnail_narrative: core_contrast, viewer_role, envy_target, emotion, scroll_stop_visual (one vivid sentence)
"""


def _packaging_system_prompt(
    *,
    target_platform: str,
    output_lang: str,
    output_lang_label: str,
    canonical_title: str | None,
) -> str:
    tp = (target_platform or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    title_rule = (
        f'- platform.title MUST be exactly: "{canonical_title}" (verbatim). title_variants: 2 scroll-stopping alternatives, same promise.\n'
        if canonical_title
        else "- platform.title: one primary YouTube title optimized for CTR in this niche.\n"
    )
    return f"""You are a YouTube packaging strategist (thumbnail + title + hook promise BEFORE the script exists).

Target platform: {tp}
Output language for all string values: {output_lang} ({output_lang_label}).

Return ONLY one JSON object. No markdown fence.
{_PACKAGING_SCHEMA}

Rules:
- Do NOT write script, voiceover, acts, or chapter timestamps.
- Thumbnail ideas must be visual, specific, and testable (face, prop, contrast, text-on-thumb if needed).
- hook_summary + thumbnail_hook_text define the click promise; Script Writer will align Act 1 to this.
- hook_type: one of paradox, statistic, scene, invitation, systemic, documentary (lowercase).
- thumbnail_narrative.scroll_stop_visual: the mental image the viewer sees on the thumbnail.
{title_rule}- Stay plausible for the topic; no invented statistics unless framed as hypothetical.
"""


def packaging_context_text(pkg: dict[str, Any]) -> str:
    """Bloque de texto para Prompt / Script Writer."""
    if not isinstance(pkg, dict) or not pkg:
        return ""
    lines: list[str] = []
    plat = pkg.get("platform") if isinstance(pkg.get("platform"), dict) else {}
    title = str(plat.get("title") or "").strip()
    if title:
        lines.append(f"Título publicado (promesa): {title}")
    variants = plat.get("title_variants")
    if isinstance(variants, list):
        v = [str(x).strip() for x in variants if str(x).strip()][:2]
        if v:
            lines.append(f"Variantes título: {' | '.join(v)}")
    ed = pkg.get("editorial") if isinstance(pkg.get("editorial"), dict) else {}
    for key, label in (
        ("one_liner", "One-liner"),
        ("hook_summary", "Promesa del gancho"),
        ("hook_type", "Tipo de gancho"),
    ):
        val = str(ed.get(key) or "").strip()
        if val:
            lines.append(f"{label}: {val}")
    ideas = ed.get("thumbnail_ideas")
    if isinstance(ideas, list):
        ti = [str(x).strip() for x in ideas if str(x).strip()][:4]
        if ti:
            lines.append("Ideas de miniatura:")
            lines.extend(f"  - {t}" for t in ti)
    mkt = pkg.get("marketing") if isinstance(pkg.get("marketing"), dict) else {}
    th = str(mkt.get("thumbnail_hook_text") or "").strip()
    if th:
        lines.append(f"Texto gancho miniatura: {th}")
    aud = str(mkt.get("target_audience") or "").strip()
    if aud:
        lines.append(f"Audiencia: {aud}")
    tn = pkg.get("thumbnail_narrative") if isinstance(pkg.get("thumbnail_narrative"), dict) else {}
    if tn:
        parts = [
            str(tn.get(k) or "").strip()
            for k in ("scroll_stop_visual", "core_contrast", "viewer_role", "emotion")
        ]
        parts = [p for p in parts if p]
        if parts:
            lines.append("Imagen mental (miniatura): " + " · ".join(parts))
    if not lines:
        return ""
    return "EMPAQUETADO (TÍTULO + MINIATURA) — el guion debe cumplir esta promesa desde el primer segundo:\n" + "\n".join(
        lines
    )


def generate_packaging_ideation(
    *,
    keywords: str = "",
    context: str = "",
    lang: str = "es",
    provider: str | None = None,
    model: str | None = None,
    target_platform: str = "youtube",
    minutes_session: float | None = None,
    topic_artifact: dict[str, Any] | None = None,
    narrative_angle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM → dict para ``pipeline/packaging.json`` (sin guion)."""
    from videomaker.llm.metadata_gen import resolve_canonical_topic_title

    selected = get_selected_topic(topic_artifact)
    eff_lang = resolve_metadata_language(lang, topic_artifact)
    topic_title = resolve_canonical_topic_title(selected_topic=selected, keywords=keywords)
    topic_angle = str(selected.get("angle") or "").strip() if selected else (context or "").strip()
    na_text = narrative_angle_context_text(narrative_angle or {})

    payload: dict[str, Any] = {
        "target_platform": target_platform,
        "output_language": eff_lang,
        "duration_minutes": (
            float(minutes_session) if minutes_session is not None and minutes_session > 0 else None
        ),
        "canonical_title": topic_title,
        "topic_angle": topic_angle or None,
        "session_topic": (keywords or "").strip() or None,
        "session_context": (context or "").strip() or None,
        "narrative_angle": na_text or None,
    }
    user = (
        "Generate packaging JSON (title + thumbnail promise) from these inputs only. "
        "No script exists yet — design the click promise first.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )

    system = _packaging_system_prompt(
        target_platform=target_platform,
        output_lang=eff_lang,
        output_lang_label=language_label(eff_lang),
        canonical_title=topic_title,
    )
    selected_prov, resolved_model = resolve_metadata_llm(provider, model)
    try:
        meta_temp = float(os.environ.get("VIDEOMAKER_PACKAGING_TEMPERATURE", "0.45"))
    except ValueError:
        meta_temp = 0.45

    from videomaker.llm.llm_routing import call_production_llm

    raw = call_production_llm(
        system=system,
        user=user,
        model=resolved_model,
        response_json=True,
        temperature=meta_temp,
    )
    parsed = _parse_json_object(raw)
    plat = parsed.get("platform") if isinstance(parsed.get("platform"), dict) else {}
    if topic_title:
        plat = {**plat, "title": topic_title}
    edit = parsed.get("editorial") if isinstance(parsed.get("editorial"), dict) else {}
    if isinstance(edit.get("hook_type"), str):
        edit = {**edit, "hook_type": edit["hook_type"].strip().lower()}
    return {
        "platform": plat,
        "editorial": edit,
        "marketing": parsed.get("marketing") if isinstance(parsed.get("marketing"), dict) else {},
        "thumbnail_narrative": (
            parsed.get("thumbnail_narrative")
            if isinstance(parsed.get("thumbnail_narrative"), dict)
            else {}
        ),
        "_gen": {
            "phase": "packaging_hook_first",
            "provider": selected_prov,
            "model": resolved_model,
            "lang": eff_lang,
            "topic_title": topic_title,
            "target_platform": target_platform,
        },
    }


def wrap_packaging_bundle(inner: dict[str, Any]) -> dict[str, Any]:
    out = dict(inner)
    out["version"] = 1
    return out


def merge_packaging_into_metadata(inner: dict[str, Any], packaging: dict[str, Any]) -> dict[str, Any]:
    """Fusiona empaquetado temprano en metadata.json (late step)."""
    out = dict(inner)
    for key in ("platform", "editorial", "marketing"):
        pkg_block = packaging.get(key)
        if isinstance(pkg_block, dict) and pkg_block:
            existing = out.get(key) if isinstance(out.get(key), dict) else {}
            merged = {**existing, **pkg_block}
            out[key] = merged
    tn = packaging.get("thumbnail_narrative")
    if isinstance(tn, dict) and tn:
        out["thumbnail_narrative"] = tn
    gen = out.get("_gen") if isinstance(out.get("_gen"), dict) else {}
    out["_gen"] = {**gen, "packaging_merged": True}
    return out
