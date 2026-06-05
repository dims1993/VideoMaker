import type { ReactNode } from "react";
import { Btn, StatusBadge } from "../../../components/ui";
import type { SectionTheme } from "./PipelineSection";

const HEADER: Record<SectionTheme, string> = {
  dark: "mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.08] bg-[#161618] px-4 py-3 ring-1 ring-white/[0.06]",
  light:
    "mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm shadow-slate-200/50",
};

const BACK_BTN: Record<SectionTheme, string> = {
  dark: "inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-[#1e1e22] text-slate-300 transition-colors hover:bg-[#252528]",
  light:
    "inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-50",
};

const STEP_TITLE: Record<SectionTheme, string> = {
  dark: "text-[15px] font-semibold tracking-tight text-white/95",
  light: "text-[15px] font-semibold tracking-tight text-slate-900",
};

const STEP_ID: Record<SectionTheme, string> = {
  dark: "text-[12px] text-white/40",
  light: "text-[12px] text-slate-500",
};

const START_BTN: Record<SectionTheme, string> = {
  dark: "border border-white/10 bg-[#1e1e22] text-slate-200 hover:bg-[#252528] disabled:opacity-50",
  light: "bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50",
};

export function PipelineWorkspace({
  stepTitle,
  stepId,
  stepState,
  theme = "dark",
  onBack,
  onStartStep,
  startLabel = "Start step",
  startDisabled,
  headerActions,
  children,
}: {
  stepTitle: string;
  stepId: string;
  stepState: string;
  theme?: SectionTheme;
  onBack: () => void;
  onStartStep: () => void;
  startLabel?: string;
  startDisabled?: boolean;
  headerActions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <>
      <div className={HEADER[theme]}>
        <div className="flex items-center gap-2">
          <button type="button" className={BACK_BTN[theme]} title="Volver" onClick={onBack}>
            &lt;
          </button>
          <div>
            <div className={STEP_TITLE[theme]}>{stepTitle}</div>
            <div className={STEP_ID[theme]}>{stepId}</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <StatusBadge state={stepState} />
          {headerActions}
          <Btn className={START_BTN[theme]} disabled={!!startDisabled} onClick={onStartStep}>
            {startLabel}
          </Btn>
        </div>
      </div>
      <div className="min-w-0 space-y-4">{children}</div>
    </>
  );
}
