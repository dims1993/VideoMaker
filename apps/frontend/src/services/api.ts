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

