"""Ensambla prompts finales para Nano Banana 2 (prosa + estilo base fijo)."""

from __future__ import annotations

import re
from typing import Any

from videomaker.llm.hook_retention_router import _has_cinematic_anchors, _is_stock_footage_prompt
from videomaker.scene_editor.protagonist_expressions import expressions_planner_block, expressions_catalog_from_settings
from videomaker.scene_editor.scene_visual_settings_store import _DEFAULT_PROTAGONIST_ACTION_RULES

_MIN_SCENE_LEN = 45
_MIN_SCENE_WORDS = 35
_MIN_FULL_LEN = 120

_STOPWORDS = frozenset(
    "the a an and or but you your is are was were be been being to of in on at for with "
    "that this it as if not no so than then one other their they them his her its our".split()
)

_STRICT_GENERIC_FILLER = (
    "inviting atmosphere",
    "sense of accomplishment",
    "blend of satisfaction",
    "determination as he",
    "determination as she",
    "contemplative as he",
    "wooden table",
    "cluttered desk",
)

_SOFT_GENERIC_FILLER = (
    "gentle shadows",
    "soft warm light filters",
    "enhancing the",
    "creating a sense",
)

_GENERIC_FILLER = _STRICT_GENERIC_FILLER + _SOFT_GENERIC_FILLER

_OVERUSED_STOCK = (
    "budget app",
    "budgeting app",
    "budget spreadsheet",
    "wooden table",
    "sleek wooden table",
    "smartphone as he navigates",
    "calculator displaying",
)

_CONTINUITY_PREFIX = (
    "Same illustration style and same protagonist design as described below — "
    "COMPLETELY DIFFERENT scene (new location, props, camera angle, body pose, and action — not a repeat). "
    "Do NOT reuse thinker pose (hand on chin), idle center observer, or seated contemplation. Scene:"
)

_BANNED_POSE_PHRASES = (
    "hand on chin",
    "hand to chin",
    "chin rest",
    "finger on chin",
    "rodin thinker",
    "thinker pose",
    "arms crossed",
    "stands in the center",
    "standing in the center",
    "standing idle",
    "watching vignettes",
)

_PASSIVE_MOOD_WORDS = (
    "thoughtful",
    "contemplat",
    "gazing reflect",
    "pensive",
    "pondering",
)

_HANDS_FRAMING_MARKERS = (
    "close-up on hands",
    "hands-only",
    "over-the-shoulder",
    "pov shot",
    "point-of-view",
    "his hands",
    "her hands",
    "with one hand",
    "with both hands",
)

_IMPLICIT_ACTION_MARKERS = (
    "finger on",
    "fingers on",
    "hand on the",
    "hands on the",
    "holding up",
    "mid-step",
    "mid stride",
    "in motion",
    "while walking",
    "while pointing",
)

_ACTION_VERBS = re.compile(
    r"\b("
    r"point|points|pointing|scroll|scrolls|scrolling|hold|holds|holding|walk|walks|walking|"
    r"reach|reaches|reaching|flip|flips|flipping|open|opens|opening|write|writes|writing|"
    r"type|types|typing|compare|compares|comparing|tap|taps|tapping|slide|slides|sliding|"
    r"turn|turns|turning|pick|picks|picking|push|pushes|pushing|pull|pulls|pulling|"
    r"step|steps|stepping|lean|leans|leaning|pin|pins|pinning|underline|underlines|underlining|"
    r"trace|traces|tracing|pass|passes|passing|study|studies|studying|read|reads|reading|"
    r"examine|examines|examining|highlight|highlights|highlighting|gesture|gestures|gesturing|"
    r"spread|spreads|spreading|unfold|unfolds|unfolding|look|looks|looking|mark|marks|marking|"
    r"circle|circles|circling|drag|drags|dragging|carry|carries|carrying|place|places|placing|"
    r"set|sets|setting|show|shows|showing|review|reviews|reviewing|scan|scans|scanning|"
    r"stamp|stamps|stamping|lift|lifts|lifting|grab|grabs|grabbing|swipe|swipes|swiping|"
    r"extend|extends|extending|display|displays|displaying|annotate|annotates|annotating|"
    r"count|counts|counting|match|matches|matching|run|runs|running|cross|crosses|crossing|"
    r"hand over|present|presents|presenting|nod|nods|nodding|raise|raises|raising|"
    r"lower|lowers|lowering|stack|stacks|stacking|arrange|arranges|arranging"
    r")\b",
    re.I,
)

_STRICT_PASSIVE_SIGNATURES = frozenset({"chin_thinker", "center_observer"})

_DISPLAY_SURFACE_WORDS = re.compile(
    r"\b("
    r"screen|whiteboard|blackboard|monitor|display|projector|"
    r"wall chart|pinned graph|graph on the wall|chart on the wall|"
    r"digital board|led screen|presentation board|large screen|"
    r"projected chart|data wall"
    r")\b",
    re.I,
)

_POINTER_GESTURE_WORDS = re.compile(
    r"\b("
    r"point|points|pointing|gestur\w+ toward|gestur\w+ towards|"
    r"indicat\w+|direct\w+ attention to|finger at"
    r")\b",
    re.I,
)

_GESTURE_RETRY_ALTERNATIVES = (
    "flipping or marking a physical paper document with a pen",
    "walking mid-step through a location named in the narration",
    "close-up on hands scrolling a phone or comparing two printouts side by side",
    "stacking, handing, or opening a folder of mortgage paperwork",
    "over-shoulder POV toward a form, screen, or object from the narration",
)

_GENERIC_PROTAGONIST_ANCHORS = frozenset(
    "face frame every same simple cartoon eyes circles minimal nose cheeks rendering shading "
    "realistic detailed irises editorial design small solid black circles shading".split()
)

_DEFAULT_PROTAGONIST_WARDROBE = (
    "messy dark brown hair, warm light-tan skin, black long-sleeve shirt, "
    "bare head with no hat cap hood or beanie"
)

_HAT_AVOID_EXTRA = "hat, cap, beanie, hood, headwear, baseball cap"


def protagonist_action_rules_from_settings(settings: dict[str, Any]) -> str:
    raw = str(settings.get("protagonist_action_rules_en") or "").strip()
    return raw or _DEFAULT_PROTAGONIST_ACTION_RULES


def protagonist_wardrobe_from_settings(settings: dict[str, Any]) -> str:
    raw = str(settings.get("protagonist_wardrobe_en") or "").strip()
    return raw or _DEFAULT_PROTAGONIST_WARDROBE


def character_design_lock(settings: dict[str, Any]) -> str:
    face = str(settings.get("protagonist_en") or "").strip()
    wardrobe = protagonist_wardrobe_from_settings(settings)
    if face and wardrobe:
        return f"{face.rstrip('.')}. {wardrobe.rstrip('.')}."
    return face or wardrobe


def effective_avoid_en(settings: dict[str, Any]) -> str:
    from videomaker.scene_editor.visual_pipeline_rules import resolved_auto_avoid_supplement

    base = str(settings.get("avoid_en") or "").strip().rstrip(".")
    extra = resolved_auto_avoid_supplement(settings)
    if re.search(r"\bhat\b|\bcap\b|\bbeanie\b", base, re.I) and extra.lower() in base.lower():
        return base
    return f"{base}, {extra}" if base else extra


def scene_has_wardrobe_lock(scene: str) -> bool:
    low = (scene or "").lower()
    has_hair = bool(re.search(r"\b(hair|brown hair|dark brown)\b", low))
    has_shirt = bool(re.search(r"\b(shirt|long-sleeve|black shirt)\b", low))
    no_hat = bool(re.search(r"\b(no hat|no cap|bare head|without hat|without cap)\b", low))
    return has_hair and has_shirt and no_hat


def protagonist_anchor_words(protagonist_en: str) -> set[str]:
    """Términos ancla del diseño del personaje (pelo, ropa, rasgos)."""
    text = (protagonist_en or "").strip()
    if not text:
        return set()
    words = _content_words(text, min_len=4) - _GENERIC_PROTAGONIST_ANCHORS
    low = text.lower()
    for phrase in (
        "dark brown hair",
        "brown hair",
        "black long-sleeve",
        "long-sleeve shirt",
        "rosy blush",
        "stubble",
        "beard",
        "black shirt",
    ):
        if phrase in low:
            words.update(w for w in phrase.split() if len(w) >= 4)
    return words


def protagonist_embedded_in_scene(scene: str, protagonist_en: str, *, min_hits: int = 2) -> bool:
    """True si la escena ancla rasgos concretos del protagonista (no solo 'young man')."""
    prot = (protagonist_en or "").strip()
    if not prot:
        return True
    s = (scene or "").strip()
    if not s:
        return False
    if prot.lower()[:35] in s.lower():
        return True
    m = re.search(r"\bsubject:\s*(.+)$", s, re.I | re.DOTALL)
    if m and protagonist_embedded_in_scene(m.group(1), prot, min_hits=min_hits):
        return True
    anchors = protagonist_anchor_words(prot)
    if len(anchors) < 2:
        return len(_content_words(prot, min_len=5)) <= 1
    scene_w = _content_words(s, min_len=4)
    hits = anchors & scene_w
    for aw in list(anchors)[:15]:
        if any(aw in sw or sw in aw for sw in scene_w if len(sw) >= 4):
            hits.add(aw)
    return len(hits) >= min_hits


def protagonist_design_complete(
    scene: str,
    protagonist_en: str,
    *,
    wardrobe_en: str | None = None,
) -> bool:
    """Cara + pelo/camiseta/sin gorro — evita falsos positivos con 'on his face'."""
    if scene_has_wardrobe_lock(scene):
        return True
    prot = (protagonist_en or "").strip()
    if prot and protagonist_embedded_in_scene(scene, prot, min_hits=2):
        return scene_has_wardrobe_lock(scene)
    _ = wardrobe_en
    return False


def _content_words(text: str, *, min_len: int = 4) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if len(w) >= min_len and w not in _STOPWORDS}


def infer_narration_visual_strategy(narration: str, director_note: str | None = None) -> str:
    """Estrategia solo desde narración (ignora nota B-roll)."""
    _ = director_note
    n = (narration or "").strip()
    if not n:
        return "single_moment"

    if re.search(
        r"\bdifference between\b|\bvs\.?\b|\bversus\b|one is .{5,40} the other is|"
        r"un comportamiento|una condición|behavior problem|structural condition",
        n,
        re.I | re.DOTALL,
    ):
        return "contrast_split"

    sentences = [s.strip() for s in re.split(r"[.!?]+", n) if s.strip()]
    short_parallel = len(sentences) >= 3 and all(len(s.split()) <= 14 for s in sentences[:4])
    list_markers = bool(
        re.search(
            r"\b(you have|tienes|you know exactly|the influencer|the article)\b",
            n,
            re.I,
        )
    )
    if short_parallel or list_markers:
        return "montage"
    if re.search(r"\b(like|as if|metaphor|imagina|como si)\b", n, re.I):
        return "metaphor"
    if len(sentences) == 1 and len(n.split()) < 25:
        return "single_moment"
    return "narrative_beat"


def strategy_instruction(strategy: str) -> str:
    instructions = {
        "contrast_split": (
            "NARRATION STRATEGY — CONTRAST / DUAL IDEA: The voiceover contrasts two concepts "
            "(e.g. irresponsible vs excluded, behavior vs structure). Show BOTH sides in ONE 16:9 frame: "
            "split screen, diptych, or left/right juxtaposition with clear visual opposition. "
            "Do NOT default to books, desks, or budget apps unless the narration names them."
        ),
        "montage": (
            "NARRATION STRATEGY — MONTAGE: Multiple beats in the voiceover. "
            "ONE 16:9 frame synthesizing ALL beats named in NARRATION (vignettes left-to-right or layered). "
            "Never illustrate only the last sentence. "
            "The protagonist must use a DIFFERENT physical action than the previous block "
            "(mark paper, walk, flip document, scroll phone, point at prop — vary each time). "
            "Other people (influencer, couple) appear only in screens, photos, or small vignettes — "
            "the PROTAGONIST keeps the same hair, black shirt, bare head (no hat/cap), and cartoon face."
        ),
        "metaphor": (
            "NARRATION STRATEGY — METAPHOR: One symbolic visual carrying the idea."
        ),
        "single_moment": (
            "NARRATION STRATEGY — SINGLE MOMENT: One action beat; tight framing."
        ),
        "narrative_beat": (
            "NARRATION STRATEGY — STORY BEAT: Concrete props and people FROM THE NARRATION. "
            "Avoid generic desk + phone + budget app unless narration says budgeting."
        ),
    }
    return instructions.get(strategy, instructions["narrative_beat"])


def scene_echoes_director_note(
    scene: str,
    director_note: str | None,
    narration: str = "",
    *,
    threshold: float = 0.42,
) -> bool:
    """True solo si la escena sigue la nota B-roll sin anclarse en la narración."""
    note = (director_note or "").strip().lower()
    if not note or len(note) < 10:
        return False
    note_words = _content_words(note, min_len=3)
    if len(note_words) < 3:
        return False
    scene_core = scene_creative_core(scene)
    scene_words = set(re.findall(r"[a-z0-9']+", scene_core.lower()))
    overlap = len(note_words & scene_words) / len(note_words)
    if overlap < threshold:
        return False

    narr = (narration or "").strip()
    if not narr:
        return True

    narr_terms = _narration_terms(narr)
    scene_terms = _narration_terms(scene_core)
    if len(_terms_overlap(narr_terms, scene_terms)) >= 2:
        return False

    ok, _ = narration_coverage(scene_core, narr)
    return not ok


def _stem_variants(word: str) -> set[str]:
    """Variantes simples (plural, -ing) para comparar narración ↔ escena."""
    w = word.lower().strip()
    if len(w) < 3:
        return set()
    out = {w}
    if len(w) > 4 and w.endswith("ies"):
        out.add(w[:-3] + "y")
    if len(w) > 4 and w.endswith("ing"):
        base = w[:-3]
        out.add(base)
        if not base.endswith("e"):
            out.add(base + "e")
    if len(w) > 4 and w.endswith("es"):
        out.add(w[:-2])
        out.add(w[:-1])
    if len(w) > 3 and w.endswith("s"):
        out.add(w[:-1])
    return out


def _narration_terms(narration: str) -> set[str]:
    terms: set[str] = set()
    for w in re.findall(r"[a-z0-9']+", (narration or "").lower()):
        if w in _STOPWORDS:
            continue
        if len(w) < 3:
            continue
        terms.update(_stem_variants(w))
    return terms


def _terms_overlap(a: set[str], b: set[str]) -> set[str]:
    hits = a & b
    for x in a:
        if len(x) < 3:
            continue
        for y in b:
            if len(y) < 3:
                continue
            if x == y:
                hits.add(x)
                continue
            if len(x) >= 4 and len(y) >= 4 and (x in y or y in x):
                hits.add(x)
                continue
            if len(x) >= 4 and len(y) >= 4 and x[:4] == y[:4]:
                hits.add(x)
    return hits


def narration_coverage(scene: str, narration: str, *, min_hits: int = 2) -> tuple[bool, str]:
    """La escena debe anclarse en palabras clave de la narración."""
    narr_terms = _narration_terms(narration)
    if len(narr_terms) < 4:
        return True, ""
    scene_terms = _narration_terms(scene)
    hits = _terms_overlap(narr_terms, scene_terms)
    needed = min_hits if len(narr_terms) >= 8 else 1
    if len(hits) >= needed:
        return True, ""
    sample = ", ".join(sorted(t for t in narr_terms if len(t) >= 4)[:6])
    return False, (
        f"Poca conexión con la narración (usa conceptos del voiceover, no solo la nota B-roll)."
        + (f" Ancla: {sample}." if sample else "")
    )


def scene_creative_core(scene: str) -> str:
    """Escena sin bloques auto-inyectados (Character lock / Subject) — para deduplicación."""
    text = (scene or "").strip()
    text = re.split(r"\.\s*Character lock:", text, maxsplit=1, flags=re.I)[0].strip()
    text = re.split(r"\.\s*Subject:", text, maxsplit=1, flags=re.I)[0].strip()
    text = re.split(r"\.\s*Protagonist facial expression:", text, maxsplit=1, flags=re.I)[0].strip()
    return text


def scene_has_display_surface(scene: str) -> bool:
    return bool(_DISPLAY_SURFACE_WORDS.search(scene_creative_core(scene)))


def scene_uses_pointer_at_display(scene: str) -> bool:
    core = scene_creative_core(scene)
    low = core.lower()
    if re.search(r"\bat a (large )?(white|black)?board\b", low):
        return True
    if _POINTER_GESTURE_WORDS.search(low) and _DISPLAY_SURFACE_WORDS.search(core):
        return True
    if re.search(r"point(ing)? at (a |the )?(chart|graph|screen|display|number on)", low):
        return True
    if re.search(r"gestur\w+ (toward|towards) (a |the )?(graph|chart|screen|display)", low):
        return True
    return False


def scene_primary_action(scene: str) -> str | None:
    m = _ACTION_VERBS.search(scene_creative_core(scene).lower())
    return m.group(1).lower() if m else None


def scene_gesture_signature(scene: str) -> str:
    low = scene_creative_core(scene).lower()
    if scene_uses_pointer_at_display(scene):
        return "pointer_display"
    if re.search(r"\b(scroll|scrolling|swipe|swiping)\b", low) and re.search(
        r"\b(phone|feed|app|tablet)\b", low
    ):
        return "scroll_device"
    if re.search(
        r"\b(flip|flipping|unfold|mark|marking|underline|stamp|read|reading|annotate)\b", low
    ) and re.search(r"\b(paper|document|form|page|application|printout|folder)\b", low):
        return "document_handle"
    if re.search(r"\b(walk|walking|step|stepping|cross|crossing|stride|mid-step)\b", low):
        return "walk_traverse"
    if any(m in low for m in _HANDS_FRAMING_MARKERS[:5]):
        return "hands_only"
    if _ACTION_VERBS.search(low):
        m = _ACTION_VERBS.search(low)
        return f"verb:{m.group(1).lower()}" if m else "verb"
    return "none"


def validate_scene_gesture(scene: str, recent_scenes: list[str] | None) -> tuple[bool, str]:
    """No repetir la misma acción/pose que el bloque inmediatamente anterior."""
    recent = [s for s in (recent_scenes or []) if s]
    if not recent:
        return True, ""

    prev = recent[-1]
    gesture = scene_gesture_signature(scene)
    prev_gesture = scene_gesture_signature(prev)
    pose = scene_pose_signature(scene)
    prev_pose = scene_pose_signature(prev)
    verb = scene_primary_action(scene)
    prev_verb = scene_primary_action(prev)

    if gesture != "none" and gesture == prev_gesture:
        return False, (
            "Misma acción que el bloque anterior; elige otro gesto "
            "(marcar papel, caminar, scroll, comparar documentos, abrir carpeta…)."
        )

    if pose not in ("other",) and pose == prev_pose:
        return False, (
            "Misma pose que el bloque anterior; cambia encuadre y gesto "
            "(de pie caminando, manos en primer plano, POV, otro ángulo…)."
        )

    if verb and prev_verb and verb == prev_verb:
        return False, (
            f"Verbo '{verb}' repetido respecto al bloque anterior; "
            "usa una acción distinta aunque la narración sea similar."
        )

    return True, ""


def gesture_retry_hint(attempt: int, recent_scenes: list[str] | None = None) -> str:
    alt = _GESTURE_RETRY_ALTERNATIVES[attempt % len(_GESTURE_RETRY_ALTERNATIVES)]
    prev_note = ""
    if recent_scenes:
        prev = recent_scenes[-1]
        pg = scene_gesture_signature(prev)
        pv = scene_primary_action(prev)
        bits = [b for b in (pg, f"verb:{pv}" if pv else "") if b and b != "none"]
        if bits:
            prev_note = f" Previous block used {', '.join(bits)} — must use a DIFFERENT action now."
    return (
        f"REQUIRED: protagonist doing {alt}.{prev_note} "
        "Use an -ing verb in the first sentence. Narration props (screens, whiteboards, papers) are OK."
    )


def scene_has_physical_action(scene: str) -> bool:
    low = scene_creative_core(scene).lower()
    if _ACTION_VERBS.search(low):
        return True
    if any(m in low for m in _HANDS_FRAMING_MARKERS):
        return True
    return any(m in low for m in _IMPLICIT_ACTION_MARKERS)


def scene_pose_signature(scene: str) -> str:
    low = scene_creative_core(scene).lower()
    if re.search(r"hand(s)? (on|to|against) (his |her )?chin|chin rest|thinker pose", low):
        return "chin_thinker"
    if any(m in low for m in _HANDS_FRAMING_MARKERS[:5]):
        return "hands_pov"
    if _ACTION_VERBS.search(low):
        m = _ACTION_VERBS.search(low)
        return f"action:{m.group(1).lower()}" if m else "action"
    if "stands in the center" in low or (
        "surrounded by vignettes" in low and re.search(r"\bstand(s|ing)?\b", low)
    ):
        return "center_observer"
    if re.search(r"\bsits at\b|\bseated at\b", low):
        if re.search(r"thoughtful|contemplat|gazing reflect|pensive", low):
            return "seated_passive"
        return "seated"
    if re.search(r"\b(thoughtful|contemplat|pensive|pondering)\b", low):
        return "passive_gaze"
    if re.search(r"\bgazing\b", low) and re.search(r"thoughtful|contemplat|reflect", low):
        return "passive_gaze"
    if re.search(r"\bstands\b|\bstanding\b", low):
        return "standing_passive"
    return "other"


def validate_scene_pose(scene: str, recent_scenes: list[str] | None) -> tuple[bool, str]:
    """Postura activa y no repetir plantillas pasivas (pensador, centro+viñetas, etc.)."""
    core = scene_creative_core(scene)
    low = core.lower()
    sig = scene_pose_signature(core)
    has_action = scene_has_physical_action(core)
    banned = sum(1 for p in _BANNED_POSE_PHRASES if p in low)
    passive_mood = sum(1 for p in _PASSIVE_MOOD_WORDS if p in low)

    if banned >= 1 and not has_action:
        return False, (
            "Postura prohibida (p. ej. mano en barbilla o observador pasivo); "
            "usa una acción concreta del voiceover."
        )

    if not has_action:
        too_static = (
            sig in _STRICT_PASSIVE_SIGNATURES
            or (sig == "passive_gaze" and passive_mood >= 1)
            or (sig == "seated_passive")
            or (sig == "standing_passive" and passive_mood >= 1)
            or passive_mood >= 3
        )
        if too_static:
            return False, (
                "Protagonista demasiado estático; describe un verbo físico "
                "(señalar, pasar página, caminar, comparar documentos…)."
            )

    recent = recent_scenes or []
    repeat_sigs = _STRICT_PASSIVE_SIGNATURES | frozenset({"passive_gaze", "seated_passive"})
    if sig in repeat_sigs:
        for prev in recent[-3:]:
            if scene_pose_signature(prev) == sig:
                return False, (
                    "Postura repetida respecto a bloques recientes; "
                    "cambia pose y encuadre (manos, perfil, caminando, POV…)."
                )

    return True, ""


def scene_generic_language_too_vague(scene: str, narration: str) -> bool:
    """Rechaza prosa vacía; permite luz/atmosfera si la escena ancla objetos de la narración."""
    core = scene_creative_core(scene).lower()
    strict = sum(1 for p in _STRICT_GENERIC_FILLER if p in core)
    soft = sum(1 for p in _SOFT_GENERIC_FILLER if p in core)
    if strict == 0 and soft < 3:
        return False

    narr_terms = _narration_terms(narration)
    scene_terms = _narration_terms(scene_creative_core(scene))
    anchor_hits = len(_terms_overlap(narr_terms, scene_terms))
    if anchor_hits >= 3:
        return False

    if strict >= 2:
        return True
    if strict >= 1 and soft >= 2:
        return True
    return soft >= 3


def scene_too_similar_to_recent(scene: str, recent_scenes: list[str], *, threshold: float = 0.38) -> tuple[bool, str]:
    if not recent_scenes:
        return False, ""
    scene_w = _content_words(scene_creative_core(scene))
    if len(scene_w) < 8:
        return False, ""
    for prev in recent_scenes[-4:]:
        prev_w = _content_words(scene_creative_core(prev))
        if len(prev_w) < 8:
            continue
        overlap = len(scene_w & prev_w) / min(len(scene_w), len(prev_w))
        if overlap >= threshold:
            return True, "Escena demasiado parecida a un bloque anterior; cambia lugar, objetos y encuadre."
    return False, ""


def scene_uses_overused_stock(scene: str, recent_scenes: list[str]) -> tuple[bool, str]:
    low = scene_creative_core(scene).lower()
    hits = [p for p in _OVERUSED_STOCK if p in low]
    if not hits:
        return False, ""
    for prev in recent_scenes[-3:]:
        pl = scene_creative_core(prev).lower()
        if any(h in pl for h in hits):
            return True, f"Repetición de escena genérica ({hits[0]}); elige otra metáfora visual."
    return False, ""


def extract_scene_from_full_prompt(full: str, base_style: str) -> str:
    """Quita estilo/avoid/spec de un prompt legacy para obtener solo escena."""
    text = (full or "").strip()
    style = (base_style or "").strip()
    if style and text.lower().startswith(style.lower()[:40]):
        text = text[len(style) :].lstrip(" .")
    text = re.split(r"\bAvoid:", text, maxsplit=1)[0].strip()
    text = re.sub(r",?\s*16:9.*$", "", text, flags=re.I).strip()
    text = re.sub(r",?\s*2K output\.?$", "", text, flags=re.I).strip()
    return text.rstrip(".")


def assemble_nano_banana_prompt(
    *,
    base_style_en: str,
    scene_prompt_en: str,
    avoid_en: str,
    aspect_ratio: str = "16:9",
    output_spec: str = "2K output",
    include_style: bool = True,
    include_avoid: bool = True,
    include_spec: bool = True,
) -> str:
    style = (base_style_en or "").strip().rstrip(".")
    scene = (scene_prompt_en or "").strip().rstrip(".")
    avoid = (avoid_en or "").strip().rstrip(".")

    parts: list[str] = []
    if include_style and style:
        parts.append(style)
    if scene:
        parts.append(scene)
    if include_avoid and avoid:
        parts.append(f"Avoid: {avoid}")
    spec_bits = [s for s in (aspect_ratio, output_spec) if s and include_spec]
    if spec_bits:
        parts.append(", ".join(spec_bits))

    out = ". ".join(parts)
    if not out.endswith("."):
        out += "."
    return re.sub(r"\.\s*\.", ".", out).strip()


def compose_gemini_queue_prompt(
    *,
    scene_prompt_en: str,
    full_prompt: str,
    settings: dict[str, Any],
    first_in_run: bool,
    previous_scene_summary: str | None = None,
) -> str:
    base_style = str(settings.get("base_style_en") or "")
    scene_raw = (scene_prompt_en or "").strip()
    if not scene_raw and full_prompt:
        scene_raw = extract_scene_from_full_prompt(full_prompt, base_style)
    if not scene_raw:
        return (full_prompt or "").strip()

    prot = str(settings.get("protagonist_en") or "").strip()
    wardrobe = protagonist_wardrobe_from_settings(settings)
    scene = enrich_scene_prompt(
        scene_raw,
        director_note=None,
        protagonist_en=prot,
        wardrobe_en=wardrobe,
    ).rstrip(".")
    avoid = effective_avoid_en(settings)
    design_lock = character_design_lock(settings)

    if first_in_run:
        return assemble_nano_banana_prompt(
            base_style_en=base_style,
            scene_prompt_en=scene,
            avoid_en=avoid,
            aspect_ratio=str(settings.get("aspect_ratio") or "16:9"),
            output_spec=str(settings.get("output_spec") or "2K output"),
        )

    spec = ", ".join(
        s for s in (str(settings.get("aspect_ratio") or "16:9"), str(settings.get("output_spec") or "2K output")) if s
    )
    avoid_short = avoid[:160]
    action_rules = protagonist_action_rules_from_settings(settings)
    parts: list[str] = [f"Protagonist (identical every frame): {design_lock[:320].rstrip('.')}"]
    from videomaker.scene_editor.visual_pipeline_rules import resolved_gemini_continuity_prefix

    parts.append(resolved_gemini_continuity_prefix(settings).rstrip("."))
    if previous_scene_summary:
        parts.append(f"Previous image showed: {previous_scene_summary[:180]}. Must look different.")
    if action_rules:
        compact = " ".join(action_rules.split())[:240]
        parts.append(f"Action & pose rules: {compact}")
    parts.append(scene)
    if avoid_short:
        parts.append(f"Avoid: {avoid_short}")
    if spec:
        parts.append(spec)
    out = ". ".join(p.rstrip(".") for p in parts if p)
    return out + ("." if not out.endswith(".") else "")


def enrich_scene_prompt(
    scene: str,
    *,
    director_note: str | None,
    protagonist_en: str | None,
    wardrobe_en: str | None = None,
) -> str:
    _ = director_note
    base = (scene or "").strip().rstrip(".")
    prot = (protagonist_en or "").strip()
    wardrobe = (wardrobe_en or _DEFAULT_PROTAGONIST_WARDROBE).strip()
    if not base:
        return ""
    if protagonist_design_complete(base, prot, wardrobe_en=wardrobe):
        return base + ("." if not base.endswith(".") else "")

    lock_bits: list[str] = []
    if prot and not protagonist_embedded_in_scene(base, prot, min_hits=2):
        lock_bits.append(prot[:200].rstrip("."))
    if not scene_has_wardrobe_lock(base):
        lock_bits.append(wardrobe.rstrip("."))
    if lock_bits:
        return f"{base}. Character lock: {'. '.join(lock_bits)}."
    return base + ("." if not base.endswith(".") else "")


def validate_scene_prompt(
    scene: str,
    *,
    narration: str = "",
    director_note: str | None = None,
    recent_scenes: list[str] | None = None,
    protagonist_en: str | None = None,
    wardrobe_en: str | None = None,
) -> tuple[bool, str]:
    s = (scene or "").strip()
    if len(s) < _MIN_SCENE_LEN:
        return False, f"Escena demasiado corta ({len(s)} chars)."
    if len(s.split()) < _MIN_SCENE_WORDS:
        return False, f"Escena demasiado breve (mín. {_MIN_SCENE_WORDS} palabras)."

    if scene_generic_language_too_vague(s, narration):
        return False, "Demasiado lenguaje genérico; usa objetos concretos de la narración."

    if scene_echoes_director_note(s, director_note, narration):
        return False, "La escena copia la nota B-roll; traduce la NARRACIÓN."

    prot = (protagonist_en or "").strip()
    wardrobe = (wardrobe_en or _DEFAULT_PROTAGONIST_WARDROBE).strip()
    if prot and not protagonist_design_complete(s, prot, wardrobe_en=wardrobe):
        return False, (
            "Falta diseño completo del protagonista (cara + pelo + camiseta negra + sin gorro). "
            "No basta con 'young man' o 'on his face'."
        )

    ok, msg = narration_coverage(s, narration)
    if not ok:
        return False, msg

    recent = recent_scenes or []
    dup, msg = scene_too_similar_to_recent(s, recent)
    if dup:
        return False, msg

    stock, msg = scene_uses_overused_stock(s, recent)
    if stock:
        return False, msg

    pose_ok, pose_msg = validate_scene_pose(s, recent)
    if not pose_ok:
        return False, pose_msg

    gesture_ok, gesture_msg = validate_scene_gesture(s, recent)
    if not gesture_ok:
        return False, gesture_msg

    return True, ""


def validate_full_prompt(prompt: str, *, base_style: str) -> tuple[bool, str]:
    p = (prompt or "").strip()
    if len(p) < _MIN_FULL_LEN:
        return False, f"Prompt final demasiado corto ({len(p)} chars)."
    combined = f"{base_style} {p}"
    if _has_cinematic_anchors(combined):
        return True, ""
    if len(p) >= 200:
        return True, ""
    if _is_stock_footage_prompt(p) and not _has_cinematic_anchors(combined):
        return False, "Falta especificidad visual."
    return True, ""


def settings_block(settings: dict[str, Any]) -> str:
    wardrobe = protagonist_wardrobe_from_settings(settings)
    action_rules = protagonist_action_rules_from_settings(settings)
    expr_block = expressions_planner_block(expressions_catalog_from_settings(settings))
    return (
        f"BASE STYLE (added automatically — never repeat in scene_prompt_en):\n"
        f"{settings.get('base_style_en', '')}\n\n"
        f"PROTAGONIST FACE (same every block):\n{settings.get('protagonist_en', '')}\n\n"
        f"PROTAGONIST WARDROBE (always — bare head, never hat/cap/hood):\n{wardrobe}\n\n"
        f"{expr_block}\n\n"
        f"PROTAGONIST ACTION & POSE (validate every block — also sent to Gemini queue):\n"
        f"{action_rules}\n\n"
        f"AVOID (added automatically):\n{effective_avoid_en(settings)}"
    )
