/** Estilos compartidos: campos inferidos (lila) y validación en el paso Prompt. */

export const INFERRED_SECTION_LABEL =
  "text-[10px] font-semibold uppercase tracking-widest text-violet-700";

/** Contenedor lila para bloques inferidos de transcripciones. */
export function inferredPanelClass(
  highlightLevel: "missing" | "warning" | null = null,
): string {
  if (highlightLevel === "missing") {
    return "rounded-xl border border-rose-300 bg-rose-50/90 px-3 py-3 ring-1 ring-rose-200";
  }
  if (highlightLevel === "warning") {
    return "rounded-xl border border-amber-300 bg-amber-50 px-3 py-3 ring-1 ring-amber-200";
  }
  return "rounded-xl border border-violet-200 bg-violet-50/80 px-3 py-3";
}

/** Inputs dentro de un panel inferido (fondo blanco, borde violeta). */
export const inferredControlClass =
  "!mt-0 rounded-xl border-violet-200/90 bg-white text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-violet-400 focus:ring-2 focus:ring-violet-100";

export function fieldHighlightClass(level: "missing" | "warning" | null): string {
  if (level === "missing") {
    return "rounded-xl ring-2 ring-rose-400/70 border border-rose-300 bg-rose-50";
  }
  if (level === "warning") {
    return "rounded-xl ring-2 ring-amber-400/60 border border-amber-200 bg-amber-50";
  }
  return "";
}

export function labelHighlightClass(level: "missing" | "warning" | null): string {
  if (level === "missing") return "text-rose-700";
  if (level === "warning") return "text-amber-800";
  return "";
}
