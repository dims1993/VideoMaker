"""Avatar Prompt Writer: genera image_prompts.json a partir del guion con avatar del canal.

Flujo:
  1. Lee script.md del work_dir (o texto pasado directamente).
  2. Limpia el texto: elimina marcadores de acto, etiquetas B-ROLL, titulares.
  3. Divide en segmentos proporcionales a secs_per_image (ritmo visual configurable).
  4. Llama al LLM en batches para asignar expresión y generar prompt IA por segmento.
  5. Persiste pipeline/image_prompts.json con la estructura canónica v2.

Ritmo de referencia (canal Nick Invests estilo):
  - Guion ~3-5 min: @5 s/img → 36-60 imágenes
  - Guion ~22 min:  @8 s/img → 165 imágenes
  - Máximo por defecto: 80 imágenes (evitar colas largas en la API de generación)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constantes del avatar
# ---------------------------------------------------------------------------

AVATAR_DEFAULT_DESCRIPTION = (
    "chibi cartoon boy, round thick-frame glasses, chubby face, short messy brown hair, "
    "light blue button-up shirt with small chest pocket, dark navy pants, simple flat shoes, "
    "flat 2D cartoon illustration, thick black outline"
)

# Expresiones visibles en la imagen de referencia del canal
AVATAR_EXPRESSIONS: dict[str, str] = {
    "smiling": "slight smile showing small teeth, friendly cheerful look",
    "surprised": "mouth wide open, eyes wide open in shock or amazement",
    "bored": "half-closed eyes, flat neutral expression, slightly disengaged",
    "sleepy": "eyes fully closed, mouth slightly open, exhausted look",
    "neutral": "straight face, large round eyes fully open, calm and serious",
    "explaining": "one finger raised pointing up, confident expression, leaning slightly forward",
    "worried": "furrowed brow, concerned expression, hands raised at chest height",
    "thinking": "hand on chin, slightly tilted head, focused contemplative look",
    "excited": "big wide smile, arms raised or hands pumped, energetic",
}

_WORDS_PER_SECOND = 2.5  # ritmo narración estándar


# ---------------------------------------------------------------------------
# Limpieza del guion
# ---------------------------------------------------------------------------

_RE_ACT_HEADING = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?(?:Acto|Act|Parte)\s*\d+(?:\*\*)?\s*$"
)
_RE_BROLL_TAG = re.compile(
    r"\[(?:B-ROLL|REFERENCIA\s*VISUAL|VISUAL|BROLL)[^\]]*\]", re.I
)
_RE_MARKDOWN_H = re.compile(r"(?m)^#{1,6}\s*.+$")
_RE_BRACKET_LINE = re.compile(r"(?m)^\s*\[[^\]]+\]\s*$")
_RE_MULTI_BLANK = re.compile(r"\n{3,}")
_RE_BOLD_LABEL = re.compile(r"\*\*[^*]+:\*\*")  # **Narrador:** etc.


def clean_script_for_avatar(script_text: str) -> str:
    """Extrae solo el texto narrativo; elimina marcadores de estructura."""
    t = _RE_ACT_HEADING.sub("", script_text)
    t = _RE_BROLL_TAG.sub("", t)
    t = _RE_MARKDOWN_H.sub("", t)
    t = _RE_BRACKET_LINE.sub("", t)
    t = _RE_BOLD_LABEL.sub("", t)
    t = _RE_MULTI_BLANK.sub("\n\n", t)
    return t.strip()


# ---------------------------------------------------------------------------
# Segmentación
# ---------------------------------------------------------------------------

def segment_script(text: str, target_words: int) -> list[str]:
    """Divide *text* en segmentos de ~target_words palabras sin cortar oraciones si es posible."""
    # Dividir por párrafos
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    segments: list[str] = []
    current: list[str] = []

    for para in paragraphs:
        words = para.split()
        current.extend(words)
        while len(current) >= target_words:
            # Intentar cortar en un punto/límite de oración
            chunk = current[:target_words]
            # Buscar el último punto en el chunk
            joined = " ".join(chunk)
            m = re.search(r"[.!?][^.!?]{0,20}$", joined)
            if m:
                cut = m.start() + 1
                segments.append(joined[:cut].strip())
                rest = joined[cut:].strip()
                current = rest.split() + current[target_words:]
            else:
                segments.append(joined)
                current = current[target_words:]

    if current:
        leftover = " ".join(current).strip()
        if leftover:
            if segments and len(current) < target_words // 3:
                segments[-1] = segments[-1] + " " + leftover
            else:
                segments.append(leftover)

    return [s for s in segments if s]


# ---------------------------------------------------------------------------
# Prompt al LLM
# ---------------------------------------------------------------------------

def _build_system_prompt(
    avatar_description: str,
    target_generator: str,
    *,
    scene_visual_settings: dict[str, Any] | None = None,
) -> str:
    generator_notes: dict[str, str] = {
        "gemini": (
            "Escribe un párrafo en inglés claro y denso (prosa, no listas de tags) para Gemini / "
            "Nano Banana: protagonista, expresión, fondo y acción. Sin parámetros Midjourney ni texto legible en imagen."
        ),
        "midjourney": (
            "Termina cada ai_prompt con los parámetros Midjourney: --ar 16:9 --style raw --q 2"
        ),
        "flux": "Usa descripción natural densa; no incluyas parámetros de Midjourney.",
        "dall_e": "Sé descriptivo y evita texto en las imágenes.",
        "sd": "Usa etiquetas separadas por coma al estilo Stable Diffusion/SDXL.",
        "custom": "Adapta el formato al generador personalizado.",
    }
    gen_note = generator_notes.get(target_generator, generator_notes["gemini"])

    expressions_block = "\n".join(
        f"  - {k}: {v}" for k, v in AVATAR_EXPRESSIONS.items()
    )
    style_block = (
        "- Flat 2D cartoon, whiteboard animation aesthetic\n"
        "- Grosor de contorno uniforme (thick black outline)\n"
        "- Paleta de colores plana y limpia\n"
        "- Fondos simples con elementos gráficos relevantes (gráficos de barras, monedas, casas, reloj, etc.)\n"
        "- Sin fotorrealismo, sin 3D, sin caras reconocibles adicionales"
    )
    avoid_note = ""
    action_note = ""
    if scene_visual_settings:
        base = str(scene_visual_settings.get("base_style_en") or "").strip()
        if base:
            style_block = base
        expr_cat = str(scene_visual_settings.get("protagonist_expressions_en") or "").strip()
        if expr_cat:
            expressions_block = expr_cat
        avoid = str(scene_visual_settings.get("avoid_en") or "").strip()
        if avoid:
            avoid_note = f"\nEVITAR EN TODAS LAS IMÁGENES:\n{avoid}\n"
        action = str(scene_visual_settings.get("protagonist_action_rules_en") or "").strip()
        if action:
            action_note = f"\nREGLAS DE POSE Y ACCIÓN:\n{action}\n"

    return f"""Eres un director de arte para un canal de vídeos educativos animados sobre finanzas personales.
Tu tarea es analizar cada segmento del guion y generar un prompt de imagen IA para generadores como Midjourney, Flux o SDXL.

AVATAR DEL CANAL (inclúyelo como sujeto principal en cada imagen):
{avatar_description}

EXPRESIONES DISPONIBLES DEL AVATAR:
{expressions_block}

ESTILO VISUAL DEL CANAL:
{style_block}
{avoid_note}{action_note}
INSTRUCCIONES PARA CADA SEGMENTO:
1. Lee el contenido emocional y temático del segmento
2. Elige la expresión del avatar que mejor encaje
3. Si el segmento menciona personajes de la historia (por ejemplo Jake o Emma), inclúyelos en el prompt y describe brevemente su acción o relación con el momento
4. Define una situación visual breve en español (qué hace el avatar y qué sucede en la escena)
5. Escribe el ai_prompt COMPLETO EN INGLÉS describiendo: avatar + personajes de la historia si aparecen + expresión + situación + estilo
6. No generes etiquetas ni prompts de tipo B-ROLL; esto debe ser un prompt de imagen narrativo y concreto.
7. {gen_note}

RESPONDE EXCLUSIVAMENTE con un array JSON válido (sin markdown, sin texto extra):
[
  {{
    "id": 1,
    "expression": "nombre_expresion",
    "situation": "descripción breve en español",
    "ai_prompt": "prompt completo en inglés",
    "negative_prompt": "realistic, photorealistic, 3D render, real photo, ugly, blurry"
  }}
]
"""


# ---------------------------------------------------------------------------
# Parser robusto
# ---------------------------------------------------------------------------

def _parse_llm_array(raw: str) -> list[dict[str, Any]]:
    """Parsea la respuesta del LLM como array JSON. Tolera markdown fence."""
    text = raw.strip()
    # Remover fences
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()
    # Extraer el primer array JSON
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        text = m.group(0)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

_INTRO_SYSTEM = """Eres un guionista especializado en canales de vídeo educativos con personaje animado.
Tu tarea es escribir UNA sola coletilla de presentación (2-3 oraciones) para intercalar
DESPUÉS del gancho (hook) del vídeo y ANTES del cuerpo del contenido.

La coletilla debe:
1. Presentar al personaje por su nombre (en el idioma del guion).
2. Hacer una transición natural desde el gancho.
3. Anunciar brevemente el tema que se tratará hoy, sin spoilear los datos clave.
4. Sonar conversacional y cercano, coherente con el tono del guion.

Responde SOLO con un objeto JSON (sin markdown):
{
  "narration_text": "texto que narrará el TTS (mismo idioma que el guion, 2-3 oraciones)",
  "situation": "descripción breve en español de lo que hace el avatar en esta imagen",
  "expression": "smiling | explaining | excited",
  "ai_prompt": "prompt completo en inglés para generador IA"
}"""


def _generate_intro_segment(
    *,
    script_text: str,
    character_name: str,
    avatar_description: str,
    target_generator: str,
    provider: str,
    model: str,
    temperature: float = 0.5,
) -> dict[str, Any]:
    """Genera la coletilla de presentación del avatar (segmento especial tras el hook)."""
    # Extraer el gancho (primeras ~300 palabras del texto limpio) para dar contexto
    clean = clean_script_for_avatar(script_text)
    hook_excerpt = " ".join(clean.split()[:300])

    mj_suffix = " --ar 16:9 --style raw --q 2" if target_generator == "midjourney" else ""

    user_msg = (
        f"Nombre del personaje: {character_name}\n"
        f"Descripción del avatar: {avatar_description}\n\n"
        f"--- GANCHO DEL VÍDEO (contexto) ---\n{hook_excerpt}\n\n"
        f"Genera la coletilla de presentación. "
        f"El ai_prompt debe terminar con: {mj_suffix if mj_suffix else '(ningún sufijo)'}."
    )

    try:
        raw = _call_llm(
            system=_INTRO_SYSTEM,
            user=user_msg,
            provider=provider,
            model=model,
            temperature=temperature,
        )
        # Parsear como objeto JSON (tolerante a fence)
        text = raw.strip()
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            text = m.group(0)
        data = json.loads(text)
    except Exception as exc:
        # Fallback si el LLM falla
        data = {
            "narration_text": (
                f"Hola, soy {character_name}. "
                f"Hoy vamos a ver algo que muy poca gente entiende… pero que cambia todo."
            ),
            "situation": "Avatar saludando a la cámara con una sonrisa",
            "expression": "smiling",
            "ai_prompt": (
                f"{avatar_description}, smiling expression, waving hello with one hand raised, "
                f"standing confidently, flat 2D cartoon, whiteboard animation style"
                f"{mj_suffix}"
            ),
            "_fallback_reason": str(exc),
        }

    return {
        "id": "intro",
        "track": "avatar",
        "role": "avatar_intro",
        "act": "intro",
        "expression": data.get("expression", "smiling"),
        "situation": data.get("situation", f"{character_name} se presenta al espectador"),
        "narration_text": data.get("narration_text", ""),
        "ai_prompt": data.get("ai_prompt", ""),
        "negative_prompt": "realistic, photorealistic, 3D render, real photo, ugly, blurry",
        "segment_text": data.get("narration_text", ""),
    }


_OUTRO_SYSTEM = """Eres un guionista especializado en canales de vídeo educativos con personaje animado.
Tu tarea es escribir UNA sola coletilla de cierre (2-3 oraciones) para usar al FINAL del vídeo,
después de que el contenido principal ha terminado.

La coletilla debe:
1. Hacer una transición natural y emotiva desde el cierre del contenido.
2. Pedir de forma auténtica y cercana que el espectador se suscriba al canal.
3. Pedir que dé "me gusta" si el contenido le ha gustado o le ha sido útil.
4. Sonar como Nick Invests: conversacional, sin frases robóticas tipo "no olvides suscribirte".
5. Usar el idioma del guion.

Responde SOLO con un objeto JSON (sin markdown):
{
  "narration_text": "texto que narrará el TTS (mismo idioma que el guion, 2-3 oraciones)",
  "situation": "descripción breve en español de lo que hace el avatar en esta imagen",
  "expression": "smiling | excited | explaining",
  "ai_prompt": "prompt completo en inglés para generador IA"
}"""


def _generate_outro_segment(
    *,
    script_text: str,
    character_name: str,
    avatar_description: str,
    target_generator: str,
    provider: str,
    model: str,
    temperature: float = 0.5,
) -> dict[str, Any]:
    """Genera la coletilla de cierre del avatar (suscripción + like)."""
    clean = clean_script_for_avatar(script_text)
    cta_excerpt = " ".join(clean.split()[-200:])  # últimas 200 palabras como contexto

    mj_suffix = " --ar 16:9 --style raw --q 2" if target_generator == "midjourney" else ""

    user_msg = (
        f"Nombre del personaje: {character_name}\n"
        f"Descripción del avatar: {avatar_description}\n\n"
        f"--- CIERRE DEL VÍDEO (contexto) ---\n{cta_excerpt}\n\n"
        f"Genera la coletilla de cierre pidiendo suscripción y like. "
        f"El ai_prompt debe terminar con: {mj_suffix if mj_suffix else '(ningún sufijo)'}."
    )

    try:
        raw = _call_llm(
            system=_OUTRO_SYSTEM,
            user=user_msg,
            provider=provider,
            model=model,
            temperature=temperature,
        )
        text = raw.strip()
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            text = m.group(0)
        data = json.loads(text)
    except Exception as exc:
        data = {
            "narration_text": (
                f"Si esto te ha hecho pensar, dale al me gusta: es la mejor forma de decirme que siga. "
                f"Y si quieres seguir haciendo las cuentas reales juntos, suscríbete. "
                f"Nos vemos en el próximo."
            ),
            "situation": f"{character_name} señala hacia la cámara con una sonrisa cómplice",
            "expression": "smiling",
            "ai_prompt": (
                f"{avatar_description}, smiling expression, pointing finger toward camera, "
                f"thumbs up gesture, friendly and confident pose, "
                f"flat 2D cartoon, whiteboard animation style{mj_suffix}"
            ),
            "_fallback_reason": str(exc),
        }

    return {
        "id": "outro",
        "track": "avatar",
        "role": "avatar_outro",
        "act": "outro",
        "expression": data.get("expression", "smiling"),
        "situation": data.get("situation", f"{character_name} pide suscripción y like"),
        "narration_text": data.get("narration_text", ""),
        "ai_prompt": data.get("ai_prompt", ""),
        "negative_prompt": "realistic, photorealistic, 3D render, real photo, ugly, blurry",
        "segment_text": data.get("narration_text", ""),
    }


def generate_avatar_image_prompts(
    work_dir: Path,
    *,
    script_text: str | None = None,
    avatar_description: str | None = None,
    scene_visual_settings: dict[str, Any] | None = None,
    intro_enabled: bool = False,
    intro_character_name: str = "Nerd",
    outro_enabled: bool = False,
    outro_character_name: str = "Nerd",
    secs_per_image: float = 6.0,
    max_images: int = 80,
    target_generator: str = "midjourney",
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Genera pipeline/image_prompts.json con prompts del avatar basados en el guion.

    Args:
        work_dir: directorio de sesión de trabajo.
        script_text: texto del guion; si es None se lee de work_dir/script.md.
        avatar_description: descripción del avatar; usa AVATAR_DEFAULT_DESCRIPTION si es None.
        secs_per_image: segundos de narración que representa cada imagen.
        max_images: máximo de prompts a generar (limita llamadas a la API de imágenes).
        target_generator: "midjourney" | "flux" | "dall_e" | "sd" | "custom".
        provider: "openai" | "ollama" (override; por defecto lee VIDEOMAKER_LLM_PROVIDER).
        model: nombre del modelo LLM (override).

    Returns:
        {"path": str, "prompt_count": int}
    """
    # --- Leer guion ---
    if script_text is None:
        script_path = work_dir / "script.md"
        if not script_path.is_file():
            raise ValueError(
                "Falta script.md. Ejecuta el paso Script Writer antes de generar prompts de avatar."
            )
        script_text = script_path.read_text(encoding="utf-8")

    if not avatar_description:
        avatar_description = AVATAR_DEFAULT_DESCRIPTION

    # --- Segmentar guion ---
    target_words = max(8, int(_WORDS_PER_SECOND * secs_per_image))
    clean_text = clean_script_for_avatar(script_text)
    segments = segment_script(clean_text, target_words)

    if len(segments) > max_images:
        segments = segments[:max_images]

    if not segments:
        raise ValueError("El guion no contiene texto narrativo para segmentar.")

    # --- Configurar proveedor LLM ---
    resolved_provider = (
        provider
        or os.environ.get("VIDEOMAKER_LLM_PROVIDER", "openai")
    ).lower()
    resolved_model = model or (
        os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
        if resolved_provider == "ollama"
        else os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    )

    try:
        temp = float(os.environ.get("VIDEOMAKER_AVATAR_PROMPT_TEMPERATURE", "0.6"))
    except ValueError:
        temp = 0.6

    system_prompt = _build_system_prompt(
        avatar_description,
        target_generator,
        scene_visual_settings=scene_visual_settings,
    )

    # --- Generar coletillas de presentación y cierre (si están habilitadas) ---
    intro_item: dict[str, Any] | None = None
    if intro_enabled and intro_character_name:
        intro_item = _generate_intro_segment(
            script_text=script_text,
            character_name=intro_character_name,
            avatar_description=avatar_description,
            target_generator=target_generator,
            provider=resolved_provider,
            model=resolved_model,
            temperature=temp,
        )

    outro_item: dict[str, Any] | None = None
    if outro_enabled and outro_character_name:
        outro_item = _generate_outro_segment(
            script_text=script_text,
            character_name=outro_character_name,
            avatar_description=avatar_description,
            target_generator=target_generator,
            provider=resolved_provider,
            model=resolved_model,
            temperature=temp,
        )

    # --- Generar en batches ---
    BATCH_SIZE = 12
    all_items: list[dict[str, Any]] = []

    for batch_start in range(0, len(segments), BATCH_SIZE):
        batch = segments[batch_start : batch_start + BATCH_SIZE]
        numbered = "\n\n".join(
            f"[{batch_start + j + 1}] {seg}" for j, seg in enumerate(batch)
        )
        user_msg = (
            f"Genera los prompts de imagen para estos {len(batch)} segmentos del guion:\n\n"
            f"{numbered}"
        )

        try:
            raw = _call_llm(
                system=system_prompt,
                user=user_msg,
                provider=resolved_provider,
                model=resolved_model,
                temperature=temp,
            )
            items = _parse_llm_array(raw)
        except Exception as exc:
            # Fallback: un prompt genérico por segmento
            items = [
                {
                    "id": batch_start + j + 1,
                    "expression": "explaining",
                    "situation": "Presentando información al espectador",
                    "ai_prompt": (
                        f"{avatar_description}, explaining expression, standing in front of a whiteboard, "
                        "educational animated video style, flat 2D cartoon, thick black outline, "
                        "simple background with financial charts --ar 16:9 --style raw --q 2"
                    ),
                    "negative_prompt": "realistic, photorealistic, 3D render, photo, blurry",
                    "_fallback_reason": str(exc),
                }
                for j in range(len(batch))
            ]

        # Normalizar y adjuntar texto del segmento
        for j, item in enumerate(items):
            item["id"] = batch_start + j + 1
            item["_segment_text"] = batch[j] if j < len(batch) else ""

        all_items.extend(items)

    # --- Calcular actos aproximados ---
    total_len = len(clean_text)

    def _guess_act(seg_text: str) -> str:
        pos = clean_text.find(seg_text[:40]) if len(seg_text) >= 40 else -1
        if pos < 0:
            return "body"
        ratio = pos / max(total_len, 1)
        if ratio < 0.15:
            return "hook"
        if ratio > 0.85:
            return "cta"
        return "body"

    # --- Ensamblar lista final: hook → intro → body/cta ---
    # Encontrar el índice donde terminan los segmentos de "hook" para insertar la intro
    hook_end_idx = 0
    for i, item in enumerate(all_items):
        act = _guess_act(item.get("_segment_text", ""))
        if act == "hook":
            hook_end_idx = i + 1
        else:
            break  # primer segmento no-hook: cortar

    serialized_body: list[dict[str, Any]] = [
        {
            "id": str(item.get("id", i + 1)),
            "track": "avatar",
            "act": _guess_act(item.get("_segment_text", "")),
            "expression": item.get("expression", "neutral"),
            "situation": item.get("situation", ""),
            "ai_prompt": item.get("ai_prompt", ""),
            "negative_prompt": item.get("negative_prompt", "realistic, photorealistic, 3D render, photo"),
            "segment_text": (item.get("_segment_text") or "")[:200],
        }
        for i, item in enumerate(all_items)
    ]

    if intro_item:
        serialized_body.insert(hook_end_idx, intro_item)

    if outro_item:
        serialized_body.append(outro_item)

    # Re-numerar IDs en orden final (preservar ids especiales "intro" / "outro")
    counter = 1
    for p in serialized_body:
        if p.get("id") in ("intro", "outro"):
            continue
        p["id"] = str(counter)
        counter += 1

    # --- Construir bundle final ---
    mj_suffix = "--ar 16:9 --style raw --q 2" if target_generator == "midjourney" else ""
    bundle: dict[str, Any] = {
        "version": 2,
        "source": "avatar_prompt_writer",
        "avatar_description": avatar_description,
        "intro_enabled": intro_enabled,
        "intro_character_name": intro_character_name if intro_enabled else "",
        "outro_enabled": outro_enabled,
        "outro_character_name": outro_character_name if outro_enabled else "",
        "target_generator": target_generator,
        "secs_per_image": secs_per_image,
        "total_prompts": len(serialized_body),
        "global_style": {
            "aspect_ratio": "16:9",
            "style": "flat 2D cartoon, whiteboard animation, educational YouTube",
            "negative_prompt": "realistic, photorealistic, 3D render, real photo, ugly, blurry",
            **({"midjourney_suffix": mj_suffix} if mj_suffix else {}),
        },
        "prompts": serialized_body,
    }
    # Carry visual symbol system into image prompt stage (editor/motion/thumb consistency).
    try:
        import json as _json
        p = work_dir / "pipeline" / "prompt.json"
        if p.is_file():
            art = _json.loads(p.read_text(encoding="utf-8"))
            vs = art.get("visual_symbols") if isinstance(art, dict) else None
            if isinstance(vs, list) and vs:
                bundle["global_style"]["visual_symbols"] = vs[:8]
            tn = art.get("thumbnail_narrative") if isinstance(art, dict) else None
            if isinstance(tn, dict) and any(str(tn.get(k) or "").strip() for k in ("core_contrast","viewer_role","envy_target","emotion")):
                bundle["global_style"]["thumbnail_narrative"] = {
                    "core_contrast": str(tn.get("core_contrast") or "").strip(),
                    "viewer_role": str(tn.get("viewer_role") or "").strip(),
                    "envy_target": str(tn.get("envy_target") or "").strip(),
                    "emotion": str(tn.get("emotion") or "").strip(),
                }
            ssf = art.get("scroll_stop_factors") if isinstance(art, dict) else None
            if isinstance(ssf, list) and ssf:
                vals = [str(x).strip() for x in ssf if str(x).strip()][:10]
                if vals:
                    bundle["global_style"]["scroll_stop_factors"] = vals
    except Exception:
        pass

    out = work_dir / "pipeline" / "image_prompts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"path": "pipeline/image_prompts.json", "prompt_count": len(all_items)}


def preview_avatar_prompt_segment(
    work_dir: Path,
    *,
    segment_text: str,
    target_generator: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Una sola llamada LLM (misma ruta que IPW Start / ``_enrich_avatar_prompt_rows``).
    No escribe ``image_prompts.json``.
    """
    from videomaker.core.image_prompt_writer_settings_store import read_image_prompt_writer_settings
    from videomaker.core.visual_style_presets_store import prepare_avatar_mode_for_work

    text = (segment_text or "").strip()
    if not text:
        raise ValueError("segment_text vacío.")

    st = read_image_prompt_writer_settings(work_dir)
    ctx = prepare_avatar_mode_for_work(work_dir)
    avatar_description = str(ctx.get("avatar_description") or AVATAR_DEFAULT_DESCRIPTION).strip()
    scene_visual_settings = ctx.get("scene_visual_settings")
    target_gen = (target_generator or st.get("target_generator") or "midjourney").strip()

    try:
        temp = float(os.environ.get("VIDEOMAKER_AVATAR_PROMPT_TEMPERATURE", "0.6"))
    except ValueError:
        temp = 0.6

    resolved_provider = (provider or os.environ.get("VIDEOMAKER_LLM_PROVIDER", "openai")).lower()
    resolved_model = model or (
        os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
        if resolved_provider == "ollama"
        else os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    )
    system_prompt = _build_system_prompt(
        avatar_description,
        target_gen,
        scene_visual_settings=scene_visual_settings if isinstance(scene_visual_settings, dict) else None,
    )
    user_msg = (
        "Genera prompts de imagen del AVATAR para este único fragmento narrado:\n\n"
        f"[1] {text[:500]}"
    )
    raw = _call_llm(
        system=system_prompt,
        user=user_msg,
        provider=resolved_provider,
        model=resolved_model,
        temperature=temp,
    )
    items = _parse_llm_array(raw)
    item = items[0] if items and isinstance(items[0], dict) else {}
    return {
        "provider": resolved_provider,
        "model": resolved_model,
        "target_generator": target_gen,
        "segment_text": text[:500],
        "ai_prompt": str(item.get("ai_prompt") or "").strip(),
        "expression": item.get("expression") or "explaining",
        "situation": item.get("situation") or "",
        "negative_prompt": item.get(
            "negative_prompt",
            "realistic, photorealistic, 3D render, photo, blurry",
        ),
        "raw_llm_preview": raw[:2000] if len(raw) > 2000 else raw,
    }


# ---------------------------------------------------------------------------
# Helper LLM (reutiliza los providers del proyecto)
# ---------------------------------------------------------------------------

def _call_llm(
    *,
    system: str,
    user: str,
    provider: str,
    model: str,
    temperature: float = 0.6,
) -> str:
    if provider == "ollama":
        from videomaker.llm.providers.ollama import ollama_chat

        return ollama_chat(
            system=system,
            user=user,
            model=model,
            response_json=False,
            temperature=temperature,
        ).strip()

    if provider == "anthropic":
        from videomaker.llm.providers.anthropic_chat import anthropic_chat

        return anthropic_chat(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
        )

    from videomaker.llm.providers.openai_compat import openai_compat_chat

    return openai_compat_chat(
        system=system,
        user=user,
        model=model,
        response_json=False,
        temperature=temperature,
    ).strip()
