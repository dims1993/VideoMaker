import { useCallback, useEffect, useMemo, useState } from "react";

type EnvInfo = {
  VIDEOMAKER_LLM_PROVIDER?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  OLLAMA_BASE_URL?: string;
  OLLAMA_MODEL?: string;
  OPENAI_API_KEY?: boolean;
  PEXELS_API_KEY?: boolean;
};

export type Session = {
  work: string;
  work_dir: string;
  voice_presets: string[];
  has_script: boolean;
  has_narration: boolean;
  has_clone_reference: boolean;
  stock_count: number;
  draft_exists: boolean;
  draft_path: string;
  env: EnvInfo;
  status: { state: string; step: string; detail: string };
  log_tail: string;
  voice_previews: { name: string; url: string }[];
  tts_reference?: { mode: string; preview_filename: string | null };
  narration_versions?: { name: string; url: string; active: boolean }[];
  active_narration?: string | null;
  urls: { narration: string; clone_reference: string };
};

async function readApiError(r: Response): Promise<string> {
  const t = (await r.json().catch(() => ({}))) as { detail?: unknown };
  const d = t.detail;
  return typeof d === "string"
    ? d
    : Array.isArray(d)
      ? d.map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: string }).msg) : String(x))).join("; ")
      : JSON.stringify(t);
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
  return r.json() as Promise<T>;
}

async function putJson<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
  return r.json() as Promise<T>;
}

async function deleteReq(url: string): Promise<void> {
  const r = await fetch(url, { method: "DELETE" });
  if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
}

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <h2 className="text-lg font-semibold tracking-tight text-slate-900">{title}</h2>
      {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
      <div className="mt-4 space-y-3">{children}</div>
    </section>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium uppercase tracking-wide text-slate-500">{children}</label>;
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 text-sm text-slate-900 outline-none ring-emerald-500/30 placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:ring-2"
    />
  );
}

function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className="mt-1 min-h-[88px] w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 text-sm text-slate-900 outline-none ring-emerald-500/30 focus:border-emerald-500 focus:bg-white focus:ring-2"
    />
  );
}

function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 text-sm text-slate-900 outline-none focus:border-emerald-500 focus:bg-white focus:ring-2 focus:ring-emerald-500/30"
    />
  );
}

function Btn({ className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { className: c2, ...rest } = props;
  return (
    <button
      type="button"
      {...rest}
      className={`inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${className} ${c2 ?? ""}`}
    />
  );
}

function StatusBadge({ state }: { state: string }) {
  const map: Record<string, string> = {
    idle: "bg-slate-100 text-slate-700 ring-slate-200",
    running: "bg-amber-50 text-amber-900 ring-amber-200",
    done: "bg-emerald-50 text-emerald-900 ring-emerald-200",
    error: "bg-rose-50 text-rose-900 ring-rose-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${map[state] ?? map.idle}`}>
      {state}
    </span>
  );
}

/** Formato backend: `[HH:MM:SS] paso: detalle` */
type ParsedLogEntry = { time: string; step: string; detail: string; raw: string };

const STEP_LABEL: Record<string, string> = {
  script: "Guion",
  voice_preview: "Voz · preview",
  tts: "Narración",
  stock: "Stock",
  render: "Render",
};

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

type AnalyzeReport = {
  video_id: string;
  url: string;
  title?: string;
  channel?: string;
  duration_s?: number;
  transcript_lang?: string | null;
  top_comments?: { author?: string; text: string; like_count?: number }[];
  insights?: {
    hookPattern?: string;
    sectionOutline?: string[];
    pacingNotes?: string[];
    suggestedBrollThemes?: string[];
    CTAStyle?: string;
    keywordOpportunities?: string[];
  };
};

type ChannelAnalyzeReport = {
  channel: string;
  channel_id: string;
  count: number;
  videos: AnalyzeReport[];
};

type ChannelSearchItem = {
  channel_id: string;
  title: string;
  handle?: string;
  avatar_url?: string | null;
  subscribers?: number;
  total_views?: number;
  video_count?: number;
  description?: string;
};

function parseLogTail(text: string): ParsedLogEntry[] {
  const out: ParsedLogEntry[] = [];
  for (const raw of text.split("\n")) {
    if (!raw.trim()) continue;
    const m = raw.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$/);
    if (m) {
      out.push({ time: m[1], step: m[2].trim(), detail: m[3].trim(), raw });
    } else {
      out.push({ time: "", step: "otro", detail: raw.trim(), raw });
    }
  }
  return out;
}

function stepDotClass(step: string): string {
  const s = step.toLowerCase();
  if (s === "script") return "bg-violet-500";
  if (s === "voice_preview") return "bg-sky-500";
  if (s === "tts") return "bg-emerald-500";
  if (s === "stock") return "bg-amber-500";
  if (s === "render") return "bg-indigo-500";
  return "bg-slate-400";
}

function ActivityPanel({ logTail }: { logTail: string }) {
  const entries = useMemo(() => parseLogTail(logTail), [logTail]);
  return (
    <div className="mt-3 border-t border-slate-100 pt-3">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Historial</h3>
      <p className="mt-0.5 text-[10px] text-slate-400">Últimas acciones (desde el archivo de sesión)</p>
      {entries.length === 0 ? (
        <p className="mt-2 text-xs italic text-slate-400">Sin entradas todavía.</p>
      ) : (
        <ul className="mt-2 max-h-52 space-y-2 overflow-y-auto pr-1">
          {entries.map((e, i) => (
            <li key={`h-${i}-${e.time}-${e.step}`} className="flex gap-2 text-xs leading-snug">
              <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${stepDotClass(e.step)}`} title={e.step} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  {e.time ? <span className="font-mono text-[10px] text-slate-400">{e.time}</span> : null}
                  <span className="font-medium text-slate-700">{STEP_LABEL[e.step] ?? e.step}</span>
                </div>
                {e.detail ? <p className="mt-0.5 break-words text-slate-600">{e.detail}</p> : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LogRawPanel({ logTail }: { logTail: string }) {
  return (
    <details className="group mt-3 border-t border-slate-100 pt-3">
      <summary className="cursor-pointer list-none text-[11px] font-semibold uppercase tracking-wide text-slate-500 marker:content-none [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-1">
          Registro técnico
          <span className="text-slate-400 transition group-open:rotate-180">▾</span>
        </span>
      </summary>
      <p className="mt-1 text-[10px] text-slate-400">`.videomaker_log.txt` — texto crudo para depurar.</p>
      <pre className="mt-2 max-h-36 overflow-auto rounded-xl bg-slate-950 p-3 font-mono text-[10px] leading-snug text-slate-200 empty:hidden whitespace-pre-wrap">
        {logTail || "— vacío —"}
      </pre>
    </details>
  );
}

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
  const [ytUrl, setYtUrl] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeReport | null>(null);
  const [analyzeLog, setAnalyzeLog] = useState<string>("");
  const [pipelineState, setPipelineState] = useState<PipelineState | null>(null);
  const [analyzeAutoPoll, setAnalyzeAutoPoll] = useState(false);
  const [channelInput, setChannelInput] = useState("");
  const [channelMaxVideos, setChannelMaxVideos] = useState(10);
  const [channelResult, setChannelResult] = useState<ChannelAnalyzeReport | null>(null);
  const [channelLog, setChannelLog] = useState("");
  const [channelAutoPoll, setChannelAutoPoll] = useState(false);

  // New: channel directory/search dashboard
  const [channelSearchQ, setChannelSearchQ] = useState("");
  const [channelMinSubs, setChannelMinSubs] = useState(0);
  const [channelMinViews, setChannelMinViews] = useState(0);
  const [channelSort, setChannelSort] = useState<"subs" | "views">("subs");
  const [channelSearchResults, setChannelSearchResults] = useState<ChannelSearchItem[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<ChannelSearchItem | null>(null);

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

  const refreshAnalyze = useCallback(async () => {
    const r = await fetch(`/api/analyze/result?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { report: AnalyzeReport | null; log: string };
    setAnalyzeResult(j.report);
    setAnalyzeLog(j.log || "");
    if (j.report?.insights) setAnalyzeAutoPoll(false);
  }, [workApplied]);

  const refreshAnalyzeChannel = useCallback(async () => {
    const r = await fetch(`/api/analyze/channel-result?work=${encodeURIComponent(workApplied)}`);
    if (!r.ok) return;
    const j = (await r.json()) as { report: ChannelAnalyzeReport | null; log: string };
    setChannelResult(j.report);
    setChannelLog(j.log || "");
    if (j.report?.videos?.length) setChannelAutoPoll(false);
  }, [workApplied]);

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

  useEffect(() => {
    if (activeTab !== "analyze") return;
    if (!analyzeAutoPoll) return;
    const id = setInterval(() => void refreshAnalyze(), 1500);
    return () => clearInterval(id);
  }, [activeTab, analyzeAutoPoll, refreshAnalyze]);

  useEffect(() => {
    if (activeTab !== "analyze") return;
    if (!channelAutoPoll) return;
    const id = setInterval(() => void refreshAnalyzeChannel(), 2000);
    return () => clearInterval(id);
  }, [activeTab, channelAutoPoll, refreshAnalyzeChannel]);

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
      <aside className="fixed inset-y-0 left-0 z-40 w-[280px] border-r border-slate-200/80 bg-white p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-base font-bold tracking-tight text-slate-900">Videomaker</div>
            <div className="mt-0.5 text-[11px] text-slate-500">Desktop · full width</div>
          </div>
          {session ? <StatusBadge state={session.status.state} /> : null}
        </div>

        <div className="mt-4 space-y-2">
          <Btn
            className={`w-full ${activeTab === "analyze" ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"}`}
            onClick={() => setActiveTab("analyze")}
          >
            Analyse
          </Btn>
          <Btn
            className={`w-full ${activeTab === "create" ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"}`}
            onClick={() => setActiveTab("create")}
          >
            Create
          </Btn>
        </div>

        <div className="mt-4 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Session</div>
          <p className="mt-2 text-xs leading-relaxed text-slate-600">{statusLine || "…"}</p>
          <div className="mt-3">
            <Label>Carpeta de trabajo</Label>
            <div className="flex gap-2">
              <Input value={work} onChange={(e) => setWork(e.target.value)} placeholder="output/ui_session" />
              <Btn className="shrink-0 bg-slate-900 text-white hover:bg-slate-800" onClick={() => setWorkApplied(work.trim() || "output/ui_session")}>
                OK
              </Btn>
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-slate-200/80 bg-white p-4 text-xs text-slate-600 shadow-sm">
          <div className="font-semibold text-slate-800">Entorno</div>
          <div className="mt-2 space-y-1">
            <div>
              Provider: <code className="rounded bg-slate-100 px-1">{String(session?.env.VIDEOMAKER_LLM_PROVIDER || "openai")}</code>
            </div>
            <div>OPENAI_API_KEY: {session?.env.OPENAI_API_KEY ? "sí" : "no"}</div>
            <div>PEXELS_API_KEY: {session?.env.PEXELS_API_KEY ? "sí" : "no"}</div>
          </div>
        </div>
      </aside>

      <main className="min-h-screen pl-[280px]">
        <div className="p-6">
          {err ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">{err}</div>
          ) : null}
          {busy ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">Enviando: {busy}…</div>
          ) : null}

          {activeTab === "analyze" ? (
            <Card title="Analyse · YouTube" subtitle="Pega una URL de YouTube y genera insights para alimentar Create.">
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
                          sort: channelSort,
                          limit: "12",
                        });
                        const r = await fetch(`/api/channels/search?${qs.toString()}`);
                        if (!r.ok) throw new Error(await readApiError(r));
                        const j = (await r.json()) as { channels: ChannelSearchItem[] };
                        setChannelSearchResults(j.channels || []);
                      })
                    }
                  >
                    Buscar
                  </Btn>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-4">
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
                    <Label>Ordenar por</Label>
                    <Select value={channelSort} onChange={(e) => setChannelSort(e.target.value as "subs" | "views")}>
                      <option value="subs">Suscriptores</option>
                      <option value="views">Visitas</option>
                    </Select>
                  </div>
                </div>

                {channelSearchResults.length ? (
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                      {channelSearchResults.map((c) => (
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
                          </div>
                        </button>
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
                                });
                              })
                            }
                          >
                            Guardar
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

              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Canal</div>
                <div className="mt-2 grid gap-3 sm:grid-cols-[1fr_10rem]">
                  <div>
                    <Label>@handle / URL / nombre del canal</Label>
                    <Input value={channelInput} onChange={(e) => setChannelInput(e.target.value)} placeholder="@DeepMadeSimple o https://www.youtube.com/@..." />
                  </div>
                  <div>
                    <Label>Max vídeos</Label>
                    <Input
                      type="number"
                      min={1}
                      max={50}
                      value={channelMaxVideos}
                      onChange={(e) => setChannelMaxVideos(Number(e.target.value))}
                    />
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Btn
                    className="bg-emerald-600 text-white hover:bg-emerald-700"
                    disabled={!channelInput.trim()}
                    onClick={() =>
                      run("Analyze Channel", async () => {
                        setChannelResult(null);
                        setChannelLog("");
                        await postJson(`/api/analyze/channel`, {
                          work: workApplied,
                          channel: channelInput.trim(),
                          lang,
                          max_videos: channelMaxVideos,
                        });
                        setChannelAutoPoll(true);
                        await refreshAnalyzeChannel();
                      })
                    }
                  >
                    Analizar canal
                  </Btn>
                  <Btn
                    className="bg-slate-900 text-white hover:bg-slate-800"
                    onClick={() =>
                      run("Refrescar canal", async () => {
                        await refreshAnalyzeChannel();
                      })
                    }
                  >
                    Refrescar canal
                  </Btn>
                </div>

                {channelResult?.videos?.length ? (
                  <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                        <tr>
                          <th className="px-3 py-2">Vídeo</th>
                          <th className="px-3 py-2">Hook</th>
                          <th className="px-3 py-2">Outline</th>
                          <th className="px-3 py-2">B-roll</th>
                          <th className="px-3 py-2 text-right">Acción</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {channelResult.videos.slice(0, 25).map((v) => (
                          <tr key={v.video_id}>
                            <td className="px-3 py-2">
                              <div className="font-medium text-slate-900">{v.title || v.video_id}</div>
                              <div className="mt-0.5 text-[10px] text-slate-500 font-mono">{v.video_id}</div>
                            </td>
                            <td className="px-3 py-2 text-slate-700">{v.insights?.hookPattern || "—"}</td>
                            <td className="px-3 py-2 text-slate-700">
                              {v.insights?.sectionOutline?.length ? v.insights.sectionOutline.slice(0, 3).join(" · ") : "—"}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {v.insights?.suggestedBrollThemes?.length ? v.insights.suggestedBrollThemes.slice(0, 4).join(", ") : "—"}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <Btn
                                className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                                onClick={() => {
                                  const ins = v.insights;
                                  const asText = [
                                    v.title ? `Referencia video: ${v.title}` : "",
                                    ins?.hookPattern ? `Hook: ${ins.hookPattern}` : "",
                                    ins?.sectionOutline?.length ? `Outline: ${ins.sectionOutline.join(" | ")}` : "",
                                    ins?.suggestedBrollThemes?.length ? `B-roll: ${ins.suggestedBrollThemes.join(", ")}` : "",
                                    ins?.CTAStyle ? `CTA: ${ins.CTAStyle}` : "",
                                  ]
                                    .filter(Boolean)
                                    .join("\n");
                                  setCtx((prev) => (prev ? `${prev}\n\n${asText}` : asText));
                                  setActiveTab("create");
                                }}
                              >
                                Enviar a Create
                              </Btn>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : channelAutoPoll ? (
                  <p className="mt-3 text-sm text-slate-600">Analizando canal… (auto refresh)</p>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">Aquí aparecerán los vídeos del canal analizados.</p>
                )}

                {channelLog ? (
                  <details className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
                    <summary className="cursor-pointer text-sm font-semibold text-slate-800">Log del canal</summary>
                    <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-3 font-mono text-[10px] leading-snug text-slate-200">
                      {channelLog}
                    </pre>
                  </details>
                ) : null}
              </div>

              <div>
                <Label>URL de YouTube</Label>
                <Input value={ytUrl} onChange={(e) => setYtUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=..." />
              </div>
              <div className="flex flex-wrap gap-2">
                <Btn
                  className="bg-emerald-600 text-white hover:bg-emerald-700"
                  disabled={!ytUrl.trim()}
                  onClick={() =>
                    run("Analyze YouTube", async () => {
                      setAnalyzeResult(null);
                      setAnalyzeLog("");
                      await postJson(`/api/analyze/youtube`, { work: workApplied, url: ytUrl.trim(), lang });
                      setAnalyzeAutoPoll(true);
                      await refreshAnalyze();
                    })
                  }
                >
                  Analizar
                </Btn>
                <Btn
                  className="bg-slate-900 text-white hover:bg-slate-800"
                  onClick={() =>
                    run("Refrescar resultado", async () => {
                      await refreshAnalyze();
                    })
                  }
                >
                  Refrescar
                </Btn>
                <Btn
                  className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
                  disabled={!analyzeResult?.insights}
                  onClick={() => {
                    const ins = analyzeResult?.insights;
                    const asText = [
                      analyzeResult?.title ? `Video: ${analyzeResult.title}` : "",
                      ins?.hookPattern ? `Hook: ${ins.hookPattern}` : "",
                      ins?.sectionOutline?.length ? `Outline: ${ins.sectionOutline.join(" | ")}` : "",
                      ins?.suggestedBrollThemes?.length ? `B-roll: ${ins.suggestedBrollThemes.join(", ")}` : "",
                      ins?.CTAStyle ? `CTA: ${ins.CTAStyle}` : "",
                    ]
                      .filter(Boolean)
                      .join("\n");
                    setCtx((prev) => (prev ? `${prev}\n\n${asText}` : asText));
                    setActiveTab("create");
                  }}
                >
                  Enviar a Create
                </Btn>
              </div>

              <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{analyzeResult?.title || "Resultado del análisis"}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {analyzeResult?.channel ? `${analyzeResult.channel} · ` : ""}
                        {analyzeResult?.video_id ? <span className="font-mono">{analyzeResult.video_id}</span> : "—"}
                        {typeof analyzeResult?.duration_s === "number" ? ` · ${Math.round(analyzeResult.duration_s)}s` : ""}
                      </div>
                    </div>
                    {analyzeResult?.url ? (
                      <a
                        className="text-xs font-medium text-emerald-700 hover:underline"
                        href={analyzeResult.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Abrir en YouTube
                      </a>
                    ) : null}
                  </div>

                  {!analyzeResult ? (
                    <p className="mt-3 text-sm text-slate-600">Pulsa “Analizar”. El resultado se mostrará aquí en cuanto termine.</p>
                  ) : null}

                  {analyzeResult?.insights ? (
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Hook</div>
                        <p className="mt-1 text-sm text-slate-800">{analyzeResult.insights.hookPattern || "—"}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">CTA</div>
                        <p className="mt-1 text-sm text-slate-800">{analyzeResult.insights.CTAStyle || "—"}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3 md:col-span-2">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Section outline</div>
                        {analyzeResult.insights.sectionOutline?.length ? (
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-800">
                            {analyzeResult.insights.sectionOutline.map((s, i) => (
                              <li key={`sec-${i}`}>{s}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-1 text-sm text-slate-800">—</p>
                        )}
                      </div>
                      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">B-roll themes</div>
                        <p className="mt-1 text-sm text-slate-800">
                          {analyzeResult.insights.suggestedBrollThemes?.length ? analyzeResult.insights.suggestedBrollThemes.join(", ") : "—"}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Keyword opps</div>
                        <p className="mt-1 text-sm text-slate-800">
                          {analyzeResult.insights.keywordOpportunities?.length ? analyzeResult.insights.keywordOpportunities.join(", ") : "—"}
                        </p>
                      </div>
                    </div>
                  ) : analyzeAutoPoll ? (
                    <p className="mt-3 text-sm text-slate-600">Analizando… (se refresca automáticamente)</p>
                  ) : analyzeResult ? (
                    <p className="mt-3 text-sm text-slate-600">Aún sin insights. Pulsa “Refrescar”.</p>
                  ) : null}

                  {analyzeResult?.top_comments?.length ? (
                    <div className="mt-4">
                      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Top comments</div>
                      <div className="mt-2 overflow-hidden rounded-2xl border border-slate-200">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                            <tr>
                              <th className="px-3 py-2">Autor</th>
                              <th className="px-3 py-2">Comentario</th>
                              <th className="px-3 py-2 text-right">Likes</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 bg-white">
                            {analyzeResult.top_comments.slice(0, 10).map((c, i) => (
                              <tr key={`c-${i}`}>
                                <td className="px-3 py-2 text-slate-700">{c.author || "—"}</td>
                                <td className="px-3 py-2 text-slate-800">{c.text}</td>
                                <td className="px-3 py-2 text-right text-slate-700">{typeof c.like_count === "number" ? c.like_count : ""}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : null}

                  <details className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
                    <summary className="cursor-pointer text-sm font-semibold text-slate-800">Transcripción (preview)</summary>
                    <p className="mt-1 text-xs text-slate-500">Si el vídeo no tiene transcript accesible, este bloque puede estar vacío.</p>
                    <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-3 font-mono text-[10px] leading-snug text-slate-200">
                      {(analyzeResult as unknown as { transcript?: string })?.transcript || "—"}
                    </pre>
                  </details>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estado</div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-900">Analyze</div>
                    <StatusBadge state={analyzeAutoPoll ? "running" : analyzeResult?.insights ? "done" : "idle"} />
                  </div>
                  <p className="mt-2 text-xs text-slate-600">
                    {analyzeAutoPoll ? "Procesando… (auto refresh)" : analyzeResult?.insights ? "Listo." : "Sin datos."}
                  </p>
                </div>
              </div>

              {analyzeLog ? (
                <details className="rounded-2xl border border-slate-200 bg-white p-4">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-800">Log de análisis</summary>
                  <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-3 font-mono text-[10px] leading-snug text-slate-200">
                    {analyzeLog}
                  </pre>
                </details>
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
