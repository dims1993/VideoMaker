"""
Composición de user_instructions del catálogo Prompt (modelo base + narrativa).

Modelo canónico (sin duplicar en BD):
- params_json.output_structure — plantilla fija OUTLINE/GUIÓN/B-ROLL + placeholders {{TEMA}}, etc.
- user_instructions — solo narrativa del canal (inferida de transcripts).
- user_instructions_merged — NO se persiste; se calcula en runtime al generar el guion.
- session_placeholders — NO se persiste; valores de la sesión Create (keywords, minutos, idioma).
"""

from __future__ import annotations

import re
from typing import Any

OUTPUT_STRUCTURE_HEADER = "## Estructura de salida del guion (pipeline)"

EDITORIAL_PRIORITY_HEADER_EN = "## Priority order (when instructions conflict)"
EDITORIAL_PRIORITY_HEADER_ES = "## Orden de prioridad (si las instrucciones chocan)"

EDITORIAL_PRIORITY_BLOCK_EN = f"""{EDITORIAL_PRIORITY_HEADER_EN}
Resolve conflicts strictly top → bottom. Lower tiers yield.

1. **Emotional clarity** — one dominant feeling per beat; no muddy “intellectual stack”.
2. **Narrative momentum** — each block escalates stakes, curiosity, or consequence; cut digressions.
3. **Human relatability** — concrete life scenes, identity, social stakes; not lecture tone.
4. **Data precision** — numbers and sources only where they sharpen emotion or stakes.
5. **Philosophical reflection** — sparing; never at the cost of items 1–3.

## Anti editorial bloat
- Do NOT sound self-aware of being a “YouTube script”. Avoid repeated meta-hooks and skepticism theater.
- Banned as repeated crutches (max once per script, preferably zero): “here’s the thing…”, “and I know what you’re thinking…”, “nobody tells you this…”, and close variants in any language.
- If any rule below fights items 1–3, **ignore that rule** for this script.
- Prefer fewer, sharper behavioral rules over stacking many competing “IMPORTANT” layers."""

EDITORIAL_PRIORITY_BLOCK_ES = f"""{EDITORIAL_PRIORITY_HEADER_ES}
Resuelve conflictos estrictamente de arriba abajo. Lo de abajo cede.

1. **Claridad emocional** — un sentimiento dominante por beat; sin “pila intelectual” confusa.
2. **Impulso narrativo** — cada bloque sube stakes, curiosidad o consecuencia; corta digresiones.
3. **Relatabilidad humana** — escenas de vida concretas, identidad, presión social; no tono de clase magistral.
4. **Precisión de datos** — cifras y fuentes solo donde afilen emoción o stakes.
5. **Reflexión filosófica** — con moderación; nunca a costa de los puntos 1–3.

## Anti-hinchazón editorial
- No suenes consciente de ser un “guion de YouTube”. Evita meta-ganchos repetidos y teatro de escepticismo.
- Prohibido como muletillas repetidas (máx. 1 vez en todo el guion, mejor cero): “lo que nadie te cuenta…”, “y sé lo que estás pensando…”, “aquí va la cosa…”, y variantes cercanas.
- Si una regla de abajo choca con los puntos 1–3, **ignórala** en este guion.
- Prefiere pocas reglas conductuales nítidas a muchas capas “IMPORTANT” que compiten entre sí."""

RETENTION_DISCIPLINE_HEADER_EN = "## Retention discipline (mandatory)"
RETENTION_DISCIPLINE_HEADER_ES = "## Disciplina de retención (obligatorio)"

RETENTION_DISCIPLINE_BLOCK_EN = f"""{RETENTION_DISCIPLINE_HEADER_EN}
Keep the script moving. Depth, nuance, and evidence do **not** justify long paragraphs or stacked proof.

**Organic retention (not a metronome):** movement should come from emotion and story, not from a timer.
- Across the script, aim for **roughly one meaningful shift every ~20–40s on average** — but **skip beats** when momentum is already strong.
- Shifts can be: new tension, visual contrast, one-sentence fact, emotional turn, or narrative reveal.
- **Interrupts must feel earned**, not algorithmically scheduled. Avoid hyper-optimized, manipulative pacing.

**Anti-density rules** (override channel habits that push essay mode):
- One idea per beat; cut before a second layer of explanation.
- Max **one** data point or citation per shift — no evidence stacking.
- If it sounds like a lecture (nuance piles, disclaimers, philosophy runs), **trim** and return to a concrete scene.
- Match target duration ({{{{DURACION_MINUTOS}}}} min): do not pad word count.
- Planning/diagnosis belongs in **Editorial Analyzer** (separate step) — not in Script Writer output."""

RETENTION_DISCIPLINE_BLOCK_ES = f"""{RETENTION_DISCIPLINE_HEADER_ES}
Mantén el guion en movimiento. Profundidad, matices y pruebas **no** justifican párrafos largos ni datos apilados.

**Retención orgánica (no metrónomo):** el movimiento debe venir de emoción e historia, no de un reloj.
- En el conjunto del guion, apunta a **~un giro significativo cada 20–40s de media** — pero **omite beats** si el impulso ya es fuerte.
- Los giros pueden ser: tensión, contraste visual, dato en una frase, giro emocional o revelación narrativa.
- Los **interrupts deben sentirse ganados**, no programados algorítmicamente. Evita pacing hiperoptimizado o manipulador.

**Reglas anti-densidad** (priman sobre hábitos del canal que empujan modo ensayo):
- Una idea por beat; corta antes de una segunda capa de explicación.
- Máximo **un** dato o cita por giro — sin “evidence stacking”.
- Si suena a clase magistral (matices en cadena, disclaimers, filosofía seguida), **recorta** y vuelve a escena concreta.
- Ajusta a la duración objetivo ({{{{DURACION_MINUTOS}}}} min): no hinches palabras.
- Planificación/diagnóstico va en **Editorial Analyzer** (paso aparte) — no en la salida del Script Writer."""

VISUAL_CINEMA_HEADER_EN = "## Write visually (cinema, not essay)"
VISUAL_CINEMA_HEADER_ES = "## Escribe en visual (cine, no ensayo)"

VISUAL_CINEMA_BLOCK_EN = f"""{VISUAL_CINEMA_HEADER_EN}
YouTube is **edited cinema** (voice + picture + cut rhythm), not a written essay.

**Write visually.** Before you explain, picture the shot:
- Every **OUTLINE** section line must imply **images, movement, contrast, or cinematic progression** (e.g. wide→close, still→motion, warm→cold, order→chaos).
- Every **[CATEGORIA]** block must open on something **filmable** (subject + action + light/mood) within the first 1–2 spoken sentences.
- If a paragraph cannot be pictured in one glance on a timeline, **rewrite it as a scene** (object, gesture, ritual, place, time of day).

**Director mindset**
- Abstract idea → concrete situation: who, where, what they touch, what changes on screen.
- Use **visual contrast** as meaning (empty fridge vs delivery notification, calm face vs shaking hand).
- At most **1–2 motifs** in the whole video; do not symbol-stack every beat.
- Spoken lines should **invite a cut**; place [B-ROLL: …] where the image must change (see pipeline rules below).

**Mundane realism balance (anti trailer tone)**
- Not every emotional moment needs a metaphor. Prefer boring, specific reality: spreadsheet on a cracked phone, fluorescent office, grocery receipt, thumb on “pay”.
- Avoid over-symbolic writing, aestheticized suffering, and moody trailer voice unless the channel truly demands it.

**Essay test (fail = rewrite)**
- Reads well on paper but not on a timeline → too essay; add movement, object, or contrast.
- Explains a concept without a visible anchor → replace with show-then-tell in one beat."""

VISUAL_CINEMA_BLOCK_ES = f"""{VISUAL_CINEMA_HEADER_ES}
YouTube es **cine editado** (voz + imagen + ritmo de corte), no un ensayo escrito.

**Escribe en visual.** Antes de explicar, imagina el plano:
- Cada línea del **OUTLINE** debe implicar **imágenes, movimiento, contraste o progresión cinematográfica** (ej. general→primer plano, quieto→movimiento, cálido→frío, orden→caos).
- Cada bloque **[CATEGORIA]** debe abrir en algo **filmable** (sujeto + acción + luz/atmósfera) en las primeras 1–2 frases habladas.
- Si un párrafo no se puede ver de un vistazo en una línea de tiempo, **reescríbelo como escena** (objeto, gesto, ritual, lugar, hora del día).

**Mentalidad de director**
- Idea abstracta → situación concreta: quién, dónde, qué toca, qué cambia en pantalla.
- Usa **contraste visual** como significado (nevera vacía vs notificación de gasto, cara calmada vs mano temblando).
- Como máximo **1–2 motivos** en todo el vídeo; no apiles símbolos en cada beat.
- Las frases habladas deben **pedir un corte**; coloca [B-ROLL: …] donde la imagen debe cambiar (ver reglas de pipeline abajo).

**Equilibrio realismo mundano (anti trailer)**
- No todo momento emocional necesita metáfora. Prefiere realidad aburrida y específica: Excel en pantalla rota, oficina fluorescente, ticket del súper, pulgar en “pagar”.
- Evita sobre-simbolismo, sufrimiento estetizado y voz de tráiler melancólico salvo que el canal lo pida de verdad.

**Test ensayo (si falla, reescribe)**
- Se lee bien en papel pero no en timeline → demasiado ensayo; añade movimiento, objeto o contraste.
- Explica un concepto sin ancla visible → sustituye por mostrar-y-luego-decir en un solo beat."""

PATTERN_INTERRUPT_HEADER_EN = "## Pattern interrupt engineering (mandatory)"
PATTERN_INTERRUPT_HEADER_ES = "## Ingeniería de pattern interrupt (obligatorio)"

PATTERN_INTERRUPT_BLOCK_EN = f"""{PATTERN_INTERRUPT_HEADER_EN}
Modern YouTube needs **pattern interrupts** — deliberate breaks in explanatory density so the brain resets.

**When explanation stacks** (not on a timer), break density with **at least one** organic interrupt:
- **Emotional pivot** — feeling shifts (control→shame, anger→relief, hope→dread) without announcing it.
- **Provocative reframe** — same fact, opposite moral (“this isn’t discipline — it’s fear with a spreadsheet”).
- **Surprising specificity** — hyper-concrete detail that feels uncanny (“Tuesday, 11:47 p.m., notification you pretend not to see”).
- **Hard cut in tone** — calm → blunt, joke → silence, warm → cold (one sentence, then move on).
- **Rhetorical reversal** — rare; never the “you think X… but actually Y” formula. If used once, earn it with a concrete scene first.

**Rules**
- Interrupts are **content**, not meta-hooks (“here’s the thing…”). Vary wording every time.
- Pair interrupts with a **visual or tonal cut** when possible (supports retention + cinema blocks).
- Do not stack two interrupts back-to-back unless the second is a single sharp line.
- In **OUTLINE**, tag planned interrupts: pivot | reframe | specificity | tone_cut | reversal."""

PATTERN_INTERRUPT_BLOCK_ES = f"""{PATTERN_INTERRUPT_HEADER_ES}
YouTube moderno exige **pattern interrupts** — cortes deliberados en la densidad explicativa para resetear atención.

**Cuando la explicación se apila** (no con reloj), rompe densidad con **al menos un** interrupt orgánico:
- **Pivot emocional** — cambio de sentimiento (control→vergüenza, rabia→alivio, esperanza→miedo) sin anunciarlo.
- **Reencuadre provocador** — mismo hecho, moral opuesta (“no es disciplina — es miedo con Excel”).
- **Especificidad sorprendente** — detalle hiperconcreto incómodo (“martes, 23:47, la notificación que finges no ver”).
- **Corte duro de tono** — calma→seco, broma→silencio, cálido→frío (una frase y sigue).
- **Reversión retórica** — rara; nunca la fórmula “crees que X… pero en realidad Y”. Si aparece una vez, que venga tras una escena concreta.

**Reglas**
- Los interrupts son **contenido**, no muletillas meta (“lo que nadie te cuenta…”). Varía el wording cada vez.
- Combina interrupts con **corte visual o de tono** cuando puedas (complementa retención + cine).
- No encadenes dos interrupts seguidos salvo que el segundo sea una línea seca.
- En el **OUTLINE**, marca interrupts planificados: pivot | reframe | specificity | tone_cut | reversal."""

GROUNDED_REALISM_HEADER_EN = "## Grounded realism (anti pseudo-intellectual cadence)"
GROUNDED_REALISM_HEADER_ES = "## Realismo vivido (anti cadencia pseudo-intelectual)"

GROUNDED_REALISM_BLOCK_EN = f"""{GROUNDED_REALISM_HEADER_EN}
Stacking **philosophical + reflective + systems critique + behavioral economics + dry humor** can make the whole script sound like a **clever essay narrator** — polished, predictable, emotionally distant.

**Counter with lived reality texture** (mandatory across the script):
- **Emotional rawness** — embarrassment, relief, petty envy, quiet panic; say it plainly, not as theory.
- **Spontaneity & unpredictability** — occasional blunt line, unfinished thought, or sideways observation (not performed “relatability”).
- **Sensory detail & grounded realism** — sound, silence, light, temperature, body, objects in hand.

**After every “smart” paragraph**, anchor with **at least one** lived beat:
- a specific **sound** (app ping, elevator ding, card declined tone)
- a **silence** that hurts (after checking the balance, after closing the listing app)
- a **micro-gesture** (thumb hovering send, jaw clench, pretending not to refresh)
- a **place + time** (kitchen at 2 a.m., bus stop in rain, fluorescent break room)

**Level of detail (do not copy verbatim)** — write fresh each time:
- the sound of a real-estate app notification you didn’t mean to trigger
- the silence right after you see your bank account
- the cheap coffee cooling while you do mental math in your head

**Anti–essay narrator test**
- If a line could be a podcast transcript for academics → rewrite with body, object, or sound.
- Dry humor is allowed **only** glued to a concrete moment — never floating as “witty narrator”.
- In **OUTLINE**, note sensory anchors: sound | silence | touch | light | body | object."""

GROUNDED_REALISM_BLOCK_ES = f"""{GROUNDED_REALISM_HEADER_ES}
Apilar **filosófico + reflexivo + crítica de sistemas + economía conductual + humor seco** puede hacer que todo suene a **narrador de ensayo listo** — pulido, predecible, emocionalmente lejano.

**Contrarresta con textura de vida vivida** (obligatorio en todo el guion):
- **Crudeza emocional** — vergüenza, alivio, envidia pequeña, pánico silencioso; dilo claro, no como teoría.
- **Espontaneidad e imprevisibilidad** — línea seca ocasional, pensamiento a medias, observación lateral (no “relatabilidad” actuada).
- **Detalle sensorial y realismo anclado** — sonido, silencio, luz, temperatura, cuerpo, objetos en la mano.

**Tras cada párrafo “inteligente”**, ancla con **al menos un** beat vivido:
- un **sonido** concreto (ping de app, timbre del ascensor, tono de pago rechazado)
- un **silencio** que duele (tras mirar el saldo, tras cerrar la app de pisos)
- un **micro-gesto** (pulgar sobre enviar, mandíbula tensa, fingir que no actualizas)
- un **lugar + hora** (cocina a las 2 a.m., parada bajo la lluvia, office fluorescente)

**Nivel de detalle (no copies literal)** — inventa cada vez:
- el sonido de la notificación de una app de pisos que no querías abrir
- el silencio justo después de ver la cuenta del banco
- el café barato enfriándose mientras haces cuentas en la cabeza

**Test anti-narrador de ensayo**
- Si una frase podría ir en un podcast académico → reescribe con cuerpo, objeto o sonido.
- El humor seco solo **pegado** a un momento concreto — nunca flotando como “narrador ingenioso”.
- En el **OUTLINE**, anota anclas sensoriales: sonido | silencio | tacto | luz | cuerpo | objeto."""

TRUTH_CLAIMS_HEADER_EN = "## Truth claims (how certainty should feel)"
TRUTH_CLAIMS_HEADER_ES = "## Afirmaciones de verdad (cómo debe sonar la certeza)"

TRUTH_CLAIMS_BLOCK_EN = f"""{TRUTH_CLAIMS_HEADER_EN}
Brilliant scripts can still feel **manipulative** if every claim sounds airtight. Protect credibility.

**Never overstate certainty.** You can be provocative without pretending you have a vault key to reality.

**Prefer** (rotate; do not spam one hedge):
- “the incentives suggest…”
- “one reason may be…”
- “the data points toward…”
- “this often shows up when…”
- “a plausible read is…”
- “it tends to…”

**Avoid** (unless quoting a source in the same beat):
- “this proves…” / “science proves…”
- “the truth is…” / “here’s the real truth…”
- “they want…” / “banks want you to…” (mind-reading institutions or people)
- “always / never / everyone / guaranteed”
- causal leaps from correlation in one sentence

**Rules**
- Strong claim → **one** supporting anchor in the **same beat** (number, study name, mechanism, or lived example) — or soften the claim.
- Separate **mechanism** from **moral verdict**: explain incentives first; let the viewer conclude.
- Systems critique is allowed; present it as **interpretation backed by incentives**, not omniscient narration.
- In **OUTLINE**, flag high-stakes claims that need hedging or a source: claim | hedge | source_needed."""

TRUTH_CLAIMS_BLOCK_ES = f"""{TRUTH_CLAIMS_HEADER_ES}
Un guion brillante puede sonar **manipulador** si cada afirmación parece cerrada al cien por cien. Protege la credibilidad.

**Nunca sobredimensiones la certeza.** Puedes ser provocador sin fingir que tienes la llave de la verdad.

**Prefiere** (rota; no abuses de una sola coletilla):
- “los incentivos sugieren…”
- “una razón puede ser…”
- “los datos apuntan a…”
- “esto suele aparecer cuando…”
- “una lectura plausible es…”
- “tiende a…”

**Evita** (salvo cita con fuente en el mismo beat):
- “esto demuestra…” / “la ciencia demuestra…”
- “la verdad es…” / “aquí está la verdad…”
- “ellos quieren…” / “los bancos quieren que…” (leer la mente a instituciones o personas)
- “siempre / nunca / todos / garantizado”
- saltos causales desde correlación en una sola frase

**Reglas**
- Afirmación fuerte → **un** ancla de apoyo en el **mismo beat** (cifra, estudio, mecanismo o ejemplo vivido) — o suaviza la afirmación.
- Separa **mecanismo** de **veredicto moral**: explica incentivos primero; que concluya el espectador.
- La crítica de sistemas está bien; preséntala como **interpretación apoyada en incentivos**, no narración omnisciente.
- En el **OUTLINE**, marca claims de alto riesgo que necesiten matiz o fuente: claim | hedge | source_needed."""

VISUAL_PACING_HEADER_EN = "## Visual pacing architecture (mandatory)"
VISUAL_PACING_HEADER_ES = "## Arquitectura de ritmo visual (obligatorio)"

VISUAL_PACING_BLOCK_EN = f"""{VISUAL_PACING_HEADER_EN}
Alternate **thinking density** with **visual/emotional breathing room**. Never stack dense explanation without a release beat.

**Dense explanation** = mechanisms, data, systems critique, stacked arguments (max ~2–3 sentences or ~20–30s before a release).

**Every dense block must be followed immediately by at least one** (pick one; rotate):
- **Human scene** — someone in a specific place doing something relatable (filmable, sensory).
- **Emotional reflection** — one honest feeling in plain language (not theory); short.
- **Mundane scene** — boring-specific reality (app screen, receipt, office light) — **default** release.
- **Cinematic metaphor** — only when earned; one symbol max, not every beat.
- **Visual simplification** — one plain image in one sentence.

**Pacing rules**
- Do not chain two dense sections back-to-back without a release in between.
- After [CATEGORIA: DATOS] or [CATEGORIA: ARGUMENTO], the **next** beat should default to mundane scene / human moment — not more abstraction or poetic symbols.
- Match B-roll to the release beat when possible (quieter frame after data-heavy lines).
- When writing, mentally pair dense → release (mundane | scene | reflection) — do not output analysis sections."""

VISUAL_PACING_BLOCK_ES = f"""{VISUAL_PACING_HEADER_ES}
Alterna **densidad de explicación** con **espacio visual/emocional**. No encadenes bloques densos sin un beat de alivio.

**Explicación densa** = mecanismos, datos, crítica de sistemas, argumentos apilados (máx. ~2–3 frases o ~20–30s antes de un release).

**Cada bloque denso debe ir seguido de inmediato por al menos uno** (elige uno; rota):
- **Escena humana** — alguien en un lugar concreto haciendo algo reconocible (filmable, sensorial).
- **Reflexión emocional** — un sentimiento honesto en lenguaje llano (no teoría); breve.
- **Escena mundana** — realidad aburrida y específica (pantalla de app, ticket, luz de oficina) — release **por defecto**.
- **Metáfora cinematográfica** — solo si está ganada; un símbolo, no en cada beat.
- **Simplificación visual** — una imagen llana en una frase.

**Reglas de ritmo**
- No encadenes dos secciones densas seguidas sin release entre medias.
- Tras [CATEGORIA: DATOS] o [CATEGORIA: ARGUMENTO], el **siguiente** beat debe ser escena mundana / momento humano — no más abstracción ni símbolos poéticos.
- Alinea B-roll con el beat de release cuando puedas (plano más quieto tras líneas cargadas de datos).
- Al escribir, empareja mentalmente denso → release (mundano | escena | reflexión) — no imprimas secciones de análisis."""

CREATIVE_LOOSENESS_HEADER_EN = "## Creative looseness (meta — read first)"
CREATIVE_LOOSENESS_HEADER_ES = "## Holgura creativa (meta — leer primero)"

CREATIVE_LOOSENESS_BLOCK_EN = f"""{CREATIVE_LOOSENESS_HEADER_EN}
**Naturalness beats optimization.** If following every rule below would sound mechanical, rigid, or “checking boxes”, loosen up.

- Occasional imperfection, asymmetry, and surprise beat procedurally perfect structure.
- Do not sound like you are executing a checklist. The script should feel **spoken**, not assembled.
- When **creative looseness** conflicts with secondary rules (tags density, outline labels, beat cadence), **prefer natural flow** — keep retention and clarity, drop performative structure.
- **Organic retention:** never feel algorithmically scheduled. If the story already moves, do not force an interrupt.
- **Mundane over moody:** a cracked phone with a spreadsheet can carry more truth than a poetic symbol — do not trailer-ize every beat.
- Channel narrative guidelines (below) win on voice; they never override emotional truth or natural speech."""

CREATIVE_LOOSENESS_BLOCK_ES = f"""{CREATIVE_LOOSENESS_HEADER_ES}
**La naturalidad gana a la optimización.** Si cumplir todas las reglas de abajo suena mecánico, rígido o a “casillas marcadas”, afloja.

- La imperfección ocasional, la asimetría y la sorpresa ganan a la estructura perfectamente procedimental.
- No suenes a checklist. El guion debe sentirse **hablado**, no ensamblado.
- Si la **holgura creativa** choca con reglas secundarias (densidad de etiquetas, labels en outline, cadencia de beats), **prioriza flujo natural** — mantén retención y claridad, suelta estructura performativa.
- **Retención orgánica:** nunca suenes a reloj de retención. Si la historia ya avanza sola, no fuerces un corte.
- **Mundano sobre melancólico:** un móvil roto con Excel puede valer más que un símbolo poético — no conviertas cada beat en tráiler.
- Las guías narrativas del canal (abajo) mandan en voz; nunca anulan verdad emocional ni habla natural."""

GOVERNANCE_CORE_HEADER_EN = "## Script governance (compact)"
GOVERNANCE_CORE_HEADER_ES = "## Gobernanza del guion (compacta)"

GOVERNANCE_CORE_BLOCK_EN = f"""{GOVERNANCE_CORE_HEADER_EN}
Single stack — integrate invisibly; do not narrate the rules.

**Priority if rules clash:** (1) emotional clarity (2) momentum (3) relatability (4) data precision (5) sparse philosophy. No meta-hooks (“here’s the thing…”, “nobody tells you this…”).

**Organic retention:** shifts emerge from emotion/story (~one meaningful turn every ~20–40s on average; skip if already moving). Never feel scheduled or manipulative. One idea per beat; honor target duration.

**Cinema not essay:** filmable scenes; [B-ROLL] on cuts. **Mundane > metaphor:** not every beat needs symbols; avoid trailer mood / aestheticized suffering.

**Pattern interrupt (when dense, not scheduled):** pivot | reframe | specificity | tone cut — not formulaic reversals (“you think X… but Y”).

**Grounded realism:** after smart lines — sound | silence | body | object; not clever essay narrator.

**Truth claims:** hedge (“incentives suggest”, “may be”, “points toward”); avoid proves / truth is / mind-reading “they want”; anchor strong claims in the same beat.

**Visual pacing:** dense → mundane scene | human moment | (metaphor only if earned); no back-to-back dense stacks.

**Creation only:** Script Writer outputs OUTLINE + SCRIPT + B-ROLL + KEYWORDS — never editorial analysis."""

GOVERNANCE_CORE_BLOCK_ES = f"""{GOVERNANCE_CORE_HEADER_ES}
Un solo bloque — intégralo sin declararlo; no narres las reglas.

**Prioridad si chocan:** (1) claridad emocional (2) impulso (3) relatabilidad (4) datos precisos (5) filosofía escasa. Sin meta-ganchos (“lo que nadie te cuenta…”, etc.).

**Retención orgánica:** giros desde emoción/historia (~cada 20–40s de media; omite si ya hay impulso). Nunca suene a reloj ni manipulación. Una idea por beat; respeta duración.

**Cine no ensayo:** escenas filmables; [B-ROLL] en cortes. **Mundano > metáfora:** no todo beat necesita símbolos; evita tono tráiler / sufrimiento estetizado.

**Pattern interrupt (cuando hay densidad, no programado):** pivot | reframe | especificidad | corte de tono — sin reversiones formulaicas (“crees que X… pero Y”).

**Realismo vivido:** tras líneas “inteligentes” — sonido | silencio | cuerpo | objeto; no narrador de ensayo listo.

**Verdad:** matiz (“los incentivos sugieren”, “puede ser”, “apunta a”); evita demuestra / la verdad es / “ellos quieren”; ancla claims fuertes en el mismo beat.

**Ritmo visual:** denso → escena mundana | momento humano | (metáfora solo si está ganada); sin dos densos seguidos.

**Solo creación:** Script Writer → OUTLINE + GUIÓN + B-ROLL + KEYWORDS. Diagnóstico → paso Editorial Analyzer."""

# Legacy alias — Script Writer ya no usa análisis editorial en salida.
PIPELINE_OUTPUT_OUTLINE_SPLIT_ES = ""
PIPELINE_OUTPUT_OUTLINE_SPLIT_EN = ""


def governance_stack_block(*, language_code: str = "", locale: str = "") -> str:
    """Meta holgura + gobernanza compacta (inyección canónica)."""
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return f"{CREATIVE_LOOSENESS_BLOCK_ES}\n\n{GOVERNANCE_CORE_BLOCK_ES}"
    if lang.lower() in ("en", "en-us", "en-gb"):
        return f"{CREATIVE_LOOSENESS_BLOCK_EN}\n\n{GOVERNANCE_CORE_BLOCK_EN}"
    return f"{CREATIVE_LOOSENESS_BLOCK_ES}\n\n{GOVERNANCE_CORE_BLOCK_ES}"


# Reglas TTS completas solo en pasos de edición; el Script Writer recibe formato mínimo en system.
PIPELINE_TTS_SPOKEN_RULES = """## TTS / spoken script
- All narrable lines must be in {{LANGUAGE_CODE}}.
- Spell out numbers and symbols for voice-over.
- [B-ROLL: …] and [CATEGORIA: …] tags are not read aloud."""

DEFAULT_PIPELINE_OUTPUT_STRUCTURE = """{{LANGUAGE_CODE}} · ~{{DURACION_MINUTOS}} min
Tema: {{TEMA}}
Ángulo: {{ANGULO}}
Restricciones: {{RESTRICCIONES}}
Fuentes: {{FUENTES}}"""

NARRATIVE_MARKER_EN = "\n\n---\n\n## Channel narrative guidelines\n\n"
NARRATIVE_MARKER_ES = "\n\n---\n\n## Instrucciones narrativas (canal)\n\n"
# Canonical marker for newly composed instructions (keep EN stable).
NARRATIVE_MARKER = NARRATIVE_MARKER_EN

_PLACEHOLDER_RE = re.compile(
    r"\{\{(LANGUAGE_CODE|DURACION_MINUTOS|TEMA|ANGULO|RESTRICCIONES|FUENTES)\}\}"
)


def _format_duration_minutes(minutes: float) -> str:
    if minutes <= 0:
        return "10"
    if abs(minutes - round(minutes)) < 1e-6:
        return str(int(round(minutes)))
    return f"{minutes:g}"


def _normalize_language_code(lang: str) -> str:
    code = (lang or "").strip()
    if not code:
        return "es-ES"
    if "-" in code or "_" in code:
        return code.replace("_", "-")
    low = code.lower()
    if low == "es":
        return "es-ES"
    if low == "en":
        return "en-US"
    return code


def _language_is_spanish(language_code: str) -> bool:
    code = (language_code or "").strip().lower().replace("_", "-")
    return code.startswith("es") or code == "es"


def has_editorial_priority(text: str) -> bool:
    t = text or ""
    return (
        EDITORIAL_PRIORITY_HEADER_EN in t
        or EDITORIAL_PRIORITY_HEADER_ES in t
        or "Anti editorial bloat" in t
        or "Anti-hinchazón editorial" in t
    )


def has_retention_discipline(text: str) -> bool:
    t = text or ""
    return RETENTION_DISCIPLINE_HEADER_EN in t or RETENTION_DISCIPLINE_HEADER_ES in t


def has_visual_cinema(text: str) -> bool:
    t = text or ""
    return VISUAL_CINEMA_HEADER_EN in t or VISUAL_CINEMA_HEADER_ES in t


def has_pattern_interrupt(text: str) -> bool:
    t = text or ""
    return PATTERN_INTERRUPT_HEADER_EN in t or PATTERN_INTERRUPT_HEADER_ES in t


def has_grounded_realism(text: str) -> bool:
    t = text or ""
    return GROUNDED_REALISM_HEADER_EN in t or GROUNDED_REALISM_HEADER_ES in t


def has_truth_claims_discipline(text: str) -> bool:
    t = text or ""
    return TRUTH_CLAIMS_HEADER_EN in t or TRUTH_CLAIMS_HEADER_ES in t


def has_visual_pacing_architecture(text: str) -> bool:
    t = text or ""
    return VISUAL_PACING_HEADER_EN in t or VISUAL_PACING_HEADER_ES in t


def has_creative_looseness(text: str) -> bool:
    t = text or ""
    return CREATIVE_LOOSENESS_HEADER_EN in t or CREATIVE_LOOSENESS_HEADER_ES in t


def has_governance_core(text: str) -> bool:
    t = text or ""
    return GOVERNANCE_CORE_HEADER_EN in t or GOVERNANCE_CORE_HEADER_ES in t


def has_legacy_expanded_governance(text: str) -> bool:
    """Plantillas guardadas con los 7 bloques largos (pre-compactación)."""
    return (
        has_editorial_priority(text)
        and has_retention_discipline(text)
        and has_visual_cinema(text)
        and has_pattern_interrupt(text)
        and has_grounded_realism(text)
        and has_truth_claims_discipline(text)
        and has_visual_pacing_architecture(text)
    )


def has_editorial_governance(text: str) -> bool:
    """Meta holgura + núcleo compacto, o legacy expandido + holgura."""
    return has_creative_looseness(text) and (
        has_governance_core(text) or has_legacy_expanded_governance(text)
    )


def _creative_looseness_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return CREATIVE_LOOSENESS_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return CREATIVE_LOOSENESS_BLOCK_EN
    return CREATIVE_LOOSENESS_BLOCK_ES


def _governance_core_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return GOVERNANCE_CORE_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return GOVERNANCE_CORE_BLOCK_EN
    return GOVERNANCE_CORE_BLOCK_ES


def _visual_pacing_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return VISUAL_PACING_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return VISUAL_PACING_BLOCK_EN
    return VISUAL_PACING_BLOCK_ES


def _truth_claims_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return TRUTH_CLAIMS_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return TRUTH_CLAIMS_BLOCK_EN
    return TRUTH_CLAIMS_BLOCK_ES


def _grounded_realism_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return GROUNDED_REALISM_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return GROUNDED_REALISM_BLOCK_EN
    return GROUNDED_REALISM_BLOCK_ES


def _pattern_interrupt_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return PATTERN_INTERRUPT_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return PATTERN_INTERRUPT_BLOCK_EN
    return PATTERN_INTERRUPT_BLOCK_ES


def _visual_cinema_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return VISUAL_CINEMA_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return VISUAL_CINEMA_BLOCK_EN
    return VISUAL_CINEMA_BLOCK_ES


def _retention_discipline_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return RETENTION_DISCIPLINE_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return RETENTION_DISCIPLINE_BLOCK_EN
    return RETENTION_DISCIPLINE_BLOCK_ES


def _editorial_priority_block(*, language_code: str = "", locale: str = "") -> str:
    lang = (locale or language_code or "").strip()
    if _language_is_spanish(lang):
        return EDITORIAL_PRIORITY_BLOCK_ES
    if lang.lower() in ("en", "en-us", "en-gb"):
        return EDITORIAL_PRIORITY_BLOCK_EN
    return EDITORIAL_PRIORITY_BLOCK_ES


def editorial_governance_block(*, language_code: str = "", locale: str = "") -> str:
    """Inyección canónica: holgura creativa + gobernanza compacta."""
    return governance_stack_block(language_code=language_code, locale=locale)


def ensure_prompt_governance(text: str, *, language_code: str = "", locale: str = "") -> str:
    """Prepends compact governance (no apila 7 bloques largos)."""
    if has_editorial_governance(text):
        return text
    prefix: list[str] = []
    if not has_creative_looseness(text):
        prefix.append(_creative_looseness_block(language_code=language_code, locale=locale))
    if not has_governance_core(text) and not has_legacy_expanded_governance(text):
        prefix.append(_governance_core_block(language_code=language_code, locale=locale))
    if not prefix:
        return text
    return "\n\n".join(prefix + [text]).strip()


def apply_user_instruction_placeholders(
    text: str,
    *,
    language_code: str = "",
    duration_minutes: float = 0,
    tema: str = "",
    angulo: str = "",
    restricciones: str = "",
    fuentes: str = "",
) -> str:
    """Sustituye placeholders del modelo base antes de enviar al Script Writer."""
    empty = "—"
    dm = float(duration_minutes) if duration_minutes and duration_minutes > 0 else 10.0
    values = {
        "LANGUAGE_CODE": _normalize_language_code(language_code),
        "DURACION_MINUTOS": _format_duration_minutes(dm),
        "TEMA": (tema or "").strip() or empty,
        "ANGULO": (angulo or "").strip() or empty,
        "RESTRICCIONES": (restricciones or "").strip() or empty,
        "FUENTES": (fuentes or "").strip() or empty,
    }

    def repl(match: re.Match[str]) -> str:
        return values.get(match.group(1), match.group(0))

    return _PLACEHOLDER_RE.sub(repl, text or "")


def compose_user_instructions(output_structure: str, narrative: str) -> str:
    out = (output_structure or "").strip()
    nar = (narrative or "").strip()
    if out and nar:
        return f"{out}{NARRATIVE_MARKER}{nar}"
    if out:
        return out
    return nar


def split_user_instructions(combined: str) -> tuple[str, str]:
    text = (combined or "").strip()
    if not text:
        return DEFAULT_PIPELINE_OUTPUT_STRUCTURE, ""
    # Backward/forward compatible: accept both ES and EN markers.
    for marker in (NARRATIVE_MARKER_EN, NARRATIVE_MARKER_ES):
        idx = text.find(marker)
        if idx >= 0:
            return text[:idx].strip(), text[idx + len(marker) :].strip()
    if OUTPUT_STRUCTURE_HEADER in text or "{{LANGUAGE_CODE}}" in text:
        return text, ""
    return DEFAULT_PIPELINE_OUTPUT_STRUCTURE, text


def merged_user_instructions_from_row(row: dict[str, Any]) -> str:
    """Texto user completo (modelo base + narrativa), sin sustituir placeholders."""
    pj = row.get("params_json") or {}
    if not isinstance(pj, dict):
        pj = {}
    stored_out = str(pj.get("output_structure") or "").strip()
    stored_narr = str(row.get("user_instructions") or "").strip()
    if stored_out:
        return compose_user_instructions(stored_out, stored_narr)
    out, nar = split_user_instructions(stored_narr)
    return compose_user_instructions(out, nar)


def merged_user_instructions_for_pipeline(
    row: dict[str, Any],
    *,
    language_code: str = "",
    duration_minutes: float = 0,
    tema: str = "",
    angulo: str = "",
    restricciones: str = "",
    fuentes: str = "",
) -> str:
    """Modelo base + narrativa con placeholders de sesión ya sustituidos."""
    combined = merged_user_instructions_from_row(row)
    applied = apply_user_instruction_placeholders(
        combined,
        language_code=language_code,
        duration_minutes=duration_minutes,
        tema=tema,
        angulo=angulo,
        restricciones=restricciones,
        fuentes=fuentes,
    )
    from videomaker.llm.script_writer_voice import prepare_script_writer_user_prompt

    return prepare_script_writer_user_prompt(
        applied, language_code=language_code, locale=language_code
    )
