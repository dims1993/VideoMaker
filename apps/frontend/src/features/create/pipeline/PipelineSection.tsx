/**
 * Shared dark-themed collapsible Section used across pipeline panels.
 * Open/closed state is persisted per-section in localStorage.
 */
import { useState } from "react";

const STORAGE_KEY = "pipeline:sections";

export function readSectionStorage(): Record<string, boolean> {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}"); }
  catch { return {}; }
}

export function writeSectionStorage(id: string, value: boolean) {
  const current = readSectionStorage();
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, [id]: value }));
}

export function PipelineSection({
  id,
  title,
  badge,
  description,
  children,
}: {
  id: string;
  title: string;
  badge?: string;
  description?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState<boolean>(() => readSectionStorage()[id] ?? false);
  return (
    <div className={`overflow-hidden rounded-xl border transition-all ${open ? "border-slate-700 shadow-md" : "border-slate-600 hover:border-slate-500"}`}>
      <button
        type="button"
        className="flex w-full items-start justify-between gap-3 bg-gradient-to-r from-slate-800 to-slate-700 px-4 py-3 text-left transition-colors hover:from-slate-750 hover:to-slate-650"
        onClick={() => setOpen((v) => { writeSectionStorage(id, !v); return !v; })}
      >
        <div className="flex min-w-0 flex-1 flex-col gap-y-0.5">
          <div className="flex items-center gap-2">
            <span className="shrink-0 text-sm font-semibold tracking-wider capitalize text-white">{title}</span>
            {badge && (
              <span className="shrink-0 rounded bg-slate-600 px-1.5 py-0.5 text-[10px] text-slate-300 font-mono">
                {badge}
              </span>
            )}
          </div>
          {description && (
            <span className="text-[11px] leading-snug text-slate-400 font-normal">
              {description}
            </span>
          )}
        </div>
        <span className={`mt-0.5 shrink-0 text-slate-400 transition-transform text-sm ${open ? "rotate-180" : ""}`}>▾</span>
      </button>
      {open && (
        <div className={[
          "border-t border-slate-700 bg-slate-800 px-4 pb-4 pt-3",
          "[&_label]:text-slate-400",
          "[&_input]:mt-1 [&_input]:bg-slate-700 [&_input]:border-slate-600 [&_input]:text-slate-200 [&_input]:placeholder:text-slate-500",
          "[&_input:focus]:bg-slate-700 [&_input:focus]:text-slate-100 [&_input:focus]:border-slate-400 [&_input:focus]:ring-slate-500/30",
          "[&_select]:mt-1 [&_select]:bg-slate-700 [&_select]:border-slate-600 [&_select]:text-slate-200",
          "[&_select:focus]:bg-slate-700 [&_select:focus]:text-slate-100 [&_select:focus]:border-slate-400",
          "[&_textarea]:bg-slate-700 [&_textarea]:border-slate-600 [&_textarea]:text-slate-200 [&_textarea]:placeholder:text-slate-500",
          "[&_textarea:focus]:bg-slate-700 [&_textarea:focus]:text-slate-100 [&_textarea:focus]:border-slate-400",
        ].join(" ")}>
          {children}
        </div>
      )}
    </div>
  );
}
