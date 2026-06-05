import type { ScriptLintReport } from "./scriptQuality";

function scoreTone(score: number): string {
  if (score >= 85) return "border-emerald-200 bg-emerald-50 text-emerald-900 ring-emerald-100";
  if (score >= 70) return "border-amber-200 bg-amber-50 text-amber-900 ring-amber-100";
  return "border-rose-200 bg-rose-50 text-rose-900 ring-rose-100";
}

export function ScriptQualityBanner({
  report,
  loading,
  error,
  onReanalyze,
}: {
  report: ScriptLintReport | null;
  loading?: boolean;
  error?: string | null;
  onReanalyze?: () => void;
}) {
  if (!report && !loading && !error) return null;

  return (
    <div className="space-y-2 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[13px] font-semibold text-slate-800">
          Diagnóstico heurístico (solo editor — no va al Script Writer)
        </div>
        {onReanalyze ? (
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
            disabled={loading}
            onClick={onReanalyze}
          >
            {loading ? "Analizando…" : "Reanalizar"}
          </button>
        ) : null}
      </div>

      {error ? (
        <p className="text-[12px] text-rose-700">{error}</p>
      ) : null}

      {loading && !report ? (
        <p className="text-[12px] text-slate-500">Analizando patrones de plantilla…</p>
      ) : null}

      {report ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex rounded-lg border px-2.5 py-1 text-[12px] font-semibold ring-1 ${scoreTone(report.score)}`}
            >
              Puntuación {report.score}/100
            </span>
            <span className="text-[11px] text-slate-600">
              ~{report.estimated_minutes.toFixed(1)} min narrables (GUIÓN)
              {report.target_minutes
                ? ` · objetivo ~${report.target_minutes.toFixed(1)} min`
                : ""}
              {report.narrable_word_count > 0
                ? ` · ${report.narrable_word_count.toLocaleString()} palabras`
                : ""}
            </span>
          </div>

          {report.findings.length === 0 ? (
            <p className="text-[12px] text-emerald-800">
              Sin alertas fuertes. Revisa igualmente oído y ritmo al leer en voz alta.
            </p>
          ) : (
            <ul className="space-y-2">
              {report.findings.map((f) => (
                <li
                  key={f.id}
                  className={
                    f.severity === "warn"
                      ? "rounded-xl border border-amber-200 bg-white px-3 py-2"
                      : "rounded-xl border border-slate-200 bg-white px-3 py-2"
                  }
                >
                  <p className="text-[12px] font-semibold text-slate-900">
                    {f.severity === "warn" ? "⚠ " : ""}
                    {f.title}
                    {f.count != null && f.count > 0 ? ` (${f.count})` : ""}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-600">{f.detail}</p>
                  {f.examples && f.examples.length > 0 ? (
                    <ul className="mt-1.5 space-y-0.5 text-[10px] font-mono text-slate-500">
                      {f.examples.map((ex, i) => (
                        <li key={`${f.id}-ex-${i}`} className="truncate">
                          {ex}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </div>
  );
}
