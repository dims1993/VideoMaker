import { useMemo, useState } from "react";
import type { Session } from "./types";
import { Sidebar } from "./components/common/Sidebar";
import { AnalyzeCard } from "./features/analyze";
import { CreatePipelineCard } from "./features/create";
import { useWorkSessionPoll } from "./hooks/useWorkSessionPoll";

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
  const {
    session,
    pipelineState,
    fetchError: err,
    setFetchError: setErr,
    refreshSession: refresh,
    refreshPipeline,
    refreshAll,
  } = useWorkSessionPoll(workApplied);
  const [busy, setBusy] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"analyze" | "create">("create");
  const [openPipelineStepId, setOpenPipelineStepId] = useState<string | null>(null);

  const [kw, setKw] = useState("motivación, hábitos, enfoque");
  const [ctx, setCtx] = useState("");
  const [lang, setLang] = useState("en");
  const [minutes, setMinutes] = useState(10);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [previewText, setPreviewText] = useState("Hola, esta es una prueba de voz antes de narrar el vídeo.");
  const [preset, setPreset] = useState("xtts_v2_es");
  const [maxChars, setMaxChars] = useState(900);
  const [maxSeg, setMaxSeg] = useState(0);

  const statusLine = useMemo(() => {
    if (!session) return "";
    const s = session.status;
    return `${s.state}${s.step ? ` · ${s.step}` : ""}${s.detail ? ` — ${s.detail}` : ""}`;
  }, [session]);

  const switchWork = (rel: string) => {
    const slug = rel.trim() || "output/ui_session";
    setWork(slug);
    setWorkApplied(slug);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("work", slug);
      window.history.replaceState({}, "", url.toString());
    } catch {
      /* ignore */
    }
  };

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setErr(null);
    try {
      await fn();
      await refreshAll({ showErrors: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
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
            <AnalyzeCard workApplied={workApplied} session={session} run={run} />
          ) : null}

          {activeTab === "create" ? (
            <CreatePipelineCard
              pipelineState={pipelineState}
              openPipelineStepId={openPipelineStepId}
              onOpenStep={(id) => setOpenPipelineStepId(id)}
              onCloseStep={() => setOpenPipelineStepId(null)}
              workApplied={workApplied}
              run={run}
              refreshPipeline={refreshPipeline}
              session={session}
              busy={busy}
              kw={kw}
              setKw={setKw}
              ctx={ctx}
              setCtx={setCtx}
              lang={lang}
              setLang={setLang}
              minutes={minutes}
              setMinutes={setMinutes}
              provider={provider}
              setProvider={setProvider}
              model={model}
              setModel={setModel}
              preset={preset}
              setPreset={setPreset}
              previewText={previewText}
              setPreviewText={setPreviewText}
              maxChars={maxChars}
              setMaxChars={setMaxChars}
              maxSeg={maxSeg}
              setMaxSeg={setMaxSeg}
              refreshSession={refresh}
              onSwitchWork={switchWork}
            />
          ) : null}
        </div>
      </main>

    </div>
  );
}
