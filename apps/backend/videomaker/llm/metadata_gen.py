"""Metadata de publicación (título, descripción, tags…) a partir del guion."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from videomaker.llm.output_language import language_label, normalize_language_code
from videomaker.pipeline.topic_generator_selection import get_selected_topic

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


def resolve_metadata_llm(
    provider: str | None = None,
    model: str | None = None,
) -> tuple[str, str]:
    """
    El paso Metadata usa siempre OpenAI API (openai_compat_chat), independiente del
    proveedor elegido en Script Writer / .env global.
    """
    prov = "openai"
    m = (model or "").strip()
    if (provider or "").strip().lower() == "openai" and m:
        return prov, m
    return prov, (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()


def _resolve_llm_model_id(provider: str, model: str | None) -> str:
    if (provider or "").strip().lower() == "openai":
        m = (model or "").strip()
        if m:
            return m
        return (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
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


def resolve_metadata_language(session_lang: str, topic_artifact: dict[str, Any] | None) -> str:
    """Idioma efectivo para metadata: Topic Generator → sesión Create → EN."""
    if isinstance(topic_artifact, dict):
        ol = normalize_language_code(str(topic_artifact.get("output_language") or ""))
        if ol in ("en", "es"):
            return ol
    code = normalize_language_code(session_lang)
    if code in ("en", "es"):
        return code
    from videomaker.llm.output_language import PIPELINE_DEFAULT_LANGUAGE

    return PIPELINE_DEFAULT_LANGUAGE


def resolve_canonical_topic_title(
    *,
    selected_topic: dict[str, Any] | None,
    keywords: str,
) -> str | None:
    """Título acordado en Topic Generator (o keywords de sesión si no hay selección)."""
    if selected_topic:
        title = str(selected_topic.get("title") or "").strip()
        if title:
            return title
    kw = (keywords or "").strip()
    return kw or None


def _metadata_script_char_limit() -> int:
    return max(4000, min(int(os.environ.get("VIDEOMAKER_METADATA_SCRIPT_CHARS", "10000")), 100000))


_METADATA_SCHEMA_HINT = """\
JSON schema (top-level keys platform, editorial, production, marketing):
- platform: title, title_variants[2], description (long, act structure), description_short, tags[8-15], chapters_suggestion[{label, summary, start_seconds}]
- editorial: one_liner, bullets[3], cta_suggestion, thumbnail_ideas[2-4], hook_summary, hook_type
- production: notes, visual_style_reference, color_palette, music_vibe, hook_scene_route
- marketing: thumbnail_hook_text, target_audience"""


def _platform_brief(target_platform: str) -> str:
    tp = (target_platform or "youtube").strip().lower()
    briefs = {
        "youtube": "YouTube: SEO title, long description with chapters, 8-15 tags, thumbnail-friendly copy.",
        "tiktok": "TikTok: ultra-short hook copy, brief description, hashtag-style tags, 3-5 chapter beats max.",
        "reels": "Instagram Reels: punchy short copy, niche hashtags, vertical thumbnail ideas, compact description.",
    }
    return briefs.get(tp, briefs["youtube"])


def _compact_system_prompt(
    *,
    target_platform: str,
    output_lang: str,
    output_lang_label: str,
    canonical_title: str | None,
    target_keywords: str,
) -> str:
    """Instrucciones fijas compactas (inglés). El contenido generado va en output_lang."""
    tp = (target_platform or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    title_rule = (
        f'- platform.title MUST be exactly: "{canonical_title}" (verbatim). title_variants: 2 SEO alternatives, same topic.\n'
        if canonical_title
        else "- platform.title: derive from the script; fit the platform.\n"
    )
    seo_rule = (
        f"- Use these SEO keywords in tags/description where natural: {target_keywords.strip()}\n"
        if (target_keywords or "").strip()
        else "- No SEO keywords provided: infer platform.tags from the script (do not copy session topic labels as tags).\n"
    )
    return f"""You produce social-video publication metadata (never script or voiceover text).

Target platform: {tp} — {_platform_brief(tp)}
Adapt tone, length, tags/hashtags, chapters, and thumbnails to this platform.

Output language for every public-facing string value: {output_lang} ({output_lang_label}).

Return ONLY one JSON object. No markdown fence.
{_METADATA_SCHEMA_HINT}

Rules:
- Do NOT output script, acts, [B-ROLL], ### headings, or narrator lines.
- Derive description, tags, hook_summary, thumbnails, and chapters from the SCRIPT in the user message.
- Session topic fields are context only, not automatic tags.
{title_rule}{seo_rule}- title_variants: 2 distinct alternatives.
- Stay faithful to the script; no invented facts.
"""


def default_system_prompt(
    lang: str,
    target_platform: str = "youtube",
    *,
    canonical_title: str | None = None,
    target_keywords: str = "",
) -> str:
    """Prompt por defecto exportado para la UI (compacto; salida en idioma de sesión)."""
    eff_lang = resolve_metadata_language(lang, None)
    return _compact_system_prompt(
        target_platform=target_platform,
        output_lang=eff_lang,
        output_lang_label=language_label(eff_lang),
        canonical_title=canonical_title,
        target_keywords=target_keywords,
    )


def _system_prompt_effective(
    lang: str,
    target_platform: str,
    system_prompt_override: str | None,
    *,
    canonical_title: str | None = None,
    target_keywords: str = "",
) -> str:
    eff_lang = lang if lang in ("en", "es") else resolve_metadata_language(lang, None)
    base = _compact_system_prompt(
        target_platform=target_platform,
        output_lang=eff_lang,
        output_lang_label=language_label(eff_lang),
        canonical_title=canonical_title,
        target_keywords=target_keywords,
    )
    raw = (system_prompt_override or "").strip()
    if not raw:
        return base
    return (
        base
        + "\n\n---\nAdditional user rules (must not contradict output language or JSON-only response):\n"
        + raw
    )


@dataclass(frozen=True)
class PreparedMetadataPrompts:
    lang: str
    target_platform: str
    topic_title: str | None
    topic_angle: str | None
    system: str
    user: str
    excerpt: str
    truncated: bool
    script_total_chars: int
    max_script_chars: int


def prepare_metadata_prompts(
    *,
    script_text: str,
    keywords: str,
    context: str,
    session_lang: str,
    target_platform: str,
    target_keywords: str,
    system_prompt_override: str | None,
    minutes_session: float | None,
    topic_artifact: dict[str, Any] | None,
) -> PreparedMetadataPrompts:
    selected = get_selected_topic(topic_artifact)
    lang = resolve_metadata_language(session_lang, topic_artifact)
    topic_title = resolve_canonical_topic_title(selected_topic=selected, keywords=keywords)
    topic_angle = str(selected.get("angle") or "").strip() if selected else (context or "").strip()
    if not topic_angle:
        topic_angle = None

    max_chars = _metadata_script_char_limit()
    excerpt, truncated = _truncate_script(script_text, max_chars)
    tp = (target_platform or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"

    system = _system_prompt_effective(
        lang,
        tp,
        system_prompt_override,
        canonical_title=topic_title,
        target_keywords=target_keywords or "",
    )
    user = _user_prompt(
        keywords=keywords,
        context=context,
        script_excerpt=excerpt,
        truncated=truncated,
        lang=lang,
        target_platform=tp,
        target_keywords=target_keywords or "",
        minutes_session=minutes_session,
        topic_title=topic_title,
        topic_angle=topic_angle,
    )
    return PreparedMetadataPrompts(
        lang=lang,
        target_platform=tp,
        topic_title=topic_title,
        topic_angle=topic_angle,
        system=system,
        user=user,
        excerpt=excerpt,
        truncated=truncated,
        script_total_chars=len(script_text.replace("\r\n", "\n")),
        max_script_chars=max_chars,
    )


def build_metadata_input_preview(
    *,
    script_text: str,
    script_source: str,
    script_exists: bool,
    keywords: str,
    context: str,
    session_lang: str,
    target_platform: str,
    target_keywords: str,
    system_prompt_override: str | None,
    minutes_session: float | None,
    topic_artifact: dict[str, Any] | None,
    target_keywords_source: str | None = None,
    stored_system_prompt: str = "",
    system_prompt_source: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    """Vista previa de entradas al LLM (sin llamar al modelo)."""
    tk_eff = (target_keywords or "").strip()
    kw_source = (target_keywords_source or "").strip().lower() or (
        "manual" if tk_eff else "infer_from_script"
    )
    sp_src = (system_prompt_source or "").strip().lower() or None
    prep = prepare_metadata_prompts(
        script_text=script_text,
        keywords=keywords,
        context=context,
        session_lang=session_lang,
        target_platform=target_platform,
        target_keywords=target_keywords,
        system_prompt_override=system_prompt_override,
        minutes_session=minutes_session,
        topic_artifact=topic_artifact,
    )
    selected = get_selected_topic(topic_artifact)
    user_full = prep.user
    user_preview = (
        user_full
        if len(user_full) <= 14000
        else user_full[:14000] + "\n… [preview truncado]"
    )
    return {
        "ready": bool(prep.excerpt.strip()),
        "missing": [] if prep.excerpt.strip() else ["script"],
        "lang": {
            "effective": prep.lang,
            "label": language_label(prep.lang),
            "session_raw": (session_lang or "").strip() or None,
            "topic_generator": (
                str(topic_artifact.get("output_language") or "").strip()
                if isinstance(topic_artifact, dict)
                and topic_artifact.get("output_language")
                else None
            ),
        },
        "topic": {
            "selected_index": (
                topic_artifact.get("selected_index")
                if isinstance(topic_artifact, dict)
                else None
            ),
            "title": prep.topic_title,
            "angle": prep.topic_angle,
            "from_topic_generator": bool(selected and prep.topic_title),
            "title_policy": (
                "canonical_from_topic_generator"
                if prep.topic_title and selected
                else ("session_keywords_as_title" if prep.topic_title else "ai_generates_title")
            ),
        },
        "session": {
            "keywords": keywords or None,
            "context": context or None,
            "minutes": minutes_session,
        },
        "settings": {
            "target_platform": prep.target_platform,
            "target_keywords_effective": tk_eff or None,
            "target_keywords_source": kw_source,
            "system_prompt_custom": bool((system_prompt_override or "").strip()),
            "system_prompt_source": sp_src,
            "prompt_style": "compact_platform_adaptive",
        },
        "llm": {
            "provider": llm_provider or "openai",
            "model": llm_model,
            "api": "openai_compat (OPENAI_API_KEY / OPENAI_BASE_URL)",
            "session_provider_ignored": True,
        },
        "checks": _build_pre_generation_checks(
            prep=prep,
            script_exists=script_exists,
            system_prompt_override=system_prompt_override,
            stored_system_prompt=stored_system_prompt,
            system_prompt_source=sp_src,
            target_keywords_source=kw_source,
        ),
        "script": {
            "source": script_source,
            "exists": script_exists,
            "total_chars": prep.script_total_chars,
            "chars_sent_to_llm": len(prep.excerpt),
            "truncated": prep.truncated,
            "max_chars": prep.max_script_chars,
        },
        "prompts": {
            "system": prep.system,
            "user": user_preview,
            "user_length": len(user_full),
        },
    }


def _user_prompt_inputs_payload(
    *,
    target_platform: str,
    eff_lang: str,
    minutes_session: float | None,
    topic_title: str | None,
    topic_angle: str | None,
    keywords: str,
    context: str,
    target_keywords: str,
    truncated: bool,
) -> dict[str, Any]:
    return {
        "target_platform": target_platform,
        "output_language": eff_lang,
        "target_duration_minutes": (
            float(minutes_session) if minutes_session is not None and minutes_session > 0 else None
        ),
        "canonical_title": topic_title,
        "topic_angle": topic_angle,
        "session_topic": (keywords or "").strip() or None,
        "session_context": (context or "").strip() or None,
        "seo_keywords_override": (target_keywords or "").strip() or None,
        "script_excerpt_truncated": truncated,
    }


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
    topic_title: str | None = None,
    topic_angle: str | None = None,
) -> str:
    eff_lang = lang if lang in ("en", "es") else resolve_metadata_language(lang, None)
    payload = _user_prompt_inputs_payload(
        target_platform=target_platform,
        eff_lang=eff_lang,
        minutes_session=minutes_session,
        topic_title=topic_title,
        topic_angle=topic_angle,
        keywords=keywords,
        context=context,
        target_keywords=target_keywords,
        truncated=truncated,
    )
    return (
        "Generate metadata JSON from the inputs and script below.\n\n"
        "inputs:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nscript:\n"
        + script_excerpt
    )


def _metadata_repair_user_prompt(
    *,
    raw: str,
    tp: str,
    eff_lang: str,
    keywords: str,
    context: str,
    topic_title: str | None,
    minutes_session: float | None,
    excerpt: str,
) -> str:
    return (
        "ERROR: Previous response was not valid metadata JSON.\n"
        "Respond ONLY with JSON (keys platform, editorial, production, marketing). No script text.\n\n"
        f"Invalid fragment (start): {raw[:900]!r}\n\n"
        f"platform={tp!r} output_language={eff_lang!r}\n"
        f"session_topic={keywords[:200]!r} session_context={(context or '')[:200]!r}\n"
        + (f"canonical_title={topic_title!r}\n" if topic_title else "")
        + (
            f"duration_minutes={minutes_session:g}\n"
            if minutes_session is not None and minutes_session > 0
            else ""
        )
        + "\nscript_excerpt:\n"
        + excerpt[:4500]
    )


def _build_pre_generation_checks(
    *,
    prep: PreparedMetadataPrompts,
    script_exists: bool,
    system_prompt_override: str | None,
    stored_system_prompt: str,
    system_prompt_source: str | None,
    target_keywords_source: str | None,
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    if not prep.excerpt.strip():
        checks.append(
            {
                "level": "error",
                "id": "script",
                "message": "No hay guion (guion.txt / pipeline/script.txt). Ejecuta Script Writer antes.",
            }
        )
    elif not script_exists:
        checks.append(
            {
                "level": "warning",
                "id": "script",
                "message": "El guion parece vacío o no se encontró en disco.",
            }
        )
    if prep.truncated:
        checks.append(
            {
                "level": "warning",
                "id": "script_truncated",
                "message": f"El guion se truncó a {prep.max_script_chars:,} caracteres para el contexto del modelo.",
            }
        )
    if not prep.topic_title:
        checks.append(
            {
                "level": "warning",
                "id": "topic_title",
                "message": "Sin título canónico de Topic Generator; la IA propondrá platform.title.",
            }
        )
    if stored_system_prompt.strip() and (system_prompt_source or "").lower() != "manual":
        checks.append(
            {
                "level": "warning",
                "id": "stale_system_prompt",
                "message": "Hay un system prompt guardado antiguo; en modo automático se ignora (usa instrucciones compactas).",
            }
        )
    if (system_prompt_override or "").strip():
        checks.append(
            {
                "level": "info",
                "id": "system_prompt_manual",
                "message": "Se aplicará tu system prompt manual además de las instrucciones base.",
            }
        )
    if (target_keywords_source or "") == "inferred":
        checks.append(
            {
                "level": "info",
                "id": "seo_inferred",
                "message": "Las keywords SEO en disco son solo referencia; se inferirán de nuevo del guion.",
            }
        )
    checks.append(
        {
            "level": "info",
            "id": "llm_openai",
            "message": "Generación vía OpenAI API (no usa Ollama aunque el Script Writer esté en Ollama).",
        }
    )
    if not any(c["level"] == "error" for c in checks):
        msg = (
            "Listo para generar: la IA adaptará metadatos a la plataforma, el guion y el idioma de sesión."
            if checks
            else "Listo para generar."
        )
        checks.insert(0, {"level": "ok", "id": "ready", "message": msg})
    return checks


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
    topic_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Llama al LLM y devuelve un dict listo para guardar en pipeline/metadata.json (sin campo version).
    """
    prep = prepare_metadata_prompts(
        script_text=script_text,
        keywords=keywords,
        context=context,
        session_lang=lang,
        target_platform=target_platform,
        target_keywords=target_keywords,
        system_prompt_override=system_prompt_override,
        minutes_session=minutes_session,
        topic_artifact=topic_artifact,
    )
    if not prep.excerpt.strip():
        raise ValueError("No hay texto de guion para derivar metadata.")

    system = prep.system
    user = prep.user
    excerpt = prep.excerpt
    truncated = prep.truncated
    tp = prep.target_platform
    eff_lang = prep.lang
    topic_title = prep.topic_title

    selected, resolved_model = resolve_metadata_llm(provider, model)
    json_mode = _env_bool("VIDEOMAKER_METADATA_JSON_MODE", True)
    try:
        meta_temp = float(os.environ.get("VIDEOMAKER_METADATA_TEMPERATURE", "0.25"))
    except ValueError:
        meta_temp = 0.25

    from .llm_routing import call_production_llm

    def call_llm(user_prompt: str) -> str:
        return call_production_llm(
            system=system,
            user=user_prompt,
            model=resolved_model,
            response_json=json_mode,
            temperature=meta_temp,
        )

    raw = call_llm(user)
    try:
        parsed = _parse_json_object(raw)
    except ValueError as first_err:
        # Reintento corto: el modelo a veces ignora instrucciones y sigue el guion.
        repair_user = _metadata_repair_user_prompt(
            raw=raw,
            tp=tp,
            eff_lang=eff_lang,
            keywords=keywords,
            context=context,
            topic_title=topic_title,
            minutes_session=minutes_session,
            excerpt=excerpt,
        )
        try:
            raw2 = call_llm(repair_user)
            parsed = _parse_json_object(raw2)
        except ValueError:
            raise RuntimeError(f"Metadata LLM: {first_err}") from first_err

    # Normalización mínima
    plat = parsed.get("platform") if isinstance(parsed.get("platform"), dict) else {}
    if topic_title:
        plat = {**plat, "title": topic_title}
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
            "lang": eff_lang,
            "session_lang_raw": (lang or "").strip() or None,
            "topic_title": topic_title,
            "topic_angle": prep.topic_angle,
            "title_policy": (
                "canonical_from_topic_generator"
                if topic_title and get_selected_topic(topic_artifact)
                else ("session_keywords_as_title" if topic_title else "ai_generates_title")
            ),
            "minutes_session": float(minutes_session)
            if minutes_session is not None and minutes_session > 0
            else None,
            "script_chars_used": len(excerpt),
            "script_truncated": truncated,
            "script_total_chars": prep.script_total_chars,
            "target_platform": tp,
            "target_keywords": (target_keywords or "").strip() or None,
            "target_keywords_inferred": not bool((target_keywords or "").strip()),
            "system_prompt_custom": bool((system_prompt_override or "").strip()),
        },
    }
    return out


_PUBLICATION_SCHEMA = """\
JSON schema (single object) — publication fields ONLY (packaging already fixed):
- platform: description (long, act structure), description_short, tags[8-15], chapters_suggestion[{label, summary, start_seconds}]
- production: notes, visual_style_reference, color_palette, music_vibe, hook_scene_route
Do NOT output platform.title, title_variants, thumbnail_ideas, hook_summary, or marketing.thumbnail_hook_text.
"""


def _publication_system_prompt(
    *,
    target_platform: str,
    output_lang: str,
    output_lang_label: str,
    target_keywords: str,
    packaging_title: str | None,
) -> str:
    tp = (target_platform or "youtube").strip().lower()
    if tp not in ("youtube", "tiktok", "reels"):
        tp = "youtube"
    seo_rule = (
        f"- Use these SEO keywords in tags/description where natural: {target_keywords.strip()}\n"
        if (target_keywords or "").strip()
        else "- Infer platform.tags from the script (do not copy session topic labels as tags).\n"
    )
    title_lock = (
        f'- Title/thumbnail promise is FIXED: "{packaging_title}". Description and Act 1 must align with it.\n'
        if packaging_title
        else ""
    )
    return f"""You produce YouTube publication metadata from an existing script.

Packaging (title + thumbnail) was decided BEFORE the script — do not change that promise.
Target platform: {tp}
Output language: {output_lang} ({output_lang_label}).

Return ONLY one JSON object. No markdown fence.
{_PUBLICATION_SCHEMA}

Rules:
- Do NOT output script text, narrator lines, or thumbnail ideas.
- Derive description, tags, and chapters from the SCRIPT in the user message.
{title_lock}{seo_rule}"""


def generate_publication_metadata(
    *,
    script_text: str,
    keywords: str = "",
    context: str = "",
    lang: str = "es",
    provider: str | None = None,
    model: str | None = None,
    target_platform: str = "youtube",
    target_keywords: str = "",
    minutes_session: float | None = None,
    packaging_title: str | None = None,
) -> dict[str, Any]:
    """Solo descripción, tags, capítulos y production — tras empaquetado hook-first."""
    eff_lang = resolve_metadata_language(lang, None)
    max_chars = _metadata_script_char_limit()
    excerpt, truncated = _truncate_script(script_text, max_chars)
    if not excerpt.strip():
        raise ValueError("No hay texto de guion para metadata de publicación.")

    system = _publication_system_prompt(
        target_platform=target_platform,
        output_lang=eff_lang,
        output_lang_label=language_label(eff_lang),
        target_keywords=target_keywords,
        packaging_title=packaging_title,
    )
    payload = {
        "target_platform": target_platform,
        "output_language": eff_lang,
        "duration_minutes": (
            float(minutes_session) if minutes_session is not None and minutes_session > 0 else None
        ),
        "packaging_title": packaging_title,
        "session_topic": (keywords or "").strip() or None,
        "session_context": (context or "").strip() or None,
        "script_excerpt_truncated": truncated,
    }
    user = (
        "Generate publication metadata JSON from the script below.\n\n"
        "inputs:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nscript:\n"
        + excerpt
    )

    selected, resolved_model = resolve_metadata_llm(provider, model)
    from .llm_routing import call_production_llm

    raw = call_production_llm(
        system=system,
        user=user,
        model=resolved_model,
        response_json=_env_bool("VIDEOMAKER_METADATA_JSON_MODE", True),
        temperature=float(os.environ.get("VIDEOMAKER_METADATA_TEMPERATURE", "0.25")),
    )
    parsed = _parse_json_object(raw)
    plat = parsed.get("platform") if isinstance(parsed.get("platform"), dict) else {}
    _normalize_platform_block(plat)
    return {
        "platform": plat,
        "production": parsed.get("production") if isinstance(parsed.get("production"), dict) else {},
        "_gen": {
            "phase": "publication_only",
            "provider": selected,
            "model": resolved_model,
            "script_chars_used": len(excerpt),
            "script_truncated": truncated,
        },
    }


def wrap_metadata_bundle(inner: dict[str, Any]) -> dict[str, Any]:
    """Version siempre 1 al final (no la sobrescribe el modelo)."""
    out = dict(inner)
    out["version"] = 1
    return out
