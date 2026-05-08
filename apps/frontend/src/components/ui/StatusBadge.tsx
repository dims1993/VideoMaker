export function StatusBadge({ state }: { state: string }) {
  const map: Record<string, string> = {
    idle: "bg-slate-100 text-slate-700 ring-slate-200",
    running: "bg-amber-50 text-amber-900 ring-amber-200",
    done: "bg-emerald-50 text-emerald-900 ring-emerald-200",
    error: "bg-rose-50 text-rose-900 ring-rose-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${map[state] ?? map.idle}`}>
      {state}
    </span>
  );
}

