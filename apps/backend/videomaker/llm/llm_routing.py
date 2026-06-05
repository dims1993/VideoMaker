"""Proveedor LLM por capa del pipeline (convención de producto).

- **Creativo** (Anthropic): Topic Generator, inferencia Prompt, Script Writer.
- **Producción** (OpenAI API): Metadata, Hook Scene Router, Body Scene Router.

La UI puede enviar `provider` de sesión; estos helpers **fijan** el proveedor correcto por paso.
"""

from __future__ import annotations

import os

CREATIVE_PROVIDER = "anthropic"
PRODUCTION_PROVIDER = "openai"


def default_creative_model() -> str:
    return (os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-5").strip()


def default_production_model() -> str:
    return (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()


def resolve_creative_model(model: str | None = None) -> str:
    m = (model or "").strip()
    return m or default_creative_model()


def resolve_production_model(model: str | None = None) -> str:
    m = (model or "").strip()
    return m or default_production_model()


def call_creative_llm(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.6,
    max_tokens: int | None = None,
) -> str:
    from videomaker.llm.providers.anthropic_chat import anthropic_chat

    return anthropic_chat(
        system=system,
        user=user,
        model=resolve_creative_model(model),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def call_production_llm(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.25,
    response_json: bool = False,
) -> str:
    from videomaker.llm.providers.openai_compat import openai_compat_chat

    return openai_compat_chat(
        system=system,
        user=user,
        model=resolve_production_model(model),
        response_json=response_json,
        temperature=temperature,
    ).strip()
