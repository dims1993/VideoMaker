import { useCallback, useEffect, useMemo, useState } from "react";
import { Btn, Card, Input, Label, Select, StatusBadge, TextArea } from "./components/ui";
import { deleteReq, postJson, putJson, readApiError } from "./services/api";
import type { ChannelSearchItem, ChannelVideoItem, SavedChannelItem, Session, TaskStatus } from "./types";
import { fmtK, fmtPct } from "./utils";
import { Sidebar } from "./components/common/Sidebar";
import { SavedChannelDetail } from "./features/dashboard/saved/SavedChannelDetail";

// (moved to src/types)

type PipelineStepState = {
  id: string;
  title: string;
  state: "idle" | "running" | "done" | "error";
  detail?: string;
  updated_at?: string;
};

type PipelineState = {
  state: "idle" | "running" | "done" | "error";
  current_step?: string | null;
  steps: PipelineStepState[];
  last_error?: string | null;
};

// Removed legacy analyze types/panels (not used in current UI).

function initialWorkFromUrl(): string {
  try {
    const w = new URLSearchParams(window.location.search).get("work");
    return w && w.trim() ? w.trim() : "output/ui_session";
  } catch {
    return "output/ui_session";
  }
}

export default function App() {
  const [work, setWork] = useState(initialWorkFromUrl);
  const [workApplied, setWorkApplied] = useState(initialWorkFromUrl);
  const [session, setSession] = useState<Session | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"analyze" | "create">("create");
  const [pipelineState, setPipelineState] = useState<PipelineState | null>(null);

  // New: channel directory/search dashboard
  const [channelSearchQ, setChannelSearchQ] = useState("");
  const [channelMinSubs, setChannelMinSubs] = useState(0);
  const [channelMinViews, setChannelMinViews] = useState(0);
  const [channelSort, setChannelSort] = useState<"subs" | "views" | "videos" | "views_per_video" | "views_per_sub">("subs");
  const [channelLang, setChannelLang] = useState<"" | "es" | "en">("");
  const [channelCategory, setChannelCategory] = useState("");
  const [channelSearchResults, setChannelSearchResults] = useState<ChannelSearchItem[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<ChannelSearchItem | null>(null);
  // Holds all channels we know in DB (pearls + scans),
  // so search results can display metrics after a quick scan.
  const [savedChannels, setSavedChannels] = useState<SavedChannelItem[]>([]);
  const [selectedSavedChannelId, setSelectedSavedChannelId] = useState<string | null>(null);
  const [analyzePanel, setAnalyzePanel] = useState<"search" | "saved">("search");
  const [savedChannelVideos, setSavedChannelVideos] = useState<ChannelVideoItem[]>([]);
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [editCat, setEditCat] = useState("");
  const [editLang, setEditLang] = useState<"" | "es" | "en">("");

  // Saved channels filters/sort (opportunity discovery)
  const [savedQ, setSavedQ] = useState("");
  const [savedCategory, setSavedCategory] = useState("");
  const [savedSort, setSavedSort] = useState<
    | "opportunity"
    | "subs_delta_30d"
    | "views_delta_30d"
    | "median_views"
    | "hit_rate"
    | "engagement"
    | "uploads_per_month"
    | "days_since_upload"
    | "views_per_sub"
  >("opportunity");
  const [savedMinSubs, setSavedMinSubs] = useState(0);
  const [savedMinViews, setSavedMinViews] = useState(0);
  const [savedMinUploadsMonth, setSavedMinUploadsMonth] = useState(0);
  const [savedMinViewsPerSub, setSavedMinViewsPerSub] = useState(0);
  const [savedMinHitRate, setSavedMinHitRate] = useState(0);
  const [savedHitViewsThreshold, setSavedHitViewsThreshold] = useState(50000);

  const [kw, setKw] = useState("motivación, hábitos, enfoque");
  const [ctx, setCtx] = useState("");
  const [lang, setLang] = useState("es");
  const [minutes, setMinutes] = useState(10);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [previewText, setPreviewText] = useState("Hola, esta es una prueba de voz antes de narrar el vídeo.");
  const [preset, setPreset] = useState("xtts_v2_es");
  const [maxChars, setMaxChars] = useState(900);
  const [maxSeg, setMaxSeg] = useState(0);
  const [stockLang, setStockLang] = useState("es");
  const [maxClips, setMaxClips] = useState(25);
  const [promptOpen, setPromptOpen] = useState(false);
  const [promptData, setPromptData] = useState<{ system: string; user: string } | null>(null);
  const [scriptEditorOpen, setScriptEditorOpen] = useState(false);
  const [scriptEditText, setScriptEditText] = useState("");
  const [promptPresets, setPromptPresets] = useState<{ id: string; name: string }[]>([]);
  const [promptSelectedId, setPromptSelectedId] = useState<string | null>(null);
  const [promptSystemExtra, setPromptSystemExtra] = useState("");
  const [promptUserExtra, setPromptUserExtra] = useState("");
  const [newPresetName, setNewPresetName] = useState("");

  const loadPromptPresets = useCallback(async () => {
    try {
      const r = await fetch("/api/prompt-presets");
      if (!r.ok) return;
      const j = (await r.json()) as { presets: { id: string; name: string }[]; selected_id: string | null };
      setPromptPresets(j.presets ?? []);
      const sid = j.selected_id;
      setPromptSelectedId(sid);
      if (sid) {
        const pr = await fetch(`/api/prompt-preset?preset_id=${encodeURIComponent(sid)}`);
        if (pr.ok) {
          const p = (await pr.json()) as { system_extra?: string; user_extra?: string };
          setPromptSystemExtra(p.system_extra ?? "");
          setPromptUserExtra(p.user_extra ?? "");
        }
      } else {
        setPromptSystemExtra("");
        setPromptUserExtra("");
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadPromptPresets();
  }, [loadPromptPresets]);

  const refresh = useCallback(async () => {
    setErr(null);
    const r = await fetch(`/api/session?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) {
      setErr(await r.text());
      setSession(null);
      return;
    }
    setSession(await r.json());
  }, [workApplied]);

  const refreshPipeline = useCallback(async () => {
    try {
      const r = await fetch(`/api/pipeline/state?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) return;
      setPipelineState((await r.json()) as PipelineState);
    } catch {
      /* ignore */
    }
  }, [workApplied]);

  const refreshSavedChannels = useCallback(async () => {
    try {
      const qs = new URLSearchParams({
        limit: "100",
        sort: savedSort,
        q: savedQ.trim(),
        category: savedCategory.trim(),
        // Only pearls (curated) to avoid extra quota-driven scans.
        pearls_only: "true",
        min_subs: String(savedMinSubs || 0),
        min_views: String(savedMinViews || 0),
        min_uploads_month: String(savedMinUploadsMonth || 0),
        min_views_per_sub: String(savedMinViewsPerSub || 0),
        min_hit_rate: String(savedMinHitRate ? savedMinHitRate / 100 : 0),
        hit_views_threshold: String(savedHitViewsThreshold || 50000),
        window_videos: "50",
      });
      const r = await fetch(`/api/channels?${qs.toString()}`);
      if (!r.ok) return;
      const j = (await r.json()) as { channels: SavedChannelItem[] };
      setSavedChannels(j.channels || []);
    } catch {
      /* ignore */
    }
  }, [
    savedCategory,
    savedHitViewsThreshold,
    savedMinHitRate,
    savedMinSubs,
    savedMinUploadsMonth,
    savedMinViews,
    savedMinViewsPerSub,
    savedQ,
    savedSort,
  ]);

  // fmtK/fmtPct moved to src/utils/format.ts

  type OpportunityGrade = "bajo" | "medio" | "alto" | "perla" | "sin_datos";
  function opportunityGrade(score: number | null | undefined): OpportunityGrade {
    if (typeof score !== "number" || !Number.isFinite(score)) return "sin_datos";
    if (score >= 6) return "perla";
    if (score >= 3) return "alto";
    if (score >= 1) return "medio";
    return "bajo";
  }
  function opportunityLabel(g: OpportunityGrade): string {
    if (g === "perla") return "Perla";
    if (g === "alto") return "Alto";
    if (g === "medio") return "Medio";
    if (g === "bajo") return "Bajo";
    return "Sin datos";
  }
  function opportunityPillClass(g: OpportunityGrade): string {
    if (g === "perla") return "border-emerald-200 bg-emerald-50 text-emerald-900";
    if (g === "alto") return "border-emerald-100 bg-emerald-50/60 text-emerald-900";
    if (g === "medio") return "border-amber-200 bg-amber-50 text-amber-950";
    if (g === "bajo") return "border-rose-200 bg-rose-50 text-rose-900";
    return "border-slate-200 bg-slate-50 text-slate-700";
  }

  const CATEGORY_OPTIONS = useMemo(
    () => [
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
    ],
    []
  );

  type MetricGrade = "good" | "mid" | "bad" | "na";
  function metricPillClass(g: MetricGrade): string {
    if (g === "good") return "border-sky-200 bg-sky-50 text-sky-900";
    if (g === "mid") return "border-emerald-200 bg-emerald-50 text-emerald-900";
    if (g === "bad") return "border-rose-200 bg-rose-50 text-rose-900";
    return "border-slate-200 bg-slate-50 text-slate-700";
  }

  function metricPill(value: string, g: MetricGrade) {
    return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${metricPillClass(g)}`}>{value}</span>;
  }

  type ThresholdProfile = {
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

  const defaultProfile: ThresholdProfile = {
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

  function profileForCategory(cat: string | null | undefined): ThresholdProfile {
    const c = (cat || "").toLowerCase();
    // Adjustments by niche (lightweight, tunable later).
    if (c.includes("finance")) {
      return { ...defaultProfile, like_good: 0.02, like_mid: 0.012, com_good: 0.002, com_mid: 0.001, eng_good: 0.025, eng_mid: 0.015 };
    }
    if (c.includes("tech")) {
      return { ...defaultProfile, like_good: 0.022, like_mid: 0.012, com_good: 0.002, com_mid: 0.001, eng_good: 0.026, eng_mid: 0.016 };
    }
    if (c.includes("education")) {
      return { ...defaultProfile, like_good: 0.025, like_mid: 0.013, com_good: 0.0025, com_mid: 0.0012, eng_good: 0.03, eng_mid: 0.018 };
    }
    if (c.includes("fitness") || c.includes("motivation") || c.includes("habits")) {
      return { ...defaultProfile, like_good: 0.04, like_mid: 0.02, com_good: 0.0035, com_mid: 0.0018, eng_good: 0.045, eng_mid: 0.025 };
    }
    if (c.includes("entertainment")) {
      return { ...defaultProfile, like_good: 0.035, like_mid: 0.018, com_good: 0.003, com_mid: 0.0015, eng_good: 0.04, eng_mid: 0.022 };
    }
    return defaultProfile;
  }

  const selectedSavedChannel = useMemo(
    () => (selectedSavedChannelId ? savedChannels.find((x) => x.channel_id === selectedSavedChannelId) ?? null : null),
    [savedChannels, selectedSavedChannelId]
  );

  const activeThresholdProfile = useMemo(() => profileForCategory(selectedSavedChannel?.internal_category), [selectedSavedChannel?.internal_category]);

  // Discovery thresholds.
  // Rates are expressed as fractions (e.g. 0.02 = 2%).
  function gradeLikeRate(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= activeThresholdProfile.like_good) return "good";
    if (x >= activeThresholdProfile.like_mid) return "mid";
    return "bad";
  }
  function gradeCommentRate(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= activeThresholdProfile.com_good) return "good";
    if (x >= activeThresholdProfile.com_mid) return "mid";
    return "bad";
  }
  function gradeEngagement(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= activeThresholdProfile.eng_good) return "good";
    if (x >= activeThresholdProfile.eng_mid) return "mid";
    return "bad";
  }
  function gradeViewsPerDay(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= activeThresholdProfile.vpd_good) return "good";
    if (x >= activeThresholdProfile.vpd_mid) return "mid";
    return "bad";
  }
  function gradeVph(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= activeThresholdProfile.vph_good) return "good";
    if (x >= activeThresholdProfile.vph_mid) return "mid";
    return "bad";
  }
  function gradeEngagementPerSub(x: number | null | undefined): MetricGrade {
    if (typeof x !== "number" || !Number.isFinite(x)) return "na";
    if (x >= activeThresholdProfile.engsub_good) return "good";
    if (x >= activeThresholdProfile.engsub_mid) return "mid";
    return "bad";
  }
  const savedById = useMemo(() => {
    const m = new Map<string, SavedChannelItem>();
    for (const c of savedChannels) m.set(c.channel_id, c);
    return m;
  }, [savedChannels]);

  const pearls = useMemo(() => savedChannels.filter((c) => !!c.is_pearl), [savedChannels]);

  const refreshSavedChannelVideos = useCallback(
    async (channelId: string) => {
      try {
        const r = await fetch(`/api/channels/${encodeURIComponent(channelId)}?videos_limit=100`);
        if (!r.ok) return;
        const j = (await r.json()) as { videos?: ChannelVideoItem[] };
        setSavedChannelVideos(j.videos || []);
        setSelectedVideoIds([]);
      } catch {
        /* ignore */
      }
    },
    []
  );

  // UX: when entering channel detail, scroll to top.
  useEffect(() => {
    if (!selectedSavedChannelId) return;
    try {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      window.scrollTo(0, 0);
    }
  }, [selectedSavedChannelId]);

  useEffect(() => {
    if (!selectedSavedChannel) return;
    setEditCat(selectedSavedChannel.internal_category || "");
    setEditLang(((selectedSavedChannel.language as "" | "es" | "en") || "") as "" | "es" | "en");
  }, [selectedSavedChannel]);

  const selectedChannelSyncState = useMemo(() => {
    const st = session?.status;
    if (!st || !selectedSavedChannelId) return null;
    const mentionsChannel = (st.detail || "").includes(selectedSavedChannelId);
    if (!mentionsChannel) return null;
    if (st.step === "channel_sync" || st.step === "channel_scan") return st;
    return null;
  }, [session?.status, selectedSavedChannelId]);

  const allVisibleVideoIds = useMemo(() => savedChannelVideos.slice(0, 100).map((v) => v.video_id), [savedChannelVideos]);
  const allSelected = useMemo(
    () => allVisibleVideoIds.length > 0 && allVisibleVideoIds.every((id) => selectedVideoIds.includes(id)),
    [allVisibleVideoIds, selectedVideoIds]
  );

  type PerlaGrade = "excelente" | "bueno" | "regular" | "malo" | "sin_datos";
  function gradeLabel(g: PerlaGrade): string {
    if (g === "excelente") return "Excelente";
    if (g === "bueno") return "Bueno";
    if (g === "regular") return "Regular";
    if (g === "malo") return "Malo";
    return "Sin datos";
  }

  function gradeClass(g: PerlaGrade): string {
    if (g === "excelente") return "border-emerald-200 bg-emerald-50 text-emerald-900";
    if (g === "bueno") return "border-emerald-100 bg-emerald-50/60 text-emerald-900";
    if (g === "regular") return "border-amber-200 bg-amber-50 text-amber-950";
    if (g === "malo") return "border-rose-200 bg-rose-50 text-rose-900";
    return "border-slate-200 bg-slate-50 text-slate-700";
  }

  function scorecard(saved: SavedChannelItem | undefined | null) {
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

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const id = setInterval(() => void refresh(), 2000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    void refreshPipeline();
    const id = setInterval(() => void refreshPipeline(), 2000);
    return () => clearInterval(id);
  }, [refreshPipeline]);

  const statusLine = useMemo(() => {
    if (!session) return "";
    const s = session.status;
    return `${s.state}${s.step ? ` · ${s.step}` : ""}${s.detail ? ` — ${s.detail}` : ""}`;
  }, [session]);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const sleep = useCallback((ms: number) => new Promise((r) => setTimeout(r, ms)), []);

  const fetchSession = useCallback(async (): Promise<Session | null> => {
    try {
      const r = await fetch(`/api/session?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) return null;
      return (await r.json()) as Session;
    } catch {
      return null;
    }
  }, [workApplied]);

  const waitForChannelJob = useCallback(
    async (step: "channel_sync" | "channel_backfill", channelId: string, timeoutMs: number = 120_000) => {
      const startedAt = Date.now();
      while (Date.now() - startedAt < timeoutMs) {
        await sleep(1000);
        const s = await fetchSession();
        if (!s?.status) continue;
        const st = s.status;
        const detail = String(st.detail || "");
        if (st.step === step && detail.includes(channelId) && (st.state === "done" || st.state === "error")) return st;
      }
      return null;
    },
    [fetchSession, sleep]
  );

  const waitForTask = useCallback(
    async (taskId: string, timeoutMs: number = 180_000) => {
      const startedAt = Date.now();
      while (Date.now() - startedAt < timeoutMs) {
        await sleep(1200);
        const r = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`);
        if (!r.ok) continue;
        const j = (await r.json()) as TaskStatus;
        const st = String(j.state || "").toLowerCase();
        if (st === "success" || st === "failure") return j;
      }
      return null;
    },
    [sleep]
  );

  useEffect(() => {
    setScriptEditorOpen(false);
  }, [workApplied]);

  const openScriptEditor = async () => {
    setErr(null);
    try {
      const r = await fetch(`/api/script?work=${encodeURIComponent(workApplied)}`);
      if (!r.ok) throw new Error(await readApiError(r));
      const j = (await r.json()) as { text: string };
      setScriptEditText(j.text);
      setScriptEditorOpen(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        session={session}
        statusLine={statusLine}
        work={work}
        setWork={setWork}
        applyWork={() => setWorkApplied(work.trim() || "output/ui_session")}
      />

      <main className="min-h-screen pl-[280px]">
        <div className="p-6">
          {err ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">{err}</div>
          ) : null}
          {busy ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">Enviando: {busy}…</div>
          ) : null}

          {activeTab === "analyze" ? (
            <Card title="Analyse" subtitle="Dashboard minimalista para buscar y sincronizar información de YouTube.">
              <div className="rounded-2xl border border-slate-200 bg-white p-2">
                <div className="grid grid-cols-2 gap-2">
                  <Btn
                    className={`${
                      analyzePanel === "search"
                        ? "bg-slate-900 text-white hover:bg-slate-800"
                        : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                    }`}
                    onClick={() => setAnalyzePanel("search")}
                  >
                    Buscar canal
                  </Btn>
                  <Btn
                    className={`${
                      analyzePanel === "saved"
                        ? "bg-slate-900 text-white hover:bg-slate-800"
                        : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                    }`}
                    onClick={() => {
                      setAnalyzePanel("saved");
                      void refreshSavedChannels();
                    }}
                  >
                    Canales guardados
                  </Btn>
                </div>
              </div>

              <div className="h-px w-full bg-slate-100" />

              {analyzePanel === "search" ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Buscador de canales</div>
                    <p className="mt-0.5 text-xs text-slate-500">Busca en YouTube por nombre y filtra por subs/views.</p>
                  </div>
                  <Btn
                    className="bg-emerald-600 text-white hover:bg-emerald-700"
                    disabled={!channelSearchQ.trim()}
                    onClick={() =>
                      run("Buscar canales", async () => {
                        const qs = new URLSearchParams({
                          q: channelSearchQ.trim(),
                          min_subs: String(channelMinSubs || 0),
                          min_views: String(channelMinViews || 0),
                          category: channelCategory.trim(),
                          language: channelLang,
                          sort: channelSort,
                          limit: "12",
                        });
                        const r = await fetch(`/api/channels/search?${qs.toString()}`);
                        if (!r.ok) throw new Error(await readApiError(r));
                        const j = (await r.json()) as { channels: ChannelSearchItem[] };
                        const chans = j.channels || [];
                        setChannelSearchResults(chans);

                        // No auto-scan here: avoid quota usage.
                        await refreshSavedChannels();
                      })
                    }
                  >
                    Buscar
                  </Btn>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-6">
                  <div className="md:col-span-2">
                    <Label>Nombre / keyword</Label>
                    <Input value={channelSearchQ} onChange={(e) => setChannelSearchQ(e.target.value)} placeholder="Deep Made Simple" />
                  </div>
                  <div>
                    <Label>Min subs</Label>
                    <Input type="number" min={0} value={channelMinSubs} onChange={(e) => setChannelMinSubs(Number(e.target.value))} />
                  </div>
                  <div>
                    <Label>Min views</Label>
                    <Input type="number" min={0} value={channelMinViews} onChange={(e) => setChannelMinViews(Number(e.target.value))} />
                  </div>
                  <div>
                    <Label>Idioma</Label>
                    <Select value={channelLang} onChange={(e) => setChannelLang(e.target.value as "" | "es" | "en")}>
                      <option value="">Cualquiera</option>
                      <option value="es">ES</option>
                      <option value="en">EN</option>
                    </Select>
                  </div>
                  <div className="md:col-span-2">
                    <Label>Categoría interna</Label>
                    <Input value={channelCategory} onChange={(e) => setChannelCategory(e.target.value)} placeholder="Fitness / Finanzas / Motivación..." />
                    <p className="mt-1 text-[10px] text-slate-500">Se aplica solo a canales ya guardados (perlas) con categoría asignada.</p>
                  </div>
                  <div>
                    <Label>Ordenar por</Label>
                    <Select
                      value={channelSort}
                      onChange={(e) =>
                        setChannelSort(e.target.value as "subs" | "views" | "videos" | "views_per_video" | "views_per_sub")
                      }
                    >
                      <option value="subs">Suscriptores</option>
                      <option value="views">Visitas</option>
                      <option value="videos">Nº vídeos</option>
                      <option value="views_per_video">Views / vídeo</option>
                      <option value="views_per_sub">Views / sub</option>
                    </Select>
                  </div>
                </div>

                {channelSearchResults.length ? (
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                      {channelSearchResults.map((c) => (
                        (() => {
                          const saved = savedById.get(c.channel_id);
                          return (
                        <button
                          key={c.channel_id}
                          type="button"
                          onClick={() => setSelectedChannel(c)}
                          className={`flex w-full items-center gap-3 rounded-2xl border px-3 py-2 text-left transition ${
                            selectedChannel?.channel_id === c.channel_id
                              ? "border-emerald-200 bg-emerald-50"
                              : "border-slate-200 bg-white hover:bg-slate-50"
                          }`}
                        >
                          <div className="h-10 w-10 overflow-hidden rounded-xl bg-slate-100">
                            {c.avatar_url ? <img src={c.avatar_url} alt="" className="h-10 w-10 object-cover" /> : null}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-semibold text-slate-900">{c.title}</div>
                            <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-slate-500">
                              <span className="font-mono">{c.channel_id}</span>
                              {typeof c.subscribers === "number" ? <span>· subs {c.subscribers}</span> : null}
                              {typeof c.total_views === "number" ? <span>· views {c.total_views}</span> : null}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {saved?.is_pearl ? (
                                <>
                                  <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                                    score {typeof saved.opportunity_score === "number" ? saved.opportunity_score.toFixed(2) : "—"}
                                  </span>
                                  <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                                    Δ30d views {fmtK(saved.views_delta_30d)}
                                  </span>
                                  <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                                    median {fmtK(saved.median_views)}
                                  </span>
                                  <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                                    hit {fmtPct(saved.hit_rate)}
                                  </span>
                                  <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700">
                                    up/mo {typeof saved.uploads_per_month_90d === "number" ? saved.uploads_per_month_90d.toFixed(1) : "—"}
                                  </span>
                                </>
                              ) : (
                                <span className="rounded-lg border border-slate-200 bg-white px-2 py-0.5 text-[10px] text-slate-500">
                                  sin métricas (marca perla + Sync)
                                </span>
                              )}
                            </div>
                          </div>
                        </button>
                          );
                        })()
                      ))}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="h-12 w-12 overflow-hidden rounded-2xl bg-slate-100">
                            {selectedChannel?.avatar_url ? <img src={selectedChannel.avatar_url} alt="" className="h-12 w-12 object-cover" /> : null}
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-slate-900">{selectedChannel?.title || "Selecciona un canal"}</div>
                            <div className="mt-0.5 text-[11px] text-slate-500 font-mono">{selectedChannel?.channel_id || ""}</div>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Btn
                            className="bg-slate-900 text-white hover:bg-slate-800"
                            disabled={!selectedChannel}
                            onClick={() =>
                              run("Guardar canal", async () => {
                                if (!selectedChannel) return;
                                await postJson(`/api/channels/save`, {
                                  channel_id: selectedChannel.channel_id,
                                  handle: selectedChannel.handle || "",
                                  title: selectedChannel.title || "",
                                  avatar_url: selectedChannel.avatar_url || "",
                                  description: selectedChannel.description || "",
                                });
                                await refreshSavedChannels();
                              })
                            }
                          >
                            Guardar
                          </Btn>
                          <Btn
                            className="bg-emerald-600 text-white hover:bg-emerald-700"
                            disabled={!selectedChannel}
                            onClick={() =>
                              run("Guardar como perla + Sync", async () => {
                                if (!selectedChannel) return;
                                await postJson(`/api/channels/save`, {
                                  channel_id: selectedChannel.channel_id,
                                  handle: selectedChannel.handle || "",
                                  title: selectedChannel.title || "",
                                  avatar_url: selectedChannel.avatar_url || "",
                                  description: selectedChannel.description || "",
                                });
                                await postJson(`/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/sync`, {
                                  work: workApplied,
                                });
                                await refreshSavedChannels();
                              })
                            }
                          >
                            Guardar + Sync
                          </Btn>
                          {selectedChannel ? (
                            <a
                              className="inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50"
                              href={`https://www.youtube.com/channel/${encodeURIComponent(selectedChannel.channel_id)}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open on YouTube
                            </a>
                          ) : null}
                        </div>
                      </div>

                      <div className="mt-4 grid gap-2 sm:grid-cols-2 text-xs text-slate-600">
                        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Subs</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">{selectedChannel?.subscribers ?? "—"}</div>
                        </div>
                        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Views</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">{selectedChannel?.total_views ?? "—"}</div>
                        </div>
                      </div>

                      <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Checklist Perla</div>
                            <div className="mt-1 text-sm font-semibold text-slate-900">
                              {(() => {
                                const saved = selectedChannel ? savedById.get(selectedChannel.channel_id) : null;
                                return scorecard(saved).decision;
                              })()}
                            </div>
                          </div>
                          <div className="text-[11px] text-slate-500">Regla: perla si 3/4 (mediana+hit+comentarios+uploads) salen bien.</div>
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          {(() => {
                            const saved = selectedChannel ? savedById.get(selectedChannel.channel_id) : null;
                            const sc = scorecard(saved);
                            return sc.rows.map((r) => (
                              <div key={r.k} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="text-[11px] font-semibold text-slate-700">{r.k}</div>
                                  <span className={`rounded-lg border px-2 py-0.5 text-[10px] ${gradeClass(r.g)}`}>{gradeLabel(r.g)}</span>
                                </div>
                                <div className="mt-1 text-sm font-semibold text-slate-900">{r.v}</div>
                                <div className="mt-0.5 text-[10px] text-slate-500">{r.rule}</div>
                              </div>
                            ));
                          })()}
                        </div>
                        <p className="mt-3 text-xs text-slate-500">
                          Para ver métricas, primero marca el canal como perla y ejecuta <b>Guardar + Sync</b>.
                        </p>
                      </div>
                      <p className="mt-3 text-xs text-slate-500">
                        Monetización/RPM: se estimará y se podrá editar cuando implementemos el directorio completo.
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Btn
                          className="bg-emerald-600 text-white hover:bg-emerald-700"
                          disabled={!selectedChannel}
                          onClick={() =>
                            run("Sync now", async () => {
                              if (!selectedChannel) return;
                              await postJson(`/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/sync`, {
                                work: workApplied,
                              });
                              await refreshSavedChannels();
                            })
                          }
                        >
                          Sync now
                        </Btn>
                        <a
                          className={`inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50 ${
                            selectedChannel ? "" : "pointer-events-none opacity-50"
                          }`}
                          href={
                            selectedChannel
                              ? `/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/thumbnails.zip?work=${encodeURIComponent(workApplied)}`
                              : "#"
                          }
                        >
                          Download thumbnails zip
                        </a>
                        <a
                          className={`inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50 ${
                            selectedChannel ? "" : "pointer-events-none opacity-50"
                          }`}
                          href={
                            selectedChannel
                              ? `/api/channels/${encodeURIComponent(selectedChannel.channel_id)}/scripts.zip?work=${encodeURIComponent(workApplied)}`
                              : "#"
                          }
                        >
                          Download scripts zip
                        </a>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
              ) : null}

              {analyzePanel === "saved" ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">Canales guardados</div>
                      <p className="mt-0.5 text-xs text-slate-500">Directorio interno (Postgres). Selecciona un canal para sincronizar o descargar ZIPs.</p>
                    </div>
                    <Btn
                      className="bg-slate-900 text-white hover:bg-slate-800"
                      onClick={() =>
                        run("Refrescar guardados", async () => {
                          await refreshSavedChannels();
                        })
                      }
                    >
                      Refrescar
                    </Btn>
                  </div>

                  <div className="mt-3 grid gap-3 md:grid-cols-6">
                    <div className="md:col-span-2">
                      <Label>Buscar</Label>
                      <Input value={savedQ} onChange={(e) => setSavedQ(e.target.value)} placeholder="motivación, hábitos, fitness..." />
                    </div>
                    <div>
                      <Label>Categoría</Label>
                      <Input value={savedCategory} onChange={(e) => setSavedCategory(e.target.value)} placeholder="Tecnología" />
                    </div>
                    <div className="md:col-span-2">
                      <Label>Ordenar por</Label>
                      <Select value={savedSort} onChange={(e) => setSavedSort(e.target.value as typeof savedSort)}>
                        <option value="opportunity">Opportunity score</option>
                        <option value="views_delta_30d">Views Δ 30d</option>
                        <option value="subs_delta_30d">Subs Δ 30d</option>
                        <option value="median_views">Mediana views (N=50)</option>
                        <option value="hit_rate">Hit-rate (&gt;=X)</option>
                        <option value="engagement">Engagement (com/1k)</option>
                        <option value="uploads_per_month">Uploads / mes</option>
                        <option value="days_since_upload">Días desde upload</option>
                        <option value="views_per_sub">Views / sub</option>
                      </Select>
                    </div>
                    <div>
                      <Label>Hit X views</Label>
                      <Input
                        type="number"
                        min={1000}
                        step={1000}
                        value={savedHitViewsThreshold}
                        onChange={(e) => setSavedHitViewsThreshold(Number(e.target.value))}
                      />
                    </div>
                    <div>
                      <Label>Min subs</Label>
                      <Input type="number" min={0} value={savedMinSubs} onChange={(e) => setSavedMinSubs(Number(e.target.value))} />
                    </div>
                    <div>
                      <Label>Min views</Label>
                      <Input type="number" min={0} value={savedMinViews} onChange={(e) => setSavedMinViews(Number(e.target.value))} />
                    </div>
                    <div>
                      <Label>Min uploads/mes</Label>
                      <Input
                        type="number"
                        min={0}
                        step={0.5}
                        value={savedMinUploadsMonth}
                        onChange={(e) => setSavedMinUploadsMonth(Number(e.target.value))}
                      />
                    </div>
                    <div>
                      <Label>Min views/sub</Label>
                      <Input
                        type="number"
                        min={0}
                        step={0.5}
                        value={savedMinViewsPerSub}
                        onChange={(e) => setSavedMinViewsPerSub(Number(e.target.value))}
                      />
                    </div>
                    <div>
                      <Label>Min hit-rate %</Label>
                      <Input type="number" min={0} max={100} value={savedMinHitRate} onChange={(e) => setSavedMinHitRate(Number(e.target.value))} />
                    </div>
                    <div className="md:col-span-6">
                      <Btn
                        className="bg-emerald-600 text-white hover:bg-emerald-700"
                        onClick={() =>
                          run("Aplicar filtros", async () => {
                            await refreshSavedChannels();
                          })
                        }
                      >
                        Aplicar
                      </Btn>
                    </div>
                  </div>

                  <div className="mt-3">
                    {!selectedSavedChannelId ? (
                      <div className="space-y-2">
                        {pearls.length ? (
                          pearls.map((c) => (
                            <button
                              key={c.channel_id}
                              type="button"
                              onClick={() => {
                                setSelectedSavedChannelId(c.channel_id);
                                void refreshSavedChannelVideos(c.channel_id);
                              }}
                              className="flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left transition hover:bg-slate-50"
                            >
                              <div className="h-10 w-10 overflow-hidden rounded-xl bg-slate-100">
                                {c.avatar_url ? <img src={c.avatar_url} alt="" className="h-10 w-10 object-cover" /> : null}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="truncate text-sm font-semibold text-slate-900">{c.title || c.channel_id}</div>
                                <div className="mt-0.5 text-[10px] text-slate-500 font-mono">{c.channel_id}</div>
                                {c.internal_category ? <div className="mt-0.5 text-[10px] text-slate-500">cat: {c.internal_category}</div> : null}
                              </div>
                            </button>
                          ))
                        ) : (
                          <p className="text-sm text-slate-600">No hay canales guardados todavía.</p>
                        )}
                      </div>
                    ) : (
                      <SavedChannelDetail
                        selectedSavedChannelId={selectedSavedChannelId}
                        selectedSavedChannel={selectedSavedChannel}
                        selectedChannelSyncState={selectedChannelSyncState}
                        workApplied={workApplied}
                        editCat={editCat}
                        setEditCat={setEditCat}
                        editLang={editLang}
                        setEditLang={setEditLang}
                        CATEGORY_OPTIONS={CATEGORY_OPTIONS}
                        savedChannelVideos={savedChannelVideos}
                        selectedVideoIds={selectedVideoIds}
                        setSelectedVideoIds={setSelectedVideoIds}
                        allSelected={allSelected}
                        allVisibleVideoIds={allVisibleVideoIds}
                        opportunityGrade={opportunityGrade}
                        opportunityLabel={opportunityLabel}
                        opportunityPillClass={opportunityPillClass}
                        fmtK={fmtK}
                        metricPill={metricPill}
                        gradeViewsPerDay={gradeViewsPerDay}
                        gradeVph={gradeVph}
                        gradeEngagement={gradeEngagement}
                        gradeLikeRate={gradeLikeRate}
                        gradeCommentRate={gradeCommentRate}
                        gradeEngagementPerSub={gradeEngagementPerSub}
                        onBack={() => {
                          setSelectedSavedChannelId(null);
                          setSavedChannelVideos([]);
                        }}
                        onRefresh={() =>
                          run("Refrescar canal", async () => {
                            await refreshSavedChannels();
                            await refreshSavedChannelVideos(selectedSavedChannelId);
                          })
                        }
                        onSaveClassification={() =>
                          run("Guardar clasificación", async () => {
                            await putJson(`/api/channels/${encodeURIComponent(selectedSavedChannelId)}`, {
                              internal_category: editCat || null,
                              language: editLang || null,
                            });
                            await refreshSavedChannels();
                          })
                        }
                        onSyncNow={() =>
                          run("Sync canal", async () => {
                            const res = await postJson<{ mode?: string; task_id?: string }>(
                              `/api/channels/${encodeURIComponent(selectedSavedChannelId)}/sync`,
                              { work: workApplied }
                            );
                            if (res?.mode === "celery" && res.task_id) {
                              await waitForTask(res.task_id, 240_000);
                            } else {
                              await waitForChannelJob("channel_sync", selectedSavedChannelId, 240_000);
                            }
                            await refreshSavedChannels();
                            await refreshSavedChannelVideos(selectedSavedChannelId);
                          })
                        }
                        onBackfill={() =>
                          run("Backfill desc/tags", async () => {
                            await postJson(`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/backfill`, { work: workApplied, limit: 200 });
                            await waitForChannelJob("channel_backfill", selectedSavedChannelId, 180_000);
                            await refreshSavedChannelVideos(selectedSavedChannelId);
                          })
                        }
                        onDownloadTranscriptsJson={() =>
                          run("Descargar transcripts JSON", async () => {
                            const ids = selectedVideoIds.length ? selectedVideoIds : [];
                            const r = await fetch(`/api/channels/${encodeURIComponent(selectedSavedChannelId)}/transcripts.json`, {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ work: workApplied, video_ids: ids, limit: 50, lang: editLang || "es" }),
                            });
                            if (!r.ok) return;
                            const text = await r.text();
                            const blob = new Blob([text], { type: "application/json" });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `transcripts_${selectedSavedChannelId}.json`;
                            document.body.appendChild(a);
                            a.click();
                            a.remove();
                            URL.revokeObjectURL(url);
                          })
                        }
                      />
                    )}
                  </div>
                </div>
              ) : null}
            </Card>
          ) : null}

          {activeTab === "create" ? (
            <Card title="Create · Pipeline" subtitle="Ejecuta la pipeline por pasos (nuevo flujo).">
              <div className="flex flex-wrap items-center gap-2">
                <Btn
                  className="bg-emerald-600 text-white hover:bg-emerald-700"
                  onClick={() =>
                    run("Start pipeline", async () => {
                      await postJson(`/api/pipeline/start`, { work: workApplied, keywords: kw, context: ctx, lang, minutes, provider, model });
                      await refreshPipeline();
                    })
                  }
                >
                  Start
                </Btn>
                <Btn className="bg-slate-900 text-white hover:bg-slate-800" onClick={() => run("Refresh pipeline", async () => refreshPipeline())}>
                  Refresh
                </Btn>
                {pipelineState?.last_error ? <span className="text-sm text-rose-700">Error: {pipelineState.last_error}</span> : null}
              </div>

              <div className="mt-3 space-y-2">
                {(pipelineState?.steps ?? []).length ? (
                  <ul className="space-y-2">
                    {pipelineState!.steps.map((st) => (
                      <li key={st.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <div className="text-sm font-semibold text-slate-900">{st.title}</div>
                            <div className="mt-0.5 text-xs text-slate-500">{st.detail || st.id}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <StatusBadge state={st.state} />
                            <Btn
                              className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                              onClick={() =>
                                run(`Re-run ${st.id}`, async () => {
                                  await postJson(`/api/pipeline/step/rerun`, { work: workApplied, step_id: st.id });
                                  await refreshPipeline();
                                })
                              }
                            >
                              Re-run
                            </Btn>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-slate-600">Pipeline aún no iniciada. Pulsa Start.</p>
                )}
              </div>
            </Card>
          ) : null}

          <div className={activeTab === "create" ? "space-y-6" : "hidden"}>
          <Card
            title="1 · Guion"
            subtitle="Keywords + LLM (OpenAI compatible u Ollama según .env). Los minutos son una referencia orientativa, no un límite rígido."
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label>Keywords (separadas por coma)</Label>
                <Input value={kw} onChange={(e) => setKw(e.target.value)} />
              </div>
              <div className="sm:col-span-2">
                <Label>Contexto</Label>
                <TextArea value={ctx} onChange={(e) => setCtx(e.target.value)} />
              </div>
              <div>
                <Label>Idioma</Label>
                <Select value={lang} onChange={(e) => setLang(e.target.value)}>
                  <option value="es">es</option>
                  <option value="en">en</option>
                </Select>
              </div>
              <div>
                <Label>Duración orientativa (min)</Label>
                <Input type="number" step={0.5} min={1} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
                <p className="mt-1 text-[11px] leading-snug text-slate-500">
                  Guía orientativa (~10 min de narración / tres actos); el modelo prioriza ~1 500 palabras y estructura en prompts.
                </p>
              </div>
              <div>
                <Label>Proveedor (vacío = .env)</Label>
                <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  <option value="">(usar .env)</option>
                  <option value="ollama">ollama</option>
                  <option value="openai">openai-compatible</option>
                </Select>
              </div>
              <div>
                <Label>Modelo (opcional)</Label>
                <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4o-mini / llama3.2:latest" />
              </div>
            </div>

            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4">
              <Label>Plantillas de prompt (ampliación opcional)</Label>
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Se añaden al system y user que ya genera Videomaker (tres actos, B-roll, etc.). Úsalas para refinar sin
                reemplazar la base. Las plantillas se guardan en la raíz del repo:{" "}
                <code className="rounded bg-white px-1">prompt_presets.json</code>.
              </p>
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <div className="min-w-[220px] flex-1">
                  <Label>Seleccionar plantilla</Label>
                  <Select
                    value={promptSelectedId ?? ""}
                    disabled={!!busy}
                    onChange={async (e) => {
                      const id = e.target.value;
                      setErr(null);
                      try {
                        if (!id) {
                          setPromptSelectedId(null);
                          setPromptSystemExtra("");
                          setPromptUserExtra("");
                          await postJson("/api/prompt-preset/select", { id: null });
                          return;
                        }
                        const pr = await fetch(`/api/prompt-preset?preset_id=${encodeURIComponent(id)}`);
                        if (!pr.ok) throw new Error(await readApiError(pr));
                        const p = (await pr.json()) as { system_extra?: string; user_extra?: string };
                        setPromptSelectedId(id);
                        setPromptSystemExtra(p.system_extra ?? "");
                        setPromptUserExtra(p.user_extra ?? "");
                        await postJson("/api/prompt-preset/select", { id });
                      } catch (ex) {
                        setErr(ex instanceof Error ? ex.message : String(ex));
                      }
                    }}
                  >
                    <option value="">— Solo prompt por defecto —</option>
                    {promptPresets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Btn
                    className="bg-white px-3 py-1.5 text-xs font-medium text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                    disabled={!!busy || !newPresetName.trim()}
                    onClick={() =>
                      run("guardar plantilla", async () => {
                        await postJson("/api/prompt-preset", {
                          name: newPresetName.trim(),
                          system_extra: promptSystemExtra,
                          user_extra: promptUserExtra,
                        });
                        setNewPresetName("");
                        await loadPromptPresets();
                      })
                    }
                  >
                    Guardar como nueva
                  </Btn>
                  <Btn
                    className="bg-white px-3 py-1.5 text-xs font-medium text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-40"
                    disabled={!!busy || !promptSelectedId}
                    onClick={() =>
                      run("actualizar plantilla", async () => {
                        await putJson("/api/prompt-preset", {
                          id: promptSelectedId,
                          system_extra: promptSystemExtra,
                          user_extra: promptUserExtra,
                        });
                        await loadPromptPresets();
                      })
                    }
                  >
                    Actualizar seleccionada
                  </Btn>
                  <Btn
                    className="bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-900 ring-1 ring-rose-200 hover:bg-rose-100 disabled:opacity-40"
                    disabled={!!busy || !promptSelectedId}
                    onClick={() =>
                      run("eliminar plantilla", async () => {
                        if (!promptSelectedId || !confirm("¿Eliminar esta plantilla de prompt?")) return;
                        await deleteReq(`/api/prompt-preset?preset_id=${encodeURIComponent(promptSelectedId)}`);
                        setPromptSelectedId(null);
                        setPromptSystemExtra("");
                        setPromptUserExtra("");
                        await loadPromptPresets();
                      })
                    }
                  >
                    Eliminar
                  </Btn>
                </div>
              </div>
              <div className="mt-2">
                <Label>Nombre para “Guardar como nueva”</Label>
                <Input
                  value={newPresetName}
                  onChange={(e) => setNewPresetName(e.target.value)}
                  placeholder="Ej. YouTube largo · B-roll cada 2 frases"
                  className="max-w-xl"
                />
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <Label>Texto extra → system</Label>
                  <textarea
                    value={promptSystemExtra}
                    onChange={(e) => setPromptSystemExtra(e.target.value)}
                    spellCheck={lang === "es"}
                    className="mt-1 min-h-[140px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-relaxed text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/25"
                  />
                </div>
                <div>
                  <Label>Texto extra → user</Label>
                  <textarea
                    value={promptUserExtra}
                    onChange={(e) => setPromptUserExtra(e.target.value)}
                    spellCheck={lang === "es"}
                    className="mt-1 min-h-[140px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-relaxed text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/25"
                  />
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Btn
                className="bg-slate-200 text-slate-900 hover:bg-slate-300"
                disabled={!!busy}
                title="Construye los prompts en el servidor y los muestra. No llama al LLM ni escribe archivos."
                onClick={() =>
                  run("prompt", async () => {
                    const j = await postJson<{ system: string; user: string }>("/api/prompt-preview", {
                      work: workApplied,
                      keywords: kw,
                      context: ctx,
                      lang,
                      minutes,
                      system_extra: promptSystemExtra,
                      user_extra: promptUserExtra,
                    });
                    setPromptData(j);
                    setPromptOpen(true);
                  })
                }
              >
                Previsualizar prompt
              </Btn>
              <Btn
                className="bg-emerald-600 text-white hover:bg-emerald-500"
                disabled={!!busy}
                onClick={() =>
                  run("guion", async () => {
                    await postJson("/api/generate-script", {
                      work: workApplied,
                      keywords: kw,
                      context: ctx,
                      lang,
                      minutes,
                      provider,
                      model,
                      system_extra: promptSystemExtra,
                      user_extra: promptUserExtra,
                    });
                  })
                }
              >
                Generar guion.txt
              </Btn>
              {session?.has_script ? (
                <Btn
                  className="bg-white text-slate-900 ring-2 ring-emerald-500/40 hover:bg-emerald-50"
                  disabled={!!busy}
                  onClick={() => void openScriptEditor()}
                >
                  Ver y editar guion
                </Btn>
              ) : null}
            </div>
            <p className="mt-3 text-xs leading-relaxed text-slate-500">
              <span className="font-semibold text-slate-600">Previsualizar prompt:</span> muestra los textos <em>system</em> y{" "}
              <em>user</em> que se mandarían al modelo (según keywords, contexto, idioma y minutos).{" "}
              <strong>No consume API</strong> ni crea <code className="rounded bg-slate-100 px-1">guion.txt</code>. Sirve para revisar instrucciones antes de gastar tokens.
            </p>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              <span className="font-semibold text-slate-600">Página HTML clásica:</span> abre el guion en una pestaña aparte, solo lectura, útil si prefieres copiar con formato simple.{" "}
              <button
                type="button"
                className="font-medium text-emerald-700 underline decoration-emerald-300 underline-offset-2 hover:text-emerald-900"
                disabled={!session?.has_script}
                onClick={() => window.open(`/view-script?work=${encodeURIComponent(workApplied)}`, "_blank")}
              >
                Abrir vista solo lectura
              </button>
              {!session?.has_script ? <span className="text-slate-400"> (genera un guion antes)</span> : null}
            </p>
            {scriptEditorOpen ? (
              <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-800">Editor · guion.txt</span>
                  <Btn className="bg-white px-2 py-1 text-xs text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setScriptEditorOpen(false)}>
                    Cerrar
                  </Btn>
                </div>
                <textarea
                  value={scriptEditText}
                  onChange={(e) => setScriptEditText(e.target.value)}
                  spellCheck={lang === "es"}
                  className="mt-3 min-h-[280px] w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-relaxed text-slate-900 shadow-inner outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/25"
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <Btn
                    className="bg-emerald-600 text-white hover:bg-emerald-500"
                    disabled={!!busy}
                    onClick={() =>
                      run("guardar guion", async () => {
                        await putJson("/api/script", { work: workApplied, text: scriptEditText });
                        await refresh();
                        setScriptEditorOpen(false);
                      })
                    }
                  >
                    Guardar cambios
                  </Btn>
                  <span className="self-center text-[11px] text-slate-500">Se guarda en la carpeta de trabajo como guion.txt</span>
                </div>
              </div>
            ) : null}
          </Card>

          <Card title="2 · Voz (XTTS + clon)" subtitle="Sube MP3/WAV; prueba en Voice Lab; luego narración completa.">
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-sm text-emerald-950">
              Con muestra subida, elige preset <code className="rounded bg-white/80 px-1">xtts_v2_es</code> o{" "}
              <code className="rounded bg-white/80 px-1">xtts_v2_en</code> para clonar.
            </div>
            <details className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2 text-xs text-slate-700">
              <summary className="cursor-pointer font-medium text-slate-800">Mejor clonación (XTTS no es magia)</summary>
              <ul className="mt-2 list-inside list-disc space-y-1.5 text-slate-600">
                <li>
                  Grabación limpia: <strong>sin música ni reverberación fuerte</strong>, una sola voz, ~15–60&nbsp;s suele bastar.
                </li>
                <li>
                  El idioma del <strong>texto generado</strong> debe coincidir con el preset (es/en); si no, el acento suena raro.
                </li>
                <li>
                  Tras subir un MP3 nuevo, la app recorta silencios y normaliza un poco el WAV; si sigue flojo, prueba un WAV más limpio o GPU (
                  <code className="rounded bg-white px-1">TTS_USE_GPU</code> si tienes CUDA).
                </li>
                <li>
                  Ajustes finos del modelo: variables <code className="rounded bg-white px-1">VIDEOMAKER_XTTS_*</code> en{" "}
                  <code className="rounded bg-white px-1">.env</code> (ver <code className="rounded bg-white px-1">.env.example</code>).
                </li>
              </ul>
            </details>
            <div>
              <Label>Archivo de voz (MP3, WAV, …)</Label>
              <input
                type="file"
                accept="audio/*,.mp3,.wav,.m4a"
                className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-white hover:file:bg-slate-800"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (!f) return;
                  await run("subir clon", async () => {
                    const fd = new FormData();
                    fd.append("work", workApplied);
                    fd.append("file", f);
                    const r = await fetch("/api/upload-voice-clone", { method: "POST", body: fd });
                    if (!r.ok) throw new Error(await r.text());
                  });
                }}
              />
            </div>
            {session?.has_clone_reference ? (
              <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-slate-500">Muestra activa</div>
                  <audio className="mt-2 w-full" controls src={session.urls.clone_reference} />
                </div>
                <Btn
                  className="shrink-0 bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50"
                  disabled={!!busy}
                  onClick={() =>
                    run("quitar clon", async () => {
                      await postJson("/api/clear-voice-clone", { work: workApplied });
                    })
                  }
                >
                  Quitar clon
                </Btn>
              </div>
            ) : null}
            <div className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label>Voz (preset)</Label>
                <Select value={preset} onChange={(e) => setPreset(e.target.value)}>
                  {session?.voice_presets.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  )) ?? null}
                </Select>
              </div>
              <div className="sm:col-span-2">
                <Label>Texto de prueba</Label>
                <Input value={previewText} onChange={(e) => setPreviewText(e.target.value)} />
              </div>
              <Btn
                className="bg-slate-900 text-white hover:bg-slate-800 sm:col-span-2"
                disabled={!!busy}
                onClick={() =>
                  run("voice preview", async () => {
                    await postJson("/api/voice-preview", { work: workApplied, preset, text: previewText });
                  })
                }
              >
                Generar muestra de voz
              </Btn>
            </div>
            {session && session.voice_previews.length > 0 ? (
              <div className="space-y-3 border-t border-slate-100 pt-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Muestras recientes</div>
                  <Btn
                    className="bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-900 ring-1 ring-rose-200 hover:bg-rose-100"
                    disabled={!!busy}
                    onClick={() =>
                      run("borrar muestras", async () => {
                        if (!confirm("¿Eliminar todas las muestras de voz (preview_voice*.wav) en esta sesión?")) return;
                        await deleteReq(`/api/voice-previews?work=${encodeURIComponent(workApplied)}`);
                        await refresh();
                      })
                    }
                  >
                    Eliminar todas las muestras
                  </Btn>
                </div>
                {[...session.voice_previews].reverse().map((v) => (
                  <div key={v.name} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <code className="min-w-0 flex-1 break-all text-[11px] text-slate-600">{v.name}</code>
                      <Btn
                        className="shrink-0 bg-white px-2 py-1 text-[11px] text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100"
                        disabled={!!busy}
                        onClick={() =>
                          run("borrar muestra", async () => {
                            await deleteReq(
                              `/api/voice-preview?work=${encodeURIComponent(workApplied)}&name=${encodeURIComponent(v.name)}`,
                            );
                            await refresh();
                          })
                        }
                      >
                        Eliminar
                      </Btn>
                    </div>
                    <audio className="mt-2 w-full" controls src={v.url} />
                  </div>
                ))}
              </div>
            ) : null}
            <div className="border-t border-slate-100 pt-4">
              <Label>Voz para narración completa (guion → narracion.wav)</Label>
              <p className="mt-1 text-[11px] leading-snug text-slate-500">
                Solo afecta la narración larga. “Automático” usa el clon subido si existe; puedes forzar una muestra de prueba concreta.
              </p>
              <Select
                className="mt-2"
                disabled={!session || !!busy}
                value={
                  session?.tts_reference?.mode === "preview" && session.tts_reference.preview_filename
                    ? session.tts_reference.preview_filename
                    : session?.tts_reference?.mode ?? "auto"
                }
                onChange={async (e) => {
                  const v = e.target.value;
                  setErr(null);
                  try {
                    if (v === "auto" || v === "clone" || v === "builtin") {
                      await postJson("/api/tts-reference", { work: workApplied, mode: v });
                    } else {
                      await postJson("/api/tts-reference", {
                        work: workApplied,
                        mode: "preview",
                        preview_filename: v,
                      });
                    }
                    await refresh();
                  } catch (err) {
                    setErr(err instanceof Error ? err.message : String(err));
                  }
                }}
              >
                <option value="auto">Automático — clon si hay muestra subida; si no, voz integrada</option>
                <option value="clone" disabled={!session?.has_clone_reference}>
                  Solo clon (clone_reference.wav){!session?.has_clone_reference ? " — sube un clon antes" : ""}
                </option>
                <option value="builtin">Solo voz integrada del modelo (sin clon ni muestra)</option>
                {session?.voice_previews.map((v) => (
                  <option key={v.name} value={v.name}>
                    Muestra: {v.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <div>
                <Label>Máx. caracteres por fragmento</Label>
                <Input type="number" value={maxChars} onChange={(e) => setMaxChars(Number(e.target.value))} />
              </div>
              <div>
                <Label>Máx. fragmentos (0 = todos)</Label>
                <Input type="number" value={maxSeg} onChange={(e) => setMaxSeg(Number(e.target.value))} />
              </div>
              <Btn
                className="bg-emerald-600 text-white hover:bg-emerald-500 sm:col-span-2"
                disabled={!!busy || !session?.has_script}
                onClick={() =>
                  run("narración", async () => {
                    await postJson("/api/speak-script", {
                      work: workApplied,
                      preset,
                      max_chars: maxChars,
                      max_segments: maxSeg,
                    });
                  })
                }
              >
                Generar narracion.wav
              </Btn>
            </div>
            {session && (session.narration_versions?.length ?? 0) > 0 ? (
              <div className="space-y-3 border-t border-slate-100 pt-4">
                <div>
                  <Label>Versión para stock y render</Label>
                  <p className="mt-1 text-[11px] leading-snug text-slate-500">
                    El render y la descarga de stock usan siempre <code className="rounded bg-slate-100 px-1">narracion.wav</code>; aquí eliges qué generación se copia ahí.
                  </p>
                  <Select
                    className="mt-2"
                    disabled={!!busy}
                    value={
                      session.active_narration ??
                      session.narration_versions?.find((x) => x.active)?.name ??
                      session.narration_versions?.[0]?.name ??
                      ""
                    }
                    onChange={(e) => {
                      const name = e.target.value;
                      if (!name) return;
                      void run("elegir narración", async () => {
                        await postJson("/api/narration/select", { work: workApplied, name });
                      });
                    }}
                  >
                    {(session.narration_versions ?? []).map((n) => (
                      <option key={n.name} value={n.name}>
                        {n.name}
                        {n.active ? " · activa" : ""}
                      </option>
                    ))}
                  </Select>
                </div>
                {session.has_narration ? (
                  <div>
                    <Label>Narración activa (preview)</Label>
                    <audio className="mt-2 w-full" controls src={session.urls.narration} />
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Historial de narraciones</div>
                </div>
                {(session.narration_versions ?? []).map((nv) => (
                  <div key={nv.name} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <code className="min-w-0 flex-1 break-all text-[11px] text-slate-600">{nv.name}</code>
                      <Btn
                        className="shrink-0 bg-white px-2 py-1 text-[11px] text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100"
                        disabled={!!busy}
                        onClick={() =>
                          run("borrar narración", async () => {
                            await deleteReq(
                              `/api/narration?work=${encodeURIComponent(workApplied)}&name=${encodeURIComponent(nv.name)}`,
                            );
                          })
                        }
                      >
                        Eliminar
                      </Btn>
                    </div>
                    <audio className="mt-2 w-full" controls src={nv.url} />
                  </div>
                ))}
              </div>
            ) : session?.has_narration ? (
              <div className="border-t border-slate-100 pt-4">
                <Label>Narración</Label>
                <audio className="mt-2 w-full" controls src={session.urls.narration} />
              </div>
            ) : null}
          </Card>

          <Card title="3 · Stock (Pexels)" subtitle="Requiere guion.txt y opcionalmente narracion.wav para alinear términos.">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label>Idioma hint</Label>
                <Select value={stockLang} onChange={(e) => setStockLang(e.target.value)}>
                  <option value="es">es</option>
                  <option value="en">en</option>
                </Select>
              </div>
              <div>
                <Label>Máx. clips</Label>
                <Input type="number" value={maxClips} onChange={(e) => setMaxClips(Number(e.target.value))} />
              </div>
            </div>
            <Btn
              className="bg-slate-900 text-white hover:bg-slate-800"
              disabled={!!busy || !session?.has_script}
              onClick={() =>
                run("stock", async () => {
                  await postJson("/api/stock-fetch", { work: workApplied, lang: stockLang, max_clips: maxClips });
                })
              }
            >
              Descargar stock
            </Btn>
            {session ? (
              <p className="text-sm text-slate-600">
                Clips en carpeta: <strong>{session.stock_count}</strong>
              </p>
            ) : null}
          </Card>

          <Card title="4 · Render" subtitle="MoviePy → draft.mp4">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" id="noMusic" className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
              <span>Sin música automática</span>
            </label>
            <Btn
              className="bg-indigo-600 text-white hover:bg-indigo-500"
              disabled={!!busy}
              onClick={() => {
                const noMusic = (document.getElementById("noMusic") as HTMLInputElement)?.checked ?? false;
                return run("render", async () => {
                  await postJson("/api/render-draft", { work: workApplied, no_music: noMusic });
                });
              }}
            >
              Renderizar draft.mp4
            </Btn>
            {session?.draft_exists ? (
              <p className="text-sm text-slate-600">
                Último render: <code className="rounded bg-slate-100 px-1 text-xs">{session.draft_path}</code>
              </p>
            ) : null}
          </Card>
          </div>
        </div>
      </main>

      {promptOpen && promptData ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" role="dialog">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <span className="font-semibold text-slate-900">Prompt (sin llamar a la API)</span>
              <button type="button" className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" onClick={() => setPromptOpen(false)}>
                Cerrar
              </button>
            </div>
            <div className="grid max-h-[calc(85vh-52px)] gap-0 sm:grid-cols-2">
              <div className="border-b border-slate-100 p-4 sm:border-b-0 sm:border-r">
                <div className="text-xs font-semibold uppercase text-slate-500">System</div>
                <pre className="mt-2 max-h-[50vh] overflow-auto whitespace-pre-wrap text-xs text-slate-800">{promptData.system}</pre>
              </div>
              <div className="p-4">
                <div className="text-xs font-semibold uppercase text-slate-500">User</div>
                <pre className="mt-2 max-h-[50vh] overflow-auto whitespace-pre-wrap text-xs text-slate-800">{promptData.user}</pre>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
