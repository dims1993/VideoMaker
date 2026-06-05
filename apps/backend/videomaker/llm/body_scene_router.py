"""Body Scene Router: macro_beats narrativos (Actos 2-4) → Image Prompt Writer."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from videomaker.llm.hook_router_presets import FINANCE_VISUAL_STYLES, FINANCE_STYLE_IDS
from videomaker.pipeline.models import PipelineInputs

_PATTERN_ACT = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?(?:Acto\s*[2-9]|Act\s*[2-9]|Parte\s*[2-9])(?:\*\*)?\b",
)


def _extract_body_text(script_text: str) -> str:
    """Extrae el cuerpo del guion (a partir del Acto 2)."""
    m = _PATTERN_ACT.search(script_text)
    if m:
        return script_text[m.start() :].strip()[:16000]
    return script_text.strip()[:16000]


def _extract_hook_text_for_plan(script_text: str) -> str:
    """Gancho (antes del Acto 2) para estimar densidad sin import circular."""
    m = _PATTERN_ACT.search(script_text or "")
    if m:
        return (script_text[: m.start()] or "").strip()[:12000]
    return (script_text or "").strip()[:8000]


def _load_hook_router(work_dir: Path) -> dict[str, Any]:
    p = work_dir / "pipeline" / "hook_scene_router.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_metadata_hints(work_dir: Path) -> dict[str, Any]:
    p = work_dir / "pipeline" / "metadata.json"
    if not p.is_file():
        return {}
    try:
        md = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(md, dict):
        return {}
    prod = md.get("production") if isinstance(md.get("production"), dict) else {}
    return {
        "visual_style_reference": str(prod.get("visual_style_reference") or "").strip() or None,
        "color_palette": prod.get("color_palette") if isinstance(prod.get("color_palette"), list) else None,
        "music_vibe": str(prod.get("music_vibe") or "").strip() or None,
    }


def _build_template_bundle(
    work_dir: Path,
    script_text: str,
    narrative_preset: str | None,
) -> dict[str, Any]:
    """Genera el bundle del body router usando la plantilla + herencia del hook router."""
    hook = _load_hook_router(work_dir)
    md_hints = _load_metadata_hints(work_dir)

    # Heredar estilo del hook si está disponible
    cl = hook.get("classification") if isinstance(hook, dict) else None
    inherited_style = (
        str(cl.get("finance_style_id") or "").strip() if isinstance(cl, dict) else ""
    ) or "deep_documentary"
    if inherited_style not in FINANCE_STYLE_IDS:
        inherited_style = "deep_documentary"

    preset = FINANCE_VISUAL_STYLES[inherited_style]
    body_text = _extract_body_text(script_text)
    has_broll = "[B-ROLL" in script_text

    # Detectar si el guion tiene los costes numerados (patrones heurísticos)
    has_numbered_costs = bool(re.search(r"(?i)coste\s+[1-5]|costo\s+[1-5]|número\s+[1-5]", script_text))
    from videomaker.llm.body_visual_language import default_body_visual_plan

    out: dict[str, Any] = {
        "version": 1,
        "narrative_preset": narrative_preset,
        "visual_style_inherited": inherited_style,
        "has_broll": has_broll,
        "has_numbered_costs": has_numbered_costs,
        "style_consistency": {
            "fps": preset.get("editing_fps_hint", 24),
            "lighting": preset.get("lighting"),
            "composition": preset.get("composition"),
            "composition_note": (
                "No aplicar el mismo encuadre de escritorio a todos los beats; "
                "usar composition_hint por macro_beat cuando exista."
            ),
            "color_palette": (
                md_hints.get("color_palette") or preset.get("color_palette")
            ),
            "typography_hint": preset.get("typography_hint"),
            "music_vibe": md_hints.get("music_vibe") or "Ambient minimal, tensión contenida",
        },
        "ia_keywords_body": preset.get("ia_keywords"),
        "prompt_tone": preset.get("opening_architecture_hint"),
        "body_excerpt": body_text[:8000],
        "body_visual_plan": default_body_visual_plan(),
        "_gen": {
            "method": "template",
            "finance_style_id": inherited_style,
            "hook_inherited": bool(cl),
        },
    }
    return out


def _run_body_llm(
    *,
    body_text: str,
    narrative_preset: str | None,
    inherited_style: str,
    inputs: PipelineInputs,
) -> dict[str, Any]:
    from videomaker.llm.metadata_gen import _parse_json_object

    from videomaker.llm.llm_routing import call_production_llm, resolve_production_model

    from videomaker.llm.body_visual_language import body_visual_system_addon

    system = f"""You are a documentary art director for long-form finance essay video (body / Acts 2-4).
Inherited hook style: {inherited_style}. Channel preset: {narrative_preset or "general"}.

{body_visual_system_addon()}

Return ONLY valid JSON:
{{
  "acts_summary": [{{"id": "acto_2|acto_3|acto_4", "label": "string", "visual_pillar": "pillar_1|pillar_2|pillar_3", "visual_note": "string"}}],
  "body_visual_plan": {{ "pillars": {{}}, "rules": [] }},
  "macro_beats": [
    {{
      "act": "acto_2|acto_3|acto_4|body",
      "visual_pillar": "pillar_1|pillar_2|pillar_3",
      "text_anchor": "EXACT phrase from script (metadata only — do NOT illustrate literally in ai_prompt)",
      "track": "avatar|insert",
      "narrator_visible": true,
      "emotional_state": "e.g. quiet anxiety, material ease, dawning clarity",
      "visual_subtext": "what the image should MAKE THE VIEWER FEEL (not what narration says)",
      "shot_hierarchy": "support|support_build|anchor|afterglow",
      "is_anchor_shot": false,
      "anchor_motif": "only if anchor: e.g. woman in fleece vest, warm suburban interior",
      "color_temperature": "warm|cool|split",
      "light_quality": "must match pillar zone",
      "composition_for_animation": "subject position + room for Ken Burns",
      "subject_position": "left_third|right_third|center_low|center_high",
      "camera_motion": "static|slow_pull_out|slow_push_in",
      "rhythm_tier": "medium|slow",
      "ai_prompt": "insert only: English still prompt with color temperature + composition + subtext — NEVER literal narration illustration"
    }}
  ],
  "style_notes": "string",
  "music_evolution": "string"
}}
macro_beats rules:
- One beat per outline bullet or clear narrative turn — do NOT over-split (body needs 4–6s holds, not hook-fast cuts).
- Minimum 12 macro_beats; ≥60% insert. Mark exactly ONE is_anchor_shot=true per visual_pillar.
- pillar_1 anchors: domestic warmth (e.g. fleece vest woman). pillar_2: solitude/screens. pillar_3: split-world contrast.
- ai_prompt: dual channel — emotional subtext, explicit light phrase, subject_position for animation.
Style {inherited_style}. No repeated "desk macro keyboard" stock.
"""
    user = f"--- CUERPO DEL GUION (Actos 2-4) ---\n{body_text[:12000]}"

    try:
        temp = float(os.environ.get("VIDEOMAKER_BODY_ROUTER_TEMPERATURE", "0.3"))
    except ValueError:
        temp = 0.3

    def call() -> str:
        return call_production_llm(
            system=system,
            user=user,
            model=resolve_production_model(inputs.model),
            response_json=True,
            temperature=temp,
        )

    raw = call()
    try:
        return _parse_json_object(raw)
    except ValueError as e:
        raise RuntimeError(f"Body Router LLM: {e}") from e


def build_body_router_bundle(
    work_dir: Path,
    script_text: str,
    inputs: PipelineInputs,
) -> dict[str, Any]:
    from videomaker.llm.hook_scene_router import narrative_preset_from_work
    from videomaker.core.hook_router_settings_store import read_hook_router_settings

    narrative_preset = narrative_preset_from_work(work_dir)
    settings = read_hook_router_settings(work_dir)
    mode = str(settings.get("mode") or "template").strip().lower()
    if mode not in ("llm", "template"):
        mode = "template"

    if mode == "llm":
        hook = _load_hook_router(work_dir)
        cl = hook.get("classification") if isinstance(hook, dict) else None
        inherited_style = (
            str(cl.get("finance_style_id") or "").strip() if isinstance(cl, dict) else ""
        ) or "deep_documentary"
        if inherited_style not in FINANCE_STYLE_IDS:
            inherited_style = "deep_documentary"
        body_text = _extract_body_text(script_text)
        hook_text = _extract_hook_text_for_plan(script_text)
        try:
            llm_data = _run_body_llm(
                body_text=body_text,
                narrative_preset=narrative_preset,
                inherited_style=inherited_style,
                inputs=inputs,
            )
        except RuntimeError:
            llm_data = {}
        bundle = _build_template_bundle(work_dir, script_text, narrative_preset)
        bundle["llm_enrichment"] = llm_data
        bundle["_gen"]["method"] = "llm+template"
        body_text = _extract_body_text(script_text)
        from videomaker.llm.body_macro_beats import finalize_macro_beats

        return finalize_macro_beats(work_dir, bundle, body_text)

    bundle = _build_template_bundle(work_dir, script_text, narrative_preset)
    body_text = _extract_body_text(script_text)
    hook_text = _extract_hook_text_for_plan(script_text)
    from videomaker.llm.body_macro_beats import finalize_macro_beats
    from videomaker.llm.section_density_plan import build_section_density_plan

    bundle = finalize_macro_beats(work_dir, bundle, body_text)
    plan = build_section_density_plan(
        work_dir,
        script_text=script_text,
        hook_text=hook_text,
        body_text=body_text,
    )
    bundle["visual_density_plan"] = plan.to_dict()
    return bundle


def run_body_scene_router_step(work_dir: Path, script_text: str, inputs: PipelineInputs) -> Path:
    bundle = build_body_router_bundle(work_dir, script_text, inputs)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "body_scene_router.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


_BODY_SHOT_ROTATION: list[dict[str, str]] = [
    {
        "shot_type": "broll_cutaway",
        "director_note": (
            "B-roll insert: hands, props, screen detail, or environment cutaway — "
            "not a static talking-head hold."
        ),
    },
    {
        "shot_type": "close_up",
        "director_note": (
            "Tight close-up on face or hands; emotional beat; shallow depth of field."
        ),
    },
    {
        "shot_type": "over_shoulder",
        "director_note": (
            "Over-shoulder or POV toward screen, document, or object the narration names."
        ),
    },
    {
        "shot_type": "wide_context",
        "director_note": (
            "Wider angle or new composition; change location or camera height vs previous cut."
        ),
    },
    {
        "shot_type": "data_ui",
        "director_note": (
            "UI/data moment: chart, notification, calculator, or article — protagonist hands in frame."
        ),
    },
]


def read_body_macro_beats(work_dir: Path) -> list[dict[str, Any]]:
    p = work_dir / "pipeline" / "body_scene_router.json"
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, dict):
        return []
    from videomaker.llm.body_macro_beats import normalize_macro_beats

    beats = normalize_macro_beats(raw.get("macro_beats") or raw.get("acts"))
    return beats


def merge_body_router_into_image_prompts(
    work_dir: Path,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Añade prompts del cuerpo desde ``macro_beats`` al bundle de imágenes."""
    from videomaker.llm.router_driven_image_prompts import append_body_prompts_to_bundle

    return append_body_prompts_to_bundle(work_dir, existing=existing)


def plan_chunk_visual_splits_from_router(
    work_dir: Path,
    chunk: Any,
    shots_needed: int,
) -> list[dict[str, str]]:
    """
    Pistas de sub-planos para un bloque largo (sin LLM).

    Usa ``body_scene_router.json`` si existe; si no, plantillas por defecto.
    """
    n = max(2, min(8, int(shots_needed)))
    router: dict[str, Any] = {}
    p = work_dir / "pipeline" / "body_scene_router.json"
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            router = raw if isinstance(raw, dict) else {}
        except Exception:
            router = {}

    keywords = router.get("ia_keywords_body")
    kw_list: list[str] = []
    if isinstance(keywords, list):
        kw_list = [str(x).strip() for x in keywords if str(x).strip()][:6]
    elif isinstance(keywords, str) and keywords.strip():
        kw_list = [keywords.strip()]

    sc = router.get("style_consistency") if isinstance(router.get("style_consistency"), dict) else {}
    lighting = str(sc.get("lighting") or "cinematic, motivated key light").strip()
    has_broll = bool(router.get("has_broll"))

    out: list[dict[str, str]] = []
    for i in range(n):
        base = dict(_BODY_SHOT_ROTATION[i % len(_BODY_SHOT_ROTATION)])
        note = base["director_note"]
        if has_broll and i % 2 == 0:
            note = f"{note} Prefer literal B-roll from narration."
        note = f"{note} Lighting: {lighting}."
        if kw_list:
            note = f"{note} Style keywords: {', '.join(kw_list[:4])}."
        section = getattr(chunk, "section", None) or ""
        if section:
            note = f"{note} Section: {section}."
        out.append({"shot_type": base["shot_type"], "director_note": note})
    return out
