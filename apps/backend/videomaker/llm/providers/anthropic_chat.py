"""Cliente nativo para la API de Anthropic (Claude)."""

from __future__ import annotations

import os


def anthropic_chat(
    *,
    system: str,
    user: str,
    model: str = "",
    temperature: float = 0.4,
) -> str:
    """
    Requiere:
    - ANTHROPIC_API_KEY en .env
    Opcional:
    - ANTHROPIC_MODEL (por defecto claude-sonnet-4-5)
    """
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "El paquete 'anthropic' no está instalado. Ejecuta: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Falta ANTHROPIC_API_KEY. Añádela a tu .env para usar el generador de prompts con Claude."
        )

    resolved_model = (
        model.strip()
        or os.environ.get("ANTHROPIC_MODEL", "").strip()
        or "claude-sonnet-4-5"
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=resolved_model,
        max_tokens=4096,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return (message.content[0].text or "").strip()  # type: ignore[union-attr]
