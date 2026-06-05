export type ScriptLintSeverity = "info" | "warn" | "error";

export type ScriptLintFinding = {
  id: string;
  severity: ScriptLintSeverity;
  title: string;
  detail: string;
  count?: number;
  examples?: string[];
};

export type ScriptLintReport = {
  ok: boolean;
  score: number;
  metrics: Record<string, unknown>;
  findings: ScriptLintFinding[];
  narrable_word_count: number;
  estimated_minutes: number;
  target_minutes?: number | null;
};

export async function fetchScriptLint(opts: {
  work: string;
  text?: string;
  targetMinutes?: number;
  persist?: boolean;
}): Promise<ScriptLintReport> {
  const r = await fetch("/api/script-lint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      work: opts.work,
      text: opts.text ?? undefined,
      target_minutes: opts.targetMinutes,
      persist: opts.persist ?? false,
    }),
  });
  if (!r.ok) {
    const err = await r.text();
    throw new Error(err || r.statusText);
  }
  return (await r.json()) as ScriptLintReport;
}
