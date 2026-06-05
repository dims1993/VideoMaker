import { useEffect, useMemo, useState } from "react";
import { Btn, JsonEditor } from "../../../components/ui";
import { readApiError } from "../../../services/api";
import { PipelineStepConfirmBar } from "./PipelineStepConfirmBar";

type ArtifactResp = { exists?: boolean; artifact?: Record<string, unknown> | null };

export function SubtitleEnginePanel({
  run,
  workApplied,
  subtitleStepState,
  refreshPipeline,
}: {
  run: (label: string, fn: () => Promise<void>) => void;
  workApplied: string;
  subtitleStepState: string;
  refreshPipeline?: () => void | Promise<void>;
}) {
  const [artifact, setArtifact] = useState<ArtifactResp | null>(null);
  const [loading, setLoading] = useState(false);

  const canRun = subtitleStepState !== "running";

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(
        `/api/pipeline/subtitles-plan?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
      setArtifact((await r.json()) as ArtifactResp);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workApplied, subtitleStepState]);

  const pretty = useMemo(
    () => (artifact?.exists && artifact.artifact ? artifact.artifact : null),
    [artifact],
  );

  const handleGenerate = () =>
    run("Subtitle Engine · generar", async () => {
      const r = await fetch("/api/pipeline/step/rerun", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work: workApplied, step_id: "subtitle_engine" }),
      });
      if (!r.ok && r.status !== 202) {
        throw new Error((await readApiError(r)) || r.statusText);
      }
    });

  return (
    <div className="space-y-4">
      <PipelineStepConfirmBar
        stepId="subtitle_engine"
        stepLabel="Subtitle Engine"
        workApplied={workApplied}
        stepState={subtitleStepState}
        run={run}
        onAfterRun={refreshPipeline}
      />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div>
          <div className="text-sm font-semibold text-slate-900">
            Subtitle Engine (subtitles_plan.json)
          </div>
          <div className="text-xs text-slate-500">
            Requiere audio en Scene Editor (TTS + Unificar → narracion.wav).
            Alinea con Whisper y guarda subtítulos.srt con tiempos reales.
          </div>
        </div>
        <Btn onClick={handleGenerate} disabled={!canRun}>
          {subtitleStepState === "running" ? "Generando…" : "Generar / Re-generar"}
        </Btn>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 bg-slate-50/80 p-4">
          <h3 className="text-sm font-semibold text-slate-800">
            Artefacto (subtitles_plan.json)
          </h3>
        </div>
        <div className="p-4">
          {loading ? (
            <div className="text-sm text-slate-500">Cargando…</div>
          ) : pretty ? (
            <JsonEditor value={pretty} onChange={() => {}} readOnly height="520px" />
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
              No existe todavía. Ejecuta el paso para crearlo.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

