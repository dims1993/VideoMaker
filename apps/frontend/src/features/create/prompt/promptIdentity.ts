/** Bloque markdown dentro de system_instructions (tono, gancho, estilo visual del canal). */
export const IDENTIDAD_DEL_CANAL_HEADER = "## identidad_del_canal";

export function hasIdentidadDelCanal(text: string): boolean {
  return /##\s*identidad_del_canal\b/i.test(text);
}

export function buildIdentidadDelCanalBlock(opts: {
  tono?: string;
  gancho?: string;
  estilo_visual?: string;
}): string {
  const lines = [IDENTIDAD_DEL_CANAL_HEADER];
  const tono = (opts.tono || "").trim();
  const gancho = (opts.gancho || "").trim();
  const estilo = (opts.estilo_visual || "").trim();
  if (tono) lines.push(`tono: ${tono}`);
  if (gancho) lines.push(`gancho: ${gancho}`);
  if (estilo) lines.push(`estilo_visual: ${estilo}`);
  return lines.length > 1 ? lines.join("\n") : "";
}

/** Migra columnas legacy (hook_style, visual_style, tone) al bloque si aún no existe. */
export function mergeLegacyIdentityIntoSystem(
  system: string,
  legacy: { hook_style?: string; visual_style?: string; tone?: string },
): string {
  const sys = (system || "").trim();
  if (hasIdentidadDelCanal(sys)) return system || "";
  const block = buildIdentidadDelCanalBlock({
    tono: legacy.tone,
    gancho: legacy.hook_style,
    estilo_visual: legacy.visual_style,
  });
  if (!block) return system || "";
  return sys ? `${sys}\n\n${block}` : block;
}

/** Campos de narrative_structure solo rellenados por análisis de transcripciones. */
export function buildInferredNarrativeStructure(fields: {
  tone?: string;
  hook_type?: string;
  cta_type?: string;
}): Record<string, string> {
  const out: Record<string, string> = {};
  const tone = (fields.tone || "").trim();
  const hook = (fields.hook_type || "").trim();
  const cta = (fields.cta_type || "").trim();
  if (tone) out.tone = tone;
  if (hook) out.hook_type = hook;
  if (cta) out.cta_type = cta;
  return out;
}

export const IDENTIDAD_DEL_CANAL_PLACEHOLDER = `Rol del narrador (psicología, no frases literales)…

## identidad_del_canal
tono: íntimo y observacional, sin tono corporativo
gancho: curiosidad por tensión personal, no fórmula de YouTube
estilo_visual: escenas mundanas filmables, no tráiler`;
