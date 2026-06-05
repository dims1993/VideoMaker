import { useCallback, useEffect, useMemo, useState } from "react";
import { Btn } from "../../../components/ui";
import { JsonEditor } from "../../../components/ui/JsonEditor";
import { postJson, readApiError } from "../../../services/api";
import type { RunFn } from "../types";

type NarrativeAngleResponse = {
  exists?: boolean;
  narrative_angle?: Record<string, unknown> | null;
  confirmed?: boolean;
};

export function NarrativeAnglePanel({
  workApplied,
  run,
  locked,
  stepState,
  onAfterRun,
}: {
  workApplied: string;
  run: RunFn;
  locked: boolean;
  stepState: string;
  onAfterRun?: () => void | Promise<void>;
}) {
  const [edited, setEdited] = useState("{}");
  const [confirmedOnDisk, setConfirmedOnDisk] = useState(false);
  const [hasArtifact, setHasArtifact] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const running = stepState === "running";
  const uiLocked = locked || confirmedOnDisk;

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const r = await fetch(
        `/api/pipeline/narrative-angle?work=${encodeURIComponent(workApplied)}`,
      );
      if (!r.ok) {
        setEdited("{}");
        setHasArtifact(false);
        setConfirmedOnDisk(false);
        setLoadError((await readApiError(r)) || r.statusText);
        return;
      }
      const j = (await r.json()) as NarrativeAngleResponse;
      const raw = j.narrative_angle;
      const exists = Boolean(j.exists && raw && Object.keys(raw).length > 0);
      setHasArtifact(exists);
      setConfirmedOnDisk(Boolean(j.confirmed));
      setEdited(exists ? JSON.stringify(raw, null, 2) : "{}");
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Error al cargar");
    }
  }, [workApplied]);

  useEffect(() => {
    void load();
  }, [load, stepState, workApplied]);

  const parsedOk = useMemo(() => {
    try {
      const p = JSON.parse(edited) as Record<string, unknown>;
      return (
        typeof p === "object" &&
        p !== null &&
        !Array.isArray(p) &&
        Object.keys(p).length > 0
      );
    } catch {
      return false;
    }
  }, [edited]);

  const handleConfirm = () =>
    run("Confirmar ángulo narrativo", async () => {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(edited) as Record<string, unknown>;
      } catch {
        alert("JSON inválido. Corrige el formato antes de confirmar.");
        return;
      }
      await postJson("/api/pipeline/narrative-angle/confirm", {
        work: workApplied,
        narrative_angle: parsed,
      });
      await onAfterRun?.();
      await load();
    });

  const handleRegenerate = () =>
    run("Regenerar Narrative Angle", async () => {
      await postJson("/api/pipeline/step/rerun", {
        work: workApplied,
        step_id: "narrative_angle",
      });
      await onAfterRun?.();
      await load();
    });

  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">Narrative Angle Builder</h3>
        <p className="mt-1 text-[12px] text-slate-600">
          Tema → tesis emocional + mecanismo + arco (JSON mínimo). Si ya generaste el JSON,{" "}
          <strong className="text-slate-800">confírmalo</strong> para bloquearlo y desbloquear Packaging
          — no hace falta volver a pulsar Start step.
        </p>
      </div>

      {uiLocked ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900">
          Ángulo <strong>confirmado y bloqueado</strong>. Los pasos siguientes (Packaging, Prompt) usarán
          este JSON. Para cambiarlo, edita el archivo en disco o regenera con Start step abajo.
        </div>
      ) : hasArtifact ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          Hay un borrador en disco sin confirmar. Revisa el JSON y pulsa{" "}
          <strong>Confirmar ángulo</strong> cuando sea el definitivo.
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] text-slate-600">
          Aún no hay artefacto. Usa Start step para generarlo con IA, o pega un JSON y confírmalo.
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Btn
          type="button"
          className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40"
          disabled={uiLocked || running || !parsedOk}
          onClick={() => void handleConfirm()}
        >
          Confirmar ángulo (bloquear)
        </Btn>
        <Btn
          type="button"
          className="border border-violet-300 bg-violet-50 text-violet-800 hover:bg-violet-100 disabled:opacity-40"
          disabled={running}
          onClick={() => void handleRegenerate()}
        >
          {running ? "Ejecutando…" : "Regenerar (Start step)"}
        </Btn>
        <Btn type="button" className="border border-slate-200 bg-slate-50" onClick={() => void load()}>
          Recargar
        </Btn>
      </div>

      {loadError ? (
        <p className="text-[11px] text-rose-600">{loadError}</p>
      ) : null}

      <JsonEditor
        value={edited}
        onChange={setEdited}
        readOnly={uiLocked || running}
        height="320px"
      />
    </div>
  );
}
