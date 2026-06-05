import type { PromptValidationResult } from "./promptCompleteness";

export function PromptValidationBanner({ result }: { result: PromptValidationResult }) {
  if (!result.missing.length && !result.warnings.length) return null;

  return (
    <div className="space-y-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 ring-1 ring-rose-100">
      {result.missing.length > 0 ? (
        <div>
          <p className="text-[13px] font-semibold text-rose-800">Falta completar antes de Start step</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {result.missing.map((m) => (
              <li key={m.id}>
                <a
                  href={`#prompt-field-${m.id}`}
                  className="inline-flex rounded-lg border border-rose-200 bg-white px-2.5 py-1 text-[11px] font-medium text-rose-700 shadow-sm hover:bg-rose-50"
                >
                  {m.sectionTitle}: {m.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {result.warnings.length > 0 ? (
        <div className={result.missing.length ? "border-t border-rose-200/80 pt-2" : ""}>
          <p className="text-[12px] font-medium text-amber-800">Recomendado (no bloquea)</p>
          <ul className="mt-1.5 flex flex-wrap gap-2">
            {result.warnings.map((w) => (
              <li key={w.id}>
                <a
                  href={`#prompt-field-${w.id}`}
                  className="inline-flex rounded-lg border border-amber-200 bg-white px-2.5 py-1 text-[11px] text-amber-800 shadow-sm hover:bg-amber-50"
                >
                  {w.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
