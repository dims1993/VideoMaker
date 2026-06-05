/** Brief mínimo del Script Writer (espejo del backend). */

export const WRITER_VOICE_HEADER_EN = "## Writer";
export const WRITER_VOICE_HEADER_ES = "## Guionista";

export const WRITER_VOICE_BLOCK_EN = `${WRITER_VOICE_HEADER_EN}
Write like a person talking, not a premium explainer brand.
**Scenes beat slogans.** ("She closed the payment tab" > "This is not a market, it is a mechanism.")
Avoid: Vox/Moon/essay voice, aphorism pairs ("not X — Y"), mechanism metaphors, sounding important.
Channel notes below = topic/tone only — not a checklist.`;

export const WRITER_VOICE_BLOCK_ES = `${WRITER_VOICE_HEADER_ES}
Escribe como alguien hablando, no como marca de vídeo premium.
**La escena gana al eslogan.** ("Cerró la pestaña del pago" > "Esto no es un mercado, es un mecanismo.")
Evita: tono Vox/ensayo, parejas "no es X — es Y", metáforas de mecanismo, sonar importante.
Notas de canal abajo = tema/tono — no checklist.`;

const STRIP_SECTION_PREFIXES = [
  "## Creative looseness",
  "## Holgura creativa",
  "## Script governance",
  "## Gobernanza del guion",
  "## Priority order",
  "## Orden de prioridad",
  "## Retention discipline",
  "## Disciplina de retención",
  "## Write visually",
  "## Escribe en visual",
  "## Pattern interrupt",
  "## Pattern Interrupt",
  "## Grounded realism",
  "## Realismo vivido",
  "## Truth claims",
  "## Verdad",
  "## Visual pacing architecture",
  "## Arquitectura de ritmo visual",
  "## Anti editorial bloat",
  "## Anti-hinchazón editorial",
  "## Estructura de salida",
  "## Script output structure",
  "## Script Writer output",
  "## TTS / spoken",
  "## TTS / guion hablado",
  "## Tema del vídeo",
  "## Video topic",
];

const NARRATIVE_MARKERS = [
  "\n\n---\n\n## Channel narrative guidelines\n\n",
  "\n\n---\n\n## Instrucciones narrativas (canal)\n\n",
];

const MAX_NARRATIVE_CHARS = 1200;

function writerVoiceBrief(languageCode?: string): string {
  const code = (languageCode || "").trim().toLowerCase().replace("_", "-");
  if (code.startsWith("es") || code === "es") return WRITER_VOICE_BLOCK_ES;
  if (code.startsWith("en") || code === "en") return WRITER_VOICE_BLOCK_EN;
  return WRITER_VOICE_BLOCK_ES;
}

export function hasWriterVoice(text: string): boolean {
  const t = text || "";
  return t.includes(WRITER_VOICE_HEADER_EN) || t.includes(WRITER_VOICE_HEADER_ES);
}

export function stripEditorialGovernanceSections(text: string): string {
  const raw = (text || "").trim();
  if (!raw) return raw;

  const parts = raw.split(/(?=^## )/m);
  if (parts.length <= 1 && !raw.startsWith("## ")) return raw;

  const kept: string[] = [];
  for (let i = 0; i < parts.length; i++) {
    const chunk = parts[i].trim();
    if (!chunk) continue;
    if (i === 0 && !chunk.startsWith("## ")) {
      kept.push(chunk);
      continue;
    }
    const firstLine = chunk.split("\n", 1)[0].trim();
    if (STRIP_SECTION_PREFIXES.some((p) => firstLine.startsWith(p))) continue;
    kept.push(chunk);
  }
  return kept.join("\n\n").trim();
}

function capNarrativeSection(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  for (const marker of NARRATIVE_MARKERS) {
    const idx = text.indexOf(marker);
    if (idx < 0) continue;
    const head = text.slice(0, idx + marker.length);
    const narrative = text.slice(idx + marker.length).trim();
    if (narrative.length <= maxChars) return text;
    const trimmed = narrative.slice(0, maxChars).replace(/\n[^\n]*$/, "").trim();
    return `${head}${trimmed}\n\n[… guía de canal recortada …]`;
  }
  if (text.length > maxChars + 400) {
    return `${text.slice(0, maxChars).replace(/\n[^\n]*$/, "").trim()}\n\n[… recortado …]`;
  }
  return text;
}

export function compactScriptWriterInstructions(
  text: string,
  maxNarrativeChars = MAX_NARRATIVE_CHARS,
): string {
  return capNarrativeSection(stripEditorialGovernanceSections(text), maxNarrativeChars);
}

export function prepareScriptWriterUserPrompt(
  text: string,
  languageCode?: string,
): string {
  const cleaned = compactScriptWriterInstructions(text);
  if (hasWriterVoice(cleaned)) return cleaned.trim();
  const brief = writerVoiceBrief(languageCode);
  return cleaned ? `${brief}\n\n${cleaned}`.trim() : brief.trim();
}
