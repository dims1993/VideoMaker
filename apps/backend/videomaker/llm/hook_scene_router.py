"""Hook Scene Router: clasifica el gancho (Acto 1) y define ruta visual → Image Prompt Writer."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from videomaker.core.hook_router_settings_store import (
    effective_hook_system_prompt_override,
    read_hook_router_settings,
)
from videomaker.core.metadata_settings_store import read_metadata_settings
from videomaker.core.script_bundle import extract_outline_and_body, read_script_bundle
from videomaker.llm.hook_retention_router import (
    build_retention_router_bundle,
    normalize_platform,
    normalize_visual_energy,
    resolve_talking_head_after_sec,
)
from videomaker.llm.hook_router_presets import FINANCE_VISUAL_STYLES, FINANCE_STYLE_IDS
from videomaker.llm.output_language import normalize_language_code
from videomaker.pipeline.models import PipelineInputs

_PATTERN_ACT2 = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?(?:Acto\s*2|Act\s*2|Acto\s*II|Parte\s*2)(?:\*\*)?\b",
)

# editorial.hook_type (metadata.json) → finance_style_id cuando el Router está en auto + plantilla.
_HOOK_TYPE_TO_FINANCE_STYLE: dict[str, str] = {
    "paradox": "data_minimalist",
    "statistic": "data_minimalist",
    "data": "data_minimalist",
    "scene": "deep_documentary",
    "documentary": "deep_documentary",
    "invitation": "intimate_pov",
    "pov": "intimate_pov",
    "systemic": "financial_noir",
    "noir": "financial_noir",
}


def read_metadata_hook_hints(work_dir: Path) -> dict[str, Any]:
    """Pistas de gancho desde ``packaging.json`` (hook-first) o ``metadata.json``."""
    md: dict[str, Any] = {}
    for name in ("packaging.json", "metadata.json"):
        p = work_dir / "pipeline" / name
        if not p.is_file():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                md = raw
                break
        except Exception:
            continue
    if not md:
        return {}
    ed = md.get("editorial") if isinstance(md.get("editorial"), dict) else {}
    prod = md.get("production") if isinstance(md.get("production"), dict) else {}
    mkt = md.get("marketing") if isinstance(md.get("marketing"), dict) else {}
    hook_type = str(ed.get("hook_type") or "").strip().lower()
    hook_summary = str(ed.get("hook_summary") or "").strip()
    return {
        "hook_type": hook_type or None,
        "hook_summary": hook_summary or None,
        "hook_scene_route": str(prod.get("hook_scene_route") or "").strip() or None,
        "visual_style_reference": str(prod.get("visual_style_reference") or "").strip() or None,
        "color_palette": prod.get("color_palette") if isinstance(prod.get("color_palette"), list) else None,
        "music_vibe": str(prod.get("music_vibe") or "").strip() or None,
        "thumbnail_hook_text": str(mkt.get("thumbnail_hook_text") or "").strip() or None,
        "target_audience": str(mkt.get("target_audience") or "").strip() or None,
    }


def _metadata_hook_context_lines(hints: dict[str, Any]) -> str:
    lines: list[str] = []
    if hints.get("hook_type"):
        lines.append(f"editorial.hook_type: {hints['hook_type']}")
    if hints.get("hook_summary"):
        hs = str(hints["hook_summary"])[:700]
        lines.append(f"editorial.hook_summary: {hs}")
    if hints.get("hook_scene_route"):
        lines.append(f"production.hook_scene_route: {hints['hook_scene_route']}")
    if hints.get("visual_style_reference"):
        lines.append(f"production.visual_style_reference: {hints['visual_style_reference']}")
    return "\n".join(lines)


def _thumbnail_narrative_lines(work_dir: Path) -> str:
    """Carry thumbnail narrative spine into hook router context."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return ""
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return ""
    tn = raw.get("thumbnail_narrative") if isinstance(raw, dict) else None
    if not isinstance(tn, dict):
        return ""
    core = str(tn.get("core_contrast") or "").strip()
    role = str(tn.get("viewer_role") or "").strip()
    envy = str(tn.get("envy_target") or "").strip()
    emo = str(tn.get("emotion") or "").strip()
    if not (core or role or envy or emo):
        return ""
    return "\n".join(
        [
            "thumbnail_narrative (spine; hook must feel like thumbnail story):",
            f"- core_contrast: {core or '—'}",
            f"- viewer_role: {role or '—'}",
            f"- envy_target: {envy or '—'}",
            f"- emotion: {emo or '—'}",
        ]
    ).strip()


def _scroll_stop_factors_lines(work_dir: Path) -> str:
    """Carry scroll-stop factors into hook router context."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return ""
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return ""
    ssf = raw.get("scroll_stop_factors") if isinstance(raw, dict) else None
    if not isinstance(ssf, list):
        return ""
    vals = [str(x).strip() for x in ssf if str(x).strip()][:10]
    if not vals:
        return ""
    return "\n".join(
        [
            "scroll_stop_factors (spine; drive subtitle emphasis + pattern interrupts):",
            "- " + ", ".join(vals),
        ]
    ).strip()


def _viewer_state_lines(work_dir: Path) -> str:
    """Carry audience emotional state into hook router context."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return ""
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(raw, dict):
        return ""
    vsb = raw.get("viewer_state_before_click")
    vsa = raw.get("viewer_state_after_video")
    lines: list[str] = []
    if isinstance(vsb, dict) and vsb:
        pairs = []
        for k, v in vsb.items():
            kk = str(k).strip()
            if not kk:
                continue
            try:
                n = int(float(v))  # type: ignore[arg-type]
            except Exception:
                continue
            n = max(0, min(100, n))
            pairs.append((kk, n))
        if pairs:
            pairs.sort(key=lambda x: x[1], reverse=True)
            lines.append("viewer_state_before_click (spine; hook calibration):")
            lines.append("- " + ", ".join([f"{k}:{n}" for k, n in pairs[:8]]))
    if isinstance(vsa, dict) and vsa:
        pairs = []
        for k, v in vsa.items():
            kk = str(k).strip()
            if not kk:
                continue
            try:
                n = int(float(v))  # type: ignore[arg-type]
            except Exception:
                continue
            n = max(0, min(100, n))
            pairs.append((kk, n))
        if pairs:
            pairs.sort(key=lambda x: x[1], reverse=True)
            lines.append("viewer_state_after_video (spine; resolution color):")
            lines.append("- " + ", ".join([f"{k}:{n}" for k, n in pairs[:8]]))
    return "\n".join(lines).strip()


def _energy_curve_lines(work_dir: Path) -> str:
    """Carry energy curve into hook router context."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return ""
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return ""
    ec = raw.get("energy_curve") if isinstance(raw, dict) else None
    if not isinstance(ec, list):
        return ""
    vals = [str(x).strip() for x in ec if str(x).strip()][:12]
    if not vals:
        return ""
    return "\n".join(
        [
            "energy_curve (spine; drive cut/motion/music/subtitle intensity):",
            "- " + " → ".join(vals),
        ]
    ).strip()


def _visual_density_lines(work_dir: Path) -> str:
    """Carry visual density rules into hook router context."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return ""
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return ""
    vd = raw.get("visual_density") if isinstance(raw, dict) else None
    if not isinstance(vd, dict) or not vd:
        return ""
    rows = []
    for k, v in vd.items():
        kk = str(k).strip()
        vv = str(v).strip()
        if not kk or not vv:
            continue
        rows.append(f"- {kk}: {vv}")
        if len(rows) >= 10:
            break
    if not rows:
        return ""
    return "\n".join(
        [
            "visual_density (spine; drive cut frequency + subtitle aggressiveness):",
            *rows,
        ]
    ).strip()


def _credibility_rules_lines(work_dir: Path) -> str:
    """Carry credibility rules into hook router context (anti-ragebait)."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return ""
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return ""
    cr = raw.get("credibility_rules") if isinstance(raw, dict) else None
    if not isinstance(cr, dict) or not cr:
        return ""
    rows = []
    for k, v in cr.items():
        kk = str(k).strip()
        if not kk:
            continue
        vv = v if isinstance(v, bool) else str(v).strip().lower() in ("true", "1", "yes", "y", "si", "sí")
        rows.append(f"- {kk}: {str(vv).lower()}")
        if len(rows) >= 12:
            break
    if not rows:
        return ""
    return "\n".join(
        [
            "credibility_rules (spine; anti-ragebait; avoid overclaiming):",
            *rows,
        ]
    ).strip()


def _hook_spine_lines(work_dir: Path) -> str:
    """Extra spine for Hook Scene Router: triggers, symbols, energy."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return ""
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(raw, dict):
        return ""
    lines: list[str] = []
    pt = str(raw.get("primary_trigger") or "").strip()
    ts = raw.get("trigger_stack") if isinstance(raw.get("trigger_stack"), list) else []
    vals = [str(x).strip() for x in ts if str(x).strip()][:8] if isinstance(ts, list) else []
    if pt or vals:
        lines.append("emotional_triggers (spine):")
        if pt:
            lines.append(f"- primary_trigger: {pt}")
        if vals:
            lines.append(f"- trigger_stack: {', '.join(vals)}")
    de = str(raw.get("dominant_emotion") or "").strip()
    if de:
        lines.append(f"dominant_emotion (spine): {de}")
    tribe = str(raw.get("tribe_boundary") or "").strip()
    if tribe:
        lines.append(f"tribe_boundary (spine): {tribe}")
    va = str(raw.get("visual_anchor") or "").strip()
    if va:
        lines.append(f"visual_anchor (spine): {va}")
    vs = raw.get("visual_symbols") if isinstance(raw.get("visual_symbols"), list) else []
    if isinstance(vs, list) and vs:
        rows = []
        for r in vs:
            if not isinstance(r, dict):
                continue
            sym = str(r.get("symbol") or "").strip()
            meaning = str(r.get("meaning") or "").strip()
            if not sym and not meaning:
                continue
            rows.append(f"- {sym}: {meaning}".strip())
            if len(rows) >= 6:
                break
        if rows:
            lines.append("visual_symbols (spine):")
            lines.extend(rows)
    return "\n".join(lines).strip()


def narrative_preset_from_work(work_dir: Path) -> str | None:
    """Lee `narrative_preset` desde plantilla Script Writer si está en catalog."""
    pj = work_dir / "pipeline" / "prompt.json"
    if not pj.is_file():
        return None
    try:
        raw = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return None
    cat = raw.get("catalog") if isinstance(raw, dict) else None
    if not isinstance(cat, dict):
        return None
    sw_tid = str(cat.get("script_writer_template_id") or "").strip()
    if not sw_tid:
        np = str(cat.get("narrative_preset") or "").strip().lower()
        return np or None
    try:
        from videomaker.llm.script_writer_templates_store import get_script_writer_template

        row = get_script_writer_template(sw_tid)
        if not row:
            return None
        pjr = row.get("params_json") or {}
        if not isinstance(pjr, dict):
            return None
        np = str(pjr.get("narrative_preset") or "").strip().lower()
        return np or None
    except Exception:
        return None


def extract_hook_narration(work_dir: Path, script_text: str) -> str:
    """Texto narrativo del primer bloque (gancho) o primer tramo antes de Acto 2."""
    bundle = read_script_bundle(work_dir)
    if bundle and isinstance(bundle.get("sections"), list) and bundle["sections"]:
        sec0 = bundle["sections"][0]
        parts = sec0.get("parts") if isinstance(sec0, dict) else None
        if isinstance(parts, list):
            lines: list[str] = []
            for p in parts:
                if not isinstance(p, dict):
                    continue
                if p.get("type") == "narration":
                    t = str(p.get("text") or "").strip()
                    if t:
                        lines.append(t)
            text = "\n".join(lines)
            if text.strip():
                return text

    _, body = extract_outline_and_body(script_text)
    m = _PATTERN_ACT2.search(body)
    if m:
        body = body[: m.start()]
    return (body.strip())[:8000]


_RULE_CLASSIFIER: list[tuple[str, list[str]]] = [
    (
        "data_minimalist",
        [
            r"%",
            r"\d+\s*%",
            r"97\s*%",
            r"estadíst",
            r"número",
            r"por\s*ciento",
            r"\bdatos\b",
            r"\bdato\b",
            r"mercado",
            r"gráfico",
            r"encuesta",
        ],
    ),
    (
        "intimate_pov",
        [
            r"imagina",
            r"piensa",
            r"\btú\b",
            r"tu\s+cocina",
            r"mental",
            r"invitaci[oó]n",
            r"persona\s+que",
        ],
    ),
    (
        "deep_documentary",
        [
            r"noche",
            r"silencio",
            r"pantalla",
            r"reloj",
            r"café",
            r"documental",
            r"sombras",
            r"macro",
        ],
    ),
    (
        "financial_noir",
        [
            r"ciudad",
            r"bolsa",
            r"financier",
            r"sistema",
            r"global",
            r"banco",
            r"crisis",
            r"ne[oó]n",
            r"cristal",
        ],
    ),
]


def classify_finance_hook_style(hook_text: str) -> str:
    """Clasificador por palabras clave (plantilla / fallback)."""
    t = hook_text.lower()
    scores: dict[str, int] = {k: 0 for k in FINANCE_STYLE_IDS}
    for sid, patterns in _RULE_CLASSIFIER:
        for p in patterns:
            if re.search(p, t, re.I):
                scores[sid] = scores.get(sid, 0) + 1
    best = max(scores, key=lambda k: scores[k])
    if scores[best] <= 0:
        return "deep_documentary"
    return best


def _default_router_system_prompt() -> str:
    return """Eres un director de arte y editor de vídeo financiero/educativo.
Analiza SOLO el texto del gancho (Acto 1 / hook) proporcionado.
Identifica cuál de estas arquitecturas de apertura encaja mejor:
- POV_Story (invitación mental, "imagina", segunda persona íntima)
- Data_Driven (dato, porcentaje, estadística, paradoja numérica)
- Documentary_Intimate (hiperconcreto, objetos cotidianos, claroscuro reflexivo)
- Noir_Systemic (sistema financiero, ciudad, mercado global, frío)

Responde SOLO con un objeto JSON (sin markdown):
{
  "opening_architecture": "POV_Story | Data_Driven | Documentary_Intimate | Noir_Systemic",
  "finance_style_id": "deep_documentary | data_minimalist | financial_noir | intimate_pov",
  "visual_route_label": "string corta",
  "color_palette": ["color1", "color2", "color3"],
  "editing_fps_hint": 24,
  "ia_keyword_bundle": "palabras clave separadas por coma para generación de imagen",
  "typography_hint": "string",
  "lighting_notes": "string",
  "composition_notes": "string",
  "psychological_impact": "string"
}

Reglas:
- finance_style_id debe ser coherente con opening_architecture (p. ej. Data_Driven → data_minimalist).
- ia_keyword_bundle debe ser inglés mix cinematográfico apto para SD/Midjourney-style prompts.
"""


def _parse_router_llm_json(raw: str) -> dict[str, Any]:
    from videomaker.llm.metadata_gen import _parse_json_object  # reuse fence tolerant parser

    return _parse_json_object(raw)


def _run_router_llm(
    *,
    hook_text: str,
    narrative_preset: str | None,
    system_extra: str,
    inputs: PipelineInputs,
    metadata_context: str = "",
) -> dict[str, Any]:
    from videomaker.llm.llm_routing import call_production_llm, resolve_production_model

    sys_base = (system_extra.strip() or _default_router_system_prompt())
    ctx = f"Categoría narrativa sesión (si aplica): {narrative_preset or 'no indicada'}.\n\n--- GANCHO (Acto 1) ---\n{hook_text}"
    if metadata_context.strip():
        ctx = f"{ctx}\n\n--- Pistas desde pipeline/metadata.json ---\n{metadata_context.strip()}"
    try:
        meta_temp = float(os.environ.get("VIDEOMAKER_HOOK_ROUTER_TEMPERATURE", "0.25"))
    except ValueError:
        meta_temp = 0.25
    json_mode = (os.environ.get("VIDEOMAKER_HOOK_ROUTER_JSON_MODE", "") or "").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

    def call_llm() -> str:
        return call_production_llm(
            system=sys_base,
            user=ctx,
            model=resolve_production_model(inputs.model),
            response_json=json_mode,
            temperature=meta_temp,
        )

    raw = call_llm()
    try:
        return _parse_router_llm_json(raw)
    except ValueError as e:
        raise RuntimeError(f"Hook Router LLM: {e}") from e


def _metadata_target_platform(work_dir: Path) -> str | None:
    st = read_metadata_settings(work_dir)
    tp = str(st.get("target_platform") or "").strip().lower()
    return tp or None


def _enrich_with_finance_preset(out: dict[str, Any], finance_sel: str) -> dict[str, Any]:
    """Aplica override de estilo finanzas y enriquece visual_direction desde catálogo."""
    cl = out.get("classification") if isinstance(out.get("classification"), dict) else {}
    sid = str(cl.get("finance_style_id") or "deep_documentary").strip().lower()
    if finance_sel != "auto" and finance_sel in FINANCE_STYLE_IDS:
        sid = finance_sel
        cl = dict(cl)
        cl["finance_style_id"] = sid
        cl["style_resolution"] = "settings_fixed"
        out["classification"] = cl
    preset = FINANCE_VISUAL_STYLES.get(sid, FINANCE_VISUAL_STYLES["deep_documentary"])
    vd = out.get("visual_direction") if isinstance(out.get("visual_direction"), dict) else {}
    out["visual_direction"] = {
        **vd,
        "label": vd.get("label") or preset.get("label"),
        "lighting": vd.get("lighting") or preset.get("lighting"),
        "composition": vd.get("composition") or preset.get("composition"),
        "color_palette": vd.get("color_palette") or preset.get("color_palette"),
        "typography_hint": vd.get("typography_hint") or preset.get("typography_hint"),
        "editing_fps_hint": vd.get("editing_fps_hint") or preset.get("editing_fps_hint"),
    }
    bridge = out.get("bridge_to_images") if isinstance(out.get("bridge_to_images"), dict) else {}
    if not str(bridge.get("ia_keywords") or "").strip():
        bridge = {**bridge, "ia_keywords": preset.get("ia_keywords")}
    if not str(bridge.get("prompt_tone") or "").strip():
        bridge = {**bridge, "prompt_tone": preset.get("opening_architecture_hint")}
    out["bridge_to_images"] = bridge
    return out


def build_router_bundle(
    *,
    work_dir: Path,
    script_text: str,
    inputs: PipelineInputs,
) -> dict[str, Any]:
    settings = read_hook_router_settings(work_dir)
    mode = str(settings.get("mode") or "llm").strip().lower()
    if mode not in ("llm", "template"):
        mode = "llm"

    finance_sel = str(settings.get("finance_style") or "auto").strip().lower()
    if finance_sel not in ("auto",) + FINANCE_STYLE_IDS:
        finance_sel = "auto"

    plat_setting = str(settings.get("platform") or "auto").strip().lower()
    energy_setting = str(settings.get("visual_energy") or "auto").strip().lower()
    meta_platform = _metadata_target_platform(work_dir)
    platform = normalize_platform(
        None if plat_setting == "auto" else plat_setting,
        meta_platform,
    )
    visual_energy = normalize_visual_energy(
        None if energy_setting == "auto" else energy_setting,
        platform,
    )

    narrative_preset = narrative_preset_from_work(work_dir)
    hook_text = extract_hook_narration(work_dir, script_text)
    if not hook_text.strip():
        raise ValueError("No se pudo extraer texto del gancho (Acto 1). Revisa guion.txt / script.json.")

    sys_override = effective_hook_system_prompt_override(settings)
    md_hints = read_metadata_hook_hints(work_dir)
    meta_ctx = _metadata_hook_context_lines(md_hints)
    tn_ctx = _thumbnail_narrative_lines(work_dir)
    if tn_ctx:
        meta_ctx = (meta_ctx + "\n" if meta_ctx else "") + tn_ctx
    ssf_ctx = _scroll_stop_factors_lines(work_dir)
    if ssf_ctx:
        meta_ctx = (meta_ctx + "\n" if meta_ctx else "") + ssf_ctx
    vs_ctx = _viewer_state_lines(work_dir)
    if vs_ctx:
        meta_ctx = (meta_ctx + "\n" if meta_ctx else "") + vs_ctx
    ec_ctx = _energy_curve_lines(work_dir)
    if ec_ctx:
        meta_ctx = (meta_ctx + "\n" if meta_ctx else "") + ec_ctx
    vd_ctx = _visual_density_lines(work_dir)
    if vd_ctx:
        meta_ctx = (meta_ctx + "\n" if meta_ctx else "") + vd_ctx
    cr_ctx = _credibility_rules_lines(work_dir)
    if cr_ctx:
        meta_ctx = (meta_ctx + "\n" if meta_ctx else "") + cr_ctx
    hs_ctx = _hook_spine_lines(work_dir)
    if hs_ctx:
        meta_ctx = (meta_ctx + "\n" if meta_ctx else "") + hs_ctx
    audience = str(md_hints.get("target_audience") or "").strip()
    lang = normalize_language_code(inputs.lang or "es")

    th_after = resolve_talking_head_after_sec(
        platform, settings.get("talking_head_after_sec")
    )
    from videomaker.llm.body_scene_router import _extract_body_text
    from videomaker.llm.hook_audio_density import densify_hook_micro_beats
    from videomaker.llm.section_density_plan import (
        build_section_density_plan,
        hook_max_beats_for_platform,
    )

    body_text = _extract_body_text(script_text)
    plan = build_section_density_plan(
        work_dir,
        script_text=script_text,
        hook_text=hook_text,
        body_text=body_text,
    )
    beat_cap = hook_max_beats_for_platform(platform, plan)

    out = build_retention_router_bundle(
        hook_text=hook_text,
        inputs=inputs,
        platform=platform,
        visual_energy=visual_energy,
        mode=mode,
        system_override=sys_override,
        metadata_context=meta_ctx,
        audience_context=audience,
        narrative_preset=narrative_preset,
        lang=lang,
        talking_head_after_sec=th_after,
        max_beats_cap=beat_cap,
        hook_duration_sec=plan.hook_pool_s,
    )
    mb = out.get("micro_beats")
    if isinstance(mb, list):
        mb = densify_hook_micro_beats(
            mb,
            hook_text,
            plan,
            platform=platform,
            visual_energy=visual_energy,
        )
        from videomaker.llm.hook_visual_sequence import finalize_hook_visual_sequence

        parsed_seq = out.get("visual_sequence_plan") if isinstance(out.get("visual_sequence_plan"), dict) else None
        mb, seq_plan = finalize_hook_visual_sequence(
            mb,
            target_beats=beat_cap,
            hook_pool_s=plan.hook_pool_s,
            parsed_plan=parsed_seq,
        )
        from videomaker.llm.narrative_visual_rhythm import apply_hook_narrative_rhythm
        from videomaker.llm.section_anchor_shot import apply_hook_anchor_hierarchy

        mb, anchor_plan = apply_hook_anchor_hierarchy(mb, parsed_seq)
        mb, rhythm_summary = apply_hook_narrative_rhythm(mb, plan.hook_pool_s)
        if isinstance(seq_plan, dict):
            seq_plan["narrative_rhythm"] = rhythm_summary
            seq_plan["anchor_shot"] = anchor_plan
        out["micro_beats"] = mb
        out["visual_sequence_plan"] = seq_plan
        out["narrative_rhythm"] = rhythm_summary
        out["anchor_shot"] = anchor_plan
        out["micro_beat_count"] = len(mb)
    out["visual_density_plan"] = plan.to_dict()
    out["settings"] = {
        "mode": mode,
        "finance_style": finance_sel,
        "platform": platform,
        "visual_energy": visual_energy,
    }
    mb = {k: v for k, v in md_hints.items() if v not in (None, [], {})}
    if mb:
        out["metadata_bridge"] = mb

    out = _enrich_with_finance_preset(out, finance_sel)
    return out


def run_hook_scene_router_step(work_dir: Path, script_text: str, inputs: PipelineInputs) -> Path:
    bundle = build_router_bundle(work_dir=work_dir, script_text=script_text, inputs=inputs)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "hook_scene_router.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _beat_image_prompt_text(beat: dict[str, Any], *, global_kw: str, label: str) -> str:
    from videomaker.llm.hook_retention_router import resolve_image_prompt_for_beat

    cinematic = resolve_image_prompt_for_beat(beat).strip()
    style = str(beat.get("visual_style") or "").strip().lower()
    if style == "noir":
        cinematic = f"{cinematic}, film noir, high contrast shadows"
    elif style == "kinetic":
        cinematic = f"{cinematic}, kinetic energy, sharp detail"
    return cinematic


def merge_hook_router_into_image_prompts(work_dir: Path) -> dict[str, Any]:
    """Construye `image_prompts.json` desde `hook_scene_router.json` (puente hacia imágenes)."""
    hr = work_dir / "pipeline" / "hook_scene_router.json"
    if not hr.is_file():
        raise ValueError("Falta pipeline/hook_scene_router.json. Ejecuta el paso Hook Scene Router.")
    try:
        router = json.loads(hr.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(str(e)) from e

    bridge = router.get("bridge_to_images") if isinstance(router, dict) else None
    ia_kw = ""
    if isinstance(bridge, dict):
        ia_kw = str(bridge.get("ia_keywords") or "").strip()

    vd = router.get("visual_direction") if isinstance(router, dict) else None
    label = ""
    if isinstance(vd, dict):
        label = str(vd.get("label") or "").strip()

    hook_ex = str(router.get("hook_excerpt") or "")[:1200] if isinstance(router, dict) else ""
    beats = router.get("micro_beats") if isinstance(router, dict) else None

    from videomaker.llm.image_prompt_hybrid import (
        _beat_duration_estimated,
        _timing_relative_from_beats,
    )

    prompts: list[dict[str, Any]] = []
    if isinstance(beats, list) and beats:
        beat_dicts = [b for b in beats if isinstance(b, dict)]
        hook_weights = [_beat_duration_estimated(b) for b in beat_dicts]
        for beat_index, beat in enumerate(beat_dicts):
            idx = int(beat.get("index", beat_index))
            prompts.append(
                {
                    "track": "insert",
                    "act": "hook",
                    "role": f"hook_beat_{idx}",
                    "layer": "hook_micro_beat",
                    "timing": _timing_relative_from_beats(
                        beat, beat_index=beat_index, weights=hook_weights
                    ),
                    "purpose": beat.get("purpose"),
                    "intensity": beat.get("intensity"),
                    "audio": beat.get("audio"),
                    "emotion": beat.get("emotion"),
                    "scene_type": beat.get("scene_type"),
                    "narrator_visible": beat.get("narrator_visible"),
                    "transition_to_next": beat.get("transition_to_next"),
                    "viewer_state": beat.get("viewer_state"),
                    "viewer_pacing_hint": beat.get("viewer_pacing_hint"),
                    "camera": beat.get("camera"),
                    "prompt_style": beat.get("prompt_style") or "cinematic_narrative",
                    "text": _beat_image_prompt_text(beat, global_kw=ia_kw, label=label),
                    "text_metadata": {
                        "emotion": beat.get("emotion"),
                        "scene_type": beat.get("scene_type"),
                        "intensity": beat.get("intensity"),
                        "audio": beat.get("audio"),
                        "transition_to_next": beat.get("transition_to_next"),
                        "viewer_state": beat.get("viewer_state"),
                    },
                }
            )
    elif ia_kw:
        prompts.append(
            {
                "role": "hook_establishing",
                "layer": "visual_route",
                "text": f"{label}. {ia_kw}. Context hook: {hook_ex[:600]}",
            }
        )
    else:
        prompts.append(
            {
                "role": "hook_establishing",
                "layer": "visual_route",
                "text": f"Establishing mood for hook. Context: {hook_ex[:900]}",
            }
        )

    router_version = int(router.get("version", 1)) if isinstance(router, dict) else 1
    bundle = {
        "version": 2 if router_version >= 2 else 1,
        "source": "hook_scene_router",
        "router_ref": "pipeline/hook_scene_router.json",
        "classification": router.get("classification") if isinstance(router, dict) else {},
        "retention_analysis": router.get("retention_analysis") if isinstance(router, dict) else None,
        "intensity_curve": router.get("intensity_curve") if isinstance(router, dict) else None,
        "intensity_arc": router.get("intensity_arc") if isinstance(router, dict) else None,
        "audio_design": router.get("audio_design") if isinstance(router, dict) else None,
        "transition_rhythm": router.get("transition_rhythm") if isinstance(router, dict) else None,
        "viewer_state_tracking": router.get("viewer_state_tracking") if isinstance(router, dict) else None,
        "micro_beat_count": len(prompts),
        "prompts": prompts,
    }
    out_p = work_dir / "pipeline" / "image_prompts.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": "pipeline/image_prompts.json", "prompt_count": len(prompts)}
