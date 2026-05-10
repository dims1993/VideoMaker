import type { PipelineStepState } from "../../../types/pipeline";

export function PipelineStepsAside({
  steps,
  selectedId,
  onSelectStep,
}: {
  steps: PipelineStepState[];
  selectedId: string | null;
  onSelectStep: (stepId: string) => void;
}) {
  return (
    <aside className="rounded-2xl border border-slate-200 bg-white p-2">
      <div className="px-2 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Pipeline</div>
      <div className="space-y-1">
        {steps.map((st) => {
          const selected = selectedId === st.id;
          return (
            <button
              key={st.id}
              type="button"
              onClick={() => onSelectStep(st.id)}
              className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left transition ${
                selected ? "bg-slate-900 text-white" : "hover:bg-slate-50"
              }`}
            >
              <div className="min-w-0">
                <div className={`truncate text-sm font-semibold ${selected ? "text-white" : "text-slate-900"}`}>{st.title}</div>
                <div className={`truncate text-[11px] ${selected ? "text-slate-200" : "text-slate-500"}`}>{st.detail || st.id}</div>
              </div>
              <span
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                  st.state === "done"
                    ? "bg-emerald-500"
                    : st.state === "running"
                      ? "bg-sky-500"
                      : st.state === "error"
                        ? "bg-rose-500"
                        : "bg-slate-300"
                }`}
                title={st.state}
              />
            </button>
          );
        })}
        {steps.length === 0 ? <div className="px-3 py-2 text-sm text-slate-600">Aún no hay pasos. Pulsa Start.</div> : null}
      </div>
    </aside>
  );
}
