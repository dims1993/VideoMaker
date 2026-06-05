export async function readApiError(r: Response): Promise<string> {
  const t = (await r.json().catch(() => ({}))) as { detail?: unknown };
  const d = t.detail;
  return typeof d === "string"
    ? d
    : Array.isArray(d)
      ? d.map((x) =>
          typeof x === "object" && x && "msg" in x ? String((x as { msg: string }).msg) : String(x)
        ).join("; ")
      : JSON.stringify(t);
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
  return r.json() as Promise<T>;
}

export async function putJson<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
  return r.json() as Promise<T>;
}

export async function patchJson<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
  return r.json() as Promise<T>;
}

export async function deleteReq(url: string): Promise<void> {
  const r = await fetch(url, { method: "DELETE" });
  if (!r.ok) throw new Error((await readApiError(r)) || r.statusText);
}

type PipelineStepSnapshot = {
  id: string;
  state: string;
  detail?: string;
};

/** Espera a que un paso de pipeline termine (POST /step/rerun es asíncrono, 202). */
export async function waitForPipelineStep(
  work: string,
  stepId: string,
  options?: { timeoutMs?: number; intervalMs?: number },
): Promise<PipelineStepSnapshot> {
  const timeoutMs = options?.timeoutMs ?? 300_000;
  const intervalMs = options?.intervalMs ?? 1_500;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const r = await fetch(
      `/api/pipeline/state?work=${encodeURIComponent(work)}`,
    );
    if (!r.ok) {
      throw new Error((await readApiError(r)) || r.statusText);
    }
    const st = (await r.json()) as { steps?: PipelineStepSnapshot[] };
    const step = st.steps?.find((s) => s.id === stepId);
    if (step?.state === "done") {
      return step;
    }
    if (step?.state === "error") {
      throw new Error(step.detail?.trim() || `El paso ${stepId} falló.`);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(
    `Tiempo de espera agotado (${Math.round(timeoutMs / 1000)}s) para el paso ${stepId}.`,
  );
}

