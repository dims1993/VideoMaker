import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import { JsonEditor } from "../../../components/ui/JsonEditor";
import {
  postJson,
  putJson,
  readApiError,
  waitForPipelineStep,
} from "../../../services/api";
import type { RunFn } from "../types";

type PackagingArtifact = {
  exists: boolean;
  packaging: Record<string, unknown> | null;
};

export function PackagingPanel({
  run,
  workApplied,
  lang,
  kw,
  ctx,
  minutes,
  provider,
  model,
  refreshPipeline,
  packagingStepState,
  topicSelected,
  narrativeAngleDone,
}: {
  run: RunFn;
  workApplied: string;
  lang: string;
  kw: string;
  ctx: string;
  minutes: number;
  provider: string;
  model: string;
  refreshPipeline: () => Promise<void>;
  packagingStepState: string;
  topicSelected: boolean;
  narrativeAngleDone: boolean;
}) {
  const [artifact, setArtifact] = useState<PackagingArtifact | null>(null);
  const [edited, setEdited] = useState("{}");
  const generationRunning = packagingStepState === "running";

  const loadArtifact = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/packaging?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
      const data = (await r.json()) as PackagingArtifact;
      setArtifact(data);
      setEdited(
        data.packaging ? JSON.stringify(data.packaging, null, 2) : "{}",
      );
    } catch (e) {
      console.error("packaging artifact", e);
    }
  }, [workApplied]);

  useEffect(() => {
    void loadArtifact();
  }, [loadArtifact]);

  useEffect(() => {
    if (packagingStepState === "done") void loadArtifact();
  }, [packagingStepState, loadArtifact]);

  const handleGenerate = () =>
    run("Generar empaquetado (título + miniatura)", async () => {
      await postJson("/api/pipeline/step/rerun", {
        work: workApplied,
        step_id: "packaging",
        keywords: kw,
        context: ctx,
        lang,
        minutes,
        provider,
        model,
      });
      await waitForPipelineStep(workApplied, "packaging");
      await refreshPipeline();
      await loadArtifact();
    });

  const handleSave = () =>
    run("Guardar packaging.json", async () => {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(edited) as Record<string, unknown>;
      } catch {
        alert("JSON inválido");
        return;
      }
      await putJson("/api/pipeline/packaging", {
        work: workApplied,
        packaging: parsed,
      });
      await refreshPipeline();
      await loadArtifact();
    });

  const ideas =
    artifact?.packaging &&
    typeof artifact.packaging === "object" &&
    artifact.packaging.editorial &&
    typeof artifact.packaging.editorial === "object" &&
    Array.isArray(
      (artifact.packaging.editorial as Record<string, unknown>).thumbnail_ideas,
    )
      ? (
          (artifact.packaging.editorial as Record<string, unknown>)
            .thumbnail_ideas as unknown[]
        )
          .map((x) => String(x).trim())
          .filter(Boolean)
      : [];

  const title =
    artifact?.packaging &&
    typeof artifact.packaging.platform === "object" &&
    artifact.packaging.platform !== null
      ? String((artifact.packaging.platform as Record<string, unknown>).title || "").trim()
      : "";

  const canRun = topicSelected && narrativeAngleDone && !generationRunning;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
        <strong>Thumbnail &amp; Hook-First</strong> — aquí se fija la promesa del clic
        (título + miniatura) <em>antes</em> del Prompt y del Script Writer. El guion debe
        cumplir lo que el espectador espera al ver la miniatura.
      </div>

      {!topicSelected ? (
        <p className="text-sm text-rose-800">
          Selecciona un tema en Topic Generator («Usar este tema»).
        </p>
      ) : null}
      {!narrativeAngleDone ? (
        <p className="text-sm text-amber-900">
          Confirma el ángulo en <strong>Narrative Angle</strong> («Confirmar ángulo (bloquear)») antes de
          generar el empaquetado.
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Btn
          type="button"
          className="bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-40"
          disabled={!canRun}
          onClick={() => void handleGenerate()}
        >
          {generationRunning ? "Generando empaquetado…" : "Generar título + miniatura (IA)"}
        </Btn>
        <Btn
          type="button"
          className="border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          disabled={generationRunning || !artifact?.exists}
          onClick={() => void handleSave()}
        >
          Guardar JSON
        </Btn>
      </div>

      {title ? (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Título acordado
          </p>
          <p className="mt-1 text-sm font-medium text-slate-900">{title}</p>
        </div>
      ) : null}

      {ideas.length > 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Ideas de miniatura
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-800">
            {ideas.map((idea, i) => (
              <li key={i}>{idea}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-2">
          <h3 className="text-sm font-semibold text-slate-800">
            Artefacto (packaging.json)
          </h3>
        </div>
        <div className="p-4">
          {artifact?.exists ? (
            <JsonEditor
              value={edited}
              onChange={setEdited}
              readOnly={generationRunning}
              height="420px"
            />
          ) : (
            <p className="text-sm text-slate-500">
              Aún no hay empaquetado. Pulsa «Generar título + miniatura».
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
