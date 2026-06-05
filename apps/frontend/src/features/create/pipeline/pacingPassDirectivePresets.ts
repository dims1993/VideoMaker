import { patchJson, postJson } from "../../../services/api";

export type PacingDirectivePreset = {
  id: string;
  name: string;
  text: string;
  updated_at?: string;
};

export async function fetchPacingDirectivePresets(): Promise<PacingDirectivePreset[]> {
  const r = await fetch("/api/pipeline/pacing-pass-directive-presets");
  if (!r.ok) return [];
  const j = (await r.json()) as { items?: PacingDirectivePreset[] };
  return Array.isArray(j.items) ? j.items : [];
}

export async function savePacingDirectivePreset(
  text: string,
  name?: string,
): Promise<PacingDirectivePreset> {
  return postJson<PacingDirectivePreset>("/api/pipeline/pacing-pass-directive-presets", {
    text,
    name: name?.trim() || undefined,
  });
}

export async function renamePacingDirectivePreset(
  id: string,
  name: string,
): Promise<PacingDirectivePreset> {
  return patchJson<PacingDirectivePreset>(
    `/api/pipeline/pacing-pass-directive-presets/${encodeURIComponent(id)}`,
    { name },
  );
}

export async function deletePacingDirectivePreset(id: string): Promise<void> {
  const r = await fetch(
    `/api/pipeline/pacing-pass-directive-presets/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
  if (!r.ok) {
    const t = (await r.json().catch(() => ({}))) as { detail?: string };
    throw new Error(t.detail || r.statusText);
  }
}
