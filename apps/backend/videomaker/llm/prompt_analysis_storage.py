"""Forma canónica de prompt_analysis en transcripts_session (sin duplicados)."""

from __future__ import annotations

from typing import Any

from videomaker.llm.prompt_instruction_contract import split_user_instructions

_SLIM_PJ_KEYS = ("target_audience", "narrative_structure")
_NS_KEYS = ("tone", "hook_type", "cta_type")


def slim_prompt_analysis_payload(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Reduce la respuesta del LLM a lo que la UI aplica al formulario Prompt.
    No guarda output_structure, merged, placeholders ni user_instructions duplicado.
    """
    if not raw or not isinstance(raw, dict):
        return None

    pj_in = raw.get("params_json")
    pj_in = pj_in if isinstance(pj_in, dict) else {}
    ns_in = pj_in.get("narrative_structure")
    ns_in = ns_in if isinstance(ns_in, dict) else {}

    narr_raw = str(
        raw.get("user_instructions_narrative") or raw.get("user_instructions") or ""
    ).strip()
    _, narr_only = split_user_instructions(narr_raw)

    slim_pj: dict[str, Any] = {}
    ta = str(pj_in.get("target_audience") or "").strip()
    if ta:
        slim_pj["target_audience"] = ta
    ns_slim = {k: ns_in[k] for k in _NS_KEYS if str(ns_in.get(k) or "").strip()}
    if ns_slim:
        slim_pj["narrative_structure"] = ns_slim

    out: dict[str, Any] = {}
    name = str(raw.get("name") or "").strip()
    if name:
        out["name"] = name
    sys_i = str(raw.get("system_instructions") or "").strip()
    if sys_i:
        out["system_instructions"] = sys_i
    if narr_only:
        out["user_instructions_narrative"] = narr_only
    if slim_pj:
        out["params_json"] = slim_pj
    lang = str(raw.get("output_language") or "").strip().lower()
    if lang in ("en", "es"):
        out["output_language"] = lang

    return out if out else None
