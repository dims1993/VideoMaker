import { fmtK, fmtPct } from "../../../utils";
import type { SavedChannelItem } from "../../../types";

export const CATEGORY_OPTIONS = [
  "Fitness",
  "Motivation & Habits",
  "Finance",
  "Tech",
  "Education",
  "Psychology",
  "Productivity",
  "Business",
  "Entertainment",
  "Other",
] as const;

export type OpportunityGrade = "bajo" | "medio" | "alto" | "perla" | "sin_datos";

export function opportunityGrade(score: number | null | undefined): OpportunityGrade {
  if (typeof score !== "number" || !Number.isFinite(score)) return "sin_datos";
  if (score >= 6) return "perla";
  if (score >= 3) return "alto";
  if (score >= 1) return "medio";
  return "bajo";
}

export function opportunityLabel(g: OpportunityGrade): string {
  if (g === "perla") return "Perla";
  if (g === "alto") return "Alto";
  if (g === "medio") return "Medio";
  if (g === "bajo") return "Bajo";
  return "Sin datos";
}

export function opportunityPillClass(g: OpportunityGrade): string {
  if (g === "perla") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (g === "alto") return "border-emerald-100 bg-emerald-50/60 text-emerald-900";
  if (g === "medio") return "border-amber-200 bg-amber-50 text-amber-950";
  if (g === "bajo") return "border-rose-200 bg-rose-50 text-rose-900";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

export type MetricGrade = "good" | "mid" | "bad" | "na";

export type ThresholdProfile = {
  like_good: number;
  like_mid: number;
  com_good: number;
  com_mid: number;
  eng_good: number;
  eng_mid: number;
  vph_good: number;
  vph_mid: number;
  vpd_good: number;
  vpd_mid: number;
  engsub_good: number;
  engsub_mid: number;
};

export const defaultThresholdProfile: ThresholdProfile = {
  like_good: 0.03,
  like_mid: 0.015,
  com_good: 0.003,
  com_mid: 0.0015,
  eng_good: 0.035,
  eng_mid: 0.02,
  vph_good: 500,
  vph_mid: 150,
  vpd_good: 10_000,
  vpd_mid: 2_000,
  engsub_good: 0.01,
  engsub_mid: 0.003,
};

export function profileForCategory(cat: string | null | undefined): ThresholdProfile {
  const c = (cat || "").toLowerCase();
  const d = defaultThresholdProfile;
  if (c.includes("finance")) {
    return { ...d, like_good: 0.02, like_mid: 0.012, com_good: 0.002, com_mid: 0.001, eng_good: 0.025, eng_mid: 0.015 };
  }
  if (c.includes("tech")) {
    return { ...d, like_good: 0.022, like_mid: 0.012, com_good: 0.002, com_mid: 0.001, eng_good: 0.026, eng_mid: 0.016 };
  }
  if (c.includes("education")) {
    return { ...d, like_good: 0.025, like_mid: 0.013, com_good: 0.0025, com_mid: 0.0012, eng_good: 0.03, eng_mid: 0.018 };
  }
  if (c.includes("fitness") || c.includes("motivation") || c.includes("habits")) {
    return { ...d, like_good: 0.04, like_mid: 0.02, com_good: 0.0035, com_mid: 0.0018, eng_good: 0.045, eng_mid: 0.025 };
  }
  if (c.includes("entertainment")) {
    return { ...d, like_good: 0.035, like_mid: 0.018, com_good: 0.003, com_mid: 0.0015, eng_good: 0.04, eng_mid: 0.022 };
  }
  return d;
}

export function createVideoMetricGraders(profile: ThresholdProfile) {
  function gradeLikeRate(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= profile.like_good) return "good";
    if (x >= profile.like_mid) return "mid";
    return "bad";
  }
  function gradeCommentRate(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= profile.com_good) return "good";
    if (x >= profile.com_mid) return "mid";
    return "bad";
  }
  function gradeEngagement(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= profile.eng_good) return "good";
    if (x >= profile.eng_mid) return "mid";
    return "bad";
  }
  function gradeViewsPerDay(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= profile.vpd_good) return "good";
    if (x >= profile.vpd_mid) return "mid";
    return "bad";
  }
  function gradeVph(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= profile.vph_good) return "good";
    if (x >= profile.vph_mid) return "mid";
    return "bad";
  }
  function gradeEngagementPerSub(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= profile.engsub_good) return "good";
    if (x >= profile.engsub_mid) return "mid";
    return "bad";
  }
  return {
    gradeLikeRate,
    gradeCommentRate,
    gradeEngagement,
    gradeViewsPerDay,
    gradeVph,
    gradeEngagementPerSub,
  };
}

export type PerlaGrade = "excelente" | "bueno" | "regular" | "malo" | "sin_datos";

export function gradeLabel(g: PerlaGrade): string {
  if (g === "excelente") return "Excelente";
  if (g === "bueno") return "Bueno";
  if (g === "regular") return "Regular";
  if (g === "malo") return "Malo";
  return "Sin datos";
}

export function gradeClass(g: PerlaGrade): string {
  if (g === "excelente") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (g === "bueno") return "border-emerald-100 bg-emerald-50/60 text-emerald-900";
  if (g === "regular") return "border-amber-200 bg-amber-50 text-amber-950";
  if (g === "malo") return "border-rose-200 bg-rose-50 text-rose-900";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

export function metricPillClass(g: MetricGrade): string {
  if (g === "good") return "border-sky-200 bg-sky-50 text-sky-900";
  if (g === "mid") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (g === "bad") return "border-rose-200 bg-rose-50 text-rose-900";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

export function scorecard(saved: SavedChannelItem | undefined | null) {
  const med = typeof saved?.median_views === "number" ? saved.median_views : null;
  const hit = typeof saved?.hit_rate === "number" ? saved.hit_rate : null;
  const com1k = typeof saved?.comments_per_1k_views === "number" ? saved.comments_per_1k_views : null;
  const upmo = typeof saved?.uploads_per_month_90d === "number" ? saved.uploads_per_month_90d : null;
  const long8 = typeof saved?.pct_over_8min === "number" ? saved.pct_over_8min : null;

  const gMedian: PerlaGrade =
    med == null ? "sin_datos" : med > 200_000 ? "excelente" : med >= 80_000 ? "bueno" : med >= 20_000 ? "regular" : "malo";
  const gHit: PerlaGrade = hit == null ? "sin_datos" : hit > 0.6 ? "excelente" : hit >= 0.35 ? "bueno" : hit >= 0.15 ? "regular" : "malo";
  const gCom: PerlaGrade =
    com1k == null ? "sin_datos" : com1k > 4 ? "excelente" : com1k >= 2 ? "bueno" : com1k >= 1 ? "regular" : "malo";
  const gUp: PerlaGrade = upmo == null ? "sin_datos" : upmo > 12 ? "excelente" : upmo >= 6 ? "bueno" : upmo >= 2 ? "regular" : "malo";
  const gLong: PerlaGrade = long8 == null ? "sin_datos" : long8 > 0.7 ? "excelente" : long8 >= 0.4 ? "bueno" : long8 >= 0.15 ? "regular" : "malo";

  const approvals = [gMedian, gHit, gCom, gUp].filter((g) => g === "excelente" || g === "bueno").length;
  const hasAny = [med, hit, com1k, upmo, long8].some((x) => typeof x === "number");
  const decision = !hasAny ? "Sin métricas (haz Guardar+Sync)" : approvals >= 3 ? "PERLA (Aprobado)" : approvals === 2 ? "Dudoso" : "Rechazar";

  return {
    decision,
    rows: [
      { k: "Mediana views (N=50)", v: med == null ? "—" : fmtK(med), rule: ">200k / 80–200k / 20–80k / <20k", g: gMedian },
      { k: "Hit-rate (>=X)", v: hit == null ? "—" : fmtPct(hit), rule: ">60% / 35–60% / 15–35% / <15%", g: gHit },
      { k: "Comentarios / 1k", v: com1k == null ? "—" : com1k.toFixed(1), rule: ">4 / 2–4 / 1–2 / <1", g: gCom },
      { k: "Uploads / mes", v: upmo == null ? "—" : upmo.toFixed(1), rule: ">12 / 6–12 / 2–6 / <2", g: gUp },
      { k: "% vídeos > 8min", v: long8 == null ? "—" : fmtPct(long8), rule: ">70% / 40–70% / 15–40% / <15%", g: gLong },
    ],
  };
}
