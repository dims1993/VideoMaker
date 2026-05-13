"""Body Scene Router: mapea Actos 2-4 a rutas visuales → scene_prompts para Image Prompt Writer."""

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
            "color_palette": (
                md_hints.get("color_palette") or preset.get("color_palette")
            ),
            "typography_hint": preset.get("typography_hint"),
            "music_vibe": md_hints.get("music_vibe") or "Ambient minimal, tensión contenida",
        },
        "ia_keywords_body": preset.get("ia_keywords"),
        "prompt_tone": preset.get("opening_architecture_hint"),
        "body_excerpt": body_text[:3000],
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

    selected = (inputs.provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER") or "openai").lower()
    system = f"""Eres un director de arte especializado en vídeo financiero/educativo.
Analiza el CUERPO del guion (Actos 2-4) proporcionado.
El estilo visual heredado del gancho es: {inherited_style}.
Preset narrativo del canal: {narrative_preset or "general"}.

Devuelve SOLO un objeto JSON con esta estructura:
{{
  "acts_summary": [{{"id": "string", "label": "string", "visual_note": "string"}}],
  "scene_prompts": [{{"act": "string", "role": "string", "ia_prompt": "string (en inglés, apto para Midjourney/SD)", "b_roll": ["string"]}}],
  "style_notes": "string",
  "music_evolution": "string"
}}
Genera al menos 6 scene_prompts cubriendo los momentos visuales más importantes del cuerpo.
Los ia_prompts deben ser en inglés y cinematográficos, coherentes con el estilo {inherited_style}.
"""
    user = f"--- CUERPO DEL GUION (Actos 2-4) ---\n{body_text[:8000]}"

    try:
        temp = float(os.environ.get("VIDEOMAKER_BODY_ROUTER_TEMPERATURE", "0.3"))
    except ValueError:
        temp = 0.3

    def call() -> str:
        if selected == "ollama":
            from videomaker.llm.providers.ollama import ollama_chat
            return ollama_chat(
                system=system, user=user,
                model=inputs.model or os.environ.get("OLLAMA_MODEL", "llama3.2:latest"),
                response_json=True, temperature=temp,
            ).strip()
        from videomaker.llm.providers.openai_compat import openai_compat_chat
        return openai_compat_chat(
            system=system, user=user,
            model=inputs.model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            response_json=True, temperature=temp,
        ).strip()

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
        return bundle

    return _build_template_bundle(work_dir, script_text, narrative_preset)


def run_body_scene_router_step(work_dir: Path, script_text: str, inputs: PipelineInputs) -> Path:
    bundle = build_body_router_bundle(work_dir, script_text, inputs)
    d = work_dir / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "body_scene_router.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
