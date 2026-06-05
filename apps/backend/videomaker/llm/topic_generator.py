"""Generación de ideas de vídeo a partir de transcripciones del canal y tendencias del nicho."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from videomaker.llm.output_language import language_label, resolve_output_language


def _strip_schema_fields_for_fast(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fast mode: keep thumbnail-first + arc + scores; drop heavy fields."""
    heavy = {
        "scene_pack",
        "broll_keywords",
        "opening_hook",
        "visual_anchor",
    }
    out: list[dict[str, Any]] = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        d = dict(t)
        for k in heavy:
            d.pop(k, None)
        out.append(d)
    return out

_TOPIC_SYSTEM_TEMPLATE = """
You are a YouTube content strategist who optimizes for CLICK IMPULSE, not academic credibility.

The user's complaint: topics are too intellectual (Bloomberg). Fix it.
Your output must feel like must-watch YouTube: visceral emotion + instant curiosity + identity/status threat.

Second complaint: topics lack VISUAL EXPLOSIVENESS (hard to visualize instantly). Fix it.
Critical test for every topic: "Can a viewer imagine 15 powerful scenes immediately?"

Third complaint: too much "explaining mode". Fix it.
Most topics currently describe what the video will analyze. That feels academic.
Instead: lead with the CENTRAL EMOTION + IDENTITY TRANSFORMATION.

Fourth complaint: still too "essay-first". Fix it.
Think THUMBNAIL-FIRST before script. If the thumbnail isn't instantly obvious, the topic is weak.
The thumbnail concept must exist BEFORE the title: the title should feel like the caption of the thumbnail.

Fifth complaint: missing "novelty injection". Fix it.
Many topics are familiar and safe. We need: familiar pain + unexpected framing (expectation break).
Every topic must contain at least one explicit contradiction / surprise / counterintuitive claim.

Sixth complaint: missing "social identity tension" (critical for finance YouTube). Fix it.
People click for status anxiety, comparison, fear of falling behind, regret, and freedom fantasy — not just money.
Every topic must include at least one social identity tension angle.

Non-negotiable rules:
- Every topic MUST trigger at least one of: fear, urgency, identity_threat, status_anxiety.
- Avoid "safe intellectual framing" (e.g. "The Real Cost of X", "A Deep Dive Into Y", "Explained").
- Make titles punchy and emotionally loaded. No corporate tone.
- Each topic must have a distinct angle (not generic rephrases).
- Ground angles in patterns you see in the transcripts AND in the trend notes when provided.
- recommended_duration_minutes: integer **10–12** for this production run (depurable first full video).
  Only exceed 12 if transcripts are explicitly long-form essays (>20 min); never above 15 without that evidence.
- Every topic MUST be instantly visualizable. Avoid abstract/philosophical frames without concrete visuals.
- Provide a 15-scene "scene_pack" with shootable, specific, cinematic scenes.
- NO "explaining mode" titles. Ban verbs like: examine, analyze, explain, documented, overview, guide, study, deep dive.
- Titles must feel like: "the moment X happens… you change" / "you think you're doing X but it's actually Y" / "this is why you feel ___".
- Every topic must contain a before→after transformation claim (emotional + identity).
- THUMBNAIL-FIRST: Start from a single iconic image with a 2-state contrast (before vs after).
  If you cannot describe the thumbnail in 1 sentence, reject the topic.
- The title must be explainable by the thumbnail in 1 glance (no abstract nouns).
- Thumbnail style: simple, bold contrast, 1–2 props max, 1 emotion, clear red vs green (or equivalent).
- NOVELTY INJECTION: Pair a familiar pain with an unexpected framing.
  Use one of these novelty devices per topic (vary devices across topics):
  - counterintuitive ranking (X feels better than Y)
  - taboo truth ("nobody says this")
  - inversion (the thing you want is the trap)
  - hidden cost that flips status (the rich habit that makes you look broke)
  - false friend (the "responsible" choice that keeps you poor)
  - contradiction hook ("more money, less peace")
  If a topic feels like standard advice, rewrite it until it creates "wait, what?".
- SOCIAL IDENTITY TENSION: Bake in at least one of:
  - fear_of_falling_behind
  - status_anxiety / social_comparison
  - regret (missed years, missed compounding, missed opportunities)
  - freedom_fantasy (escape, calm, control, "not living like everyone else")
  Titles should imply a tribe boundary: "people who do X" vs "everyone else".
- OUTPUT LANGUAGE (mandatory): all text fields in {output_language_label} only.
  Match the language of the transcripts and channel; do NOT switch languages.
- Return ONLY valid JSON (no markdown fences).

Helpful patterns for titles (use varied structures, not all the same):
- "If you're doing X, you're falling behind"
- "Stop doing X — it’s quietly ruining Y"
- "The mistake that makes you look broke (even if you're not)"
- "You’re not lazy — you’re stuck in this trap"
- "Everyone says X. Here’s what it really costs you."
- "Before you turn {{age}}, do this (or regret it)"

Schema:
{{
  "topics": [
    {{
      "title": "<must-watch title (aim < 70 chars)>",
      "angle": "<unique editorial angle in 1-3 sentences>",
      "recommended_duration_minutes": <number>,
      "why_now": "<1 sentence linking to trend or gap in catalog>",
      "primary_trigger": "fear|urgency|identity_threat|status_anxiety|curiosity_gap",
      "trigger_stack": ["fear|urgency|identity_threat|status_anxiety|curiosity_gap", "..."],
      "core_emotion": "<1-3 words: fear|relief|shame|envy|anger|hope|status_anxiety|pride|regret|panic>",
      "identity_shift": "<before → after identity in one sentence>",
      "identity_transformation": {{
        "from": "<identity before>",
        "to": "<identity after>"
      }},
      "transformation_claim": "<1 sentence: what changes in their life/personality>",
      "emotional_promise": "<1 sentence: what they FEEL after watching>",
      "emotional_arc": {{
        "start": "<one word or short phrase>",
        "mid": "<one word or short phrase>",
        "end": "<one word or short phrase (often clarity/empowerment)>"
      }},
      "visual_symbols": [
        {{
          "symbol": "locked_door",
          "meaning": "systemic exclusion",
          "recurrence_strategy": "appears every act"
        }}
      ],
      "psychological_triggers": [
        "identity_threat",
        "status_anxiety",
        "taboo_truth",
        "shame_relief"
      ],
      "viewer_state_before_click": {{
        "financial_shame": 85,
        "confusion": 72,
        "status_anxiety": 90
      }},
      "viewer_state_after_video": {{
        "clarity": 88,
        "agency": 74,
        "motivation": 70
      }},
      "energy_curve": [
        "hook_tension",
        "validation",
        "rage_spike",
        "data_reveal",
        "relief",
        "empowerment"
      ],
      "visual_density": {{
        "hook": "high",
        "middle_explanation": "medium",
        "emotional_reveal": "low + intimate"
      }},
      "credibility_rules": {{
        "avoid_totalizing_claims": true,
        "include_counterarguments": true,
        "end_with_empowerment": true
      }},
      "thumbnail_narrative": {{
        "core_contrast": "locked_out_vs_inside",
        "viewer_role": "locked_out",
        "envy_target": "homeowner_holding_key",
        "emotion": "anxiety"
      }},
      "thumbnail_text": "<2-4 words, ALL CAPS in {output_language_label}>",
      "thumbnail_concept": {{
        "one_sentence": "<1 sentence describing the thumbnail image in {output_language_label}>",
        "contrast": "<before vs after in 3-6 words>",
        "props": ["<1-2 concrete props>", "..."],
        "face_emotion": "<anxiety|calm|shame|confidence|panic|relief|envy|anger|hope>",
        "color_story": "<red vs green / cold vs warm / etc>",
        "composition": "<split-screen? close-up? wide? where is text?>",
        "avoid": ["<visual clichés to avoid>", "..."]
      }},
      "thumbnailability": <0-100>,
      "familiar_pain": "<1 sentence: the everyday pain the viewer already feels>",
      "expectation_break": "<1 sentence: the surprising claim that flips the familiar pain>",
      "novelty_device": "counterintuitive_ranking|taboo_truth|inversion|hidden_cost|false_friend|contradiction_hook|weird_analogy",
      "opening_hook": "<first 5 seconds: 1-2 lines of spoken hook in {output_language_label}>",
      "visual_anchor": "<1 sentence describing the core visual metaphor / recurring prop>",
      "scene_pack": [
        "<6-15 scenes, each: who+where+action+prop+emotion (shootable in one shot). Prefer 15, but never fail JSON to reach 15.>"
      ],
      "broll_keywords": ["<short visual noun phrases>", "..."],
      "instantly_visualizable": true,
      "click_impulse_score": <0-100>,
      "visual_explosiveness_score": <0-100>,
      "abstractness_score": <0-100>,
      "explaining_mode_score": <0-100>,
      "novelty_score": <0-100>,
      "social_identity_tension": "<1 sentence: 'people like you' vs 'everyone else' tension>",
      "tribe_boundary": "<short phrase: 'savers vs spenders' / 'quiet rich vs loud rich' / etc>",
      "status_anxiety_hook": "<1 sentence capturing the status fear>",
      "freedom_fantasy": "<1 sentence: the fantasy payoff>",
      "regret_trigger": "<1 sentence: what they'll regret if they don't watch>",
      "identity_tension": <0-100>,
      "dominant_emotion": "<e.g. 'financial anxiety transforming into relief' in {output_language_label}>",
      "visualizability": {{
        "broll_strength": <0-100>,
        "symbolic_visuals": <0-100>,
        "motion_graphics_potential": <0-100>
      }},
      "scroll_stop_factors": ["identity threat", "financial fear", "curiosity contradiction"],
      "intellectual_tone_score": <0-100>
    }}
  ]
}}
""".strip()


def _topic_system(output_language: str) -> str:
    code = output_language if output_language in ("en", "es") else "es"
    return _TOPIC_SYSTEM_TEMPLATE.format(output_language_label=language_label(code))


def _call_llm(*, system: str, user: str, provider: str, model: str, temperature: float = 0.55) -> str:
    from videomaker.llm.avatar_prompt_writer import _call_llm as _llm

    return _llm(system=system, user=user, provider=provider, model=model, temperature=temperature)


def _parse_topics_json(raw: str) -> list[dict[str, Any]]:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Robustness: models sometimes add a preface or trailing text. Try to extract JSON object.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            snippet = cleaned[start : end + 1].strip()
            try:
                data = json.loads(snippet)
            except json.JSONDecodeError as exc2:
                raise ValueError(f"LLM devolvió JSON inválido: {exc2}") from exc2
        else:
            raise ValueError(f"LLM devolvió JSON inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("La respuesta debe ser un objeto JSON")
    topics = data.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("JSON sin lista «topics»")
    out: list[dict[str, Any]] = []
    for i, t in enumerate(topics):
        if not isinstance(t, dict):
            continue
        title = str(t.get("title") or "").strip()
        angle = str(t.get("angle") or "").strip()
        if not title or not angle:
            continue
        from videomaker.pipeline.duration_policy import format_pipeline_duration_minutes

        dm = format_pipeline_duration_minutes(t.get("recommended_duration_minutes"))
        def _num(x: Any) -> int | None:
            if x is None:
                return None
            try:
                return int(float(x))
            except (TypeError, ValueError):
                return None

        out.append(
            {
                "title": title,
                "angle": angle,
                "recommended_duration_minutes": dm,
                "why_now": str(t.get("why_now") or "").strip(),
                "primary_trigger": str(t.get("primary_trigger") or "").strip(),
                "trigger_stack": (
                    [str(x).strip() for x in (t.get("trigger_stack") or []) if str(x).strip()]
                    if isinstance(t.get("trigger_stack"), list)
                    else []
                ),
                "emotional_promise": str(t.get("emotional_promise") or "").strip(),
                "emotional_arc": t.get("emotional_arc") if isinstance(t.get("emotional_arc"), dict) else None,
                "visual_symbols": (
                    [
                        x
                        for x in (t.get("visual_symbols") or [])
                        if isinstance(x, dict) and (x.get("symbol") or x.get("meaning") or x.get("recurrence_strategy"))
                    ][:8]
                    if isinstance(t.get("visual_symbols"), list)
                    else []
                ),
                "psychological_triggers": (
                    [
                        str(x).strip()
                        for x in (t.get("psychological_triggers") or [])
                        if str(x).strip()
                    ][:10]
                    if isinstance(t.get("psychological_triggers"), list)
                    else []
                ),
                "viewer_state_before_click": t.get("viewer_state_before_click")
                if isinstance(t.get("viewer_state_before_click"), dict)
                else None,
                "viewer_state_after_video": t.get("viewer_state_after_video")
                if isinstance(t.get("viewer_state_after_video"), dict)
                else None,
                "energy_curve": (
                    [str(x).strip() for x in (t.get("energy_curve") or []) if str(x).strip()]
                    if isinstance(t.get("energy_curve"), list)
                    else []
                )[:12],
                "visual_density": t.get("visual_density")
                if isinstance(t.get("visual_density"), dict)
                else None,
                "credibility_rules": t.get("credibility_rules")
                if isinstance(t.get("credibility_rules"), dict)
                else None,
                "thumbnail_narrative": t.get("thumbnail_narrative")
                if isinstance(t.get("thumbnail_narrative"), dict)
                else None,
                "core_emotion": str(t.get("core_emotion") or "").strip(),
                "identity_shift": str(t.get("identity_shift") or "").strip(),
                "identity_transformation": t.get("identity_transformation")
                if isinstance(t.get("identity_transformation"), dict)
                else None,
                "transformation_claim": str(t.get("transformation_claim") or "").strip(),
                "thumbnail_text": str(t.get("thumbnail_text") or "").strip(),
                "thumbnail_concept": t.get("thumbnail_concept")
                if isinstance(t.get("thumbnail_concept"), dict)
                else None,
                "thumbnailability": _num(t.get("thumbnailability")),
                "familiar_pain": str(t.get("familiar_pain") or "").strip(),
                "expectation_break": str(t.get("expectation_break") or "").strip(),
                "novelty_device": str(t.get("novelty_device") or "").strip(),
                "social_identity_tension": str(t.get("social_identity_tension") or "").strip(),
                "tribe_boundary": str(t.get("tribe_boundary") or "").strip(),
                "status_anxiety_hook": str(t.get("status_anxiety_hook") or "").strip(),
                "freedom_fantasy": str(t.get("freedom_fantasy") or "").strip(),
                "regret_trigger": str(t.get("regret_trigger") or "").strip(),
                "identity_tension": _num(t.get("identity_tension") or t.get("social_tension_score")),
                "dominant_emotion": str(t.get("dominant_emotion") or "").strip(),
                "visualizability": t.get("visualizability")
                if isinstance(t.get("visualizability"), dict)
                else None,
                "scroll_stop_factors": (
                    [str(x).strip() for x in (t.get("scroll_stop_factors") or []) if str(x).strip()]
                    if isinstance(t.get("scroll_stop_factors"), list)
                    else []
                ),
                "opening_hook": str(t.get("opening_hook") or "").strip(),
                "visual_anchor": str(t.get("visual_anchor") or "").strip(),
                "scene_pack": (
                    [str(x).strip() for x in (t.get("scene_pack") or []) if str(x).strip()]
                    if isinstance(t.get("scene_pack"), list)
                    else []
                )[:15],
                "broll_keywords": (
                    [str(x).strip() for x in (t.get("broll_keywords") or []) if str(x).strip()]
                    if isinstance(t.get("broll_keywords"), list)
                    else []
                )[:12],
                "instantly_visualizable": bool(t.get("instantly_visualizable"))
                if t.get("instantly_visualizable") is not None
                else None,
                "click_impulse_score": _num(t.get("click_impulse_score")),
                "visual_explosiveness_score": _num(t.get("visual_explosiveness_score")),
                "abstractness_score": _num(t.get("abstractness_score")),
                "explaining_mode_score": _num(t.get("explaining_mode_score")),
                "novelty_score": _num(t.get("novelty_score")),
                # legacy field kept for backward compatibility; prefer `identity_tension`
                "social_tension_score": _num(t.get("social_tension_score")),
                "intellectual_tone_score": _num(t.get("intellectual_tone_score")),
            }
        )
    if not out:
        raise ValueError("Ningún tema válido en la respuesta del modelo")
    return out


def generate_topic_ideas(
    *,
    transcript_text: str,
    niche_trends: str = "",
    topic_count: int = 8,
    output_language: str | None = None,
    channel_language: str | None = None,
    provider: str = "anthropic",
    model: str = "",
    detail_level: str = "fast",  # "fast" | "full"
) -> dict[str, Any]:
    """Llama al LLM y devuelve payload listo para guardar en topic_generator.json."""
    text = (transcript_text or "").strip()
    if len(text) < 50:
        raise ValueError("Se necesita más texto de transcripciones (mín. ~50 caracteres)")
    lang = resolve_output_language(
        explicit=output_language,
        channel_language=channel_language,
        transcript_text=text,
    )
    count = max(3, min(20, int(topic_count or 8)))
    trends = (niche_trends or "").strip() or "(no niche trend notes — infer gaps from catalog only)"
    from videomaker.llm.llm_routing import CREATIVE_PROVIDER, resolve_creative_model

    resolved_provider = CREATIVE_PROVIDER
    resolved_model = resolve_creative_model(model)

    fast = str(detail_level or "fast").strip().lower() != "full"
    mode_lines = (
        [
            "- Do NOT include long lists. Fast mode.",
            "- Do NOT generate scene_pack, broll_keywords, opening_hook or visual_anchor.",
        ]
        if fast
        else [
            "- scene_pack: prefer 15 scenes, but you may return 6-15; each must be short (max ~12 words).",
            "- broll_keywords: 6-10 items max.",
        ]
    )
    from videomaker.pipeline.duration_policy import (
        PIPELINE_TARGET_MAX_MINUTES,
        PIPELINE_TARGET_MIN_MINUTES,
    )

    user_msg = "\n".join(
        [
            f"Generate exactly {count} video topic ideas.",
            f"Required output language: {language_label(lang)} ({lang}).",
            "",
            f"Target duration for every topic: {int(PIPELINE_TARGET_MIN_MINUTES)}–{int(PIPELINE_TARGET_MAX_MINUTES)} minutes "
            f"(recommended_duration_minutes must be an integer in that range).",
            "",
            "Keep the output COMPACT.",
            "- Titles: punchy, < 70 chars.",
            "- angle/why_now/emotional_promise/etc: 1 sentence each.",
            *mode_lines,
            "- thumbnail_concept.one_sentence: 1 sentence.",
            "",
            "--- NICHE TRENDS ---",
            trends,
            "",
            "--- CHANNEL TRANSCRIPTS ---",
            text[:20_000],
            "",
            "Return JSON with the «topics» list. All text fields must be in the required output language.",
        ]
    )

    system_msg = _topic_system(lang)
    last_err: str | None = None
    raw = ""
    for attempt in range(3):
        raw = _call_llm(
            system=system_msg,
            user=(
                user_msg
                if not last_err
                else (
                    user_msg
                    + "\n\n"
                    + "Your previous response was INVALID JSON.\n"
                    + f"Error: {last_err}\n"
                    + "Return ONLY a valid JSON object matching the schema. No commentary."
                )
            ),
            provider=resolved_provider,
            model=resolved_model,
            temperature=0.35 if attempt == 0 else 0.2,
        )
        try:
            topics = _parse_topics_json(raw)[:count]
            break
        except ValueError as e:
            last_err = str(e)
            topics = []
    if not topics:
        preview = (raw or "").strip().replace("\n", " ")
        preview = preview[:3000]
        raise ValueError(
            "El modelo devolvió JSON inválido tras reintentos. "
            "Prueba a bajar `topic_count` o simplificar el transcript.\n"
            f"Detalle: {last_err or '(sin detalle)'}\n"
            f"Preview: {preview}"
        )
    from datetime import datetime, timezone

    topics_out = _strip_schema_fields_for_fast(topics) if fast else topics
    from videomaker.pipeline.duration_policy import apply_duration_policy_to_topic_payload

    return apply_duration_policy_to_topic_payload(
        {
            "version": 2,
            "output_language": lang,
            "topic_count_requested": count,
            "topic_count": len(topics_out),
            "niche_trends": (niche_trends or "").strip(),
            "transcript_chars": len(text),
            "topics": topics_out,
            "selected_index": None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def enrich_topic_idea(
    *,
    base_topic: dict[str, Any],
    transcript_text: str,
    niche_trends: str,
    output_language: str,
    provider: str,
    model: str,
) -> dict[str, Any]:
    """Heavy pass: fill scene_pack + broll_keywords + opening_hook + visual_anchor."""
    lang = resolve_output_language(
        explicit=output_language,
        transcript_text=transcript_text,
    )
    system_msg = _topic_system(lang)
    title = str(base_topic.get("title") or "").strip()
    angle = str(base_topic.get("angle") or "").strip()
    thumb = str(base_topic.get("thumbnail_text") or "").strip()
    arc = base_topic.get("emotional_arc") if isinstance(base_topic.get("emotional_arc"), dict) else {}
    arc_s = str(arc.get("start") or "").strip()
    arc_m = str(arc.get("mid") or "").strip()
    arc_e = str(arc.get("end") or "").strip()
    user_msg = (
        "Enrich ONE selected topic with visual director details.\n"
        "Return ONLY valid JSON (no markdown).\n\n"
        f"Selected topic title: {title}\n"
        f"Angle: {angle}\n"
        f"Thumbnail text: {thumb}\n"
        f"Emotional arc: start={arc_s} mid={arc_m} end={arc_e}\n\n"
        "Return JSON with these keys:\n"
        "{\n"
        '  "opening_hook": "<1-2 lines for first 5 seconds>",\n'
        '  "visual_anchor": "<1 sentence recurring symbol/prop>",\n'
        '  "broll_keywords": ["..."],\n'
        '  "scene_pack": ["..."]\n'
        "}\n\n"
        "Constraints:\n"
        "- broll_keywords: 6-10 items.\n"
        "- scene_pack: 12-15 short scenes (<= ~12 words each).\n"
        "- Must match the thumbnail and emotional arc.\n\n"
        f"--- NICHE TRENDS ---\n{(niche_trends or '').strip() or '(none)'}\n\n"
        f"--- CHANNEL TRANSCRIPTS ---\n{(transcript_text or '')[:12_000]}\n"
    )
    raw = _call_llm(system=system_msg, user=user_msg, provider=provider, model=model, temperature=0.25)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Enrich response must be a JSON object")
    merged = dict(base_topic)
    for k in ("opening_hook", "visual_anchor"):
        if isinstance(data.get(k), str) and str(data.get(k)).strip():
            merged[k] = str(data.get(k)).strip()
    if isinstance(data.get("broll_keywords"), list):
        merged["broll_keywords"] = [str(x).strip() for x in data["broll_keywords"] if str(x).strip()][:12]
    if isinstance(data.get("scene_pack"), list):
        merged["scene_pack"] = [str(x).strip() for x in data["scene_pack"] if str(x).strip()][:15]
    return merged
