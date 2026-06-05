/**
 * Collapsible section for pipeline panels. Default theme is dark; pass theme="light" for Prompt.
 */
import { useState } from "react";

const STORAGE_KEY = "pipeline:sections";

export type SectionAccent = "neutral" | "sky" | "violet" | "cyan" | "amber";
export type SectionStatus = "default" | "complete" | "incomplete" | "warning";
export type SectionTheme = "dark" | "light";

const ACCENT_STRIPE: Record<SectionTheme, Record<SectionAccent, string>> = {
  dark: {
    neutral: "bg-white/20",
    sky: "bg-sky-400",
    violet: "bg-violet-400",
    cyan: "bg-cyan-400",
    amber: "bg-amber-400",
  },
  light: {
    neutral: "bg-slate-300",
    sky: "bg-sky-500",
    violet: "bg-violet-500",
    cyan: "bg-cyan-500",
    amber: "bg-amber-500",
  },
};

const STATUS_PILL: Record<
  SectionTheme,
  Record<SectionStatus, { show: boolean; className: string; label: string }>
> = {
  dark: {
    default: { show: false, className: "", label: "" },
    complete: {
      show: true,
      className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
      label: "Completo",
    },
    incomplete: {
      show: true,
      className: "border-rose-500/40 bg-rose-500/15 text-rose-300",
      label: "Incompleto",
    },
    warning: {
      show: true,
      className: "border-amber-500/40 bg-amber-500/15 text-amber-200",
      label: "Revisar",
    },
  },
  light: {
    default: { show: false, className: "", label: "" },
    complete: {
      show: true,
      className: "border-emerald-200 bg-emerald-50 text-emerald-800",
      label: "Completo",
    },
    incomplete: {
      show: true,
      className: "border-rose-200 bg-rose-50 text-rose-700",
      label: "Incompleto",
    },
    warning: {
      show: true,
      className: "border-amber-200 bg-amber-50 text-amber-800",
      label: "Revisar",
    },
  },
};

const SHELL: Record<SectionTheme, (status: SectionStatus, open: boolean) => string> = {
  dark: (status, open) =>
    [
      "overflow-hidden rounded-2xl ring-1 transition-shadow",
      status === "incomplete"
        ? "ring-rose-500/35 shadow-[0_0_0_1px_rgba(244,63,94,0.12)]"
        : status === "warning"
          ? "ring-amber-500/25"
          : "ring-white/[0.08] shadow-lg shadow-black/20",
      open ? "bg-[#121214]" : "bg-[#161618]",
    ].join(" "),
  light: (status, open) =>
    [
      "overflow-hidden rounded-2xl border transition-shadow",
      status === "incomplete"
        ? "border-rose-300 ring-1 ring-rose-200 shadow-sm"
        : status === "warning"
          ? "border-amber-200 ring-1 ring-amber-100 shadow-sm"
          : "border-slate-200 shadow-sm shadow-slate-200/40",
      open ? "bg-white" : "bg-slate-50/80",
    ].join(" "),
};

const HEADER: Record<SectionTheme, (open: boolean) => string> = {
  dark: (open) =>
    [
      "relative flex w-full items-start justify-between gap-3 border-b px-4 py-3.5 text-left transition-colors",
      open ? "border-white/[0.06] bg-[#1e1e22]" : "border-transparent bg-[#1a1a1e] hover:bg-[#1e1e22]",
    ].join(" "),
  light: (open) =>
    [
      "relative flex w-full items-start justify-between gap-3 border-b px-4 py-3.5 text-left transition-colors",
      open ? "border-slate-200 bg-slate-50" : "border-transparent bg-white hover:bg-slate-50",
    ].join(" "),
};

const BODY: Record<SectionTheme, string> = {
  dark: [
    "px-4 py-4 sm:px-5 sm:py-5 bg-[#0c0c0e]",
    "[&_label]:text-[11px] [&_label]:font-medium [&_label]:uppercase [&_label]:tracking-wider [&_label]:text-white/45",
    "[&_input]:mt-1.5 [&_input]:rounded-xl [&_input]:border-white/10 [&_input]:bg-[#1a1a1e] [&_input]:text-[14px] [&_input]:text-white/90",
    "[&_input]:placeholder:text-white/25",
    "[&_input:focus]:border-sky-500/50 [&_input:focus]:ring-2 [&_input:focus]:ring-sky-500/20",
    "[&_select]:mt-1.5 [&_select]:rounded-xl [&_select]:border-white/10 [&_select]:bg-[#1a1a1e] [&_select]:text-white/90",
    "[&_select:focus]:border-sky-500/50 [&_select:focus]:ring-2 [&_select:focus]:ring-sky-500/20",
    "[&_textarea]:rounded-xl [&_textarea]:border-white/10 [&_textarea]:bg-[#1a1a1e] [&_textarea]:text-white/90",
  ].join(" "),
  light: [
    "px-4 py-4 sm:px-5 sm:py-5 bg-white",
    "[&_label]:text-[11px] [&_label]:font-medium [&_label]:uppercase [&_label]:tracking-wider [&_label]:text-slate-500",
    "[&_input]:mt-1.5 [&_input]:rounded-xl [&_input]:border-slate-200 [&_input]:bg-white [&_input]:text-[14px] [&_input]:text-slate-900",
    "[&_input]:placeholder:text-slate-400",
    "[&_input:focus]:border-sky-400 [&_input:focus]:ring-2 [&_input:focus]:ring-sky-100",
    "[&_select]:mt-1.5 [&_select]:rounded-xl [&_select]:border-slate-200 [&_select]:bg-white [&_select]:text-slate-900",
    "[&_select:focus]:border-sky-400 [&_select:focus]:ring-2 [&_select:focus]:ring-sky-100",
    "[&_textarea]:rounded-xl [&_textarea]:border-slate-200 [&_textarea]:bg-white [&_textarea]:text-slate-900",
  ].join(" "),
};

const TITLE: Record<SectionTheme, string> = {
  dark: "text-[15px] font-semibold tracking-tight text-white/95",
  light: "text-[15px] font-semibold tracking-tight text-slate-900",
};

const DESCRIPTION: Record<SectionTheme, string> = {
  dark: "max-w-2xl text-[12px] leading-relaxed text-white/40",
  light: "max-w-2xl text-[12px] leading-relaxed text-slate-500",
};

const BADGE: Record<SectionTheme, string> = {
  dark: "shrink-0 rounded-md bg-white/[0.08] px-1.5 py-0.5 font-mono text-[10px] text-white/50",
  light: "shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500",
};

const CHEVRON: Record<SectionTheme, string> = {
  dark: "mt-1 shrink-0 text-[11px] text-white/35 transition-transform",
  light: "mt-1 shrink-0 text-[11px] text-slate-400 transition-transform",
};

export function readSectionStorage(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function writeSectionStorage(id: string, value: boolean) {
  const current = readSectionStorage();
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, [id]: value }));
}

export function openSections(ids: string[]) {
  const current = readSectionStorage();
  const next = { ...current };
  for (const id of ids) next[id] = true;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function PipelineSection({
  id,
  title,
  badge,
  description,
  children,
  accent = "neutral",
  status = "default",
  defaultOpen = false,
  theme = "dark",
}: {
  id: string;
  title: string;
  badge?: string;
  description?: string;
  children: React.ReactNode;
  accent?: SectionAccent;
  status?: SectionStatus;
  defaultOpen?: boolean;
  theme?: SectionTheme;
}) {
  const [open, setOpen] = useState<boolean>(() => readSectionStorage()[id] ?? defaultOpen);
  const pill = STATUS_PILL[theme][status];

  const toggle = () => {
    setOpen((v) => {
      writeSectionStorage(id, !v);
      return !v;
    });
  };

  return (
    <section id={id} className={SHELL[theme](status, open)}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        className={HEADER[theme](open)}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
      >
        <span
          className={`absolute left-0 top-3 bottom-3 w-1 rounded-r-full ${ACCENT_STRIPE[theme][accent]}`}
          aria-hidden
        />
        <div className="flex min-w-0 flex-1 flex-col gap-1 pl-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={TITLE[theme]}>{title}</span>
            {badge ? <span className={BADGE[theme]}>{badge}</span> : null}
            {pill.show ? (
              <span
                className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${pill.className}`}
              >
                {pill.label}
              </span>
            ) : null}
          </div>
          {description ? <p className={DESCRIPTION[theme]}>{description}</p> : null}
        </div>
        <span className={`${CHEVRON[theme]} ${open ? "rotate-180" : ""}`}>▾</span>
      </div>

      {open ? <div className={BODY[theme]}>{children}</div> : null}
    </section>
  );
}
