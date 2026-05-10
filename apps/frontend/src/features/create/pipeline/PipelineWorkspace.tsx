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
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
            title="Volver"
            onClick={onBack}
          >
            &lt;
          </button>
          <div>
            <div className="text-sm font-semibold text-slate-900">{stepTitle}</div>
            <div className="text-xs text-slate-500">{stepId}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge state={stepState} />
          <Btn
            className="bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-50"
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
