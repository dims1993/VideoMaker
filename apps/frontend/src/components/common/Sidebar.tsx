import type React from "react";
import type { Session } from "../../types";
import { Btn, Input, Label, StatusBadge } from "../ui";

export function Sidebar({
  activeTab,
  onSelectTab,
  session,
  statusLine,
  work,
  setWork,
  applyWork,
}: {
  activeTab: "analyze" | "create";
  onSelectTab: (t: "analyze" | "create") => void;
  session: Session | null;
  statusLine: string;
  work: string;
  setWork: (v: string) => void;
  applyWork: () => void;
}) {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 w-[280px] border-r border-slate-200/80 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-base font-bold tracking-tight text-slate-900">Videomaker</div>
          <div className="mt-0.5 text-[11px] text-slate-500">Desktop · full width</div>
        </div>
        {session ? <StatusBadge state={session.status.state} /> : null}
      </div>

      <div className="mt-4 space-y-2">
        <Btn
          className={`w-full ${activeTab === "analyze" ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"}`}
          onClick={() => onSelectTab("analyze")}
        >
          Analyse
        </Btn>
        <Btn
          className={`w-full ${activeTab === "create" ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-white text-slate-900 ring-1 ring-slate-200 hover:bg-slate-50"}`}
          onClick={() => onSelectTab("create")}
        >
          Create
        </Btn>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Session</div>
        <p className="mt-2 text-xs leading-relaxed text-slate-600">{statusLine || "…"}</p>
        <div className="mt-3">
          <Label>Carpeta de trabajo</Label>
          <div className="flex gap-2">
            <Input value={work} onChange={(e) => setWork(e.target.value)} placeholder="output/ui_session" />
            <Btn className="shrink-0 bg-slate-900 text-white hover:bg-slate-800" onClick={applyWork}>
              OK
            </Btn>
          </div>
        </div>
      </div>
    </aside>
  );
}

