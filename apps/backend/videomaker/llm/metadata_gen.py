"""Metadata de publicación (título, descripción, tags…) a partir del guion."""

from __future__ import annotations

import json
import os
import re
from typing import Any

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def _truncate_script(text: str, max_chars: int) -> tuple[str, bool]:
    t = (text or "").replace("\r\n", "\n").strip()
    if len(t) <= max_chars:
        return t, False
    return t[:max_chars], True


def _parse_json_object(raw: str) -> dict[str, Any]:
    """Interpreta la salida del LLM; mensajes claros si viene vacío o solo markdown."""
    original = (raw or "").strip()
    if not original:
        raise ValueError(
            "El modelo devolvió una respuesta vacía (no hay JSON). "
            "Comprueba que Ollama/OpenAI respondan y que el modelo no haya cortado la salida."
        )

    candidates: list[str] = []
    for m in _JSON_FENCE.finditer(original):
        inner = (m.group(1) or "").strip()
        if inner:
            candidates.append(inner)
    candidates.append(original)

    errors: list[str] = []
    for s in candidates:
        if not s.strip():
            continue
        try:
            data = json.loads(s)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as e:
            errors.append(str(e))
        i = s.find("{")
        j = s.rfind("}")
        if i >= 0 and j > i:
            chunk = s[i : j + 1]
            try:
                data = json.loads(chunk)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError as e:
                errors.append(str(e))

    snippet = original[:480].replace("\n", " ")
    hint = errors[-1] if errors else "sin detalle"
    raise ValueError(
        "No se pudo extraer un objeto JSON de la respuesta del modelo. "
        f"Último error de parseo: {hint}. "
        f"Inicio de la respuesta: {snippet!r}"
        + ("…" if len(original) > 480 else "")
    )


def _resolve_llm_model_id(provider: str, model: str | None) -> str:
    sel = (provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER") or "openai").lower()
    m = (model or "").strip()
    if m:
        return m
    if sel == "ollama":
        return (os.environ.get("OLLAMA_MODEL") or "llama3.2:latest").strip()
    return (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()


def _normalize_platform_block(platform: dict[str, Any]) -> None:
    """Normaliza capítulos (timestamps numéricos)."""
    ch = platform.get("chapters_suggestion")
    if not isinstance(ch, list):
        return
    for item in ch:
        if not isinstance(item, dict):
            continue
        raw = item.get("start_seconds")
        if raw is None:
            continue
        try:
            item["start_seconds"] = max(0, int(round(float(raw))))
        except (TypeError, ValueError):
            item.pop("start_seconds", None)


def default_system_prompt(lang: str, target_platform: str = "youtube") -> str:
    """Prompt de sistema por defecto (idioma + plataforma). Exportado para la UI / API."""
    loc = "español" if (lang or "es").lower().startswith("es") else "English"
    tp = (target_platform or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"

    platform_hints = {
        "youtube": (
            "Plataforma: YouTube. Prioriza título SEO (≤100 caracteres útiles), descripción larga con capítulos,"
            " tags relevantes y miniaturas legibles a tamaño pequeño."
        ),
        "tiktok": (
            "Plataforma: TikTok. Prioriza gancho en los primeros segundos en texto corto, hashtags trending coherentes,"
            " descripción muy breve; capítulos pueden ser 3–5 beats rápidos."
        ),
        "reels": (
            "Plataforma: Instagram Reels. Estilo visual/vertical en miniaturas, copy breve y punchy,"
            " hashtags de nicho; descripción compacta."
        ),
    }

    hint = platform_hints.get(tp, platform_hints["youtube"])

    return f"""Eres un editor de metadatos para vídeo orientado a publicación social.

PROHIBIDO en tu respuesta: escribir o continuar el GUION, actos, [B-ROLL], encabezados ###, diálogo del narrador o cualquier texto que parezca locución. El usuario ya tiene el guion; tú solo produces METADATOS.

{hint}
Lee el material de referencia y devuelve SOLO un objeto JSON válido (sin markdown alrededor).
Idioma de salida: {loc} para los campos de texto visibles al público.

Esquema obligatorio (todas las claves de primer nivel):
{{
  "platform": {{
    "title": "string",
    "title_variants": ["string", "string"],
    "description": "string — DESCRIPCIÓN LARGA para SEO y retención: incluye la ESTRUCTURA NARRATIVA POR ACTOS (etiquetas claras tipo «Acto 1 — …», «Acto 2 — …» o equivalente). Cada bloque resume qué encontrará el espectador en ese tramo (sin copiar la locución del guion). Usa saltos \\n entre actos/párrafos.",
    "description_short": "string (primeras ~200 caracteres gancho)",
    "tags": ["string", ...],
    "chapters_suggestion": [
      {{
        "label": "string (título corto del capítulo)",
        "summary": "string (1 línea)",
        "start_seconds": 0
      }}
    ]
  }},
  "editorial": {{
    "one_liner": "string",
    "bullets": ["string", "string", "string"],
    "cta_suggestion": "string",
    "thumbnail_ideas": ["string", "string"],
    "hook_summary": "string — 1-3 frases ESPECÍFICAS al gancho real del guion (no genéricas tipo «introducción al problema»). Qué promete el hook y qué tensión crea.",
    "hook_type": "paradox | statistic | scene | invitation | systemic | documentary | mixed"
  }},
  "production": {{
    "notes": "string (opcional: tono, advertencias legales)",
    "visual_style_reference": "string (ej. Deep Documentary, Data Minimalist — coherente con el gancho)",
    "color_palette": ["#hex o nombre color", "..."],
    "music_vibe": "string (ej. ambient minimal, tensión corporativa)",
    "hook_scene_route": "string (ej. POV_Story, Data_Driven, Documentary_Intimate, Noir_Systemic o etiqueta corta tipo Cinematic_Personal)"
  }},
  "marketing": {{
    "thumbnail_hook_text": "string (texto muy corto para miniatura, MAYÚSCULAS opcionales)",
    "target_audience": "string (perfil: edad, nivel, intereses)"
  }}
}}

Reglas:
- title y title_variants: cuando el tono sea educativo/financiero o storytelling de inversión, prioriza títulos con pérdida-coste-error-curiosidad (ej. consecuencia antes del número) si encaja con el guion; evita títulos planos si el contenido lo permite.
- title_variants: 2 títulos alternativos distintos al principal.
- tags: 8-15 etiquetas cortas, sin #.
- editorial.thumbnail_ideas: 2–4 ideas concretas para miniatura (texto en imagen, expresión, contraste).
- editorial.hook_type: clasifica el tipo de gancho del Acto 1 (paradox=paradoja/contraintuitivo; statistic=dato/porcentaje; invitation=«imagina/tú»; scene=escena hiperconcreta; systemic=sistema/mercado global; documentary=introspectivo-objetos; mixed=mezcla).
- platform.chapters_suggestion: alineados con la estructura del guion (YouTube: 4–10); usa la duración aproximada de la sesión para repartir timestamps. Cada ítem lleva start_seconds (entero ≥0) desde el inicio; orden creciente; sin repetir el mismo ángulo temático en dos capítulos (evita duplicar subtemas como dos bloques sobre la misma idea).
- Sé fiel al contenido del guion; no inventes datos factuales no presentes.
"""


def _system_prompt_effective(
    lang: str,
    target_platform: str,
    system_prompt_override: str | None,
) -> str:
    raw = (system_prompt_override or "").strip()
    if raw:
        return (
            "IMPORTANTE: No escribas guion, actos ni [B-ROLL]. Solo metadata JSON.\n\n"
            + raw
            + "\n\n---\nDebes responder SOLO con un único objeto JSON con las claves de primer nivel "
            '"platform", "editorial", "production" y "marketing" según las reglas que hayas definido arriba. '
            "Sin markdown ni texto fuera del JSON."
        )
    return default_system_prompt(lang, target_platform)


def _user_prompt(
    *,
    keywords: str,
    context: str,
    script_excerpt: str,
    truncated: bool,
    lang: str,
    target_platform: str,
    target_keywords: str,
    minutes_session: float | None,
) -> str:
    dur_line = (
        f"Duración orientativa del vídeo (minutos, sesión): {minutes_session:g}"
        if minutes_session is not None and minutes_session > 0
        else "Duración orientativa del vídeo (minutos, sesión): (no indicada — infiere un rango razonable para timestamps)"
    )
    header = """=== TU ÚNICA TAREA ===
Devuelve SOLO un objeto JSON (raíz con keys platform, editorial, production, marketing).
NO escribas guion, NO continúes actos, NO uses [B-ROLL] ni encabezados ###.
El bloque «GUION» más abajo es SOLO lectura para extraer títulos/tags; no lo copies ni lo reescribas.

=== DATOS DE SESIÓN ===
"""
    parts = [
        header.rstrip(),
        f"Plataforma destino: {target_platform}",
        f"Palabras clave objetivo (SEO): {target_keywords or '(no indicadas)'}",
        f"Keywords / tema (sesión Create): {keywords or '(no indicado)'}",
        f"Contexto adicional (sesión): {context or '(no indicado)'}",
        f"Idioma sesión: {lang}",
        dur_line,
    ]
    if truncated:
        parts.append(
            "AVISO: el guion está truncado al inicio; infiere con moderación o anótalo en production.notes."
        )
    parts.append("\n=== GUION (solo referencia; no reproducir, no continuar) ===\n")
    parts.append(script_excerpt)
    return "\n".join(parts)


def generate_video_metadata(
    *,
    script_text: str,
    keywords: str = "",
    context: str = "",
    lang: str = "es",
    provider: str | None = None,
    model: str | None = None,
    target_platform: str = "youtube",
    target_keywords: str = "",
    system_prompt_override: str | None = None,
    minutes_session: float | None = None,
) -> dict[str, Any]:
    """
    Llama al LLM y devuelve un dict listo para guardar en pipeline/metadata.json (sin campo version).
    """
    # Menos tokens de contexto → menos confusión con “seguir escribiendo el guion”.
    max_chars = max(4000, min(int(os.environ.get("VIDEOMAKER_METADATA_SCRIPT_CHARS", "10000")), 100000))
    excerpt, truncated = _truncate_script(script_text, max_chars)
    if not excerpt.strip():
        raise ValueError("No hay texto de guion para derivar metadata.")

    tp = (target_platform or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"

    system = _system_prompt_effective(lang, tp, system_prompt_override)
    user = _user_prompt(
        keywords=keywords,
        context=context,
        script_excerpt=excerpt,
        truncated=truncated,
        lang=lang,
        target_platform=tp,
        target_keywords=target_keywords or "",
        minutes_session=minutes_session,
    )

    selected = (provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER") or "openai").lower()
    resolved_model = _resolve_llm_model_id(selected, model)
    json_mode = _env_bool("VIDEOMAKER_METADATA_JSON_MODE", True)
    try:
        meta_temp = float(os.environ.get("VIDEOMAKER_METADATA_TEMPERATURE", "0.25"))
    except ValueError:
        meta_temp = 0.25

    def call_llm(user_prompt: str) -> str:
        if selected == "ollama":
            from .providers.ollama import ollama_chat

            return ollama_chat(
                system=system,
                user=user_prompt,
                model=resolved_model,
                response_json=json_mode,
                temperature=meta_temp,
            ).strip()

        if selected == "openai":
            from .providers.openai_compat import openai_compat_chat

            return openai_compat_chat(
                system=system,
                user=user_prompt,
                model=resolved_model,
                response_json=json_mode,
                temperature=meta_temp,
            ).strip()

        raise ValueError(f"Proveedor LLM no soportado: {selected}")

    raw = call_llm(user)
    try:
        parsed = _parse_json_object(raw)
    except ValueError as first_err:
        # Reintento corto: el modelo a veces ignora instrucciones y sigue el guion.
        repair_user = (
            "ERROR: Tu respuesta anterior NO fue un objeto JSON válido o era texto de guion.\n"
            "Debes responder ÚNICAMENTE con JSON: raíz con keys platform, editorial, production, marketing.\n"
            "No escribas actos, [B-ROLL], ni Markdown ###.\n\n"
            f"Fragmento incorrecto (inicio): {raw[:900]!r}\n\n"
            "=== Datos compactos ===\n"
            f"Plataforma: {tp}. Keywords sesión: {keywords or '—'}. Contexto: {(context or '')[:400]}\n"
            + (
                f"Duración vídeo orientativa (min): {minutes_session:g}\n"
                if minutes_session is not None and minutes_session > 0
                else ""
            )
            + "=== Extracto corto del guion (solo ideas, no copiar) ===\n"
            + excerpt[:4500]
        )
        try:
            raw2 = call_llm(repair_user)
            parsed = _parse_json_object(raw2)
        except ValueError:
            raise RuntimeError(f"Metadata LLM: {first_err}") from first_err

    # Normalización mínima
    plat = parsed.get("platform") if isinstance(parsed.get("platform"), dict) else {}
    _normalize_platform_block(plat)
    edit = parsed.get("editorial") if isinstance(parsed.get("editorial"), dict) else {}
    if isinstance(edit.get("hook_type"), str):
        edit = {**edit, "hook_type": edit["hook_type"].strip().lower()}
    out: dict[str, Any] = {
        "platform": plat,
        "editorial": edit,
        "production": parsed.get("production") if isinstance(parsed.get("production"), dict) else {},
        "marketing": parsed.get("marketing") if isinstance(parsed.get("marketing"), dict) else {},
        "_gen": {
            "provider": selected,
            "model": resolved_model,
            "lang": (lang or "es").strip() or "es",
            "minutes_session": float(minutes_session)
            if minutes_session is not None and minutes_session > 0
            else None,
            "script_chars_used": len(excerpt),
            "script_truncated": truncated,
            "script_total_chars": len(script_text.replace("\r\n", "\n")),
            "target_platform": tp,
            "target_keywords": (target_keywords or "").strip(),
            "system_prompt_custom": bool((system_prompt_override or "").strip()),
        },
    }
    return out


def wrap_metadata_bundle(inner: dict[str, Any]) -> dict[str, Any]:
    """Version siempre 1 al final (no la sobrescribe el modelo)."""
    out = dict(inner)
    out["version"] = 1
    return out
