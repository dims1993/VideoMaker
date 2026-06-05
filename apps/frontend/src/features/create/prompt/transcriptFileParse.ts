/** Extensiones aceptadas en la zona de transcripts del paso Prompt. */
export const TRANSCRIPT_FILE_EXTENSIONS = [
  ".txt",
  ".pdf",
  ".json",
  ".srt",
  ".vtt",
] as const;

export const TRANSCRIPT_ACCEPT_ATTR = TRANSCRIPT_FILE_EXTENSIONS.join(",");

type VideoTranscriptRow = {
  title?: string;
  video_id?: string;
  duration_s?: number;
  transcript?: string;
  status?: string;
};

/**
 * Normaliza JSON de export del canal (p. ej. /channels/.../transcripts.json).
 */
export function extractTranscriptsFromJson(data: unknown): string {
  let videos: VideoTranscriptRow[] | null = null;

  if (Array.isArray(data)) {
    videos = data as VideoTranscriptRow[];
  } else if (data && typeof data === "object" && Array.isArray((data as { videos?: unknown }).videos)) {
    videos = (data as { videos: VideoTranscriptRow[] }).videos;
  }

  if (!videos?.length) {
    throw new Error("JSON sin lista «videos» reconocible");
  }

  const blocks = videos
    .filter((v) => {
      const transcript = (v.transcript ?? "").trim();
      if (!transcript) return false;
      if (v.status != null && v.status !== "ok") return false;
      return true;
    })
    .map((v) => {
      const title = (v.title || v.video_id || "Sin título").trim();
      const dur = v.duration_s;
      const mins =
        typeof dur === "number" && Number.isFinite(dur) ? Math.round(dur / 60) : null;
      const header =
        mins != null
          ? `=== VÍDEO: ${title} (${mins} min) ===`
          : `=== VÍDEO: ${title} ===`;
      return `${header}\n${(v.transcript ?? "").trim()}`;
    });

  if (!blocks.length) {
    throw new Error("JSON sin transcripciones con status ok");
  }

  return blocks.join("\n\n");
}

/** Extrae texto legible de subtítulos .srt / .vtt. */
export function parseSubtitleFile(raw: string, filename: string): string {
  const low = filename.toLowerCase();
  const lines: string[] = [];

  for (const line of raw.split(/\r?\n/)) {
    let s = line.trim();
    if (!s) continue;
    if (low.endsWith(".vtt")) {
      if (s === "WEBVTT" || s.startsWith("NOTE")) continue;
      s = s.replace(/<[^>]+>/g, "").trim();
      if (!s) continue;
    }
    if (/^\d+$/.test(s)) continue;
    if (/-->/.test(s)) continue;
    lines.push(s);
  }

  const text = lines.join("\n").trim();
  if (!text) {
    throw new Error(`${filename}: no se extrajo texto del subtítulo`);
  }
  return text;
}

async function extractPdfViaApi(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("files", file);
  const res = await fetch("/api/prompt-templates/parse-transcript-files", {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const j = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(j.detail ?? `Error ${res.status}`);
  }
  const j = (await res.json()) as { combined_text?: string };
  return (j.combined_text ?? "").trim();
}

export async function extractTranscriptFile(
  file: File,
): Promise<{ name: string; text: string }> {
  const name = file.name;
  const low = name.toLowerCase();

  if (low.endsWith(".pdf")) {
    const text = await extractPdfViaApi(file);
    return { name, text };
  }

  const raw = await file.text();

  if (low.endsWith(".json")) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new Error(`${name}: JSON inválido`);
    }
    return { name, text: extractTranscriptsFromJson(parsed) };
  }

  if (low.endsWith(".srt") || low.endsWith(".vtt")) {
    return { name, text: parseSubtitleFile(raw, name) };
  }

  if (low.endsWith(".txt")) {
    return { name, text: raw.trim() };
  }

  throw new Error(
    `${name}: formato no soportado. Usa ${TRANSCRIPT_FILE_EXTENSIONS.join(", ")}`,
  );
}
