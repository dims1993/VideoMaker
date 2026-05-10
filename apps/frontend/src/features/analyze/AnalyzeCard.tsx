import type { Session } from "../../types";
import type { RunFn } from "../../types/run";
import { Btn, Card } from "../../components/ui";
import { ChannelSearchTab } from "./ChannelSearchTab";
import { SavedPearlsSection } from "./SavedPearlsSection";
import { useAnalyzeChannels } from "./useAnalyzeChannels";

export function AnalyzeCard({
  workApplied,
  session,
  run,
}: {
  workApplied: string;
  session: Session | null;
  run: RunFn;
}) {
  const api = useAnalyzeChannels({ workApplied, session });

  return (
    <Card title="Analyse" subtitle="Dashboard minimalista para buscar y sincronizar información de YouTube.">
      <div className="rounded-2xl border border-slate-200 bg-white p-2">
        <div className="grid grid-cols-2 gap-2">
          <Btn
            className={`${
              api.analyzePanel === "search" ? "bg-slate-900 text-white hover:bg-slate-800" : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
            }`}
            onClick={() => api.setAnalyzePanel("search")}
          >
            Buscar canal
          </Btn>
          <Btn
            className={`${
              api.analyzePanel === "saved" ? "bg-slate-900 text-white hover:bg-slate-800" : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"
            }`}
            onClick={() => {
              api.setAnalyzePanel("saved");
              void api.refreshSavedChannels();
            }}
          >
            Canales guardados
          </Btn>
        </div>
      </div>

      <div className="h-px w-full bg-slate-100" />

      {api.analyzePanel === "search" ? <ChannelSearchTab api={api} workApplied={workApplied} run={run} /> : null}

      {api.analyzePanel === "saved" ? <SavedPearlsSection api={api} workApplied={workApplied} run={run} /> : null}
    </Card>
  );
}
