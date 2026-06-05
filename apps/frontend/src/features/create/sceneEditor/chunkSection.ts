/** section del guion → act para badges (hook / body / cta). */

export function sectionToAct(section: string | null | undefined): "hook" | "body" | "cta" {
  if (!section) return "body";
  const s = section.toLowerCase();
  if (
    s.includes("introducción") ||
    s.includes("introduccion") ||
    s.includes("gancho") ||
    s.includes("hook") ||
    s.startsWith("intro")
  ) {
    return "hook";
  }
  if (s.includes("cierre") || s.includes("cta") || s.includes("closing") || s.includes("outro")) {
    return "cta";
  }
  return "body";
}

export const ACT_LABELS: Record<string, string> = {
  hook: "Hook",
  body: "Body",
  cta: "CTA",
};

export const ACT_COLORS: Record<string, string> = {
  hook: "bg-amber-100 text-amber-900 ring-1 ring-amber-300/60",
  body: "bg-slate-100 text-slate-700 ring-1 ring-slate-300/60",
  cta: "bg-sky-100 text-sky-900 ring-1 ring-sky-300/60",
};
