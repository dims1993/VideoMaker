"""Cliente nativo para la API de Anthropic (Claude)."""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def anthropic_chat(
    *,
    system: str,
    user: str,
    model: str = "",
    temperature: float = 0.4,
    max_tokens: int | None = None,
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

    out_tokens = max_tokens if max_tokens is not None else _env_int("ANTHROPIC_MAX_OUTPUT_TOKENS", 8192)
    out_tokens = max(1024, min(out_tokens, 64000))
    timeout_sec = _env_float("ANTHROPIC_TIMEOUT_SEC", 600.0)

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout_sec)
    message = client.messages.create(
        model=resolved_model,
        max_tokens=out_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return (message.content[0].text or "").strip()  # type: ignore[union-attr]
