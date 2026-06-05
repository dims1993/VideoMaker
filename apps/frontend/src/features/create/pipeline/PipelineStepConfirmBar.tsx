import { useCallback, useEffect, useState } from "react";
import { Btn } from "../../../components/ui";
import { postJson } from "../../../services/api";
import type { RunFn } from "../types";

type StepStatus = {
  exists?: boolean;
  step_done?: boolean;
  source?: string | null;
  artifact_hint?: string;
  title?: string;
};

export function PipelineStepConfirmBar({
  stepId,
  stepLabel,
  workApplied,
  stepState,
  run,
  onAfterRun,
  artifactHint,
}: {
  stepId: string;
  stepLabel: string;
  workApplied: string;
  stepState: string;
  run: RunFn;
  onAfterRun?: () => void | Promise<void>;
  /** Texto fijo; si se omite, usa artifact_hint del API. */
  artifactHint?: string;
}) {
  const [status, setStatus] = useState<StepStatus | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(
        `/api/pipeline/step-status?work=${encodeURIComponent(workApplied)}&step_id=${encodeURIComponent(stepId)}`,
      );
      if (!r.ok) {
        setStatus(null);
        return;
      }
      setStatus((await r.json()) as StepStatus);
    } catch {
      setStatus(null);
    }
  }, [stepId, workApplied]);

  useEffect(() => {
    void load();
  }, [load, stepState, workApplied]);

  const running = stepState === "running";
  const locked = stepState === "done";
  const exists = !!status?.exists;
  const hint = artifactHint?.trim() || status?.artifact_hint || "artefacto del paso";
  const source = status?.source;

  const handleConfirm = () =>
    run(`Confirmar · ${stepLabel}`, async () => {
      await postJson("/api/pipeline/step/confirm", {
        work: workApplied,
        step_id: stepId,
      });
      await onAfterRun?.();
      await load();
    });

  return (
    <div className="space-y-2">
      {locked && !running ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900">
          <strong>{stepLabel}</strong> confirmado
          {source ? (
            <>
              {" "}
              (<code className="text-[11px]">{source}</code>)
            </>
          ) : null}
          . El paso está en <em>done</em>.
        </div>
      ) : exists && !locked ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          Hay salida en disco ({source ? <code className="text-[11px]">{source}</code> : hint}) pero el
          paso está en <strong>idle</strong>. Confírmalo para marcar <em>done</em> sin Start step.
        </div>
      ) : !exists && !locked ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] text-slate-600">
          Aún no hay artefacto ({hint}). Ejecuta Start step o restaura el archivo y confirma.
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Btn
          type="button"
          className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40"
          disabled={locked || running || !exists}
          onClick={() => void handleConfirm()}
        >
          Confirmar paso (bloquear)
        </Btn>
        <Btn
          type="button"
          className="border border-slate-200 bg-slate-50 text-slate-700"
          onClick={() => void load()}
        >
          Recargar estado
        </Btn>
      </div>
    </div>
  );
}
