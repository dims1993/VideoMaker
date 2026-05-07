"""Generación de guion vía proveedor configurable (OpenAI-compatible / Ollama / etc.)."""

from __future__ import annotations

import os
import re
from typing import Callable

from videomaker.core.models import Locale, ScriptBlueprint
from videomaker.llm.prompts import build_user_prompt_from_blueprint, master_script_system_prompt

_PROMPT_ADDON_TITLE = "--- Instrucciones adicionales (plantilla / editor) ---"


def _script_min_words_default() -> int:
    raw = os.environ.get("VIDEOMAKER_SCRIPT_MIN_WORDS", "1500").strip()
    try:
        v = int(raw)
    except ValueError:
        v = 1500
    return max(200, min(v, 5000))


def _strip_non_narrable_for_metrics(text: str) -> str:
    """
    Aproxima el texto narrable para métricas (longitud y densidad visual).

    Quita:
    - Sección OUTLINE (si existe).
    - Bloque final de keywords/stock tags.
    - Líneas de [CATEGORIA: …] y etiquetas [B-ROLL: …].
    """
    t = text or ""

    # Si hay GUIÓN, empezamos ahí. Si no, quitamos OUTLINE si está.
    m = re.search(r"(?im)^\s*(GUI[ÓO]N|GUION)\s*$", t)
    if m:
        t = t[m.end() :]
    else:
        m2 = re.search(r"(?im)^\s*OUTLINE\s*$", t)
        if m2:
            t = t[m2.end() :]

    # Corta keywords para stock al final (no narrable).
    cut = re.search(
        r"(?im)^\s*(KEYWORDS\s+PARA\s+STOCK|TAGS?\s+PARA\s+STOCK|KEYWORDS?\s*(PEXELS)?|B[- ]?ROLL\s+TAGS?)\b.*$",
        t,
    )
    if cut:
        t = t[: cut.start()]

    # Quita líneas de categoría y cualquier [B-ROLL: ...] inline.
    t = re.sub(r"(?im)^\s*\[CATEGORIA\s*:[^\]]+\]\s*$", "", t)
    t = re.sub(r"(?i)\[B-ROLL\s*:?[^\]]*\]", "", t)

    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _count_narrable_words(text: str) -> int:
    t = _strip_non_narrable_for_metrics(text)
    return len(re.findall(r"\b\w+\b", t, flags=re.UNICODE))


def _count_broll_tags(text: str) -> int:
    return len(re.findall(r"(?i)\[B-ROLL\s*:?[^\]]*\]", text or ""))


def _count_sentences_narrable(text: str) -> int:
    """
    Conteo aproximado de oraciones para verificar: 1 [B-ROLL] cada 2 oraciones.
    """
    t = _strip_non_narrable_for_metrics(text)
    parts = re.split(r"[.!?]+(?:\s+|$)", t)
    return len([p for p in parts if re.search(r"\w", p)])


def _script_issues(text: str, *, min_words: int) -> list[str]:
    issues: list[str] = []
    words = _count_narrable_words(text)
    if words < min_words:
        issues.append(
            f"- Longitud insuficiente: {words} palabras narrables (mínimo {min_words}, sin contar etiquetas)."
        )
    sentences = _count_sentences_narrable(text)
    broll = _count_broll_tags(text)
    need = max(0, sentences // 2)
    if broll < need:
        issues.append(
            f"- Densidad B-ROLL insuficiente: {broll} etiquetas para ~{sentences} oraciones (objetivo ≥ {need})."
        )
    return issues


def compose_messages(
    blueprint: ScriptBlueprint,
    *,
    system_extra: str = "",
    user_extra: str = "",
) -> tuple[str, str]:
    system = master_script_system_prompt(blueprint.locale, blueprint.target_minutes)
    user = build_user_prompt_from_blueprint(blueprint)
    se = (system_extra or "").strip()
    ue = (user_extra or "").strip()
    if se:
        system = system.rstrip() + f"\n\n{_PROMPT_ADDON_TITLE}\n\n" + se
    if ue:
        user = user.rstrip() + f"\n\n{_PROMPT_ADDON_TITLE}\n\n" + ue
    return system, user


def generate_script(
    blueprint: ScriptBlueprint,
    *,
    provider: str | None = None,
    model: str | None = None,
    system_extra: str = "",
    user_extra: str = "",
) -> str:
    """
    Llama al proveedor configurado.

    Proveedores soportados:
    - openai: API compatible OpenAI chat/completions (OPENAI_API_KEY + OPENAI_BASE_URL opcional)
    - ollama: servidor local Ollama (OLLAMA_BASE_URL opcional; por defecto http://localhost:11434)
    """
    system, user = compose_messages(
        blueprint,
        system_extra=system_extra,
        user_extra=user_extra,
    )
    selected = (provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER") or "openai").lower()

    def call_llm(user_prompt: str) -> str:
        if selected == "ollama":
            from .providers.ollama import ollama_chat

            return ollama_chat(
                system=system,
                user=user_prompt,
                model=model or os.environ.get("OLLAMA_MODEL", "llama3.2:latest"),
            ).strip()

        if selected == "openai":
            from .providers.openai_compat import openai_compat_chat

            return openai_compat_chat(
                system=system,
                user=user_prompt,
                model=model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            ).strip()

        raise ValueError(f"Proveedor LLM no soportado: {selected}")

    min_words = _script_min_words_default()
    max_repairs = 2

    draft = call_llm(user)
    for attempt in range(max_repairs + 1):
        issues = _script_issues(draft, min_words=min_words)
        if not issues:
            return draft.strip()
        if attempt >= max_repairs:
            return draft.strip()

        repair_instructions = "\n".join(issues)
        draft = call_llm(
            user.rstrip()
            + "\n\n"
            + _PROMPT_ADDON_TITLE
            + "\n\n"
            + "Tu borrador NO cumple los requisitos. Corrige y devuelve el documento completo otra vez.\n"
            + "Incumplimientos detectados:\n"
            + repair_instructions
            + "\n\n"
            + "Reglas de corrección:\n"
            + "- Mantén el tema/keywords, el tono y la estructura (OUTLINE + GUIÓN con [CATEGORIA: …]).\n"
            + "- Asegura al menos el mínimo de palabras narrables (las etiquetas no cuentan).\n"
            + "- Inserta [B-ROLL: ...] cada dos oraciones del texto narrable, distribuidas dentro del texto.\n"
            + "- No añadas otras etiquetas entre corchetes (solo [CATEGORIA] y [B-ROLL]).\n"
            + "- No pongas una sección final de “ETIQUETAS DE B-ROLL”.\n"
            + "\n\n"
            + "BORRADOR ANTERIOR (para corregir/expandir):\n"
            + draft.strip()
        )

    return draft.strip()


def dry_run_prompt(
    blueprint: ScriptBlueprint,
    *,
    system_extra: str = "",
    user_extra: str = "",
) -> str:
    """Útil para la pantalla de 'previsualizar / editar prompt' sin gastar tokens."""
    system, user = compose_messages(
        blueprint,
        system_extra=system_extra,
        user_extra=user_extra,
    )
    return f"--- SYSTEM ---\n{system}\n\n--- USER ---\n{user}\n"


def split_script_into_segments(
    full_text: str,
    max_chars: int = 900,
    on_chunk: Callable[[int, str], None] | None = None,
) -> list[str]:
    """
    Trocea por párrafos para TTS por fragmentos (menos RAM / reintentos más baratos).
    """
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for p in paragraphs:
        if size + len(p) > max_chars and buf:
            chunk = "\n\n".join(buf)
            chunks.append(chunk)
            if on_chunk:
                on_chunk(len(chunks) - 1, chunk)
            buf = []
            size = 0
        buf.append(p)
        size += len(p) + 2
    if buf:
        chunk = "\n\n".join(buf)
        chunks.append(chunk)
        if on_chunk:
            on_chunk(len(chunks) - 1, chunk)
    return chunks
