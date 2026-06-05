import { prepareScriptWriterUserPrompt } from "./scriptWriterVoice";

/**
 * Contrato de instrucciones del paso Prompt:
 * - system_instructions: destilado completo del canal (inferido de transcripts).
 * - user_instructions en BD: solo parte narrativa.
 * - params_json.output_structure: modelo base (manual) con placeholders de sesión.
 * - narrative (user_instructions en API): solo hábitos narrativos del canal.
 * - No guardar user_instructions_merged ni session_placeholders: se derivan al generar el guion.
 */

export const OUTPUT_STRUCTURE_HEADER =
  "## Estructura de salida del guion (pipeline)";
export const OUTPUT_STRUCTURE_HEADER_EN =
  "## Script output structure (pipeline)";
export const OUTPUT_STRUCTURE_HEADER_EN_CAPITALIZED =
  "## Script Output Structure (pipeline)";

export const EDITORIAL_PRIORITY_HEADER_EN =
  "## Priority order (when instructions conflict)";
export const EDITORIAL_PRIORITY_HEADER_ES =
  "## Orden de prioridad (si las instrucciones chocan)";

export const EDITORIAL_PRIORITY_BLOCK_EN = `${EDITORIAL_PRIORITY_HEADER_EN}
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
- Prefer fewer, sharper behavioral rules over stacking many competing “IMPORTANT” layers.`;

export const EDITORIAL_PRIORITY_BLOCK_ES = `${EDITORIAL_PRIORITY_HEADER_ES}
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
- Prefiere pocas reglas conductuales nítidas a muchas capas “IMPORTANT” que compiten entre sí.`;

export const RETENTION_DISCIPLINE_HEADER_EN = "## Retention discipline (mandatory)";
export const RETENTION_DISCIPLINE_HEADER_ES = "## Disciplina de retención (obligatorio)";

export const RETENTION_DISCIPLINE_BLOCK_EN = `${RETENTION_DISCIPLINE_HEADER_EN}
Keep the script moving. Depth, nuance, and evidence do **not** justify long paragraphs or stacked proof.

**Every 20–30 seconds** of narration (~1–3 short spoken sentences), introduce **at least one**:
- new tension or risk
- visual contrast (before/after, object, gesture, light)
- surprising fact in **one sentence** (no source stacking)
- emotional shift (relief, shame, control, hope)
- narrative reveal or “if true, then…” implication

**Anti-density rules** (override channel habits that push essay mode):
- One idea per beat; cut before a second layer of explanation.
- Max **one** data point or citation per retention beat — no evidence stacking.
- If it sounds like a lecture (nuance piles, disclaimers, philosophy runs), **trim** and return to a concrete scene.
- Match target duration ({{DURACION_MINUTOS}} min): do not pad word count; retention beats beat volume.
- In **OUTLINE**, note retention micro-beats every ~20–30s with type: tension | visual | fact | emotion | reveal.`;

export const RETENTION_DISCIPLINE_BLOCK_ES = `${RETENTION_DISCIPLINE_HEADER_ES}
Mantén el guion en movimiento. Profundidad, matices y pruebas **no** justifican párrafos largos ni datos apilados.

**Cada 20–30 segundos** de narración (~1–3 frases cortas habladas), introduce **al menos uno**:
- nueva tensión o riesgo
- contraste visual (antes/después, objeto, gesto, luz)
- dato sorprendente en **una frase** (sin apilar fuentes)
- cambio emocional (alivio, vergüenza, control, esperanza)
- revelación narrativa o implicación (“si esto es verdad, entonces…”)

**Reglas anti-densidad** (priman sobre hábitos del canal que empujan modo ensayo):
- Una idea por beat; corta antes de una segunda capa de explicación.
- Máximo **un** dato o cita por beat de retención — sin “evidence stacking”.
- Si suena a clase magistral (matices en cadena, disclaimers, filosofía seguida), **recorta** y vuelve a escena concreta.
- Ajusta a la duración objetivo ({{DURACION_MINUTOS}} min): no hinches palabras; los beats de retención mandan sobre el volumen.
- En el **OUTLINE**, marca micro-beats de retención cada ~20–30s con tipo: tensión | visual | dato | emoción | revelación.`;

export const VISUAL_CINEMA_HEADER_EN = "## Write visually (cinema, not essay)";
export const VISUAL_CINEMA_HEADER_ES = "## Escribe en visual (cine, no ensayo)";

export const VISUAL_CINEMA_BLOCK_EN = `${VISUAL_CINEMA_HEADER_EN}
YouTube is **edited cinema** (voice + picture + cut rhythm), not a written essay.

**Write visually.** Before you explain, picture the shot:
- Every **OUTLINE** section line must imply **images, movement, contrast, or cinematic progression** (e.g. wide→close, still→motion, warm→cold, order→chaos).
- Every **[CATEGORY]** block must open on something **filmable** (subject + action + light/mood) within the first 1–2 spoken sentences.
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
- Explains a concept without a visible anchor → replace with show-then-tell in one beat.`;

export const VISUAL_CINEMA_BLOCK_ES = `${VISUAL_CINEMA_HEADER_ES}
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
- Explica un concepto sin ancla visible → sustituye por mostrar-y-luego-decir en un solo beat.`;

export const PATTERN_INTERRUPT_HEADER_EN =
  "## Pattern interrupt engineering (mandatory)";
export const PATTERN_INTERRUPT_HEADER_ES =
  "## Ingeniería de pattern interrupt (obligatorio)";

export const PATTERN_INTERRUPT_BLOCK_EN = `${PATTERN_INTERRUPT_HEADER_EN}
Modern YouTube needs **pattern interrupts** — deliberate breaks in explanatory density so the brain resets.

**Interrupt explanatory density regularly** (after ~2–3 explanatory sentences, or whenever a section risks “lecture mode”). Use **at least one** per interrupt:
- **Emotional pivot** — feeling shifts (control→shame, anger→relief, hope→dread) without announcing it.
- **Provocative reframe** — same fact, opposite moral (“this isn’t discipline — it’s fear with a spreadsheet”).
- **Surprising specificity** — hyper-concrete detail that feels uncanny (“Tuesday, 11:47 p.m., notification you pretend not to see”).
- **Hard cut in tone** — calm → blunt, joke → silence, warm → cold (one sentence, then move on).
- **Rhetorical reversal** — rare; never the “you think X… but actually Y” formula. If used once, earn it with a concrete scene first.

**Rules**
- Interrupts are **content**, not meta-hooks (“here’s the thing…”). Vary wording every time.
- Pair interrupts with a **visual or tonal cut** when possible (supports retention + cinema blocks).
- Do not stack two interrupts back-to-back unless the second is a single sharp line.
- In **OUTLINE**, tag planned interrupts: pivot | reframe | specificity | tone_cut | reversal.`;

export const PATTERN_INTERRUPT_BLOCK_ES = `${PATTERN_INTERRUPT_HEADER_ES}
YouTube moderno exige **pattern interrupts** — cortes deliberados en la densidad explicativa para resetear atención.

**Interrumpe la densidad explicativa con regularidad** (tras ~2–3 frases explicativas, o cuando una sección huele a “clase”). Usa **al menos uno** por interrupción:
- **Pivot emocional** — cambio de sentimiento (control→vergüenza, rabia→alivio, esperanza→miedo) sin anunciarlo.
- **Reencuadre provocador** — mismo hecho, moral opuesta (“no es disciplina — es miedo con Excel”).
- **Especificidad sorprendente** — detalle hiperconcreto incómodo (“martes, 23:47, la notificación que finges no ver”).
- **Corte duro de tono** — calma→seco, broma→silencio, cálido→frío (una frase y sigue).
- **Reversión retórica** — rara; nunca la fórmula “crees que X… pero en realidad Y”. Si aparece una vez, que venga tras una escena concreta.

**Reglas**
- Los interrupts son **contenido**, no muletillas meta (“lo que nadie te cuenta…”). Varía el wording cada vez.
- Combina interrupts con **corte visual o de tono** cuando puedas (complementa retención + cine).
- No encadenes dos interrupts seguidos salvo que el segundo sea una línea seca.
- En el **OUTLINE**, marca interrupts planificados: pivot | reframe | specificity | tone_cut | reversal.`;

export const GROUNDED_REALISM_HEADER_EN =
  "## Grounded realism (anti pseudo-intellectual cadence)";
export const GROUNDED_REALISM_HEADER_ES =
  "## Realismo vivido (anti cadencia pseudo-intelectual)";

export const GROUNDED_REALISM_BLOCK_EN = `${GROUNDED_REALISM_HEADER_EN}
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
- In **OUTLINE**, note sensory anchors: sound | silence | touch | light | body | object.`;

export const GROUNDED_REALISM_BLOCK_ES = `${GROUNDED_REALISM_HEADER_ES}
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
- En el **OUTLINE**, anota anclas sensoriales: sonido | silencio | tacto | luz | cuerpo | objeto.`;

export const TRUTH_CLAIMS_HEADER_EN = "## Truth claims (how certainty should feel)";
export const TRUTH_CLAIMS_HEADER_ES =
  "## Afirmaciones de verdad (cómo debe sonar la certeza)";

export const TRUTH_CLAIMS_BLOCK_EN = `${TRUTH_CLAIMS_HEADER_EN}
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
- In **OUTLINE**, flag high-stakes claims that need hedging or a source: claim | hedge | source_needed.`;

export const TRUTH_CLAIMS_BLOCK_ES = `${TRUTH_CLAIMS_HEADER_ES}
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
- En el **OUTLINE**, marca claims de alto riesgo que necesiten matiz o fuente: claim | hedge | source_needed.`;

export const VISUAL_PACING_HEADER_EN = "## Visual pacing architecture (mandatory)";
export const VISUAL_PACING_HEADER_ES =
  "## Arquitectura de ritmo visual (obligatorio)";

export const VISUAL_PACING_BLOCK_EN = `${VISUAL_PACING_HEADER_EN}
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
- After [CATEGORY: DATA] or [CATEGORY: ARGUMENT], the **next** beat should default to mundane scene / human moment — not more abstraction or poetic symbols.
- Match B-roll to the release beat when possible (quieter frame after data-heavy lines).
- In the **SCRIPT**, follow each dense block with a release beat (mundane | scene | reflection | metaphor if earned).`;

export const VISUAL_PACING_BLOCK_ES = `${VISUAL_PACING_HEADER_ES}
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
- En el **GUIÓN**, tras cada bloque denso incluye un beat de release (mundano | escena | reflexión | metáfora si está ganada).`;

export const CREATIVE_LOOSENESS_HEADER_EN = "## Creative looseness (meta — read first)";
export const CREATIVE_LOOSENESS_HEADER_ES =
  "## Holgura creativa (meta — leer primero)";

export const CREATIVE_LOOSENESS_BLOCK_EN = `${CREATIVE_LOOSENESS_HEADER_EN}
**Naturalness beats optimization.** If following every rule below would sound mechanical, rigid, or “checking boxes”, loosen up.

- Occasional imperfection, asymmetry, and surprise beat procedurally perfect structure.
- Do not sound like you are executing a checklist. The script should feel **spoken**, not assembled.
- When **creative looseness** conflicts with secondary rules (tags density, outline labels, beat cadence), **prefer natural flow** — keep retention and clarity, drop performative structure.
- **Organic retention:** never feel algorithmically scheduled. If the story already moves, do not force an interrupt.
- **Mundane over moody:** a cracked phone with a spreadsheet can carry more truth than a poetic symbol — do not trailer-ize every beat.
- Channel narrative guidelines (below) win on voice; they never override emotional truth or natural speech.`;

export const CREATIVE_LOOSENESS_BLOCK_ES = `${CREATIVE_LOOSENESS_HEADER_ES}
**La naturalidad gana a la optimización.** Si cumplir todas las reglas de abajo suena mecánico, rígido o a “casillas marcadas”, afloja.

- La imperfección ocasional, la asimetría y la sorpresa ganan a la estructura perfectamente procedimental.
- No suenes a checklist. El guion debe sentirse **hablado**, no ensamblado.
- Si la **holgura creativa** choca con reglas secundarias (densidad de etiquetas, labels en outline, cadencia de beats), **prioriza flujo natural** — mantén retención y claridad, suelta estructura performativa.
- **Retención orgánica:** nunca suenes a reloj de retención. Si la historia ya avanza sola, no fuerces un corte.
- **Mundano sobre melancólico:** un móvil roto con Excel puede valer más que un símbolo poético — no conviertas cada beat en tráiler.
- Las guías narrativas del canal (abajo) mandan en voz; nunca anulan verdad emocional ni habla natural.`;

export const GOVERNANCE_CORE_HEADER_EN = "## Script governance (compact)";
export const GOVERNANCE_CORE_HEADER_ES = "## Gobernanza del guion (compacta)";

export const GOVERNANCE_CORE_BLOCK_EN = `${GOVERNANCE_CORE_HEADER_EN}
Single stack — integrate invisibly; do not narrate the rules.

**Priority if rules clash:** (1) emotional clarity (2) momentum (3) relatability (4) data precision (5) sparse philosophy. No meta-hooks (“here’s the thing…”, “nobody tells you this…”).

**Organic retention:** shifts emerge from emotion/story (~one meaningful turn every ~20–40s on average; skip if already moving). Never feel scheduled or manipulative. One idea per beat; honor target duration.

**Cinema not essay:** filmable scenes; [B-ROLL] on cuts. **Mundane > metaphor:** not every beat needs symbols; avoid trailer mood / aestheticized suffering.

**Pattern interrupt (when dense, not scheduled):** pivot | reframe | specificity | tone cut — not formulaic reversals (“you think X… but Y”).

**Grounded realism:** after smart lines — sound | silence | body | object; not clever essay narrator.

**Truth claims:** hedge (“incentives suggest”, “may be”, “points toward”); avoid proves / truth is / mind-reading “they want”; anchor strong claims in the same beat.

**Visual pacing:** dense → mundane scene | human moment | (metaphor only if earned); no back-to-back dense stacks.

**Creation only:** Script Writer outputs OUTLINE + SCRIPT + B-ROLL + KEYWORDS — never editorial analysis.`;

/** @deprecated Script Writer no longer outputs editorial analysis — use Editorial Analyzer step. */
export const PIPELINE_OUTPUT_OUTLINE_SPLIT_EN = "";

/** @deprecated Script Writer ya no incluye análisis editorial — paso Editorial Analyzer. */
export const PIPELINE_OUTPUT_OUTLINE_SPLIT_ES = "";

export const GOVERNANCE_CORE_BLOCK_ES = `${GOVERNANCE_CORE_HEADER_ES}
Un solo bloque — intégralo sin declararlo; no narres las reglas.

**Prioridad si chocan:** (1) claridad emocional (2) impulso (3) relatabilidad (4) datos precisos (5) filosofía escasa. Sin meta-ganchos (“lo que nadie te cuenta…”, etc.).

**Retención orgánica:** giros desde emoción/historia (~cada 20–40s de media; omite si ya hay impulso). Nunca suene a reloj ni manipulación. Una idea por beat; respeta duración.

**Cine no ensayo:** escenas filmables; [B-ROLL] en cortes. **Mundano > metáfora:** no todo beat necesita símbolos; evita tono tráiler / sufrimiento estetizado.

**Pattern interrupt (cuando hay densidad, no programado):** pivot | reframe | especificidad | corte de tono — sin reversiones formulaicas (“crees que X… pero Y”).

**Realismo vivido:** tras líneas “inteligentes” — sonido | silencio | cuerpo | objeto; no narrador de ensayo listo.

**Verdad:** matiz (“los incentivos sugieren”, “puede ser”, “apunta a”); evita demuestra / la verdad es / “ellos quieren”; ancla claims fuertes en el mismo beat.

**Ritmo visual:** denso → escena mundana | momento humano | (metáfora solo si está ganada); sin dos densos seguidos.

**Solo creación:** Script Writer → OUTLINE + GUIÓN + B-ROLL + KEYWORDS. Diagnóstico → paso Editorial Analyzer.`;

function hasCreativeLooseness(text: string): boolean {
  const t = text || "";
  return (
    t.includes(CREATIVE_LOOSENESS_HEADER_EN) ||
    t.includes(CREATIVE_LOOSENESS_HEADER_ES)
  );
}

function hasGovernanceCore(text: string): boolean {
  const t = text || "";
  return (
    t.includes(GOVERNANCE_CORE_HEADER_EN) ||
    t.includes(GOVERNANCE_CORE_HEADER_ES)
  );
}

function hasLegacyExpandedGovernance(text: string): boolean {
  return (
    hasEditorialPriority(text) &&
    hasRetentionDiscipline(text) &&
    hasVisualCinema(text) &&
    hasPatternInterrupt(text) &&
    hasGroundedRealism(text) &&
    hasTruthClaimsDiscipline(text) &&
    hasVisualPacingArchitecture(text)
  );
}

function hasEditorialPriority(text: string): boolean {
  const t = text || "";
  return (
    t.includes(EDITORIAL_PRIORITY_HEADER_EN) ||
    t.includes(EDITORIAL_PRIORITY_HEADER_ES) ||
    t.includes("Anti editorial bloat") ||
    t.includes("Anti-hinchazón editorial")
  );
}

function hasRetentionDiscipline(text: string): boolean {
  const t = text || "";
  return (
    t.includes(RETENTION_DISCIPLINE_HEADER_EN) ||
    t.includes(RETENTION_DISCIPLINE_HEADER_ES)
  );
}

function hasVisualCinema(text: string): boolean {
  const t = text || "";
  return (
    t.includes(VISUAL_CINEMA_HEADER_EN) ||
    t.includes(VISUAL_CINEMA_HEADER_ES)
  );
}

function hasPatternInterrupt(text: string): boolean {
  const t = text || "";
  return (
    t.includes(PATTERN_INTERRUPT_HEADER_EN) ||
    t.includes(PATTERN_INTERRUPT_HEADER_ES)
  );
}

function hasGroundedRealism(text: string): boolean {
  const t = text || "";
  return (
    t.includes(GROUNDED_REALISM_HEADER_EN) ||
    t.includes(GROUNDED_REALISM_HEADER_ES)
  );
}

function hasTruthClaimsDiscipline(text: string): boolean {
  const t = text || "";
  return (
    t.includes(TRUTH_CLAIMS_HEADER_EN) ||
    t.includes(TRUTH_CLAIMS_HEADER_ES)
  );
}

function hasVisualPacingArchitecture(text: string): boolean {
  const t = text || "";
  return (
    t.includes(VISUAL_PACING_HEADER_EN) ||
    t.includes(VISUAL_PACING_HEADER_ES)
  );
}

export function hasEditorialGovernance(text: string): boolean {
  return (
    hasCreativeLooseness(text) &&
    (hasGovernanceCore(text) || hasLegacyExpandedGovernance(text))
  );
}

function creativeLoosenessBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return CREATIVE_LOOSENESS_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return CREATIVE_LOOSENESS_BLOCK_EN;
  return CREATIVE_LOOSENESS_BLOCK_ES;
}

function governanceCoreBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return GOVERNANCE_CORE_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return GOVERNANCE_CORE_BLOCK_EN;
  return GOVERNANCE_CORE_BLOCK_ES;
}

export function governanceStackBlock(languageCode?: string): string {
  return `${creativeLoosenessBlock(languageCode)}\n\n${governanceCoreBlock(languageCode)}`;
}

function retentionDisciplineBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return RETENTION_DISCIPLINE_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return RETENTION_DISCIPLINE_BLOCK_EN;
  return RETENTION_DISCIPLINE_BLOCK_ES;
}

function editorialPriorityBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return EDITORIAL_PRIORITY_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return EDITORIAL_PRIORITY_BLOCK_EN;
  return EDITORIAL_PRIORITY_BLOCK_ES;
}

function visualCinemaBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return VISUAL_CINEMA_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return VISUAL_CINEMA_BLOCK_EN;
  return VISUAL_CINEMA_BLOCK_ES;
}

function patternInterruptBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return PATTERN_INTERRUPT_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return PATTERN_INTERRUPT_BLOCK_EN;
  return PATTERN_INTERRUPT_BLOCK_ES;
}

function groundedRealismBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return GROUNDED_REALISM_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return GROUNDED_REALISM_BLOCK_EN;
  return GROUNDED_REALISM_BLOCK_ES;
}

function truthClaimsBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return TRUTH_CLAIMS_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return TRUTH_CLAIMS_BLOCK_EN;
  return TRUTH_CLAIMS_BLOCK_ES;
}

function visualPacingBlock(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return VISUAL_PACING_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return VISUAL_PACING_BLOCK_EN;
  return VISUAL_PACING_BLOCK_ES;
}

export function editorialGovernanceBlock(languageCode?: string): string {
  return governanceStackBlock(languageCode);
}

export function ensurePromptGovernance(text: string, languageCode?: string): string {
  if (hasEditorialGovernance(text)) return text;
  const prefix: string[] = [];
  if (!hasCreativeLooseness(text)) prefix.push(creativeLoosenessBlock(languageCode));
  if (!hasGovernanceCore(text) && !hasLegacyExpandedGovernance(text)) {
    prefix.push(governanceCoreBlock(languageCode));
  }
  if (!prefix.length) return text;
  return `${prefix.join("\n\n")}\n\n${text}`;
}

export function hasOutputStructureHeader(text: string): boolean {
  return (
    text.includes(OUTPUT_STRUCTURE_HEADER) ||
    text.includes(OUTPUT_STRUCTURE_HEADER_EN) ||
    text.includes(OUTPUT_STRUCTURE_HEADER_EN_CAPITALIZED)
  );
}

/** Reglas TTS en inglés (meta-instrucciones): el guion hablado sigue {{LANGUAGE_CODE}}. */
export const PIPELINE_TTS_SPOKEN_RULES = `## TTS / spoken script
- All narrable lines must be in {{LANGUAGE_CODE}} (same as «Output language» above).
- Write for voice-over: full sentences, natural spoken rhythm in that language.
- Spell out numbers, currencies, and symbols in words appropriate to that language (avoid raw digits or symbols TTS would misread).
- [B-ROLL: …] and [CATEGORY: …] tags are not read aloud.
- Avoid decorative Markdown inside spoken lines if it could confuse TTS.`;

/** Modelo base de USER INSTRUCTIONS; placeholders se sustituyen al generar el guion. */
export const DEFAULT_PIPELINE_OUTPUT_STRUCTURE = `{{LANGUAGE_CODE}} · ~{{DURACION_MINUTOS}} min
Topic: {{TEMA}}
Angle: {{ANGULO}}
Restrictions: {{RESTRICCIONES}}
Sources: {{FUENTES}}`;

export const SYSTEM_INSTRUCTIONS_PLACEHOLDER =
  "Tras analizar transcripts: identidad del canal (## channel_identity) — psicología y voz, no listas de copy.";

export const USER_NARRATIVE_PLACEHOLDER = `Tras analizar transcripts — secciones 1–10 (psicología creativa):

1 Estrella creativa · 2 Mecanismo central · 3 Psicología del espectador · 4 Perfil de tono · 5 Movimiento narrativo · 6 Mundo visual · 7 Textura humana · 8 Estándar intelectual · 9 Naturalidad · 10 Patrones prohibidos

El formato técnico (OUTLINE/GUIÓN/B-ROLL) va solo en el modelo base — no aquí.`;

export const PROMPT_WRITER_OBJECTIVES_BLURB =
  "Motor de compresión narrativa: psicología, tensión, movimiento y realismo — no fórmulas de redacción. Tras Topic → Angle, esto alimenta al Script Writer.";

export const USER_BASE_MODEL_LABEL = "Base model (fixed template)";

/** Markers — EN is canonical (new); ES kept for backward compatibility. */
const NARRATIVE_MARKER_EN = "\n\n---\n\n## Channel narrative guidelines\n\n";
const NARRATIVE_MARKER_ES =
  "\n\n---\n\n## Instrucciones narrativas (canal)\n\n";

const PLACEHOLDER_RE =
  /\{\{(LANGUAGE_CODE|DURACION_MINUTOS|TEMA|ANGULO|RESTRICCIONES|FUENTES)\}\}/g;

function formatDurationMinutes(minutes: number): string {
  if (!(minutes > 0)) return "10";
  if (Math.abs(minutes - Math.round(minutes)) < 1e-6)
    return String(Math.round(minutes));
  return String(minutes);
}

function normalizeLanguageCode(lang: string): string {
  const code = (lang || "").trim();
  if (!code) return "es-ES";
  if (code.includes("-") || code.includes("_")) return code.replace("_", "-");
  const low = code.toLowerCase();
  if (low === "es") return "es-ES";
  if (low === "en") return "en-US";
  return code;
}

/** Sustituye placeholders del modelo base (preview / documentación). */
export function applyUserInstructionPlaceholders(
  text: string,
  opts: {
    languageCode?: string;
    durationMinutes?: number;
    tema?: string;
    angulo?: string;
    restricciones?: string;
    fuentes?: string;
  },
): string {
  const empty = "—";
  const values: Record<string, string> = {
    LANGUAGE_CODE: normalizeLanguageCode(opts.languageCode ?? ""),
    DURACION_MINUTOS: formatDurationMinutes(opts.durationMinutes ?? 10),
    TEMA: (opts.tema ?? "").trim() || empty,
    ANGULO: (opts.angulo ?? "").trim() || empty,
    RESTRICCIONES: (opts.restricciones ?? "").trim() || empty,
    FUENTES: (opts.fuentes ?? "").trim() || empty,
  };
  return (text || "").replace(
    PLACEHOLDER_RE,
    (_, key: string) => values[key] ?? `{{${key}}}`,
  );
}

/** Always writes EN marker; reads both EN and ES for backward compatibility. */
export function composeUserInstructions(
  outputStructure: string,
  narrative: string,
): string {
  const out = (outputStructure || "").trim();
  const nar = (narrative || "").trim();
  if (out && nar) return `${out}${NARRATIVE_MARKER_EN}${nar}`;
  if (out) return out;
  return nar;
}

/** Separa plantillas antiguas (todo en user_instructions) en modelo base + narrativa. */
export function splitUserInstructions(combined: string): {
  outputStructure: string;
  narrative: string;
} {
  const text = (combined || "").trim();
  if (!text) {
    return {
      outputStructure: DEFAULT_PIPELINE_OUTPUT_STRUCTURE,
      narrative: "",
    };
  }

  // Detect marker — EN first (canonical), ES for backward compatibility
  const marker = text.includes(NARRATIVE_MARKER_EN)
    ? NARRATIVE_MARKER_EN
    : text.includes(NARRATIVE_MARKER_ES)
      ? NARRATIVE_MARKER_ES
      : null;

  if (marker) {
    const idx = text.indexOf(marker);
    return {
      outputStructure: text.slice(0, idx).trim(),
      narrative: text.slice(idx + marker.length).trim(),
    };
  }

  if (
    hasOutputStructureHeader(text) ||
    text.includes("{{LANGUAGE_CODE}}")
  ) {
    return { outputStructure: text, narrative: "" };
  }

  return {
    outputStructure: DEFAULT_PIPELINE_OUTPUT_STRUCTURE,
    narrative: text,
  };
}

/** Valores de sesión que sustituyen placeholders del modelo base. */
export type PromptSessionValues = {
  languageCode: string;
  durationMinutes: number;
  tema: string;
  angulo: string;
  restricciones: string;
  fuentes?: string;
};

/** Vista previa del paso Prompt Writer (no confundir con Script Writer). */
export type PromptWriterPreviewPayload = {
  step: "prompt_writer";
  /** Lo que guardas con Save / paso Prompt (tabla prompt_templates + pipeline/prompt.json). */
  catalog_saved: {
    _maps_to_ui: string;
    name: string;
    template_id: string | null;
    system_instructions: string;
    user_instructions: string;
    params_json: {
      output_structure: string;
      target_audience: string;
      narrative_structure: Record<string, unknown>;
    };
  };
  /** Modelo base + narrativa unidos; placeholders de sesión aplicados (sin transformación Script Writer). */
  composed_user_instructions: {
    _description: string;
    _built_from: string[];
    text: string;
  };
  /** Solo al ejecutar Script Writer — no se persiste en el catálogo Prompt. */
  downstream_script_writer: {
    _description: string;
    _backend_modules: string[];
    catalog_after_voice_prep: string;
    extra_appended_at_runtime: {
      session_block: string;
      system_technical_format_note: string;
    };
  };
};

function sessionBlockPreview(session: PromptSessionValues): string {
  const tema = (session.tema ?? "").trim() || "—";
  const angulo = (session.angulo ?? "").trim() || "—";
  const dm = session.durationMinutes > 0 ? session.durationMinutes : 10;
  return `Tema: ${tema}\nContexto: ${angulo}\nDuración ~${dm} min.`;
}

/**
 * Preview del paso **Prompt Writer**: catálogo guardado + texto compuesto.
 * La capa Script Writer (`script_writer_voice.py`, `script_gen.compose_messages`) va aparte.
 */
export function buildPromptPreviewPayload(opts: {
  templateId: string | null;
  name: string;
  systemInstructions: string;
  outputStructure: string;
  narrative: string;
  targetAudience: string;
  narrativeStructure: Record<string, unknown>;
  session: PromptSessionValues;
}): PromptWriterPreviewPayload {
  const composedRaw = applyUserInstructionPlaceholders(
    composeUserInstructions(opts.outputStructure, opts.narrative),
    opts.session,
  );
  const afterVoicePrep = prepareScriptWriterUserPrompt(
    composedRaw,
    opts.session.languageCode,
  );

  return {
    step: "prompt_writer",
    catalog_saved: {
      _maps_to_ui:
        "SYSTEM INSTRUCTIONS + USER (modelo base + narrativa) + PARÁMETROS EXTRA → payload Save / prompt_templates",
      name: opts.name,
      template_id: opts.templateId,
      system_instructions: opts.systemInstructions,
      user_instructions: opts.narrative,
      params_json: {
        output_structure: opts.outputStructure,
        target_audience: opts.targetAudience,
        narrative_structure: opts.narrativeStructure,
      },
    },
    composed_user_instructions: {
      _description:
        "Unión output_structure + narrativa con {{TEMA}}, {{LANGUAGE_CODE}}, etc. ya sustituidos. " +
        "Es lo que fusiona prompt_instruction_contract.merged_user_instructions_for_pipeline (antes del brief Guionista).",
      _built_from: [
        "apps/frontend: composeUserInstructions + applyUserInstructionPlaceholders",
        "apps/backend: videomaker/llm/prompt_instruction_contract.py",
      ],
      text: composedRaw,
    },
    downstream_script_writer: {
      _description:
        "Al pulsar Start en Script Writer, el backend añade bloque de sesión, contrato técnico de etiquetas (system) " +
        "y prepara el user con script_writer_voice.py. Esto NO es salida del Prompt Writer.",
      _backend_modules: [
        "videomaker/llm/script_writer_voice.py → prepare_script_writer_user_prompt",
        "videomaker/llm/script_gen.py → compose_messages (+ build_session_user_prompt)",
        "videomaker/llm/script_pipeline_format.py → technical_pipeline_format_addon (va en system, no en user)",
      ],
      catalog_after_voice_prep: afterVoicePrep,
      extra_appended_at_runtime: {
        session_block: sessionBlockPreview(opts.session),
        system_technical_format_note:
          "OUTLINE/GUIÓN/B-ROLL/TTS (~script_output_contract) se añaden al system del LLM, no al catálogo Prompt.",
      },
    },
  };
}
