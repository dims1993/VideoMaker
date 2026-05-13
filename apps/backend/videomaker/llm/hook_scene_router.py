"""Hook Scene Router: clasifica el gancho (Acto 1) y define ruta visual → Image Prompt Writer."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from videomaker.core.hook_router_settings_store import read_hook_router_settings
from videomaker.core.script_bundle import extract_outline_and_body, read_script_bundle
from videomaker.llm.hook_router_presets import FINANCE_VISUAL_STYLES, FINANCE_STYLE_IDS
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
    """Lee pistas de gancho / producción desde pipeline/metadata.json (si existe)."""
    p = work_dir / "pipeline" / "metadata.json"
    if not p.is_file():
        return {}
    try:
        md = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(md, dict):
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
    selected = (inputs.provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER") or "openai").lower()
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
        if selected == "ollama":
            from videomaker.llm.providers.ollama import ollama_chat

            return ollama_chat(
                system=sys_base,
                user=ctx,
                model=inputs.model or os.environ.get("OLLAMA_MODEL", "llama3.2:latest"),
                response_json=json_mode,
                temperature=meta_temp,
            ).strip()

        if selected == "openai":
            from videomaker.llm.providers.openai_compat import openai_compat_chat

            return openai_compat_chat(
                system=sys_base,
                user=ctx,
                model=inputs.model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                response_json=json_mode,
                temperature=meta_temp,
            ).strip()

        raise ValueError(f"Proveedor LLM no soportado: {selected}")

    raw = call_llm()
    try:
        return _parse_router_llm_json(raw)
    except ValueError as e:
        raise RuntimeError(f"Hook Router LLM: {e}") from e


def build_router_bundle(
    *,
    work_dir: Path,
    script_text: str,
    inputs: PipelineInputs,
) -> dict[str, Any]:
    settings = read_hook_router_settings(work_dir)
    mode = str(settings.get("mode") or "template").strip().lower()
    if mode not in ("llm", "template"):
        mode = "template"

    finance_sel = str(settings.get("finance_style") or "auto").strip().lower()
    if finance_sel not in ("auto",) + FINANCE_STYLE_IDS:
        finance_sel = "auto"

    narrative_preset = narrative_preset_from_work(work_dir)
    hook_text = extract_hook_narration(work_dir, script_text)
    if not hook_text.strip():
        raise ValueError("No se pudo extraer texto del gancho (Acto 1). Revisa guion.txt / script.json.")

    sys_override = str(settings.get("system_prompt") or "").strip()
    md_hints = read_metadata_hook_hints(work_dir)
    meta_ctx = _metadata_hook_context_lines(md_hints)

    # Finanzas: usar catálogo de estilos (plantilla o LLM que devuelve finance_style_id)
    use_finance = (narrative_preset or "").lower() == "finanzas"

    out: dict[str, Any] = {
        "version": 1,
        "narrative_preset": narrative_preset,
        "hook_character_count": len(hook_text),
        "settings": {"mode": mode, "finance_style": finance_sel},
    }
    mb = {k: v for k, v in md_hints.items() if v not in (None, [], {})}
    if mb:
        out["metadata_bridge"] = mb

    if use_finance:
        if mode == "template":
            if finance_sel != "auto":
                sid = finance_sel
                tpl_method = "template_fixed"
                style_resolution = "template_fixed"
            else:
                ht = str(md_hints.get("hook_type") or "").strip().lower()
                mapped = _HOOK_TYPE_TO_FINANCE_STYLE.get(ht) if ht else None
                if mapped:
                    sid = mapped
                    tpl_method = "metadata_hook_type"
                    style_resolution = "metadata_hook_type"
                else:
                    sid = classify_finance_hook_style(hook_text)
                    tpl_method = "template_keywords"
                    style_resolution = "keyword_classifier"
            preset = FINANCE_VISUAL_STYLES.get(sid, FINANCE_VISUAL_STYLES["deep_documentary"])
            arch_map = {
                "deep_documentary": "Documentary_Intimate",
                "data_minimalist": "Data_Driven",
                "financial_noir": "Noir_Systemic",
                "intimate_pov": "POV_Story",
            }
            out["classification"] = {
                "method": tpl_method,
                "style_resolution": style_resolution,
                "opening_architecture": arch_map.get(sid, "Documentary_Intimate"),
                "finance_style_id": sid,
            }
            out["visual_direction"] = {
                "label": preset.get("label"),
                "lighting": preset.get("lighting"),
                "composition": preset.get("composition"),
                "color_palette": preset.get("color_palette"),
                "typography_hint": preset.get("typography_hint"),
                "editing_fps_hint": preset.get("editing_fps_hint"),
            }
            out["bridge_to_images"] = {
                "ia_keywords": preset.get("ia_keywords"),
                "prompt_tone": preset.get("opening_architecture_hint"),
            }
        else:
            parsed = _run_router_llm(
                hook_text=hook_text,
                narrative_preset=narrative_preset,
                system_extra=sys_override,
                inputs=inputs,
                metadata_context=meta_ctx,
            )
            sid = str(parsed.get("finance_style_id") or "").strip().lower()
            if sid not in FINANCE_STYLE_IDS:
                sid = classify_finance_hook_style(hook_text)
            preset = FINANCE_VISUAL_STYLES.get(sid, FINANCE_VISUAL_STYLES["deep_documentary"])
            out["classification"] = {
                "method": "llm",
                "style_resolution": "llm",
                "opening_architecture": parsed.get("opening_architecture"),
                "finance_style_id": sid,
                "psychological_impact": parsed.get("psychological_impact"),
            }
            out["visual_direction"] = {
                "label": parsed.get("visual_route_label") or preset.get("label"),
                "lighting": parsed.get("lighting_notes") or preset.get("lighting"),
                "composition": parsed.get("composition_notes") or preset.get("composition"),
                "color_palette": parsed.get("color_palette") or preset.get("color_palette"),
                "typography_hint": parsed.get("typography_hint") or preset.get("typography_hint"),
                "editing_fps_hint": parsed.get("editing_fps_hint") or preset.get("editing_fps_hint"),
            }
            merged_kw = parsed.get("ia_keyword_bundle") or preset.get("ia_keywords")
            out["bridge_to_images"] = {
                "ia_keywords": merged_kw,
                "prompt_tone": preset.get("opening_architecture_hint"),
            }
            out["llm_raw"] = {k: v for k, v in parsed.items() if k != "llm_raw"}
    else:
        # No finanzas: solo LLM genérico o plantilla mínima
        if mode == "llm":
            parsed = _run_router_llm(
                hook_text=hook_text,
                narrative_preset=narrative_preset,
                system_extra=sys_override,
                inputs=inputs,
                metadata_context=meta_ctx,
            )
            out["classification"] = {
                "method": "llm",
                "style_resolution": "llm",
                "opening_architecture": parsed.get("opening_architecture"),
            }
            out["visual_direction"] = {
                "label": parsed.get("visual_route_label"),
                "lighting": parsed.get("lighting_notes"),
                "composition": parsed.get("composition_notes"),
                "color_palette": parsed.get("color_palette"),
                "typography_hint": parsed.get("typography_hint"),
                "editing_fps_hint": parsed.get("editing_fps_hint"),
            }
            out["bridge_to_images"] = {"ia_keywords": parsed.get("ia_keyword_bundle")}
            out["llm_raw"] = parsed
        else:
            sid = classify_finance_hook_style(hook_text)
            preset = FINANCE_VISUAL_STYLES[sid]
            out["classification"] = {
                "method": "template_keywords_generic",
                "style_resolution": "keyword_classifier",
                "finance_style_id": sid,
                "note": "Categoría no finanzas: se usó clasificador de estilo tipo financiero como aproximación.",
            }
            out["visual_direction"] = {
                "label": preset.get("label"),
                "lighting": preset.get("lighting"),
                "composition": preset.get("composition"),
                "color_palette": preset.get("color_palette"),
                "typography_hint": preset.get("typography_hint"),
                "editing_fps_hint": preset.get("editing_fps_hint"),
            }
            out["bridge_to_images"] = {"ia_keywords": preset.get("ia_keywords")}

    out["hook_excerpt"] = hook_text[:2500]
    return out


def run_hook_scene_router_step(work_dir: Path, script_text: str, inputs: PipelineInputs) -> Path:
    bundle = build_router_bundle(work_dir=work_dir, script_text=script_text, inputs=inputs)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "hook_scene_router.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


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

    prompts: list[dict[str, Any]] = []
    if ia_kw:
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

    bundle = {
        "version": 1,
        "source": "hook_scene_router",
        "router_ref": "pipeline/hook_scene_router.json",
        "classification": router.get("classification") if isinstance(router, dict) else {},
        "prompts": prompts,
    }
    out_p = work_dir / "pipeline" / "image_prompts.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": "pipeline/image_prompts.json", "prompt_count": len(prompts)}
