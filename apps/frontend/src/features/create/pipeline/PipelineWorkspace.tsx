import type { ReactNode } from "react";
import { Btn, StatusBadge } from "../../../components/ui";

export function PipelineWorkspace({
  stepTitle,
  stepId,
  stepState,
  onBack,
  onStartStep,
  startDisabled,
  children,
}: {
  stepTitle: string;
  stepId: string;
  stepState: string;
  onBack: () => void;
  onStartStep: () => void;
  /** Evita doble envío mientras el paso está en marcha o hay otra acción global en curso. */
  startDisabled?: boolean;
  children: ReactNode;
}) {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700"
            title="Volver"
            onClick={onBack}
          >
            &lt;
          </button>
          <div>
            <div className="text-sm font-semibold text-white">{stepTitle}</div>
            <div className="text-xs text-slate-400">{stepId}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge state={stepState} />
          <Btn
            className="border border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            disabled={!!startDisabled}
            onClick={onStartStep}
          >
            Start step
          </Btn>
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </>
  );
}
